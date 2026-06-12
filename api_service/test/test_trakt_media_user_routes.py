from unittest.mock import MagicMock, patch

from flask import Flask, g

from api_service.blueprints.trakt.routes import trakt_bp
from api_service.services.trakt.trakt_client import (
    TraktDeviceDenied,
    TraktDevicePending,
)


class FakeTraktClient:
    instances = []

    def __init__(
        self,
        client_id,
        client_secret,
        access_token="",
        refresh_token="",
        expires_at=None,
        session=None,
        db=None,
        link_id=None,
        token_source="manual_oauth",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.db = db
        self.link_id = link_id
        self.token_source = token_source
        FakeTraktClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request_device_code(self):
        return {"device_code": "dev-1", "user_code": "ABCD", "interval": 5, "expires_in": 600}

    async def poll_for_token(self, device_code):
        if device_code == "pending":
            raise TraktDevicePending("Trakt device authorization pending")
        if device_code == "denied":
            raise TraktDeviceDenied("Trakt authorization was denied")
        return {"access_token": "access", "refresh_token": "refresh", "expires_at": 12345}

    async def get_user_settings(self):
        return {"trakt_user_id": "trakt-user-1", "trakt_username": "trakt_name"}

    async def get_recent_items(self, limit=10):
        return [
            {
                "media_type": "movie",
                "tmdb_id": "123",
                "title": "Recent Movie",
                "year": 2024,
                "watched_at": 1710000000,
            }
        ][:limit]


SELECTED = {"SELECTED_SERVICE": "jellyfin", "SELECTED_USERS": [{"id": "jf-1", "name": "alice"}]}


def make_app(caller=None):
    app = Flask(__name__)
    app.config["TESTING"] = True
    caller_ref = {"user": caller or {"id": "1", "username": "admin", "role": "admin"}}

    @app.before_request
    def inject_caller():
        g.current_user = caller_ref["user"]

    app.register_blueprint(trakt_bp, url_prefix="/api/trakt")
    return app, caller_ref


def _patches(db):
    return (
        patch("api_service.blueprints.trakt.routes.DatabaseManager", return_value=db),
        patch("api_service.blueprints.trakt.routes.TraktClient", FakeTraktClient),
        patch("api_service.blueprints.trakt.routes.load_env_vars", return_value=SELECTED),
        patch(
            "api_service.blueprints.trakt.routes._resolve_trakt_credentials",
            return_value=("cid", "secret", False),
        ),
    )


def test_list_media_users_merges_selected_users_with_link_status():
    app, _ = make_app()
    db = MagicMock()
    db.get_media_user_identity.return_value = {"id": 1, "provider": "jellyfin", "external_user_id": "jf-1"}
    db.get_trakt_account_link.return_value = {
        "id": 5, "media_user_identity_id": 1, "connected": True, "trakt_username": "alice_t",
    }
    db.get_enabled_trakt_sources.return_value = [
        {"source_type": "watched_history", "use_as_seed": True, "use_as_exclusion": True},
    ]
    p1, p2, p3, p4 = _patches(db)
    with p1, p2, p3, p4:
        resp = app.test_client().get("/api/trakt/media-users")
    assert resp.status_code == 200
    rows = resp.get_json()["media_users"]
    assert rows[0]["external_user_id"] == "jf-1"
    assert rows[0]["external_username"] == "alice"
    assert rows[0]["trakt"]["connected"] is True
    db.get_trakt_account_link.assert_called_once_with(1)


def test_device_token_creates_identity_link_tokens_and_source():
    app, _ = make_app()
    db = MagicMock()
    db.upsert_media_user_identity.return_value = {"id": 1}
    db.upsert_trakt_account_link.return_value = 5
    p1, p2, p3, p4 = _patches(db)
    with p1, p2, p3, p4:
        resp = app.test_client().post(
            "/api/trakt/media-users/jellyfin/jf-1/device/token",
            json={"device_code": "dev-1"},
        )
    assert resp.status_code == 200
    # Step 1: identity (the (provider, external_user_id) anchor)
    db.upsert_media_user_identity.assert_called_once_with("jellyfin", "jf-1", "alice")
    # Step 2: link keyed by the identity
    db.upsert_trakt_account_link.assert_called_once()
    assert db.upsert_trakt_account_link.call_args.kwargs["media_user_identity_id"] == 1
    assert db.upsert_trakt_account_link.call_args.kwargs["trakt_username"] == "trakt_name"
    assert db.upsert_trakt_account_link.call_args.kwargs["token_source"] == "manual_oauth"
    # Step 3: tokens
    db.upsert_trakt_oauth_tokens.assert_called_once()
    assert db.upsert_trakt_oauth_tokens.call_args.kwargs["link_id"] == 5
    assert db.upsert_trakt_oauth_tokens.call_args.kwargs["access_token"] == "access"
    # Step 4: source keyed by the identity
    db.upsert_trakt_source.assert_called_once_with(
        media_user_identity_id=1, source_type="watched_history",
        source_key="watched_history", enabled=True, use_as_seed=True, use_as_exclusion=True,
    )


def test_device_token_pending_returns_202():
    app, _ = make_app()
    db = MagicMock()
    p1, p2, p3, p4 = _patches(db)
    with p1, p2, p3, p4:
        resp = app.test_client().post(
            "/api/trakt/media-users/jellyfin/jf-1/device/token",
            json={"device_code": "pending"},
        )
    assert resp.status_code == 202
    db.upsert_media_user_identity.assert_not_called()


def test_unknown_media_user_returns_404():
    app, _ = make_app()
    db = MagicMock()
    p1, p2, p3, p4 = _patches(db)
    with p1, p2, p3, p4:
        resp = app.test_client().post(
            "/api/trakt/media-users/jellyfin/ghost/device/code", json={}
        )
    assert resp.status_code == 404


def test_wrong_provider_returns_404():
    app, _ = make_app()
    db = MagicMock()
    p1, p2, p3, p4 = _patches(db)
    with p1, p2, p3, p4:
        resp = app.test_client().delete("/api/trakt/media-users/plex/jf-1")
    assert resp.status_code == 404


def test_delete_unlinks_trakt_account():
    app, _ = make_app()
    db = MagicMock()
    db.get_media_user_identity.return_value = {"id": 1}
    p1, p2, p3, p4 = _patches(db)
    with p1, p2, p3, p4:
        resp = app.test_client().delete("/api/trakt/media-users/jellyfin/jf-1")
    assert resp.status_code == 200
    db.unlink_trakt_account.assert_called_once_with(1)


def test_recent_preview_returns_normalized_items():
    app, _ = make_app()
    db = MagicMock()
    db.get_media_user_identity.return_value = {"id": 1}
    db.get_trakt_account_link.return_value = {
        "id": 5,
        "media_user_identity_id": 1,
        "connected": True,
        "trakt_username": "alice_t",
        "token_source": "manual_oauth",
    }
    db.get_trakt_oauth_tokens.return_value = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_at": 12345,
    }
    p1, p2, p3, p4 = _patches(db)
    with p1, p2, p3, p4:
        resp = app.test_client().get("/api/trakt/media-users/jellyfin/jf-1/recent?limit=5")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "success"
    assert payload["trakt_username"] == "alice_t"
    assert payload["items"][0]["title"] == "Recent Movie"
    assert payload["items"][0]["tmdb_id"] == "123"


def test_recent_preview_requires_linked_account():
    app, _ = make_app()
    db = MagicMock()
    db.get_media_user_identity.return_value = {"id": 1}
    db.get_trakt_account_link.return_value = None
    p1, p2, p3, p4 = _patches(db)
    with p1, p2, p3, p4:
        resp = app.test_client().get("/api/trakt/media-users/jellyfin/jf-1/recent")
    assert resp.status_code == 404
    assert resp.get_json()["message"] == "Trakt account not linked"
