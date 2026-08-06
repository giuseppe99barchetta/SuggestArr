import logging
from unittest.mock import AsyncMock, MagicMock
import sqlite3

import pytest

from api_service.jobs.unwatched_suggestion_gate import UnwatchedSuggestionGate
from api_service.services.simkl.media_user_augmentor import SimklAugmentation
from api_service.services.simkl.simkl_client import SimklAuthError


class _Db:
    db_type = "sqlite"

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript("""
            CREATE TABLE requests (tmdb_request_id TEXT, media_type TEXT, requested_by TEXT, user_id TEXT, requested_at TIMESTAMP);
            CREATE TABLE unwatched_suggestion_cycles (job_id INTEGER, user_id TEXT, media_type TEXT, reset_at TIMESTAMP, PRIMARY KEY(job_id,user_id,media_type));
        """)

    def get_connection(self):
        return self.conn


@pytest.mark.asyncio
async def test_gate_returns_only_allowed_user_type_slices():
    gate = UnwatchedSuggestionGate.__new__(UnwatchedSuggestionGate)
    gate._watched_ids = AsyncMock(return_value={
        "u1": {"movie": set(), "tv": set()},
        "u2": {"movie": set(), "tv": set()},
    })
    gate._is_allowed = MagicMock(side_effect=lambda _job, user, media_type, _watched: (user, media_type) in {
        ("u1", "movie"), ("u2", "tv")
    })

    slices = await gate.allowed_slices({
        "id": 1,
        "job_type": "recommendation",
        "media_type": "both",
        "user_ids": ["u1", "u2"],
        "prevent_suggestions_if_unwatched": True,
    })

    assert slices == [
        {"media_type": "movie", "user_ids": ["u1"]},
        {"media_type": "tv", "user_ids": ["u2"]},
    ]


@pytest.mark.asyncio
async def test_disabled_gate_leaves_job_unchanged():
    gate = UnwatchedSuggestionGate.__new__(UnwatchedSuggestionGate)
    assert await gate.allowed_slices({"job_type": "recommendation"}) is None


def test_old_unwatched_request_blocks_and_watched_request_resets_cycle():
    gate = UnwatchedSuggestionGate.__new__(UnwatchedSuggestionGate)
    gate.db = _Db()
    gate.db.conn.execute(
        "INSERT INTO requests VALUES ('42','movie','SuggestArr','u1',datetime('now','-8 days'))"
    )
    job = {"id": 1, "unwatched_suggestion_days": 7}

    assert gate._is_allowed(job, "u1", "movie", set()) is False
    assert gate._is_allowed(job, "u1", "movie", {"42"}) is True
    assert gate._is_allowed(job, "u1", "movie", set()) is True


# ---- Simkl exclusions --------------------------------------------------------
#
# The Trakt source swallows its own provider errors; the Simkl one does not.
# Anything that escapes here unwinds past every remaining user and trips the
# fail-open handler in allowed_slices, which switches the gate off for the
# whole job — so one user's dead token would stop suppressing already watched
# suggestions for everybody.

def _gate():
    gate = UnwatchedSuggestionGate.__new__(UnwatchedSuggestionGate)
    gate.logger = logging.getLogger("test-gate")
    return gate


@pytest.mark.asyncio
async def test_simkl_exclusions_are_merged_when_the_link_works():
    source = MagicMock(enabled=True)
    source.load = AsyncMock(return_value=SimklAugmentation(
        seed_items=[], watched_ids={"movie": {"1"}, "tv": {"2"}},
    ))

    assert await _gate()._simkl_watched_ids(source, 5) == {"movie": {"1"}, "tv": {"2"}}


@pytest.mark.asyncio
async def test_a_rejected_simkl_token_does_not_disable_the_gate():
    source = MagicMock(enabled=True)
    source.load = AsyncMock(side_effect=SimklAuthError("401"))

    assert await _gate()._simkl_watched_ids(source, 5) == {"movie": set(), "tv": set()}


@pytest.mark.asyncio
async def test_an_unconfigured_simkl_is_not_consulted():
    source = MagicMock(enabled=False)
    source.load = AsyncMock()

    assert await _gate()._simkl_watched_ids(source, 5) == {"movie": set(), "tv": set()}
    source.load.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_user_with_no_simkl_link_contributes_nothing():
    source = MagicMock(enabled=True)
    source.load = AsyncMock(return_value=None)

    assert await _gate()._simkl_watched_ids(source, 5) == {"movie": set(), "tv": set()}


@pytest.mark.asyncio
async def test_one_broken_link_leaves_the_other_users_exclusions_intact():
    """The failure has to stay inside the loop, not unwind past it."""
    source = MagicMock(enabled=True)
    source.load = AsyncMock(side_effect=[
        SimklAuthError("401"),
        SimklAugmentation(seed_items=[], watched_ids={"movie": {"9"}, "tv": set()}),
    ])
    gate = _gate()

    first = await gate._simkl_watched_ids(source, 1)
    second = await gate._simkl_watched_ids(source, 2)

    assert first == {"movie": set(), "tv": set()}
    assert second["movie"] == {"9"}
