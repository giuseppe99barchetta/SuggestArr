"""Test the flat Trakt data layer tables and DatabaseManager methods.

Tables tested: media_user_identities, trakt_account_links, trakt_oauth_tokens,
trakt_sources. Trakt links and sources are keyed directly by the media-user
identity (provider, external_user_id) — there is no separate profile layer.
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from api_service.db.database_manager import DatabaseManager


@pytest.fixture
def db():
    import api_service.db.database_manager as dm_mod

    dm_mod.DatabaseManager._instance = None
    fd, db_file = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    path_patch = patch.object(dm_mod, "DB_PATH", db_file)
    env_patch = patch(
        "api_service.db.database_manager.load_env_vars",
        return_value={"DB_TYPE": "sqlite"},
    )
    path_patch.start()
    env_patch.start()

    manager = DatabaseManager()
    try:
        yield manager
    finally:
        dm_mod.DatabaseManager._instance = None
        path_patch.stop()
        env_patch.stop()
        try:
            os.unlink(db_file)
        except FileNotFoundError:
            pass


def _identity_id(db, provider="jellyfin", external_user_id="jf-1", username="alice"):
    return db.upsert_media_user_identity(provider, external_user_id, username)["id"]


# ---- Table existence ----------------------------------------------------------

NEW_TABLES = [
    "media_user_identities",
    "trakt_account_links",
    "trakt_oauth_tokens",
    "trakt_sources",
]


@pytest.mark.parametrize("table", NEW_TABLES)
def test_new_tables_exist(db, table):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        assert cursor.fetchone() is not None, f"Table {table} missing"


def test_removed_tables_do_not_exist(db):
    """The over-built profile layer must be gone."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        for table in ("recommendation_profiles", "profile_media_user_identities"):
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            assert cursor.fetchone() is None, f"Table {table} should be removed"


# ---- media_user_identities ----------------------------------------------------

def test_upsert_media_user_identity_is_idempotent(db):
    first = db.upsert_media_user_identity("jellyfin", "jf-1", "alice")
    second = db.upsert_media_user_identity("jellyfin", "jf-1", "alice_updated")
    assert first["id"] == second["id"]
    assert first["provider"] == "jellyfin"
    assert first["external_user_id"] == "jf-1"
    # Username should be updated on re-upsert
    updated = db.get_media_user_identity("jellyfin", "jf-1")
    assert updated["external_username"] == "alice_updated"


def test_upsert_media_user_identity_returns_valid_dict(db):
    result = db.upsert_media_user_identity("jellyfin", "jf-1", "alice")
    assert "id" in result
    assert result["provider"] == "jellyfin"
    assert result["external_user_id"] == "jf-1"
    assert result["external_username"] == "alice"


def test_get_media_user_identity_returns_correct_row(db):
    db.upsert_media_user_identity("jellyfin", "jf-1", "alice")
    identity = db.get_media_user_identity("jellyfin", "jf-1")
    assert identity["provider"] == "jellyfin"
    assert identity["external_user_id"] == "jf-1"


def test_same_user_id_different_provider_creates_separate_identities(db):
    a = db.upsert_media_user_identity("jellyfin", "u1", "alice")
    b = db.upsert_media_user_identity("plex", "u1", "alice")
    assert a["id"] != b["id"]
    jf = db.get_media_user_identity("jellyfin", "u1")
    px = db.get_media_user_identity("plex", "u1")
    assert jf["provider"] == "jellyfin"
    assert px["provider"] == "plex"


def test_get_media_user_identity_by_id(db):
    created = db.upsert_media_user_identity("jellyfin", "jf-1", "alice")
    found = db.get_media_user_identity_by_id(created["id"])
    assert found is not None
    assert found["id"] == created["id"]


def test_get_media_user_identity_by_id_unknown_returns_none(db):
    assert db.get_media_user_identity_by_id(999999) is None


# ---- trakt_account_links ------------------------------------------------------

def test_upsert_trakt_account_link_is_idempotent(db):
    identity_id = _identity_id(db)

    first = db.upsert_trakt_account_link(
        media_user_identity_id=identity_id,
        trakt_user_id="t-1",
        trakt_username="trakt_alice",
        token_source="manual_oauth",
        status="connected",
    )
    second = db.upsert_trakt_account_link(
        media_user_identity_id=identity_id,
        trakt_user_id="t-2",
        trakt_username="trakt_alice_updated",
        token_source="manual_oauth",
        status="connected",
    )
    # Re-link must return the same (real) link id, not 0 — the returned id is
    # used as a foreign key for the token upsert that follows.
    assert first == second
    assert second > 0
    link = db.get_trakt_account_link(identity_id)
    assert link["id"] == second
    assert link["media_user_identity_id"] == identity_id
    assert link["trakt_username"] == "trakt_alice_updated"
    assert link["trakt_user_id"] == "t-2"


def test_get_trakt_account_link_unknown_returns_none(db):
    assert db.get_trakt_account_link(999999) is None


def test_get_trakt_account_link_by_id(db):
    identity_id = _identity_id(db)
    link_id = db.upsert_trakt_account_link(media_user_identity_id=identity_id, trakt_user_id="t1", trakt_username="u1")
    found = db.get_trakt_account_link_by_id(link_id)
    assert found is not None
    assert found["media_user_identity_id"] == identity_id


def test_get_trakt_account_link_by_id_unknown_returns_none(db):
    assert db.get_trakt_account_link_by_id(999999) is None


def test_mark_trakt_account_link_error_for_unknown_identity_returns_false(db):
    assert db.mark_trakt_account_link_error(999999, "error", "boom") is False


def test_mark_trakt_account_link_error_sets_status_and_message(db):
    identity_id = _identity_id(db)
    db.upsert_trakt_account_link(media_user_identity_id=identity_id, trakt_user_id="t1", trakt_username="u1", status="connected")
    assert db.mark_trakt_account_link_error(identity_id, "error", "boom") is True
    link = db.get_trakt_account_link(identity_id)
    assert link["connected"] is False
    assert link["status"] == "error"
    assert link["last_error"] == "boom"


def test_get_all_trakt_account_link_statuses(db):
    identity_id = _identity_id(db)
    db.upsert_trakt_account_link(
        media_user_identity_id=identity_id, trakt_user_id="t1",
        trakt_username="alice_t", status="connected",
    )

    rows = db.get_all_trakt_account_link_statuses()
    assert len(rows) == 1
    assert rows[0]["trakt_username"] == "alice_t"
    assert rows[0]["media_user_identity_id"] == identity_id
    assert rows[0]["connected"] is True


def test_unlink_trakt_account(db):
    identity_id = _identity_id(db)
    db.upsert_trakt_account_link(media_user_identity_id=identity_id, trakt_user_id="t1", trakt_username="u1")
    assert db.unlink_trakt_account(identity_id) is True
    assert db.get_trakt_account_link(identity_id) is None
    assert db.unlink_trakt_account(identity_id) is False


def test_unlink_trakt_account_removes_oauth_tokens(db):
    """Unlinking must clean up dependent OAuth tokens explicitly (not relying on FK cascade)."""
    identity_id = _identity_id(db)
    link_id = db.upsert_trakt_account_link(media_user_identity_id=identity_id, trakt_user_id="t1", trakt_username="u1")
    db.upsert_trakt_oauth_tokens(link_id, "access", "refresh", datetime.now(timezone.utc) + timedelta(hours=2))

    assert db.get_trakt_oauth_tokens(link_id) is not None
    assert db.unlink_trakt_account(identity_id) is True
    assert db.get_trakt_oauth_tokens(link_id) is None


# ---- trakt_oauth_tokens -------------------------------------------------------

def test_trakt_oauth_tokens_upsert_and_get(db):
    identity_id = _identity_id(db)
    link_id = db.upsert_trakt_account_link(media_user_identity_id=identity_id, trakt_user_id="t1", trakt_username="u1")

    expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    db.upsert_trakt_oauth_tokens(link_id, "access", "refresh", expires_at)
    tokens = db.get_trakt_oauth_tokens(link_id)
    assert tokens["access_token"] == "access"
    assert tokens["refresh_token"] == "refresh"


def test_trakt_oauth_tokens_upsert_is_idempotent(db):
    identity_id = _identity_id(db)
    link_id = db.upsert_trakt_account_link(media_user_identity_id=identity_id, trakt_user_id="t1", trakt_username="u1")

    db.upsert_trakt_oauth_tokens(link_id, "a1", "r1", None)
    db.upsert_trakt_oauth_tokens(link_id, "a2", "r2", None)
    tokens = db.get_trakt_oauth_tokens(link_id)
    assert tokens["access_token"] == "a2"
    assert tokens["refresh_token"] == "r2"


def test_update_trakt_oauth_tokens_persists_new_values(db):
    identity_id = _identity_id(db)
    link_id = db.upsert_trakt_account_link(media_user_identity_id=identity_id, trakt_user_id="t1", trakt_username="u1")
    db.upsert_trakt_oauth_tokens(link_id, "old", "old-r", None)

    assert db.update_trakt_oauth_tokens(link_id, "new", "new-r", 123456) is True
    tokens = db.get_trakt_oauth_tokens(link_id)
    assert tokens["access_token"] == "new"
    assert tokens["refresh_token"] == "new-r"
    assert tokens["expires_at"] == 123456


def test_update_trakt_oauth_tokens_for_missing_link_returns_false(db):
    assert db.update_trakt_oauth_tokens(999999, "a", "b", None) is False


def test_delete_trakt_oauth_tokens(db):
    identity_id = _identity_id(db)
    link_id = db.upsert_trakt_account_link(media_user_identity_id=identity_id, trakt_user_id="t1", trakt_username="u1")
    db.upsert_trakt_oauth_tokens(link_id, "a", "r", None)
    assert db.delete_trakt_oauth_tokens(link_id) is True
    assert db.get_trakt_oauth_tokens(link_id) is None
    assert db.delete_trakt_oauth_tokens(link_id) is False


# ---- trakt_sources ------------------------------------------------------------

def test_upsert_trakt_source_respects_unique_constraint(db):
    identity_id = _identity_id(db)
    db.upsert_trakt_source(
        media_user_identity_id=identity_id, source_type="watched_history",
        source_key="watched_history", enabled=True,
    )
    db.upsert_trakt_source(
        media_user_identity_id=identity_id, source_type="watched_history",
        source_key="watched_history", enabled=False,
    )
    sources = db.get_trakt_sources(identity_id)
    assert len(sources) == 1
    assert sources[0]["enabled"] is False


def test_get_enabled_trakt_sources(db):
    identity_id = _identity_id(db)
    db.upsert_trakt_source(
        media_user_identity_id=identity_id, source_type="watched_history",
        source_key="wh", enabled=True,
    )
    db.upsert_trakt_source(
        media_user_identity_id=identity_id, source_type="watchlist",
        source_key="wl", enabled=False,
    )
    enabled = db.get_enabled_trakt_sources(identity_id)
    assert len(enabled) == 1
    assert enabled[0]["source_type"] == "watched_history"
