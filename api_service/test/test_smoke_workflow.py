import asyncio
from unittest.mock import AsyncMock, MagicMock

from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.automation import routes as automation_routes
from api_service.blueprints.config import routes as config_routes
from api_service.blueprints.jobs import routes as jobs_routes
from api_service.jobs.discover_automation import ExecutionResult


def test_setup_preview_and_approval_smoke_flow(monkeypatch):
    """Exercise the setup probe, dry-run preview, and approval endpoints without providers."""
    config_db = MagicMock()
    config_db.get_all_integrations.return_value = {}
    monkeypatch.setattr(config_routes, "DatabaseManager", MagicMock(return_value=config_db))
    monkeypatch.setattr(config_routes, "load_env_vars", lambda: {
        "SETUP_COMPLETED": False,
        "SELECTED_SERVICE": "plex",
        "TMDB_API_KEY": "test-key",
    })
    monkeypatch.setattr(config_routes, "is_setup_complete", lambda _config: False)

    job = {"id": 7, "name": "Smoke preview", "job_type": "recommendation", "owner_id": 1}
    repository = MagicMock()
    repository.get_job.return_value = job
    monkeypatch.setattr(jobs_routes, "JobRepository", MagicMock(return_value=repository))
    preview = MagicMock()
    preview.run = AsyncMock(return_value=ExecutionResult(
        success=True,
        results_count=1,
        requested_count=0,
        dry_run_items=[{"tmdb_id": 42, "title": "Smoke title", "would_request": True}],
    ))
    monkeypatch.setattr(jobs_routes.RecommendationAutomation, "create", AsyncMock(return_value=preview))
    monkeypatch.setattr(jobs_routes, "run_async", lambda coro: asyncio.run(coro))

    queue = MagicMock()
    queue.decide_suggestions.return_value = 1
    monkeypatch.setattr(automation_routes, "DatabaseManager", MagicMock(return_value=queue))

    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
    limiter.init_app(app)

    @app.before_request
    def inject_admin():
        g.current_user = {"id": "1", "username": "admin", "role": "admin"}

    app.register_blueprint(config_routes.config_bp, url_prefix="/api/config")
    app.register_blueprint(jobs_routes.jobs_bp, url_prefix="/api/jobs")
    app.register_blueprint(automation_routes.automation_bp, url_prefix="/api/automation")

    client = app.test_client()
    assert client.get("/api/config/status").get_json()["setup_completed"] is False

    preview_response = client.post("/api/jobs/7/dry-run")
    assert preview_response.status_code == 200
    assert preview_response.get_json()["items"] == [
        {"tmdb_id": 42, "title": "Smoke title", "would_request": True}
    ]

    approval_response = client.post("/api/automation/requests/workflow/approve", json={"ids": [42]})
    assert approval_response.status_code == 200
    assert approval_response.get_json()["updated"] == 1
    queue.decide_suggestions.assert_called_once_with([42], None, 1, True, False)
