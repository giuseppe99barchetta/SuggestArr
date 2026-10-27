"""Non-admin users must not reach admin-only read endpoints (GHSA-f2r6-9fm5-8743)."""
import pytest
from flask import Flask, g

from api_service.blueprints.admin.routes import admin_bp
from api_service.blueprints.cleanup.routes import cleanup_bp


def _client(role):
    app = Flask(__name__)
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(cleanup_bp, url_prefix="/api/cleanup")

    @app.before_request
    def _set_user():
        if role:
            g.current_user = {"id": "2", "role": role}

    return app.test_client()


@pytest.mark.parametrize("path", [
    "/api/admin/export-config",
    "/api/admin/export-config?include_secrets=true",
    "/api/cleanup/log",
])
@pytest.mark.parametrize("role,status", [("user", 403), (None, 401)])
def test_admin_reads_reject_non_admin(path, role, status):
    assert _client(role).get(path).status_code == status


def test_export_config_allows_admin(monkeypatch):
    from api_service.blueprints.admin import routes

    class FakeDB:
        def get_all_integrations(self):
            return {"seer": {"api_url": "http://seer", "api_key": "k"}}

    monkeypatch.setattr(routes, "DatabaseManager", FakeDB)
    monkeypatch.setattr(routes, "load_env_vars", lambda: {"SEER_TOKEN": "t", "DB_HOST": "db"})

    response = _client("admin").get("/api/admin/export-config")

    assert response.status_code == 200
    assert response.get_json()["schema_version"] == 2
