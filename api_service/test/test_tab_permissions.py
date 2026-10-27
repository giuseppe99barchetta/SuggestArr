"""Pages an admin removes from a user are refused by the server, not only hidden in the UI."""
from unittest.mock import MagicMock

import pytest
from flask import Flask, g

from api_service.auth.middleware import require_tab
from api_service.blueprints.ai_search import routes as ai_routes
from api_service.blueprints.jobs import routes as jobs_routes

NO_JOBS_NO_AI = {"id": "2", "role": "user", "visible_tabs": "requests,profile"}


def _status(user, tab):
    app = Flask(__name__)
    with app.test_request_context():
        g.current_user = user
        refused = require_tab(tab)
    return refused[1] if refused else 200


@pytest.mark.parametrize("user,tab,status", [
    ({"id": "1", "role": "admin", "visible_tabs": "profile"}, "jobs", 200),
    ({"id": "2", "role": "user", "visible_tabs": ""}, "jobs", 200),      # no list = every page, as in the SPA
    ({"id": "2", "role": "user", "visible_tabs": None}, "jobs", 200),
    ({"id": "2", "role": "user", "visible_tabs": "jobs,profile"}, "jobs", 200),
    ({"id": "2", "role": "user", "visible_tabs": "ai-search"}, "ai_search", 200),  # legacy alias
    (NO_JOBS_NO_AI, "jobs", 403),
    (NO_JOBS_NO_AI, "ai_search", 403),
])
def test_require_tab_matches_the_spa_rule(user, tab, status):
    assert _status(user, tab) == status


def _app(user, blueprint, prefix):
    app = Flask(__name__)

    @app.before_request
    def _caller():
        g.current_user = user

    app.register_blueprint(blueprint, url_prefix=prefix)
    return app.test_client()


def test_jobs_page_actions_are_refused_without_the_jobs_page(monkeypatch):
    repository = MagicMock()
    monkeypatch.setattr(jobs_routes, "JobRepository", MagicMock(return_value=repository))
    client = _app(NO_JOBS_NO_AI, jobs_routes.jobs_bp, "/api/jobs")

    assert client.post("/api/jobs", json={}).status_code == 403
    assert client.put("/api/jobs/1", json={}).status_code == 403
    assert client.delete("/api/jobs/1").status_code == 403
    assert client.post("/api/jobs/1/toggle").status_code == 403
    assert client.post("/api/jobs/1/run").status_code == 403
    assert client.post("/api/jobs/1/dry-run").status_code == 403
    assert client.post("/api/jobs/lists/import", json={}).status_code == 403
    repository.create_job.assert_not_called()
    repository.get_job.assert_not_called()


def test_shared_reads_stay_open_without_the_jobs_page(monkeypatch):
    repository = MagicMock()
    repository.get_all_jobs.return_value = []
    monkeypatch.setattr(jobs_routes, "JobRepository", MagicMock(return_value=repository))
    client = _app(NO_JOBS_NO_AI, jobs_routes.jobs_bp, "/api/jobs")

    assert client.get("/api/jobs").status_code != 403
    assert client.get("/api/jobs/lists/import").status_code != 403


def test_ai_search_and_request_are_refused_without_the_ai_page():
    client = _app(NO_JOBS_NO_AI, ai_routes.ai_search_bp, "/api/ai-search")
    assert client.post("/api/ai-search/query", json={"query": "x"}).status_code == 403
    assert client.post("/api/ai-search/request", json={"tmdb_id": 1}).status_code == 403
