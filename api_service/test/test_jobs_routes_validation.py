import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.jobs import routes as jobs_routes
from api_service.jobs.discover_automation import ExecutionResult


def _make_client(monkeypatch, existing_job=None):
    repository = MagicMock()
    repository.get_job.return_value = existing_job
    repository.update_job.return_value = True
    monkeypatch.setattr(jobs_routes, "JobRepository", MagicMock(return_value=repository))
    monkeypatch.setattr(jobs_routes, "get_job_manager", MagicMock())

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    app.secret_key = "test-secret"

    @app.before_request
    def inject_admin():
        g.current_user = {"id": "1", "username": "admin", "role": "admin"}

    limiter.init_app(app)
    app.register_blueprint(jobs_routes.jobs_bp, url_prefix="/api/jobs")
    return app.test_client(), repository


def test_update_job_rejects_invalid_job_type(monkeypatch):
    existing = {
        "id": 1,
        "job_type": "discover",
        "owner_id": 1,
        "media_type": "movie",
        "user_ids": [],
    }
    client, repository = _make_client(monkeypatch, existing_job=existing)

    response = client.put("/api/jobs/1", json={"job_type": "invalid"})

    assert response.status_code == 400
    assert "job_type must be one of" in response.get_json()["message"]
    repository.update_job.assert_not_called()


def test_update_trakt_job_rejects_empty_user_ids(monkeypatch):
    existing = {
        "id": 2,
        "job_type": "trakt_recommendations",
        "owner_id": 1,
        "media_type": "both",
        "user_ids": ["plex-user-1"],
    }
    client, repository = _make_client(monkeypatch, existing_job=existing)

    response = client.put("/api/jobs/2", json={"user_ids": []})

    assert response.status_code == 400
    assert "exactly one linked media user" in response.get_json()["message"]
    repository.update_job.assert_not_called()


def test_update_trakt_job_rejects_multiple_user_ids(monkeypatch):
    existing = {
        "id": 2,
        "job_type": "trakt_recommendations",
        "owner_id": 1,
        "media_type": "both",
        "user_ids": ["plex-user-1"],
    }
    client, repository = _make_client(monkeypatch, existing_job=existing)

    response = client.put("/api/jobs/2", json={"user_ids": ["plex-user-1", "plex-user-2"]})

    assert response.status_code == 400
    assert "exactly one linked media user" in response.get_json()["message"]
    repository.update_job.assert_not_called()


def test_update_trakt_job_accepts_single_user_id(monkeypatch):
    existing = {
        "id": 2,
        "job_type": "trakt_recommendations",
        "owner_id": 1,
        "media_type": "both",
        "user_ids": ["plex-user-1"],
        "enabled": True,
    }
    client, repository = _make_client(monkeypatch, existing_job=existing)
    repository.get_job.side_effect = [existing, existing]

    response = client.put("/api/jobs/2", json={"user_ids": ["plex-user-2"]})

    assert response.status_code == 200
    repository.update_job.assert_called_once_with(2, {"user_ids": ["plex-user-2"]})


def test_update_job_rejects_non_positive_unwatched_days(monkeypatch):
    existing = {"id": 1, "job_type": "recommendation", "owner_id": 1, "media_type": "movie", "user_ids": ["u1"]}
    client, repository = _make_client(monkeypatch, existing_job=existing)

    response = client.put("/api/jobs/1", json={"unwatched_suggestion_days": 0})

    assert response.status_code == 400
    assert "positive integer" in response.get_json()["message"]
    repository.update_job.assert_not_called()


def test_dry_run_trakt_job_initializes_in_dry_run_mode(monkeypatch):
    existing = {
        "id": 2,
        "job_type": "trakt_recommendations",
        "owner_id": 1,
        "media_type": "both",
        "user_ids": ["plex-user-1"],
    }
    client, _repository = _make_client(monkeypatch, existing_job=existing)
    automation = MagicMock()
    automation.run = AsyncMock(return_value=ExecutionResult(
        success=True,
        results_count=0,
        requested_count=0,
        dry_run_items=[],
    ))
    create = AsyncMock(return_value=automation)
    monkeypatch.setattr(jobs_routes.TraktRecommendationsAutomation, "create", create)
    monkeypatch.setattr(jobs_routes, "run_async", lambda coro: asyncio.run(coro))

    response = client.post("/api/jobs/2/dry-run")

    assert response.status_code == 200
    create.assert_awaited_once_with(2, dry_run=True)
