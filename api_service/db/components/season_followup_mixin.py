"""Watch progress and scan watermarks for the next-season follow-up job."""

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from api_service.db.recap_repository import utc_datetime


def _naive_utc(value) -> Optional[datetime]:
    """Normalize a datetime or stored timestamp to naive UTC (None stays None)."""
    value = utc_datetime(value)
    return value.replace(tzinfo=None) if value else None


class SeasonFollowupMixin:
    """Per-server show progress (``season_followups``) and scan watermark (``season_followup_scans``).

    Only the follow-up job writes these tables, under its own lock, so plain read-then-write
    is enough and keeps the SQL identical on SQLite, PostgreSQL, MySQL and MariaDB.
    """

    def _season_followup_placeholder(self) -> str:
        return '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'

    def record_season_progress(self, server_key: str, rows: Iterable[Dict[str, Any]]) -> int:
        """Store the furthest episode watched per show, committing all rows in one transaction.

        The position ``(season, episode)`` only moves forward; ``last_watched_at`` moves to the
        newest play independently, so a rewatch keeps the show inside the eligibility window.

        :param server_key: Media server key (see ``jobs.season_followup.server_key``).
        :param rows: ``{tmdb_id, season, episode, watched_at}`` per show (one row per show).
        :return: Number of shows inserted or updated.
        """
        ph = self._season_followup_placeholder()
        changed = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for row in rows:
                tmdb_id, watched_at = int(row['tmdb_id']), _naive_utc(row['watched_at'])
                cursor.execute(f"SELECT season, episode, last_watched_at FROM season_followups "
                               f"WHERE server_key={ph} AND tmdb_id={ph}", (server_key, tmdb_id))
                stored = cursor.fetchone()
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                if row.get('season') is None:
                    # Only a special or an unnumbered episode: it can keep a tracked show fresh.
                    if stored is None:
                        continue
                    position = (int(stored[0]), int(stored[1]))
                else:
                    position = (int(row['season']), int(row['episode']))
                if stored is None:
                    cursor.execute(f"INSERT INTO season_followups (server_key, tmdb_id, season, episode, "
                                   f"last_watched_at, updated_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                                   (server_key, tmdb_id, *position, watched_at, now))
                    changed += 1
                    continue
                stored_at = _naive_utc(stored[2])
                new_position = max(position, (int(stored[0]), int(stored[1])))
                new_at = max(filter(None, (watched_at, stored_at)), default=None)
                if new_position != (int(stored[0]), int(stored[1])) or new_at != stored_at:
                    cursor.execute(f"UPDATE season_followups SET season={ph}, episode={ph}, last_watched_at={ph}, "
                                   f"updated_at={ph} WHERE server_key={ph} AND tmdb_id={ph}",
                                   (*new_position, new_at, now, server_key, tmdb_id))
                    changed += 1
            conn.commit()
        return changed

    def season_followup_candidates(self, server_key: str, since: datetime) -> List[Dict[str, Any]]:
        """Shows of one server last watched at or after ``since``.

        :return: ``{tmdb_id, season, episode, last_watched_at, requested_season}`` dicts.
        """
        ph = self._season_followup_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT tmdb_id, season, episode, last_watched_at, requested_season "
                           f"FROM season_followups WHERE server_key={ph} AND last_watched_at >= {ph} "
                           f"ORDER BY last_watched_at DESC", (server_key, _naive_utc(since)))
            return [{'tmdb_id': int(r[0]), 'season': int(r[1]), 'episode': int(r[2]),
                     'last_watched_at': _naive_utc(r[3]),
                     'requested_season': int(r[4]) if r[4] is not None else None}
                    for r in cursor.fetchall()]

    def mark_season_requested(self, server_key: str, tmdb_id: int, season: int) -> None:
        """Record that the follow-up delivered ``season`` of a show (never moves backwards)."""
        ph = self._season_followup_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE season_followups SET requested_season={ph}, updated_at={ph} "
                           f"WHERE server_key={ph} AND tmdb_id={ph} "
                           f"AND (requested_season IS NULL OR requested_season < {ph})",
                           (int(season), datetime.now(timezone.utc).replace(tzinfo=None),
                            server_key, int(tmdb_id), int(season)))
            conn.commit()

    def get_scan_watermark(self, server_key: str) -> Optional[datetime]:
        """Return the aware-UTC time the server's history was scanned through, or None."""
        ph = self._season_followup_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT scanned_through FROM season_followup_scans WHERE server_key={ph}",
                           (server_key,))
            row = cursor.fetchone()
        return utc_datetime(row[0]) if row and row[0] is not None else None

    def set_scan_watermark(self, server_key: str, scanned_through: datetime) -> None:
        """Store the time the server's history was scanned through."""
        ph = self._season_followup_placeholder()
        value = _naive_utc(scanned_through)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Look the row up instead of trusting rowcount: MySQL reports 0 for an unchanged value.
            cursor.execute(f"SELECT 1 FROM season_followup_scans WHERE server_key={ph}", (server_key,))
            if cursor.fetchone():
                cursor.execute(f"UPDATE season_followup_scans SET scanned_through={ph} WHERE server_key={ph}",
                               (value, server_key))
            else:
                cursor.execute(f"INSERT INTO season_followup_scans (server_key, scanned_through) "
                               f"VALUES ({ph}, {ph})", (server_key, value))
            conn.commit()
