import unittest
from unittest.mock import patch

from flask import Flask, g

from api_service.blueprints.plex.routes import plex_bp


class _FakePlexClient:
    def __init__(self, *args, **kwargs):
        self._users = [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get_all_users(self):
        return self._users


class TestPlexUsersRoute(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(plex_bp, url_prefix="/api/plex")
        self.client = app.test_client()

    def test_users_post_reads_credentials_from_json_body(self):
        with patch("api_service.blueprints.plex.routes.PlexClient", _FakePlexClient), \
                patch("api_service.blueprints.plex.routes.validate_url", return_value=None):
            resp = self.client.post(
                "/api/plex/users",
                json={
                    "PLEX_TOKEN": "secret-token",
                    "PLEX_API_URL": "https://plex.direct:32400",
                },
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["message"], "Users fetched successfully")
        self.assertEqual(len(data["users"]), 2)

    def test_users_post_missing_token_returns_400(self):
        resp = self.client.post(
            "/api/plex/users",
            json={"PLEX_API_URL": "https://plex.example:32400"},
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("message", resp.get_json())

    def test_users_get_not_allowed(self):
        resp = self.client.get(
            "/api/plex/users?PLEX_TOKEN=secret-token&PLEX_API_URL=https://plex.example:32400"
        )
        self.assertEqual(resp.status_code, 405)


class _RecordingPlexClient(_FakePlexClient):
    """Records every (token, api_url) a route would send to Plex."""
    sent = []

    def __init__(self, *args, **kwargs):
        super().__init__()
        _RecordingPlexClient.sent.append((kwargs.get("token"), kwargs.get("api_url")))

    async def get_libraries(self):
        return [{"key": "1", "title": "Movies"}]


STORED = {"PLEX_TOKEN": "stored-token", "PLEX_API_URL": "http://192.168.1.100:32400"}


class TestRedactedPlexToken(unittest.TestCase):
    """The '***' sentinel may stand in for the stored token only for an admin,
    and only towards the configured Plex server."""

    def _client(self, role):
        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.before_request
        def authenticate():
            g.current_user = {"id": "7", "role": role}

        app.register_blueprint(plex_bp, url_prefix="/api/plex")
        return app.test_client()

    def _post(self, role, path, body):
        _RecordingPlexClient.sent = []
        with patch("api_service.blueprints.plex.routes.PlexClient", _RecordingPlexClient), \
                patch("api_service.blueprints.plex.routes.validate_url", return_value=None), \
                patch("api_service.blueprints.plex.routes.ConfigService.get_runtime_config",
                      return_value=dict(STORED)):
            return self._client(role).post(path, json=body)

    def test_admin_gets_the_stored_token_for_the_configured_server(self):
        # Case and a trailing slash do not make it a different server.
        resp = self._post("admin", "/api/plex/users",
                          {"PLEX_TOKEN": "***", "PLEX_API_URL": "HTTP://192.168.1.100:32400/"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(_RecordingPlexClient.sent, [("stored-token", "HTTP://192.168.1.100:32400/")])

    def test_stored_token_is_never_sent_to_another_url(self):
        for path, body in (
            ("/api/plex/users", {"PLEX_TOKEN": "***", "PLEX_API_URL": "http://attacker.example:32400"}),
            ("/api/plex/libraries", {"PLEX_TOKEN": "***", "PLEX_API_URL": "http://10.0.0.66:32400"}),
            ("/api/plex/test", {"token": "***", "api_url": "http://attacker.example:32400"}),
        ):
            with self.subTest(path=path):
                resp = self._post("admin", path, body)
                self.assertEqual(resp.status_code, 400)
                self.assertNotIn("stored-token", [token for token, _ in _RecordingPlexClient.sent])

    def test_non_admin_never_gets_the_stored_token(self):
        # Not even towards the configured server.
        for path, body in (
            ("/api/plex/users", {"PLEX_TOKEN": "***", "PLEX_API_URL": STORED["PLEX_API_URL"]}),
            ("/api/plex/libraries", {"PLEX_TOKEN": "***", "PLEX_API_URL": STORED["PLEX_API_URL"]}),
            ("/api/plex/test", {"token": "***", "api_url": "http://attacker.example:32400"}),
        ):
            with self.subTest(path=path):
                resp = self._post("user", path, body)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(_RecordingPlexClient.sent, [])

    def test_redacted_token_with_nothing_stored_returns_400(self):
        _RecordingPlexClient.sent = []
        with patch("api_service.blueprints.plex.routes.PlexClient", _RecordingPlexClient), \
                patch("api_service.blueprints.plex.routes.ConfigService.get_runtime_config",
                      return_value={"PLEX_API_URL": STORED["PLEX_API_URL"]}):
            resp = self._client("admin").post(
                "/api/plex/users", json={"PLEX_TOKEN": "***", "PLEX_API_URL": STORED["PLEX_API_URL"]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(_RecordingPlexClient.sent, [])

    def test_a_real_token_is_used_as_given(self):
        resp = self._post("user", "/api/plex/users",
                          {"PLEX_TOKEN": "typed-token", "PLEX_API_URL": "http://other.example:32400"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(_RecordingPlexClient.sent, [("typed-token", "http://other.example:32400")])


if __name__ == "__main__":
    unittest.main()
