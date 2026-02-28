import unittest
from unittest.mock import patch

from flask import Flask

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


if __name__ == "__main__":
    unittest.main()
