"""Tests for the Simkl database layer against a real SQLite schema.

These run against an actual database rather than mocks because the behaviour
worth protecting here is in the SQL: upsert conflict targets, the cascade on
unlink, and the ordering the seed path depends on.
"""
from unittest.mock import patch

import pytest

import api_service.db.database_manager as dm_mod
from api_service.db.database_manager import DatabaseManager


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database per test.

    DB_PATH is a module constant read during __init__, so it has to be patched
    before the singleton is rebuilt; otherwise every test shares one file and
    rows leak across them.
    """
    db_file = str(tmp_path / "simkl.db")
    with patch.object(dm_mod, "DB_PATH", db_file), \
         patch("api_service.db.database_manager.load_env_vars", return_value={"DB_TYPE": "sqlite"}):
        DatabaseManager._instance = None
        manager = DatabaseManager()
        yield manager
        DatabaseManager._instance = None


@pytest.fixture
def link(db):
    identity = db.upsert_media_user_identity("plex", "u1", "Wire")
    link_id = db.upsert_simkl_account_link(identity["id"], "8307044", "Wire")
    return {"identity_id": identity["id"], "link_id": link_id}


def rows(**overrides):
    base = [
        {"simkl_id": "273", "simkl_type": "shows", "media_type": "tv", "status": "watching",
         "tmdb_id": "78", "title": "Dateline NBC", "year": 1992, "last_watched_at": 300},
        {"simkl_id": "561826", "simkl_type": "shows", "media_type": "tv", "status": "completed",
         "tmdb_id": "70453", "title": "Sharp Objects", "year": 2018, "last_watched_at": 200},
        {"simkl_id": "53226", "simkl_type": "movies", "media_type": "movie", "status": "completed",
         "tmdb_id": "120", "title": "LOTR", "year": 2001, "last_watched_at": 100},
    ]
    return [dict(r, **overrides) for r in base]


# ---- Links -------------------------------------------------------------------

def test_relinking_updates_in_place_and_returns_the_same_row_id(db, link):
    again = db.upsert_simkl_account_link(link["identity_id"], "8307044", "Renamed")
    assert again == link["link_id"]
    assert db.get_simkl_account_link(link["identity_id"])["simkl_username"] == "Renamed"


def test_needs_reauth_is_not_overwritten_by_a_later_generic_error(db, link):
    """It is the one status that tells the UI to prompt for a new PIN."""
    db.mark_simkl_account_link_error(link["identity_id"], "needs_reauth", "401")
    db.mark_simkl_account_link_error(link["identity_id"], "error", "transient blip")

    assert db.get_simkl_account_link(link["identity_id"])["status"] == "needs_reauth"


def test_a_relink_clears_needs_reauth(db, link):
    db.mark_simkl_account_link_error(link["identity_id"], "needs_reauth", "401")
    db.upsert_simkl_account_link(link["identity_id"], "8307044", "Wire")

    result = db.get_simkl_account_link(link["identity_id"])
    assert result["status"] == "connected"
    assert result["last_error"] is None


def test_a_generic_error_still_applies_to_a_healthy_link(db, link):
    db.mark_simkl_account_link_error(link["identity_id"], "error", "boom")
    assert db.get_simkl_account_link(link["identity_id"])["status"] == "error"


# ---- Tokens ------------------------------------------------------------------

def test_tokens_round_trip_without_a_refresh_token(db, link):
    db.upsert_simkl_oauth_tokens(link["link_id"], "tok-abc")
    assert db.get_simkl_oauth_tokens(link["link_id"]) == {
        "access_token": "tok-abc", "expires_at": None,
    }


def test_upserting_tokens_twice_replaces_rather_than_duplicates(db, link):
    db.upsert_simkl_oauth_tokens(link["link_id"], "first")
    db.upsert_simkl_oauth_tokens(link["link_id"], "second")
    assert db.get_simkl_oauth_tokens(link["link_id"])["access_token"] == "second"


# ---- Pending PIN -------------------------------------------------------------

def test_a_pending_code_can_be_stored_before_any_link_exists(db):
    """The first link has no row yet, so setting a code must create one."""
    identity = db.upsert_media_user_identity("plex", "fresh", "New")
    db.set_simkl_pending_user_code(identity["id"], "8CCE9")

    assert db.get_simkl_pending_user_code(identity["id"]) == "8CCE9"
    assert db.get_simkl_account_link(identity["id"])["status"] == "pending"


def test_completing_a_link_clears_the_pending_code(db, link):
    db.set_simkl_pending_user_code(link["identity_id"], "8CCE9")
    db.upsert_simkl_account_link(link["identity_id"], "8307044", "Wire")
    assert db.get_simkl_pending_user_code(link["identity_id"]) is None


# ---- Cache -------------------------------------------------------------------

def test_the_cache_returns_newest_watched_first(db, link):
    db.upsert_simkl_watched_cache(link["link_id"], rows())
    titles = [r["title"] for r in db.get_simkl_watched_cache(link["link_id"])]
    assert titles == ["Dateline NBC", "Sharp Objects", "LOTR"]


def test_status_filtering_separates_seeds_from_exclusions(db, link):
    db.upsert_simkl_watched_cache(link["link_id"], rows())

    seeds = db.get_simkl_watched_cache(link["link_id"], ("watching", "completed"))
    exclusions = db.get_simkl_watched_cache(link["link_id"], ("completed",))

    assert len(seeds) == 3
    assert sorted(r["title"] for r in exclusions) == ["LOTR", "Sharp Objects"]


def test_re_upserting_an_item_updates_it_without_duplicating(db, link):
    db.upsert_simkl_watched_cache(link["link_id"], rows())
    db.upsert_simkl_watched_cache(link["link_id"], [{
        "simkl_id": "273", "simkl_type": "shows", "media_type": "tv", "status": "completed",
        "tmdb_id": "78", "title": "Dateline NBC", "year": 1992, "last_watched_at": 999,
    }])

    cached = db.get_simkl_watched_cache(link["link_id"])
    assert len(cached) == 3
    assert cached[0]["status"] == "completed"
    assert cached[0]["last_watched_at"] == 999


def test_the_same_simkl_id_can_exist_under_two_types(db, link):
    """The unique key includes simkl_type, and the id spaces are separate."""
    db.upsert_simkl_watched_cache(link["link_id"], [
        {"simkl_id": "1", "simkl_type": "shows", "media_type": "tv", "status": "watching",
         "tmdb_id": "1", "title": "A show", "year": 2000, "last_watched_at": 1},
        {"simkl_id": "1", "simkl_type": "movies", "media_type": "movie", "status": "completed",
         "tmdb_id": "2", "title": "A movie", "year": 2000, "last_watched_at": 1},
    ])
    assert len(db.get_simkl_watched_cache(link["link_id"])) == 2


def test_reconcile_drops_only_the_ids_simkl_no_longer_reports(db, link):
    db.upsert_simkl_watched_cache(link["link_id"], rows())

    removed = db.reconcile_simkl_watched_cache(link["link_id"], "shows", ["273"])

    assert removed == 1
    remaining = {r["simkl_id"] for r in db.get_simkl_watched_cache(link["link_id"])}
    assert remaining == {"273", "53226"}


def test_reconcile_leaves_other_types_untouched(db, link):
    db.upsert_simkl_watched_cache(link["link_id"], rows())
    db.reconcile_simkl_watched_cache(link["link_id"], "shows", [])

    remaining = {r["simkl_type"] for r in db.get_simkl_watched_cache(link["link_id"])}
    assert remaining == {"movies"}


def test_reconcile_with_nothing_stale_is_a_no_op(db, link):
    db.upsert_simkl_watched_cache(link["link_id"], rows())
    assert db.reconcile_simkl_watched_cache(link["link_id"], "shows", ["273", "561826"]) == 0


def test_upserting_an_empty_batch_is_harmless(db, link):
    assert db.upsert_simkl_watched_cache(link["link_id"], []) == 0


# ---- Sync state --------------------------------------------------------------

def test_activities_are_stored_verbatim_including_nulls(db, link):
    """Nulls are meaningful: they mark lists the user has never used."""
    payload = {"tv_shows": {"watching": "2026-08-05T21:27:57Z", "hold": None}}
    db.update_simkl_sync_state(link["link_id"], activities=payload)

    assert db.get_simkl_sync_state(link["link_id"])["activities"] == payload


def test_sync_clocks_are_only_set_when_asked_for(db, link):
    db.update_simkl_sync_state(link["link_id"], mark_activities_check=True)
    state = db.get_simkl_sync_state(link["link_id"])

    assert state["last_activities_check_at"]
    assert state["last_full_sync_at"] is None


def test_corrupt_stored_activities_degrade_to_empty_rather_than_raising(db, link):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE simkl_account_links SET activities_json = ? WHERE id = ?",
            ("{not json", link["link_id"]),
        )
        conn.commit()

    assert db.get_simkl_sync_state(link["link_id"])["activities"] == {}


def test_sync_state_for_a_missing_link_is_empty(db):
    assert db.get_simkl_sync_state(9999) == {
        "activities": {}, "last_full_sync_at": None, "last_activities_check_at": None,
    }


# ---- Unlink ------------------------------------------------------------------

def test_unlink_removes_the_link_tokens_and_cached_history(db, link):
    db.upsert_simkl_oauth_tokens(link["link_id"], "tok")
    db.upsert_simkl_watched_cache(link["link_id"], rows())

    assert db.unlink_simkl_account(link["identity_id"]) is True
    assert db.get_simkl_account_link(link["identity_id"]) is None
    assert db.get_simkl_oauth_tokens(link["link_id"]) is None
    assert db.get_simkl_watched_cache(link["link_id"]) == []


def test_unlinking_an_unlinked_user_reports_false(db):
    identity = db.upsert_media_user_identity("plex", "nobody", "Nobody")
    assert db.unlink_simkl_account(identity["id"]) is False


# ---- Sources -----------------------------------------------------------------

def test_source_flags_round_trip_and_update_in_place(db, link):
    db.upsert_simkl_source(link["identity_id"], "watched_history", "watched_history")
    db.upsert_simkl_source(
        link["identity_id"], "watched_history", "watched_history", use_as_seed=False,
    )

    sources = db.get_simkl_sources(link["identity_id"])
    assert len(sources) == 1
    assert sources[0]["use_as_seed"] is False
    assert sources[0]["use_as_exclusion"] is True


def test_disabled_sources_are_excluded_from_the_enabled_query(db, link):
    db.upsert_simkl_source(
        link["identity_id"], "watched_history", "watched_history", enabled=False,
    )
    assert db.get_enabled_simkl_sources(link["identity_id"]) == []
