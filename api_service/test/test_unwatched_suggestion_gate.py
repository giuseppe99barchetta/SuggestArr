from unittest.mock import AsyncMock, MagicMock
import sqlite3

import pytest

from api_service.jobs.unwatched_suggestion_gate import UnwatchedSuggestionGate


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
