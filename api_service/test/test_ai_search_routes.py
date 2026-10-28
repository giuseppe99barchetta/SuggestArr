import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from flask import Flask, g

from api_service.blueprints.ai_search.routes import ai_search_inspiration, ai_search_query, ai_search_request


class TestAiSearchLanguage(unittest.IsolatedAsyncioTestCase):
    async def test_passes_valid_language_choices_and_defaults_to_prompt(self):
        app = Flask(__name__)
        for choice in (None, 'auto', 'any', 'en', 'es'):
            with self.subTest(choice=choice):
                body = {'query': 'a mystery'}
                if choice is not None:
                    body['original_language'] = choice
                with app.test_request_context(json=body), \
                     patch('api_service.blueprints.ai_search.routes.get_llm_client', return_value=object()), \
                     patch('api_service.blueprints.ai_search.routes.AiSearchService') as factory:
                    factory.return_value.search = AsyncMock(return_value={'results': [], 'total': 0})
                    response, status = await ai_search_query.__wrapped__()
                self.assertEqual(status, 200)
                self.assertEqual(response.get_json()['status'], 'success')
                self.assertEqual(factory.return_value.search.await_args.kwargs['original_language'], choice or 'auto')

    async def test_invalid_language_is_rejected_before_calling_external_services(self):
        app = Flask(__name__)
        for choice in (None, '', 'English', 'en-US', 'ES', ['es'], {'id': 'es'}, 42, True):
            with self.subTest(choice=choice), \
                 app.test_request_context(json={'query': 'a mystery', 'original_language': choice}), \
                 patch('api_service.blueprints.ai_search.routes.get_llm_client') as llm, \
                 patch('api_service.blueprints.ai_search.routes.AiSearchService') as factory:
                response, status = await ai_search_query.__wrapped__()
                self.assertEqual(status, 400)
                self.assertIn('original_language', response.get_json()['message'])
                llm.assert_not_called()
                factory.assert_not_called()


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

    async def test_tv_request_sends_no_tvdb_id_and_keeps_metadata_on_requested_id(self):
        app = Flask(__name__)
        session = _session(_response(201))
        config = {"SEER_API_URL": "http://seer.local", "SEER_TOKEN": "api-key"}
        body = {"tmdb_id": 1399, "media_type": "tv",
                "metadata": {"id": "603", "title": "Game of Thrones", "poster_path": "/p.jpg", "secret": "x"}}

        with app.test_request_context(json=body), \
             patch("api_service.blueprints.ai_search.routes.ConfigService.get_runtime_config", return_value=config), \
             patch("api_service.blueprints.ai_search.routes.DatabaseManager") as database, \
             patch("api_service.blueprints.ai_search.routes.aiohttp.ClientSession", return_value=session):
            response, status = await ai_search_request.__wrapped__()

        self.assertEqual(status, 200)
        self.assertNotIn("tvdbId", session.post.call_args.kwargs["json"])
        saved, media_type = database.return_value.save_metadata.call_args.args
        self.assertEqual(saved, {"id": "1399", "title": "Game of Thrones", "poster_path": "/p.jpg"})
        self.assertEqual(media_type, "tv")

    async def test_request_errors_do_not_expose_internal_details(self):
        app = Flask(__name__)
        with app.test_request_context(json={"tmdb_id": 42}), \
             patch("api_service.blueprints.ai_search.routes.ConfigService.get_runtime_config",
                   side_effect=RuntimeError("http://internal:5055 token=abc")):
            response, status = await ai_search_request.__wrapped__()

        self.assertEqual(status, 500)
        self.assertNotIn("internal", response.get_data(as_text=True))
