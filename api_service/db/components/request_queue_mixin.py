import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

class RequestQueueMixin:
    def try_acquire_submission_lock(self, tmdb_id: str, media_type: str, ttl_seconds: int = 60) -> bool:
        """Attempt to acquire a per-media submission lock to prevent cross-process duplicates.

        Uses DB-native INSERT-ignore semantics (atomic check+acquire). Cleans stale locks
        (from crashes) before attempting acquisition. Fails open on DB errors so a broken
        lock table never blocks all submissions.

        :param tmdb_id: TMDB ID as string.
        :param media_type: 'movie' or 'tv'.
        :param ttl_seconds: Locks older than this are considered stale and deleted first.
        :return: True if lock acquired (caller should proceed), False if already held.
        """
        # Build stale-lock cleanup query (DB-specific timestamp arithmetic)
        if self.db_type == 'sqlite':
            cleanup_query = (
                "DELETE FROM submission_locks WHERE tmdb_id = ? AND media_type = ? "
                "AND locked_at < datetime('now', '-' || ? || ' seconds')"
            )
            cleanup_params = (str(tmdb_id), media_type, str(ttl_seconds))
        elif self.db_type == 'postgres':
            cleanup_query = (
                "DELETE FROM submission_locks WHERE tmdb_id = %s AND media_type = %s "
                "AND locked_at < NOW() - (INTERVAL '1 second' * %s)"
            )
            cleanup_params = (str(tmdb_id), media_type, ttl_seconds)
        else:  # mysql / mariadb
            cleanup_query = (
                "DELETE FROM submission_locks WHERE tmdb_id = %s AND media_type = %s "
                "AND locked_at < DATE_SUB(NOW(), INTERVAL %s SECOND)"
            )
            cleanup_params = (str(tmdb_id), media_type, ttl_seconds)

        # Build atomic lock-acquisition INSERT (INSERT OR IGNORE / INSERT IGNORE / ON CONFLICT DO NOTHING)
        insert_query = "INSERT OR IGNORE INTO submission_locks (tmdb_id, media_type) VALUES (?, ?)"
        insert_params = (str(tmdb_id), media_type)

        if self.db_type in ['mysql', 'mariadb']:
            insert_query = insert_query.replace("INSERT OR IGNORE", "INSERT IGNORE")
            insert_query = insert_query.replace("?", "%s")
        elif self.db_type == 'postgres':
            insert_query = insert_query.replace("INSERT OR IGNORE", "INSERT")
            insert_query = insert_query.rstrip() + " ON CONFLICT DO NOTHING"
            insert_query = insert_query.replace("?", "%s")

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(cleanup_query, cleanup_params)
                cursor.execute(insert_query, insert_params)
                acquired = cursor.rowcount > 0  # Read BEFORE commit
                conn.commit()
                self.logger.debug(
                    "Submission lock %s: tmdb_id=%s, media_type=%s",
                    "acquired" if acquired else "already held",
                    tmdb_id, media_type
                )
                return acquired
        except Exception as e:
            self.logger.error(
                "Error acquiring submission lock for tmdb_id=%s, media_type=%s: %s",
                tmdb_id, media_type, e
            )
            return True  # Fail open: don't block submissions if lock table has issues

    def release_submission_lock(self, tmdb_id: str, media_type: str) -> None:
        """Release a previously acquired submission lock.

        Should always be called in a finally block so the lock is never left dangling.
        Stale locks (from crashes) are cleaned automatically on the next acquire attempt.

        :param tmdb_id: TMDB ID as string.
        :param media_type: 'movie' or 'tv'.
        """
        query = "DELETE FROM submission_locks WHERE tmdb_id = ? AND media_type = ?"
        params = (str(tmdb_id), media_type)

        if self.db_type in ['mysql', 'mariadb', 'postgres']:
            query = query.replace("?", "%s")

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                self.logger.debug(
                    "Released submission lock: tmdb_id=%s, media_type=%s", tmdb_id, media_type
                )
        except Exception as e:
            self.logger.error(
                "Error releasing submission lock for tmdb_id=%s, media_type=%s: %s",
                tmdb_id, media_type, e
            )

    def enqueue_request(self, tmdb_id: str, media_type: str, user_id: Optional[str],
                        payload: dict, status: str = 'queued', job_id=None, owner_id=None) -> bool:
        """Enqueue a Seer submission for background delivery.

        Idempotent: silently no-ops when an entry for (tmdb_id, media_type) already
        exists in any status.  Items that were already successfully submitted (present
        in the ``requests`` table) are also skipped.

        :param tmdb_id: TMDB media ID.
        :param media_type: 'movie' or 'tv'.
        :param user_id: Seer user ID to attribute the request to (may be None).
        :param payload: Complete Seer request body plus private meta-keys prefixed
            with ``_`` (``_source_id``, ``_rationale``, ``_is_anime``).
        :return: True if a new row was inserted, False if already present or already
            submitted.
        """
        if self.check_request_exists(media_type, tmdb_id):
            self.logger.debug("enqueue_request: %s %s already submitted, skipping.", media_type, tmdb_id)
            return False

        if self.is_suggestion_blacklisted(tmdb_id, media_type):
            return False
        query = """
            INSERT OR IGNORE INTO pending_requests
                (tmdb_id, media_type, user_id, payload, status, job_id, owner_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (str(tmdb_id), media_type, user_id, json.dumps(payload), status, job_id, owner_id)

        if self.db_type in ['mysql', 'mariadb']:
            query = query.replace("INSERT OR IGNORE", "INSERT IGNORE").replace("?", "%s")
        elif self.db_type == 'postgres':
            query = (query.replace("INSERT OR IGNORE", "INSERT").replace("?", "%s").rstrip()
                     + " ON CONFLICT (tmdb_id, media_type) DO NOTHING")

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                inserted = cursor.rowcount > 0
                conn.commit()
                if inserted:
                    self.logger.debug("Enqueued %s tmdb:%s for Seer delivery.", media_type, tmdb_id)
                else:
                    self.logger.info(
                        "enqueue_request: %s tmdb:%s already exists in pending queue, skipping.",
                        media_type,
                        tmdb_id,
                    )
                return inserted
        except Exception as e:
            self.logger.error("Failed to enqueue %s tmdb:%s: %s", media_type, tmdb_id, e)
            return False

    def is_suggestion_blacklisted(self, tmdb_id: str, media_type: str) -> bool:
        ph = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT 1 FROM suggestion_blacklist WHERE tmdb_id={ph} AND media_type={ph}",
                           (str(tmdb_id), media_type))
            return cursor.fetchone() is not None

    def list_suggestions(self, owner_id=None):
        ph = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'
        query = """SELECT p.id,p.tmdb_id,p.media_type,p.status,p.created_at,p.job_id,p.owner_id,
                          m.title,m.poster_path,m.overview,j.name
                   FROM pending_requests p
                   LEFT JOIN metadata m ON m.media_id=p.tmdb_id AND m.media_type=p.media_type
                   LEFT JOIN discover_jobs j ON j.id=p.job_id
                   WHERE p.status='awaiting_approval'"""
        params = ()
        if owner_id is not None:
            query += f" AND p.owner_id={ph}"
            params = (owner_id,)
        query += " ORDER BY p.created_at DESC"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def decide_suggestions(self, ids, owner_id, decided_by, approve):
        if not ids:
            return 0
        ph = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'
        marks = ','.join([ph] * len(ids))
        owner_clause = '' if owner_id is None else f' AND owner_id={ph}'
        params = [('queued' if approve else 'rejected'), decided_by, *ids]
        if owner_id is not None:
            params.append(owner_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE pending_requests SET status={ph},decided_by={ph},decided_at=CURRENT_TIMESTAMP "
                           f"WHERE status='awaiting_approval' AND id IN ({marks}){owner_clause}", tuple(params))
            changed = cursor.rowcount
            if not approve:
                insert = "INSERT OR IGNORE" if self.db_type == 'sqlite' else "INSERT IGNORE"
                if self.db_type == 'postgres':
                    insert = "INSERT"
                cursor.execute(f"SELECT tmdb_id,media_type FROM pending_requests WHERE status='rejected' "
                               f"AND decided_by={ph} AND id IN ({marks})", (decided_by, *ids))
                for tmdb_id, media_type in cursor.fetchall():
                    sql = f"{insert} INTO suggestion_blacklist(tmdb_id,media_type,created_by) VALUES ({ph},{ph},{ph})"
                    if self.db_type == 'postgres':
                        sql += " ON CONFLICT DO NOTHING"
                    cursor.execute(sql, (tmdb_id, media_type, decided_by))
            conn.commit()
            return changed

    def list_blacklist(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tmdb_id,media_type,created_by,created_at FROM suggestion_blacklist ORDER BY created_at DESC")
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def remove_blacklist(self, tmdb_id, media_type):
        ph = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM suggestion_blacklist WHERE tmdb_id={ph} AND media_type={ph}",
                           (str(tmdb_id), media_type))
            conn.commit()
            return cursor.rowcount > 0

    def get_due_requests(self, max_items: int = 50) -> List[Dict[str, Any]]:
        """Return up to *max_items* queued rows whose next_attempt_at is due.

        :param max_items: Maximum number of rows to return.
        :return: List of row dicts ordered by created_at ASC.
        """
        now = self._utc_naive(datetime.now(timezone.utc))
        placeholder = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'

        query = f"""
            SELECT id, tmdb_id, media_type, user_id, payload, retry_count
            FROM pending_requests
            WHERE status = 'queued'
              AND (next_attempt_at IS NULL OR next_attempt_at <= {placeholder})
            ORDER BY created_at ASC
            LIMIT {placeholder}
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (now, max_items))
                cols = [d[0] for d in cursor.description]
                return [dict(zip(cols, row)) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error("Failed to fetch due pending_requests: %s", e)
            return []

    def _update_pending_status(self, row_id: int, status: str, retry_count: int,
                               last_attempt_at: Optional[datetime] = None,
                               next_attempt_at: Optional[datetime] = None) -> None:
        """Internal helper - update status / retry columns on a pending_requests row."""
        placeholder = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'
        query = (f"UPDATE pending_requests SET status={placeholder}, retry_count={placeholder}"
                 f", last_attempt_at={placeholder}, next_attempt_at={placeholder}"
                 f" WHERE id={placeholder}")
        db_last = self._utc_naive(last_attempt_at) if last_attempt_at is not None else None
        db_next = self._utc_naive(next_attempt_at) if next_attempt_at is not None else None
        params = (status, retry_count, db_last, db_next, row_id)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
        except Exception as e:
            self.logger.error("Failed to update pending_requests row %s: %s", row_id, e)

    def mark_pending_submitting(self, row_id: int, retry_count: int) -> None:
        """Mark a row as in-flight so concurrent workers skip it.

        :param row_id: Primary key of the pending_requests row.
        :param retry_count: Current retry count (unchanged at this point).
        """
        self._update_pending_status(row_id, 'submitting', retry_count,
                                    last_attempt_at=datetime.now(timezone.utc))

    def mark_pending_submitted(self, row_id: int, retry_count: int) -> None:
        """Mark a row as successfully submitted.

        :param row_id: Primary key of the pending_requests row.
        :param retry_count: Final retry count at time of success.
        """
        self._update_pending_status(row_id, 'submitted', retry_count)

    def mark_pending_failed(self, row_id: int, retry_count: int) -> None:
        """Mark a row as permanently failed (max retries exceeded).

        :param row_id: Primary key of the pending_requests row.
        :param retry_count: Final retry count.
        """
        self._update_pending_status(row_id, 'failed', retry_count,
                                    last_attempt_at=datetime.now(timezone.utc))

    def increment_pending_retry(self, row_id: int, new_retry_count: int,
                                next_attempt_at: datetime) -> None:
        """Bump retry counter and schedule next attempt with exponential backoff.

        :param row_id: Primary key of the pending_requests row.
        :param new_retry_count: Incremented retry count.
        :param next_attempt_at: UTC datetime for next eligible attempt.
        """
        self._update_pending_status(row_id, 'queued', new_retry_count,
                                    last_attempt_at=datetime.now(timezone.utc),
                                    next_attempt_at=next_attempt_at)

    def reset_stale_inflight(self, cutoff_minutes: int = 10) -> int:
        """Reset 'submitting' rows that have been stuck longer than *cutoff_minutes*.

        Called at queue worker startup to recover from crashes.

        :param cutoff_minutes: Rows locked for longer than this are re-queued.
        :return: Number of rows reset.
        """
        cutoff = self._utc_naive(datetime.now(timezone.utc) - timedelta(minutes=cutoff_minutes))
        placeholder = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'
        query = (f"UPDATE pending_requests SET status='queued'"
                 f" WHERE status='submitting' AND last_attempt_at < {placeholder}")
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (cutoff,))
                reset = cursor.rowcount
                conn.commit()
                if reset:
                    self.logger.warning("reset_stale_inflight: re-queued %d stuck row(s).", reset)
                return reset
        except Exception as e:
            self.logger.error("Failed to reset stale in-flight rows: %s", e)
            return 0

    # ---------------------------------------------------------------------------
    # Auth-user methods (SuggestArr internal accounts - NOT external service users)
    # ---------------------------------------------------------------------------

