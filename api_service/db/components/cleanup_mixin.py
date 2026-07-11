import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

class CleanupMixin:
    def get_cleanup_settings(self) -> dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, enabled, dry_run, grace_days, last_run_at, last_run_status, last_run_summary FROM cleanup_settings WHERE id = 1")
            row = cursor.fetchone()
            if not row:
                placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
                cursor.execute(
                    f"INSERT INTO cleanup_settings (id, enabled, dry_run, grace_days) VALUES (1, {placeholder}, {placeholder}, {placeholder})",
                    (0, 1, 7),
                )
                conn.commit()
                return {'enabled': False, 'dry_run': True, 'grace_days': 7,
                        'last_run_at': None, 'last_run_status': None, 'last_run_summary': None}
            return {
                'enabled': bool(row[1]),
                'dry_run': bool(row[2]),
                'grace_days': int(row[3]),
                'last_run_at': row[4],
                'last_run_status': row[5],
                'last_run_summary': row[6],
            }

    def update_cleanup_settings(self, enabled=None, dry_run=None, grace_days=None,
                                last_run_at=None, last_run_status=None, last_run_summary=None) -> dict:
        # Ensure row exists.
        self.get_cleanup_settings()
        sets = []
        params = []
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
        if enabled is not None:
            sets.append(f"enabled = {placeholder}"); params.append(1 if enabled else 0)
        if dry_run is not None:
            sets.append(f"dry_run = {placeholder}"); params.append(1 if dry_run else 0)
        if grace_days is not None:
            sets.append(f"grace_days = {placeholder}"); params.append(int(grace_days))
        if last_run_at is not None:
            sets.append(f"last_run_at = {placeholder}"); params.append(last_run_at)
        if last_run_status is not None:
            sets.append(f"last_run_status = {placeholder}"); params.append(last_run_status)
        if last_run_summary is not None:
            sets.append(f"last_run_summary = {placeholder}"); params.append(last_run_summary)
        sets.append("updated_at = CURRENT_TIMESTAMP")
        if sets:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"UPDATE cleanup_settings SET {', '.join(sets)} WHERE id = 1", params)
                conn.commit()
        return self.get_cleanup_settings()

    def add_cleanup_log(self, *, tmdb_id, media_type, title, action,
                        was_dry_run, user_rating=None, reason=None) -> None:
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO cleanup_log (tmdb_id, media_type, title, action, was_dry_run, user_rating, reason) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                (str(tmdb_id) if tmdb_id is not None else None, media_type, title, action,
                 1 if was_dry_run else 0, user_rating, reason),
            )
            conn.commit()

    def get_cleanup_log(self, limit: int = 100) -> list:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, ran_at, tmdb_id, media_type, title, action, was_dry_run, user_rating, reason FROM cleanup_log ORDER BY id DESC LIMIT ?".replace('?', '%s' if self.db_type in ('mysql', 'postgres') else '?'),
                (int(limit),),
            )
            rows = cursor.fetchall()
            return [{
                'id': r[0], 'ran_at': r[1], 'tmdb_id': r[2], 'media_type': r[3],
                'title': r[4], 'action': r[5], 'was_dry_run': bool(r[6]),
                'user_rating': r[7], 'reason': r[8],
            } for r in rows]

    def get_suggestarr_requests_older_than(self, cutoff_iso: str) -> list:
        """Return SuggestArr-originated requests requested before cutoff."""
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""SELECT r.tmdb_request_id, r.media_type, r.requested_at, m.title
                     FROM requests r
                     LEFT JOIN metadata m ON m.media_id = r.tmdb_request_id AND m.media_type = r.media_type
                     WHERE r.requested_by = 'SuggestArr' AND r.requested_at < {placeholder}
                     ORDER BY r.requested_at ASC""",
                (cutoff_iso,),
            )
            return [{'tmdb_id': str(row[0]), 'media_type': row[1], 'requested_at': row[2], 'title': row[3]}
                    for row in cursor.fetchall()]

    def delete_request_row(self, tmdb_id: str, media_type: str) -> None:
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM requests WHERE tmdb_request_id = {placeholder} AND media_type = {placeholder} AND requested_by = 'SuggestArr'",
                (str(tmdb_id), media_type),
            )
            conn.commit()

