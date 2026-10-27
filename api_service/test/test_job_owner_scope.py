"""A regular user's jobs and AI searches only ever reach their own linked media accounts.

Before, an empty user list meant "every monitored user" for everyone, so a
household member's job scanned the admin's history and could request in
other people's Seer names.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from flask import Flask, g

from api_service.blueprints.ai_search.routes import ai_search_query
from api_service.blueprints.jobs import routes as jobs_routes
from api_service.jobs.recommendation_automation import RecommendationAutomation
from api_service.jobs.trakt_recommendations_automation import TraktRecommendationsAutomation
from api_service.utils.request_scope import scan_user_ids

ADMIN = {"id": "1", "role": "admin"}
VIEWER = {"id": "2", "role": "user"}


class FakeDB:
    """Linked media accounts per SuggestArr user id."""

    def __init__(self, links=None, users=None):
        self.links = links or {}
        self.users = users or {}

    def get_user_media_profiles(self, user_id):
        return [{"provider": "jellyfin", "external_user_id": uid} for uid in self.links.get(int(user_id), [])]

    def get_auth_user_by_id(self, user_id):
        return self.users.get(int(user_id))


# --- the rule itself -------------------------------------------------------

def test_admin_and_ownerless_keep_their_choice():
    db = FakeDB()
    assert scan_user_ids(db, ADMIN, []) is None
    assert scan_user_ids(db, None, []) is None
    assert scan_user_ids(db, ADMIN, ["anyone"]) == ["anyone"]


def test_regular_user_is_narrowed_to_own_accounts():
    db = FakeDB(links={2: ["mine"]})
    assert scan_user_ids(db, VIEWER, []) == ["mine"]
    assert scan_user_ids(db, VIEWER, ["mine", "admin-id"]) == ["mine"]
    assert scan_user_ids(FakeDB(), VIEWER, []) == []


# --- recommendation job execution ------------------------------------------

def _automation(owner_id, user_ids, db):
    automation = RecommendationAutomation()
    automation.job_data = {"owner_id": owner_id, "user_ids": user_ids}
    automation.env_vars = {"SELECTED_USERS": [{"id": "mine", "name": "Me"}, {"id": "admin-id", "name": "Admin"}]}
    automation.db_manager = db
    return automation


def test_regular_users_job_with_no_user_list_scans_only_their_account():
    db = FakeDB(links={2: ["mine"]}, users={2: VIEWER})
    automation = _automation(2, [], db)
    assert [u["id"] for u in automation._get_selected_users([])] == ["mine"]
    assert automation.no_users_reason is None


def test_admin_job_with_no_user_list_still_scans_everyone():
    db = FakeDB(users={1: ADMIN})
    automation = _automation(1, [], db)
    assert [u["id"] for u in automation._get_selected_users([])] == ["mine", "admin-id"]


def test_unlinked_or_deleted_owner_scans_nobody():
    for db in (FakeDB(users={2: VIEWER}), FakeDB()):
        automation = _automation(2, [], db)
        assert automation._get_selected_users([]) == []
        assert automation.no_users_reason


@pytest.mark.asyncio
async def test_job_without_users_is_logged_as_skipped_without_scanning():
    automation = _automation(2, [], FakeDB(users={2: VIEWER}))
    automation.no_users_reason = "nothing to scan"
    automation.job_id = 9
    automation.job_data["name"] = "Mine"
    automation.repository = MagicMock()
    automation.repository.log_execution_start.return_value = 77
    automation.media_handler = MagicMock(process_recent_items=AsyncMock())

    result = await automation.run()

    assert result.success is False
    automation.media_handler.process_recent_items.assert_not_called()
    end = automation.repository.log_execution_end.call_args.kwargs
    assert end["exec_id"] == 77 and end["status"] == "skipped"


# --- trakt job execution ---------------------------------------------------

def test_regular_users_trakt_job_cannot_use_someone_elses_account():
    automation = TraktRecommendationsAutomation()
    automation.job_data = {"owner_id": 2, "user_ids": ["admin-id"]}
    automation.env_vars = {"SELECTED_SERVICE": "jellyfin", "TRAKT_CLIENT_ID": "cid"}
    automation.db_manager = FakeDB(links={2: ["mine"]}, users={2: VIEWER})
    with pytest.raises(ValueError, match="own linked media account"):
        automation._build_trakt_client()


# --- job API ---------------------------------------------------------------

def _client(monkeypatch, user, db):
    repository = MagicMock()
    repository.create_job.return_value = 5
    repository.get_job.return_value = {"id": 5, "owner_id": 2, "job_type": "recommendation",
                                       "user_ids": [], "enabled": False}
    repository.update_job.return_value = True
    monkeypatch.setattr(jobs_routes, "JobRepository", MagicMock(return_value=repository))
    monkeypatch.setattr(jobs_routes, "get_job_manager", MagicMock())
    monkeypatch.setattr("api_service.db.database_manager.DatabaseManager", lambda: db)
    app = Flask(__name__)

    @app.before_request
    def _caller():
        g.current_user = user

    app.register_blueprint(jobs_routes.jobs_bp, url_prefix="/api/jobs")
    return app.test_client(), repository


def _payload(user_ids):
    return {"name": "Mine", "job_type": "recommendation", "media_type": "both", "filters": {},
            "schedule_type": "preset", "schedule_value": "daily", "user_ids": user_ids}


def test_regular_user_cannot_create_a_job_on_someone_elses_account(monkeypatch):
    client, repository = _client(monkeypatch, VIEWER, FakeDB(links={2: ["mine"]}))
    assert client.post("/api/jobs", json=_payload(["admin-id"])).status_code == 403
    repository.create_job.assert_not_called()


def test_regular_user_without_a_linked_account_is_told_to_link_one(monkeypatch):
    client, repository = _client(monkeypatch, VIEWER, FakeDB())
    response = client.post("/api/jobs", json=_payload([]))
    assert response.status_code == 400
    assert "Link your media server account" in response.get_json()["message"]


def test_regular_user_can_create_a_job_on_their_own_account(monkeypatch):
    client, _ = _client(monkeypatch, VIEWER, FakeDB(links={2: ["mine"]}))
    assert client.post("/api/jobs", json=_payload([])).status_code == 201
    assert client.post("/api/jobs", json=_payload(["mine"])).status_code == 201


def test_admin_can_still_pick_any_user(monkeypatch):
    client, _ = _client(monkeypatch, ADMIN, FakeDB())
    assert client.post("/api/jobs", json=_payload(["anyone"])).status_code == 201


def test_regular_user_cannot_repoint_their_job_at_someone_else(monkeypatch):
    client, repository = _client(monkeypatch, VIEWER, FakeDB(links={2: ["mine"]}))
    assert client.put("/api/jobs/5", json={"user_ids": ["admin-id"]}).status_code == 403
    repository.update_job.assert_not_called()


def test_unlinked_regular_user_can_still_edit_an_existing_job(monkeypatch):
    client, _ = _client(monkeypatch, VIEWER, FakeDB())
    assert client.put("/api/jobs/5", json={"name": "Renamed"}).status_code == 200


# --- AI search -------------------------------------------------------------

async def _search(user, db, user_ids=None):
    app = Flask(__name__)
    service = MagicMock()
    service.search = AsyncMock(return_value={"results": [], "total": 0})
    with app.test_request_context(json={"query": "space", "user_ids": user_ids or []}), \
         patch("api_service.blueprints.ai_search.routes.get_llm_client", return_value=object()), \
         patch("api_service.blueprints.ai_search.routes.AiSearchService", return_value=service), \
         patch("api_service.blueprints.ai_search.routes.DatabaseManager", return_value=db):
        g.current_user = user
        await ai_search_query.__wrapped__()
    return service.search.call_args.kwargs


@pytest.mark.asyncio
async def test_ai_search_uses_only_the_callers_history():
    kwargs = await _search(VIEWER, FakeDB(links={2: ["mine"]}))
    assert kwargs["user_ids"] == ["mine"]
    assert kwargs["use_history"] is True


@pytest.mark.asyncio
async def test_ai_search_ignores_someone_elses_id():
    kwargs = await _search(VIEWER, FakeDB(links={2: ["mine"]}), ["admin-id"])
    assert kwargs["use_history"] is False


@pytest.mark.asyncio
async def test_ai_search_without_linked_account_uses_no_history():
    kwargs = await _search(VIEWER, FakeDB())
    assert kwargs["use_history"] is False


@pytest.mark.asyncio
async def test_ai_search_for_admin_still_reads_every_user():
    kwargs = await _search(ADMIN, FakeDB())
    assert kwargs["user_ids"] is None
