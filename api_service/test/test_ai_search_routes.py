import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from flask import Flask, g

from api_service.blueprints.ai_search.routes import ai_search_inspiration, ai_search_request


class TestAiSearchInspiration(unittest.IsolatedAsyncioTestCase):
    async def test_only_uses_current_users_linked_profile(self):
        app = Flask(__name__)
        with app.test_request_context('/inspiration?user_ids=other-user'), \
             patch('api_service.blueprints.ai_search.routes.DatabaseManager') as database, \
             patch('api_service.blueprints.ai_search.routes.AiSearchService') as factory:
            g.current_user = {'id': 7, 'role': 'admin'}
            service = factory.return_value
            service.config = {'SELECTED_SERVICE': 'plex'}
            profile = {'provider': 'plex', 'external_user_id': 'own-id'}
            database.return_value.get_user_media_profiles.return_value = [
                {'provider': 'jellyfin', 'external_user_id': 'unused'}, profile,
            ]
            database.return_value.upsert_media_user_identity.return_value = {'id': 42}
            database.return_value.list_watched_media.return_value = [{'title': 'Saved'}, {'title': 'Kids', 'excluded': True}]
            service.inspiration = AsyncMock(return_value=[{'title': 'Own title'}])
            response, status = await ai_search_inspiration.__wrapped__()
            self.assertEqual(status, 200)
            self.assertEqual(response.get_json()['items'], [{'title': 'Own title'}])
            database.return_value.get_user_media_profiles.assert_called_once_with(7)
            database.return_value.list_watched_media.assert_called_once_with(42, limit=50)
            service.inspiration.assert_awaited_once_with(profile, [{'title': 'Saved'}])

    async def test_missing_profile_never_loads_all_server_history(self):
        app = Flask(__name__)
        with app.test_request_context(), \
             patch('api_service.blueprints.ai_search.routes.DatabaseManager') as database, \
             patch('api_service.blueprints.ai_search.routes.AiSearchService') as factory:
            g.current_user = {'id': 8}
            factory.return_value.config = {'SELECTED_SERVICE': 'jellyfin'}
            database.return_value.get_user_media_profiles.return_value = []
            response, status = await ai_search_inspiration.__wrapped__()
            self.assertEqual(status, 200)
            self.assertEqual(response.get_json()['items'], [])
            factory.return_value.inspiration.assert_not_called()

    async def test_no_identity_does_not_access_database(self):
        app = Flask(__name__)
        with app.test_request_context(), \
             patch('api_service.blueprints.ai_search.routes.DatabaseManager') as database:
            response, status = await ai_search_inspiration.__wrapped__()
            self.assertEqual(status, 200)
            self.assertEqual(response.get_json()['items'], [])
            database.assert_not_called()

    async def test_errors_do_not_expose_internal_details(self):
        app = Flask(__name__)
        with app.test_request_context(), \
             patch('api_service.blueprints.ai_search.routes.DatabaseManager', side_effect=RuntimeError('private')), \
             patch('api_service.blueprints.ai_search.routes.AiSearchService'):
            g.current_user = {'id': 7}
            response, status = await ai_search_inspiration.__wrapped__()
            self.assertEqual(status, 503)
            self.assertNotIn('private', response.get_data(as_text=True))


def _response(status):
    response = MagicMock()
    response.status = status
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    return response


def _session(response):
    session = MagicMock()
    session.post.return_value = response
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


class TestAiSearchRequest(unittest.IsolatedAsyncioTestCase):
    async def test_retries_with_api_key_when_stored_session_is_forbidden(self):
        app = Flask(__name__)
        session_request = _session(_response(403))
        api_key_request = _session(_response(201))
        config = {
            "SEER_API_URL": "http://seer.local",
            "SEER_TOKEN": "api-key",
            "SEER_SESSION_TOKEN": "restricted-session",
        }

        with app.test_request_context(json={"tmdb_id": 42}), \
             patch("api_service.blueprints.ai_search.routes.ConfigService.get_runtime_config", return_value=config), \
             patch("api_service.blueprints.ai_search.routes.DatabaseManager"), \
             patch("api_service.blueprints.ai_search.routes.aiohttp.ClientSession",
                   side_effect=[session_request, api_key_request]) as client_session:
            response, status = await ai_search_request.__wrapped__()

        self.assertEqual(status, 200)
        self.assertEqual(response.get_json()["status"], "success")
        self.assertEqual(client_session.call_args_list[0].kwargs["cookies"], {"connect.sid": "restricted-session"})
        self.assertEqual(client_session.call_args_list[1].kwargs["headers"]["X-Api-Key"], "api-key")
