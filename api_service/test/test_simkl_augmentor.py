"""Tests for the Simkl resolver, watch-history source, and augmentor."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from api_service.services.simkl.media_user_augmentor import (
    MediaUserSimklAugmentor,
    SimklAccountResolver,
    SimklWatchHistorySource,
)
from api_service.services.simkl.simkl_client import SimklAuthError, SimklClientIdError

CACHE_ROWS = [
    {"simkl_id": "1", "simkl_type": "shows", "media_type": "tv", "status": "watching",
     "tmdb_id": "78", "title": "Dateline NBC", "year": 1992, "last_watched_at": 300},
    {"simkl_id": "2", "simkl_type": "shows", "media_type": "tv", "status": "completed",
     "tmdb_id": "70453", "title": "Sharp Objects", "year": 2018, "last_watched_at": 200},
    {"simkl_id": "3", "simkl_type": "movies", "media_type": "movie", "status": "completed",
     "tmdb_id": "120", "title": "LOTR", "year": 2001, "last_watched_at": 100},
]


def make_db(status="connected", token="tok", sources=None, rows=None):
    db = MagicMock()
    db.get_simkl_account_link.return_value = {
        "id": 5, "media_user_identity_id": 1, "status": status,
        "connected": status == "connected", "token_source": "manual_oauth",
        "simkl_username": "Wire",
    }
    db.get_simkl_oauth_tokens.return_value = {"access_token": token} if token else None
    db.get_enabled_simkl_sources.return_value = (
        sources if sources is not None
        else [{"source_type": "watched_history", "use_as_seed": True, "use_as_exclusion": True}]
    )

    rows = CACHE_ROWS if rows is None else rows

    def cache(link_id, statuses=None):
        if statuses is None:
            return rows
        return [r for r in rows if r["status"] in statuses]

    db.get_simkl_watched_cache.side_effect = cache
    return db


async def _sync_ok(self, link, token):
    return True


def patch_sync(replacement=_sync_ok):
    """Replace the network-touching sync so only cache reads are exercised."""
    return patch(
        "api_service.services.simkl.watch_history_sync.SimklWatchHistorySync.ensure_synced",
        replacement,
    )


# ---- Resolver ----------------------------------------------------------------

def test_resolver_returns_the_link_with_its_token():
    resolved = SimklAccountResolver(make_db()).resolve(1)
    assert resolved["access_token"] == "tok"
    assert resolved["id"] == 5


@pytest.mark.parametrize("status", ["revoked", "error", "needs_reauth", "pending"])
def test_resolver_skips_links_that_cannot_currently_work(status):
    """needs_reauth is skipped for the same reason as revoked: retrying burns
    quota against a token Simkl has already rejected."""
    assert SimklAccountResolver(make_db(status=status)).resolve(1) is None


def test_resolver_returns_none_without_a_token():
    assert SimklAccountResolver(make_db(token=None)).resolve(1) is None


def test_resolver_returns_none_without_a_link():
    db = MagicMock()
    db.get_simkl_account_link.return_value = None
    assert SimklAccountResolver(db).resolve(1) is None


# ---- Source ------------------------------------------------------------------

def test_source_is_enabled_by_a_client_id_alone():
    """Unlike Trakt there is no client secret; the PIN flow does not use one."""
    assert SimklWatchHistorySource("cid", db=MagicMock()).enabled is True
    assert SimklWatchHistorySource("", db=MagicMock()).enabled is False


def test_seeds_come_from_watching_and_completed_newest_first():
    source = SimklWatchHistorySource("cid", db=make_db(), max_content=10)
    with patch_sync():
        result = asyncio.run(source.load(1))

    assert [s["title"] for s in result.seed_items] == [
        "Dateline NBC", "Sharp Objects", "LOTR",
    ]
    assert result.seed_items[0]["watched_at"] == 300


def test_exclusions_come_from_completed_only():
    source = SimklWatchHistorySource("cid", db=make_db())
    with patch_sync():
        result = asyncio.run(source.load(1))

    # Dateline NBC is still being watched, so it must remain suggestible.
    assert result.watched_ids == {"movie": {"120"}, "tv": {"70453"}}


def test_seeds_are_capped_at_max_content():
    source = SimklWatchHistorySource("cid", db=make_db(), max_content=2)
    with patch_sync():
        result = asyncio.run(source.load(1))
    assert len(result.seed_items) == 2


def test_rows_without_a_tmdb_id_are_dropped_from_seeds():
    rows = [dict(CACHE_ROWS[0], tmdb_id=None), CACHE_ROWS[1]]
    source = SimklWatchHistorySource("cid", db=make_db(rows=rows))
    with patch_sync():
        result = asyncio.run(source.load(1))
    assert [s["title"] for s in result.seed_items] == ["Sharp Objects"]


def test_per_user_source_flags_switch_off_seeds():
    db = make_db(sources=[
        {"source_type": "watched_history", "use_as_seed": False, "use_as_exclusion": True},
    ])
    source = SimklWatchHistorySource("cid", db=db)
    with patch_sync():
        result = asyncio.run(source.load(1))

    assert result.seed_items == []
    assert result.watched_ids["movie"] == {"120"}


def test_job_level_overrides_take_precedence_over_the_stored_flags():
    db = make_db(sources=[
        {"source_type": "watched_history", "use_as_seed": True, "use_as_exclusion": True},
    ])
    source = SimklWatchHistorySource("cid", db=db, use_as_exclusion=False)
    with patch_sync():
        result = asyncio.run(source.load(1))

    assert result.seed_items
    assert result.watched_ids == {"movie": set(), "tv": set()}


def test_a_user_with_no_source_row_contributes_nothing():
    source = SimklWatchHistorySource("cid", db=make_db(sources=[]))
    with patch_sync():
        assert asyncio.run(source.load(1)) is None


# ---- Augmentor ---------------------------------------------------------------

def test_augment_returns_seeds_and_watched_ids():
    aug = MediaUserSimklAugmentor("cid", db=make_db())
    with patch_sync():
        result = asyncio.run(aug.augment(1))

    assert len(result.seed_items) == 3
    assert result.watched_ids["tv"] == {"70453"}


def test_augment_is_a_no_op_without_a_client_id():
    aug = MediaUserSimklAugmentor("", db=make_db())
    assert aug.enabled is False
    assert asyncio.run(aug.augment(1)) is None


def test_augment_returns_none_when_there_is_nothing_to_contribute():
    aug = MediaUserSimklAugmentor("cid", db=make_db(rows=[]))
    with patch_sync():
        assert asyncio.run(aug.augment(1)) is None


def test_an_auth_failure_marks_the_link_needs_reauth():
    """There is no refresh grant, so the UI has to prompt for a new PIN."""
    db = make_db()
    aug = MediaUserSimklAugmentor("cid", db=db)

    async def boom(self, link, token):
        raise SimklAuthError("401")

    with patch_sync(boom):
        assert asyncio.run(aug.augment(1)) is None

    db.mark_simkl_account_link_error.assert_called_once()
    assert db.mark_simkl_account_link_error.call_args[0][1] == "needs_reauth"


def test_a_client_id_failure_does_not_blame_the_users_link():
    """A 412 is install-wide; flagging the user would point at the wrong fix."""
    db = make_db()
    aug = MediaUserSimklAugmentor("cid", db=db)

    async def boom(self, link, token):
        raise SimklClientIdError("412")

    with patch_sync(boom):
        assert asyncio.run(aug.augment(1)) is None

    db.mark_simkl_account_link_error.assert_not_called()


def test_an_unexpected_failure_marks_a_generic_error():
    db = make_db()
    aug = MediaUserSimklAugmentor("cid", db=db)

    async def boom(self, link, token):
        raise RuntimeError("kaboom")

    with patch_sync(boom):
        assert asyncio.run(aug.augment(1)) is None

    assert db.mark_simkl_account_link_error.call_args[0][1] == "error"


def test_the_stored_error_does_not_echo_the_exception_text():
    """last_error is rendered verbatim on the user's Simkl card.

    This branch catches everything, including failures from layers whose
    messages carry connection strings or file paths, so the detail belongs in
    the log rather than in the browser.
    """
    db = make_db()
    aug = MediaUserSimklAugmentor("cid", db=db)

    async def boom(self, link, token):
        raise RuntimeError("postgresql://user:hunter2@db.internal:5432/suggestarr")

    with patch_sync(boom):
        asyncio.run(aug.augment(1))

    stored = db.mark_simkl_account_link_error.call_args[0][2]
    assert "hunter2" not in stored
    assert stored == "Could not read Simkl watch history"


# ---- from_env ----------------------------------------------------------------

@patch("api_service.services.simkl.media_user_augmentor.DatabaseManager")
def test_from_env_returns_none_without_a_client_id(_db):
    assert MediaUserSimklAugmentor.from_env({}) is None
    assert MediaUserSimklAugmentor.from_env({"SIMKL_CLIENT_ID": ""}) is None


@patch("api_service.services.simkl.media_user_augmentor.DatabaseManager")
def test_from_env_needs_no_client_secret(_db):
    aug = MediaUserSimklAugmentor.from_env({"SIMKL_CLIENT_ID": "cid"})
    assert aug is not None and aug.enabled is True


@patch("api_service.services.simkl.media_user_augmentor.DatabaseManager")
def test_from_env_falls_back_to_the_integrations_block(_db):
    aug = MediaUserSimklAugmentor.from_env({"integrations": {"simkl": {"client_id": "cid"}}})
    assert aug is not None and aug.enabled is True


@patch("api_service.services.simkl.media_user_augmentor.DatabaseManager")
def test_from_env_passes_the_tmdb_key_through_for_the_tvdb_fallback(_db):
    aug = MediaUserSimklAugmentor.from_env({"SIMKL_CLIENT_ID": "cid", "TMDB_API_KEY": "tk"})
    assert aug.source.sync.tmdb_api_key == "tk"
