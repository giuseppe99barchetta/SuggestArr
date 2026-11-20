"""Non-admin users must not reach admin-only read endpoints (GHSA-f2r6-9fm5-8743)."""
import pytest
from flask import Flask, g

from api_service.blueprints.cleanup.routes import cleanup_bp
from api_service.blueprints.config.routes import config_bp


def _client(role):
    app = Flask(__name__)
    app.register_blueprint(config_bp, url_prefix="/api/config")
    app.register_blueprint(cleanup_bp, url_prefix="/api/cleanup")

    @app.before_request
    def _set_user():
        if role:
            g.current_user = {"id": "2", "role": role}

    return app.test_client()


@pytest.mark.parametrize("path", [
    "/api/config/export",
    "/api/config/export?include_secrets=true",
    "/api/cleanup/log",
])
@pytest.mark.parametrize("role,status", [("user", 403), (None, 401)])
def test_admin_reads_reject_non_admin(path, role, status):
    assert _client(role).get(path).status_code == status
