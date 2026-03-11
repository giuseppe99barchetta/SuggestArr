"""Tests for credential-based self-link endpoints under /api/integrations."""

import os
import unittest
from unittest.mock import MagicMock, patch

import logging

logging.disable(logging.CRITICAL)

TEST_SECRET = "test-secret-for-integrations-self-link"
os.environ["SUGGESTARR_SECRET_KEY"] = TEST_SECRET


class _IntegrationsBase(unittest.TestCase):
    """Minimal app with integrations blueprint and in-memory profile storage."""

    _CALLER = {"id": "1", "username": "alice", "role": "user"}

    def setUp(self):
        os.environ["SUGGESTARR_AUTH_DISABLED"] = "true"
        os.environ["SUGGESTARR_SECRET_KEY"] = TEST_SECRET
        self._caller = dict(self._CALLER)
        self._profiles = []
        self._build_fake_db()
        self._setup_app()

    def tearDown(self):
        os.environ.pop("SUGGESTARR_AUTH_DISABLED", None)
        from api_service.auth.middleware import invalidate_setup_cache

        invalidate_setup_cache()
        for patcher in self._patches:
            patcher.stop()

    def _build_fake_db(self):
        profiles = self._profiles

        class FakeDB:
            def __init__(self_inner):
                pass

            def get_auth_user_count(self_inner):
                return 1

            def create_user_media_profile(
                self_inner,
                user_id,
                provider,
                external_user_id,
                external_username,
                access_token=None,
            ):
                profiles.append(
                    {
                        "id": len(profiles) + 1,
                        "user_id": user_id,
                        "provider": provider,
                        "external_user_id": external_user_id,
                        "external_username": external_username,
                        "access_token": access_token,
                        "created_at": "2025-01-01 00:00:00",
                    }
                )

        self.FakeDB = FakeDB

    def _setup_app(self):
        from flask import Flask, g

        from api_service.auth.middleware import enforce_authentication, invalidate_setup_cache
        from api_service.blueprints.integrations.routes import integrations_bp

        invalidate_setup_cache()

        app = Flask(__name__)
        app.config["TESTING"] = True

        caller_ref = self

        @app.before_request
        def inject_caller():
            g.current_user = caller_ref._caller

        self._patches = [
            patch("api_service.blueprints.integrations.routes.DatabaseManager", self.FakeDB),
            patch("api_service.auth.middleware.DatabaseManager", self.FakeDB),
        ]
        for patcher in self._patches:
            patcher.start()

        app.before_request(enforce_authentication)
        app.register_blueprint(integrations_bp, url_prefix="/api/integrations")

        self.client = app.test_client()


class TestJellyfinSelfLink(_IntegrationsBase):
    def test_missing_credentials_returns_400(self):
        resp = self.client.post("/api/integrations/jellyfin/link", json={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_not_configured_returns_503(self):
        with patch(
            "api_service.blueprints.integrations.routes.ConfigService.get_runtime_config",
            return_value={},
        ):
            resp = self.client.post(
                "/api/integrations/jellyfin/link",
                json={"username": "jf_user", "password": "pw"},
            )
        self.assertEqual(resp.status_code, 503)

    def test_invalid_credentials_returns_401(self):
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch(
            "api_service.blueprints.integrations.routes.ConfigService.get_runtime_config",
            return_value={"JELLYFIN_API_URL": "http://jf.local"},
        ), patch(
            "api_service.blueprints.integrations.routes.http_requests.post",
            return_value=mock_response,
        ):
            resp = self.client.post(
                "/api/integrations/jellyfin/link",
                json={"username": "jf_user", "password": "bad"},
            )

        self.assertEqual(resp.status_code, 401)

    def test_success_links_profile_and_never_stores_password(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"User": {"Id": "jf-1", "Name": "jf_user"}}

        with patch(
            "api_service.blueprints.integrations.routes.ConfigService.get_runtime_config",
            return_value={"JELLYFIN_API_URL": "http://jf.local"},
        ), patch(
            "api_service.blueprints.integrations.routes.http_requests.post",
            return_value=mock_response,
        ):
            resp = self.client.post(
                "/api/integrations/jellyfin/link",
                json={"username": "jf_user", "password": "secret"},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self._profiles), 1)
        stored = self._profiles[0]
        self.assertEqual(stored["provider"], "jellyfin")
        self.assertEqual(stored["external_user_id"], "jf-1")
        self.assertEqual(stored["external_username"], "jf_user")
        self.assertIsNone(stored["access_token"])


class TestPlexSelfLink(_IntegrationsBase):
    def test_missing_credentials_returns_400(self):
        resp = self.client.post("/api/integrations/plex/link", json={})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_credentials_returns_401(self):
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch(
            "api_service.blueprints.integrations.routes.http_requests.post",
            return_value=mock_response,
        ):
            resp = self.client.post(
                "/api/integrations/plex/link",
                json={"username": "plex_user", "password": "bad"},
            )

        self.assertEqual(resp.status_code, 401)

    def test_success_links_profile_and_does_not_store_token(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "id": 777,
                "username": "plex_user",
                "authToken": "plex-token-should-not-be-stored",
            }
        }

        with patch(
            "api_service.blueprints.integrations.routes.http_requests.post",
            return_value=mock_response,
        ):
            resp = self.client.post(
                "/api/integrations/plex/link",
                json={"username": "plex_user", "password": "secret"},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self._profiles), 1)
        stored = self._profiles[0]
        self.assertEqual(stored["provider"], "plex")
        self.assertEqual(stored["external_user_id"], "777")
        self.assertEqual(stored["external_username"], "plex_user")
        self.assertIsNone(stored["access_token"])


if __name__ == "__main__":
    unittest.main()
