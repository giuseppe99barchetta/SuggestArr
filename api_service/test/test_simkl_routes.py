"""Tests for the Simkl HTTP routes.

Beyond the usual link/unlink coverage, these pin down the two places the Simkl
routes deliberately diverge from the Trakt ones: the client id is never taken
from a request body, and the in-flight PIN is held server-side.
"""
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g

from api_service.blueprints.simkl.routes import simkl_bp
from api_service.services.simkl.simkl_client import (
    SimklAuthError,
    SimklClientIdError,
    SimklPinExpired,
    SimklPinPending,
)

SELECTED = {"SELECTED_SERVICE": "jellyfin", "SELECTED_USERS": [{"id": "jf-1", "name": "alice"}]}
PIN = {
    "user_code": "8CCE9",
    "verification_uri": "https://simkl.com/pin",
    "expires_in": 900,
    "interval": 5,
}
SETTINGS = {"simkl_user_id": "8307044", "simkl_username": "Wire"}


class FakeClient:
    """Stands in for SimklClient; behaviour is driven by class-level knobs."""
    pin_error = None
    instances = []

    def __init__(self, client_id, access_token="", session=None, link_id=None):
        self.client_id = client_id
        FakeClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def request_pin_code(self):
        if FakeClient.pin_error:
            raise FakeClient.pin_error
        return dict(PIN)

    async def poll_for_token(self, user_code):
        if FakeClient.pin_error:
            raise FakeClient.pin_error
        return "tok-123"

    async def get_user_settings(self):
        return dict(SETTINGS)


async def _sync_ok(self, link, token):
    """Stand-in for the sync layer so preview tests exercise cache reads only."""
    return True


@pytest.fixture(autouse=True)
def reset_fake():
    FakeClient.pin_error = None
    FakeClient.instances = []
    yield


def make_app():
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.before_request
    def inject_caller():
        g.current_user = {"id": "1", "username": "admin", "role": "admin"}

    app.register_blueprint(simkl_bp, url_prefix="/api/simkl")
    return app


def make_db(**overrides):
    db = MagicMock()
    db.upsert_media_user_identity.return_value = {"id": 1}
    db.get_media_user_identity.return_value = {
        "id": 1, "provider": "jellyfin", "external_user_id": "jf-1",
    }
    db.upsert_simkl_account_link.return_value = 5
    db.get_simkl_account_link.return_value = None
    db.get_simkl_pending_user_code.return_value = "8CCE9"
    db.get_simkl_watched_cache.return_value = []
    db.get_enabled_simkl_sources.return_value = []
    for key, value in overrides.items():
        getattr(db, key).return_value = value
    return db


def run(db, method, path, client_id="cid", **kwargs):
    app = make_app()
    with patch("api_service.blueprints.simkl.routes.DatabaseManager", return_value=db), \
         patch("api_service.blueprints.simkl.routes.SimklClient", FakeClient), \
         patch("api_service.blueprints.simkl.routes.load_env_vars", return_value=SELECTED), \
         patch("api_service.blueprints.simkl.routes._simkl_client_id", return_value=client_id):
        return getattr(app.test_client(), method)(path, **kwargs)


# ---- Configuration gate ------------------------------------------------------

def test_requesting_a_pin_without_a_configured_client_id_is_rejected():
    resp = run(make_db(), "post", "/api/simkl/media-users/jellyfin/jf-1/pin/code", client_id="")
    assert resp.status_code == 400
    assert "client ID" in resp.get_json()["message"]


def test_a_client_id_in_the_request_body_is_ignored():
    """Trakt's routes persist payload credentials; doing that for Simkl would
    let any admin-authenticated request rewrite the install's integration."""
    db = make_db()
    resp = run(
        db, "post", "/api/simkl/media-users/jellyfin/jf-1/pin/code",
        json={"client_id": "attacker-supplied", "client_secret": "nope"},
    )

    assert resp.status_code == 200
    db.set_integration.assert_not_called()
    assert FakeClient.instances[0].client_id == "cid"


# ---- PIN flow ----------------------------------------------------------------

def test_requesting_a_pin_returns_the_code_and_binds_it_to_the_identity():
    db = make_db()
    resp = run(db, "post", "/api/simkl/media-users/jellyfin/jf-1/pin/code")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["user_code"] == "8CCE9"
    assert body["verification_uri"] == "https://simkl.com/pin"
    db.set_simkl_pending_user_code.assert_called_once_with(1, "8CCE9")


def test_the_poll_uses_the_stored_code_not_one_supplied_by_the_caller():
    """Otherwise a caller could attach whichever Simkl account authorized a
    code they did not request to someone else's media user."""
    db = make_db()
    polled = {}

    class Recording(FakeClient):
        async def poll_for_token(self, user_code):
            polled["code"] = user_code
            return "tok-123"

    app = make_app()
    with patch("api_service.blueprints.simkl.routes.DatabaseManager", return_value=db), \
         patch("api_service.blueprints.simkl.routes.SimklClient", Recording), \
         patch("api_service.blueprints.simkl.routes.load_env_vars", return_value=SELECTED), \
         patch("api_service.blueprints.simkl.routes._simkl_client_id", return_value="cid"):
        resp = app.test_client().post(
            "/api/simkl/media-users/jellyfin/jf-1/pin/token",
            json={"user_code": "ATTACKER"},
        )

    assert resp.status_code == 200
    assert polled["code"] == "8CCE9"


def test_polling_before_requesting_a_pin_is_rejected():
    db = make_db(get_simkl_pending_user_code=None)
    resp = run(db, "post", "/api/simkl/media-users/jellyfin/jf-1/pin/token")
    assert resp.status_code == 400


def test_a_pending_pin_returns_202_so_the_client_keeps_polling():
    FakeClient.pin_error = SimklPinPending("pending")
    resp = run(make_db(), "post", "/api/simkl/media-users/jellyfin/jf-1/pin/token")

    assert resp.status_code == 202
    assert resp.get_json() == {"connected": False, "status": "pending"}


def test_an_expired_pin_clears_the_stored_code():
    FakeClient.pin_error = SimklPinExpired("expired")
    db = make_db()
    resp = run(db, "post", "/api/simkl/media-users/jellyfin/jf-1/pin/token")

    assert resp.status_code == 400
    db.set_simkl_pending_user_code.assert_called_with(1, None)


def test_a_rejected_client_id_surfaces_as_a_400_not_a_500():
    FakeClient.pin_error = SimklClientIdError("client id rejected")
    resp = run(make_db(), "post", "/api/simkl/media-users/jellyfin/jf-1/pin/code")
    assert resp.status_code == 400


def test_a_rejected_client_id_is_tagged_so_the_ui_can_place_it():
    """It belongs on the integration card, not on the user whose request hit
    it, and the UI should not have to match on message text to know that."""
    FakeClient.pin_error = SimklClientIdError("client id rejected")
    resp = run(make_db(), "post", "/api/simkl/media-users/jellyfin/jf-1/pin/code")
    assert resp.get_json()["code"] == "client_id_failed"


def test_an_expired_pin_is_not_tagged_as_an_install_level_failure():
    FakeClient.pin_error = SimklPinExpired("expired")
    resp = run(make_db(), "post", "/api/simkl/media-users/jellyfin/jf-1/pin/token")
    assert "code" not in resp.get_json()


# ---- Cancelling an in-flight PIN ---------------------------------------------

def test_cancelling_clears_the_pending_code():
    """A Simkl PIN stays live for fifteen minutes, so an abandoned flow leaves
    a code that could still be completed against this identity."""
    db = make_db()
    resp = run(db, "delete", "/api/simkl/media-users/jellyfin/jf-1/pin")

    assert resp.status_code == 200
    db.set_simkl_pending_user_code.assert_called_once_with(1, None)


def test_cancelling_does_not_unlink_the_account():
    db = make_db()
    run(db, "delete", "/api/simkl/media-users/jellyfin/jf-1/pin")
    db.unlink_simkl_account.assert_not_called()


def test_cancelling_for_an_identity_that_was_never_created_still_succeeds():
    db = make_db()
    db.get_media_user_identity.side_effect = ValueError("not found")
    resp = run(db, "delete", "/api/simkl/media-users/jellyfin/jf-1/pin")

    assert resp.status_code == 200
    db.set_simkl_pending_user_code.assert_not_called()


def test_cancelling_for_an_unknown_media_user_is_rejected():
    resp = run(make_db(), "delete", "/api/simkl/media-users/jellyfin/nope/pin")
    assert resp.status_code == 404


def test_a_completed_pin_persists_the_link_token_and_default_source():
    db = make_db()
    resp = run(db, "post", "/api/simkl/media-users/jellyfin/jf-1/pin/token")

    assert resp.status_code == 200
    assert resp.get_json()["simkl_username"] == "Wire"
    db.upsert_simkl_account_link.assert_called_once()
    db.upsert_simkl_oauth_tokens.assert_called_once_with(link_id=5, access_token="tok-123")
    db.upsert_simkl_source.assert_called_once()
    db.set_simkl_pending_user_code.assert_called_with(1, None)


def test_relinking_a_different_simkl_account_clears_the_cache():
    """Otherwise the previous account's history would be served as this one's."""
    db = make_db(get_simkl_account_link={
        "id": 5, "simkl_user_id": "99999", "connected": True, "status": "connected",
    })
    run(db, "post", "/api/simkl/media-users/jellyfin/jf-1/pin/token")
    db.clear_simkl_watched_cache.assert_called_once_with(5)


def test_relinking_the_same_simkl_account_keeps_the_cache():
    db = make_db(get_simkl_account_link={
        "id": 5, "simkl_user_id": "8307044", "connected": True, "status": "connected",
    })
    run(db, "post", "/api/simkl/media-users/jellyfin/jf-1/pin/token")
    db.clear_simkl_watched_cache.assert_not_called()


def test_an_unknown_media_user_is_rejected():
    resp = run(make_db(), "post", "/api/simkl/media-users/jellyfin/nope/pin/code")
    assert resp.status_code == 404


# ---- Status ------------------------------------------------------------------

def test_link_status_never_exposes_the_pending_pin_or_the_activities_blob():
    db = make_db(get_simkl_account_link={
        "id": 5, "connected": True, "status": "connected", "simkl_username": "Wire",
        "pending_user_code": "8CCE9", "activities_json": "{}", "last_full_sync_at": 123,
    })
    resp = run(db, "get", "/api/simkl/media-users")

    link = resp.get_json()["media_users"][0]["simkl"]
    assert "pending_user_code" not in link
    assert "activities_json" not in link
    assert link["connected"] is True


def test_link_status_reports_whether_the_first_sync_has_finished():
    """Lets the UI distinguish "still syncing" from "no watch history"."""
    db = make_db(get_simkl_account_link={
        "id": 5, "connected": True, "status": "connected", "last_full_sync_at": None,
    })
    resp = run(db, "get", "/api/simkl/media-users")
    assert resp.get_json()["media_users"][0]["simkl"]["initial_sync_complete"] is False


def test_an_unlinked_user_reports_disconnected():
    resp = run(make_db(), "get", "/api/simkl/media-users")
    assert resp.get_json()["media_users"][0]["simkl"] == {"connected": False}


# ---- Unlink ------------------------------------------------------------------

def test_unlink_states_plainly_that_it_could_not_revoke_upstream():
    """Simkl exposes no revocation endpoint, so claiming otherwise would lie."""
    db = make_db()
    resp = run(db, "delete", "/api/simkl/media-users/jellyfin/jf-1")

    body = resp.get_json()
    assert resp.status_code == 200
    assert body["connected"] is False
    assert body["revoked_upstream"] is False
    assert "connected-apps" in body["message"]
    db.unlink_simkl_account.assert_called_once_with(1)


# ---- Preview -----------------------------------------------------------------

def test_preview_returns_cached_rows():
    db = make_db(
        get_simkl_account_link={
            "id": 5, "connected": True, "status": "connected", "simkl_username": "Wire",
        },
        get_simkl_oauth_tokens={"access_token": "tok"},
        get_simkl_account_link_by_id={"id": 5, "last_full_sync_at": 123},
    )
    db.get_simkl_watched_cache.return_value = [{
        "tmdb_id": "78", "media_type": "tv", "title": "Dateline NBC",
        "year": 1992, "last_watched_at": 300, "status": "watching",
    }]

    with patch(
        "api_service.services.simkl.watch_history_sync.SimklWatchHistorySync.ensure_synced",
        _sync_ok,
    ):
        resp = run(db, "get", "/api/simkl/media-users/jellyfin/jf-1/recent")

    body = resp.get_json()
    assert resp.status_code == 200
    assert body["items"][0]["title"] == "Dateline NBC"
    assert body["initial_sync_complete"] is True


def test_preview_on_an_unlinked_user_is_a_404():
    resp = run(make_db(), "get", "/api/simkl/media-users/jellyfin/jf-1/recent")
    assert resp.status_code == 404


def test_preview_flags_needs_reauth_when_the_token_is_rejected():
    db = make_db(
        get_simkl_account_link={"id": 5, "connected": True, "status": "connected"},
        get_simkl_oauth_tokens={"access_token": "stale"},
    )

    async def boom(self, link, token):
        raise SimklAuthError("401")

    with patch(
        "api_service.services.simkl.watch_history_sync.SimklWatchHistorySync.ensure_synced", boom
    ):
        resp = run(db, "get", "/api/simkl/media-users/jellyfin/jf-1/recent")

    assert resp.status_code == 400
    assert resp.get_json()["status"] == "needs_reauth"
    assert db.mark_simkl_account_link_error.call_args[0][1] == "needs_reauth"


# ---- Sources -----------------------------------------------------------------

def test_updating_source_flags_persists_them():
    db = make_db(get_simkl_sources=[{
        "source_type": "watched_history", "source_key": "watched_history",
        "enabled": True, "use_as_seed": True, "use_as_exclusion": True,
    }])
    resp = run(
        db, "put", "/api/simkl/sources/jellyfin/jf-1",
        json={"use_as_seed": False, "use_as_exclusion": True},
    )

    assert resp.status_code == 200
    assert resp.get_json() == {"use_as_seed": False, "use_as_exclusion": True}
    assert db.upsert_simkl_source.call_args.kwargs["use_as_seed"] is False


def test_updating_sources_without_a_watched_history_row_is_a_404():
    resp = run(
        make_db(get_simkl_sources=[]), "put", "/api/simkl/sources/jellyfin/jf-1", json={},
    )
    assert resp.status_code == 404
