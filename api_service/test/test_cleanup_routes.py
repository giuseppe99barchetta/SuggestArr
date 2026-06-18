"""Tests for cleanup automation blueprint RBAC."""

import unittest
from unittest.mock import AsyncMock, patch

from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.cleanup.routes import cleanup_bp


class TestCleanupRoutePermissions(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["RATELIMIT_ENABLED"] = False

        self._caller = {"id": "2", "username": "viewer", "role": "user"}

        @app.before_request
        def inject_caller():
            g.current_user = self._caller

        limiter.init_app(app)
        app.register_blueprint(cleanup_bp, url_prefix="/api/cleanup")
        self.client = app.test_client()

    def test_non_admin_cannot_update_cleanup_settings(self):
        resp = self.client.post("/api/cleanup/settings", json={"enabled": False})

        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.get_json(), {"error": "Insufficient permissions"})

    def test_non_admin_cannot_run_cleanup(self):
        resp = self.client.post("/api/cleanup/run", json={"dry_run": True})

        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.get_json(), {"error": "Insufficient permissions"})

    def test_admin_cleanup_run_awaits_coroutine(self):
        self._caller = {"id": "1", "username": "admin", "role": "admin"}
        result = {
            "status": "ok",
            "summary": "No requests older than 7 days.",
            "dry_run": True,
        }

        with patch(
            "api_service.blueprints.cleanup.routes.execute_cleanup_job",
            new=AsyncMock(return_value=result),
        ) as execute_cleanup_job:
            resp = self.client.post("/api/cleanup/run", json={"dry_run": True})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"status": "success", "result": result})
        execute_cleanup_job.assert_awaited_once_with(force_run=True, override_dry_run=True)


if __name__ == "__main__":
    unittest.main()
