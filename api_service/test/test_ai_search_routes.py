import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from flask import Flask

from api_service.blueprints.ai_search.routes import ai_search_request


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
