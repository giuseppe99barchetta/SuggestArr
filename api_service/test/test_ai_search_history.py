"""Tests for recent AI searches stored per user on the server."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from flask import Flask, g

from api_service.blueprints.ai_search import routes
from api_service.db import database_manager as dm_mod
from api_service.db.database_manager import DatabaseManager


@pytest.fixture
def db(tmp_path):
    with (
        patch.object(dm_mod, "DB_PATH", str(tmp_path / "history.db")),
        patch("api_service.db.database_manager.load_env_vars", return_value={"DB_TYPE": "sqlite"}),
    ):
        DatabaseManager._instance = None
        manager = DatabaseManager()
        with manager.get_connection() as conn:
            conn.execute("INSERT INTO auth_users(id,username,password_hash,role) VALUES (1,'ann','h','user'),(2,'bob','h','user')")
            conn.commit()
        yield manager
    DatabaseManager._instance = None


def test_history_is_newest_first_deduplicated_capped_and_per_user(db):
    for query in ["a", "b", "c", "a", "d", "e", "f"]:
        db.add_ai_search_history(1, query)
    db.add_ai_search_history(2, "bob's search")
    db.add_ai_search_history(1, "   ")

    assert db.get_ai_search_history(1) == ["f", "e", "d", "a", "c"]
    assert db.get_ai_search_history(2) == ["bob's search"]


def test_long_queries_are_cut_and_clearing_is_per_user(db):
    db.add_ai_search_history(1, "x" * 900)
    db.add_ai_search_history(2, "kept")
    assert len(db.get_ai_search_history(1)[0]) == db.AI_SEARCH_QUERY_MAX

    db.clear_ai_search_history(1)
    assert db.get_ai_search_history(1) == []
    assert db.get_ai_search_history(2) == ["kept"]


def test_deleting_a_user_deletes_their_history(db):
    db.add_ai_search_history(1, "secret")
    db.delete_auth_user(1)
    with db.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM ai_search_history").fetchone()[0] == 0


def _client(user=None):
    app = Flask(__name__)

    @app.before_request
    def _user():
        g.current_user = user

    app.register_blueprint(routes.ai_search_bp, url_prefix="/api/ai-search")
    return app.test_client()


def test_routes_list_import_and_clear_the_callers_history():
    db = MagicMock(AI_SEARCH_HISTORY_LIMIT=5)
    db.get_ai_search_history.return_value = ["newest", "older"]
    client = _client({"id": "7"})
    with patch.object(routes, "DatabaseManager", return_value=db):
        listed = client.get("/api/ai-search/history")
        imported = client.post("/api/ai-search/history", json={"queries": ["newest", "older"]})
        bad = client.post("/api/ai-search/history", json={"queries": "nope"})
        cleared = client.delete("/api/ai-search/history")

    assert listed.get_json()["history"] == ["newest", "older"]
    assert imported.status_code == 200
    assert [call.args for call in db.add_ai_search_history.call_args_list] == [(7, "older"), (7, "newest")]
    assert bad.status_code == 400
    assert cleared.status_code == 200
    db.clear_ai_search_history.assert_called_once_with(7)


def test_a_successful_search_is_recorded_for_the_caller():
    db = MagicMock()
    client = _client({"id": 3})
    service = MagicMock(search=AsyncMock(return_value={"results": [], "total": 0}))
    with patch.object(routes, "DatabaseManager", return_value=db), \
            patch.object(routes, "get_llm_client", return_value=object()), \
            patch.object(routes, "AiSearchService", return_value=service):
        response = client.post("/api/ai-search/query", json={"query": "  cozy mystery  "})
    assert response.status_code == 200
    db.add_ai_search_history.assert_called_once_with(3, "cozy mystery")
