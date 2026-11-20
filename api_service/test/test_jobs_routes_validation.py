import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
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


def test_update_job_rejects_invalid_rolling_request_limit(monkeypatch):
    existing = {"id": 1, "job_type": "recommendation", "owner_id": 1, "media_type": "movie", "user_ids": ["u1"]}
    client, repository = _make_client(monkeypatch, existing_job=existing)

    response = client.put("/api/jobs/1", json={"max_requests_per_user": -1})

    assert response.status_code == 400
    assert "max_requests_per_user" in response.get_json()["message"]
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


def _preview_item():
    return {"tmdb_id": 1186, "media_type": "tv", "title": "My Lovely Sam Soon",
            "overview": "English overview", "would_request": True}


def _stub_dry_run(monkeypatch, client_path):
    """Make the job dry-run or the list preview return one English item."""
    automation = MagicMock()
    automation.next_offset = 1
    automation.scan_complete = True
    automation.run = AsyncMock(return_value=ExecutionResult(
        success=True, results_count=1, requested_count=1, dry_run_items=[_preview_item()]))
    create = AsyncMock(return_value=automation)
    monkeypatch.setattr(jobs_routes.DiscoverAutomation, "create", create)
    monkeypatch.setattr(jobs_routes.ListImportAutomation, "from_config", create)
    monkeypatch.setattr(jobs_routes, "_list_import_config", lambda data: {})
    monkeypatch.setattr(jobs_routes, "run_async", lambda coro: asyncio.run(coro))
    return {} if client_path.endswith("dry-run") else {"offset": 0}


@pytest.mark.parametrize("path", ["/api/jobs/1/dry-run", "/api/jobs/lists/preview"])
def test_preview_items_follow_display_language(monkeypatch, path):
    """Issue #568: preview titles use TMDB_LANGUAGE like the request lists."""
    from api_service.blueprints.automation import routes as automation_routes
    from api_service.db import database_manager
    from api_service.services.tmdb import localization

    client, _ = _make_client(monkeypatch, existing_job={"id": 1, "job_type": "discover", "owner_id": 1})
    body = _stub_dry_run(monkeypatch, path)
    db = MagicMock()
    db.get_user_language.return_value = None
    db.get_integration.return_value = {"api_key": "key"}
    monkeypatch.setattr(database_manager, "DatabaseManager", lambda: db)
    monkeypatch.setattr(automation_routes, "load_env_vars", lambda: {"TMDB_LANGUAGE": "ko"})
    seen = {}

    def translations(_db, api_key, pairs, language, run):
        seen["language"] = language
        return {("1186", "tv"): {"title": "내 이름은 김삼순", "overview": "한국어 줄거리"}}

    monkeypatch.setattr(localization, "translations_for", translations)

    response = client.post(path, json=body)

    assert response.status_code == 200
    item = response.get_json()["items"][0]
    assert (item["title"], item["overview"]) == ("내 이름은 김삼순", "한국어 줄거리")
    assert seen["language"] == "ko"


@pytest.mark.parametrize("path", ["/api/jobs/1/dry-run", "/api/jobs/lists/preview"])
def test_preview_survives_localization_setup_failure(monkeypatch, path):
    from api_service.db import database_manager

    client, _ = _make_client(monkeypatch, existing_job={"id": 1, "job_type": "discover", "owner_id": 1})
    body = _stub_dry_run(monkeypatch, path)

    def broken():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(database_manager, "DatabaseManager", broken)

    response = client.post(path, json=body)

    assert response.status_code == 200
    assert response.get_json()["items"] == [_preview_item()]


@pytest.mark.parametrize("schedule_type,schedule_value", [
    ("cron", "0 0 * *"),
    ("preset", "fortnightly"),
    ("preset", None),
    ("cron", 5),
    ("preset", []),
])
def test_update_job_rejects_invalid_schedule(monkeypatch, schedule_type, schedule_value):
    """An invalid schedule is refused before saving; saving it would silently unschedule the job."""
    existing = {"id": 1, "job_type": "discover", "owner_id": 1, "media_type": "movie", "user_ids": [],
                "schedule_type": "preset", "schedule_value": "daily"}
    client, repository = _make_client(monkeypatch, existing_job=existing)

    response = client.put("/api/jobs/1", json={"schedule_type": schedule_type, "schedule_value": schedule_value})

    assert response.status_code == 400
    repository.update_job.assert_not_called()


def test_update_job_checks_new_value_against_stored_type(monkeypatch):
    existing = {"id": 1, "job_type": "discover", "owner_id": 1, "media_type": "movie", "user_ids": [],
                "schedule_type": "cron", "schedule_value": "0 0 * * *"}
    client, repository = _make_client(monkeypatch, existing_job=existing)

    assert client.put("/api/jobs/1", json={"schedule_value": "daily"}).status_code == 400
    repository.update_job.assert_not_called()
    repository.update_job.reset_mock()
    client.put("/api/jobs/1", json={"schedule_value": "30 4 * * 1"})
    repository.update_job.assert_called_once()


@pytest.mark.parametrize("schedule_value", ["0 0 * *", None, 5])
def test_create_job_rejects_invalid_schedule(monkeypatch, schedule_value):
    client, repository = _make_client(monkeypatch)

    response = client.post("/api/jobs", json={
        "name": "Bad schedule", "media_type": "movie", "filters": {},
        "schedule_type": "cron", "schedule_value": schedule_value,
    })

    assert response.status_code == 400
    repository.create_job.assert_not_called()


@pytest.mark.parametrize("raw,expected", [("-1", 1), ("100000000", 500), ("20", 20), ("abc", 100)])
def test_history_limit_is_clamped(monkeypatch, raw, expected):
    client, repository = _make_client(monkeypatch)
    repository.get_recent_history.return_value = []

    response = client.get(f"/api/jobs/history?limit={raw}")

    assert response.status_code == 200
    repository.get_recent_history.assert_called_once_with(expected, owner_id=None)
