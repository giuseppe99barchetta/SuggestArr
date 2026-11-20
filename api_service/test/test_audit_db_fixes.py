"""Regression tests on a real SQLite database for the history, delete-cascade and queue-cutoff fixes."""
import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from api_service.db import database_manager as dm_mod
from api_service.db.database_manager import DatabaseManager
from api_service.db.job_repository import JobRepository


@pytest.fixture
def db(tmp_path):
    """A fresh SQLite DatabaseManager on a temp file, with the real schema."""
    db_file = str(tmp_path / "audit.db")
    with (
        patch.object(dm_mod, "DB_PATH", db_file),
        patch("api_service.db.database_manager.load_env_vars", return_value={"DB_TYPE": "sqlite"}),
    ):
        DatabaseManager._instance = None
        manager = DatabaseManager()
        yield manager
    DatabaseManager._instance = None


def _execute(db, query, params=()):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.lastrowid


def _count(db, query, params=()):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()[0]


def _job(db, owner_id, name):
    return _execute(
        db,
        "INSERT INTO discover_jobs (name, media_type, filters, schedule_type, schedule_value, owner_id) "
        "VALUES (?, 'movie', '{}', 'preset', 'daily', ?)",
        (name, owner_id),
    )


def _run(db, job_id, started_at):
    _execute(db, "INSERT INTO job_execution_history (job_id, started_at, status) VALUES (?, ?, 'completed')",
             (job_id, started_at))


def test_owner_history_is_filtered_before_the_limit(db):
    """A user's older runs are returned even when other people's newer runs fill the limit."""
    mine = _job(db, 2, "Mine")
    theirs = _job(db, 1, "Admin job")
    _run(db, mine, "2026-01-01T10:00:00")
    for minute in range(5):
        _run(db, theirs, f"2026-02-01T10:0{minute}:00")

    with patch("api_service.db.job_repository.DatabaseManager", return_value=db):
        repository = JobRepository()
        owned = repository.get_recent_history(3, owner_id=2)
        everything = repository.get_recent_history(3)

    assert [row["job_id"] for row in owned] == [mine]
    assert len(everything) == 3 and all(row["job_id"] == theirs for row in everything)


def _pending(db, tmdb_id, status, created_sql, job_id=None, user_id=None):
    _execute(
        db,
        "INSERT INTO pending_requests (tmdb_id, media_type, user_id, payload, status, job_id, created_at) "
        f"VALUES (?, 'movie', ?, '{{}}', ?, ?, {created_sql})",
        (tmdb_id, user_id, status, job_id),
    )


def test_expire_pending_approvals_uses_the_database_clock(db):
    _pending(db, "1", "awaiting_approval", "datetime('now', '-2 days')")
    _pending(db, "2", "awaiting_approval", "CURRENT_TIMESTAMP")

    assert db.expire_pending_approvals(1) == 1
    assert _count(db, "SELECT COUNT(*) FROM pending_requests WHERE status='rejected' AND tmdb_id='1'") == 1
    assert _count(db, "SELECT COUNT(*) FROM pending_requests WHERE status='awaiting_approval'") == 1


def test_per_user_request_window_counts_recent_rows_only(db):
    job_id = _job(db, 1, "Limited")
    _execute(db, "UPDATE discover_jobs SET max_requests_per_user=1, request_limit_window_hours=1 WHERE id=?", (job_id,))
    _pending(db, "10", "queued", "datetime('now', '-3 hours')", job_id=job_id, user_id="u1")

    assert db._automated_submission_skip_reason(job_id, 1, "11", "movie", "u1") is None

    _pending(db, "12", "queued", "CURRENT_TIMESTAMP", job_id=job_id, user_id="u1")
    assert "job limit" in db._automated_submission_skip_reason(job_id, 1, "13", "movie", "u1")


def test_deleting_a_user_cascades_on_sqlite(db):
    """SQLite applies ON DELETE CASCADE only with foreign keys on; the user's rows must go."""
    keep = db.create_auth_user("keeper", "x", role="admin")
    gone = db.create_auth_user("leaver", "x", role="user")
    for user_id in (keep, gone):
        db.store_refresh_token(user_id, f"hash-{user_id}", datetime(2099, 1, 1, tzinfo=timezone.utc))
        _execute(db, "INSERT INTO api_keys (user_id, name, key_id, secret_hash, prefix) VALUES (?, 'k', ?, ?, 'p')",
                 (user_id, f"kid{user_id}", f"secret{user_id}"))
        _execute(db, "INSERT INTO suggestion_feedback (user_id, media_user_id, tmdb_id, media_type, feedback) "
                     "VALUES (?, '', '1', 'movie', 'not_interested')", (user_id,))
        _execute(db, "INSERT INTO ai_search_history (user_id, query) VALUES (?, 'heist films')", (user_id,))

    assert db.delete_auth_user(gone) is True

    for table in ("refresh_tokens", "api_keys", "suggestion_feedback", "ai_search_history"):
        assert _count(db, f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (gone,)) == 0, table
        assert _count(db, f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (keep,)) == 1, table


def test_deleting_a_job_removes_its_history_on_sqlite(db):
    doomed = _job(db, 1, "Doomed")
    kept = _job(db, 1, "Kept")
    _run(db, doomed, "2026-01-01T10:00:00")
    _run(db, kept, "2026-01-01T10:00:00")

    with patch("api_service.db.job_repository.DatabaseManager", return_value=db):
        assert JobRepository().delete_job(doomed) is True

    assert _count(db, "SELECT COUNT(*) FROM job_execution_history WHERE job_id = ?", (doomed,)) == 0
    assert _count(db, "SELECT COUNT(*) FROM job_execution_history WHERE job_id = ?", (kept,)) == 1


def test_cascading_delete_refuses_instead_of_orphaning_children(db):
    """A child table without an ON DELETE rule makes the delete fail as a whole: nothing is half-deleted."""
    user_id = db.create_auth_user("legacy", "x", role="user")
    db.store_refresh_token(user_id, "hash-legacy", datetime(2099, 1, 1, tzinfo=timezone.utc))
    _execute(db, "CREATE TABLE legacy_child (user_id INTEGER REFERENCES auth_users(id))")
    _execute(db, "INSERT INTO legacy_child (user_id) VALUES (?)", (user_id,))

    with pytest.raises(sqlite3.IntegrityError):
        db.delete_auth_user(user_id)

    assert db.get_auth_user_by_id(user_id) is not None
    assert _count(db, "SELECT COUNT(*) FROM refresh_tokens WHERE user_id = ?", (user_id,)) == 1
