import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set


def _wall_clock(value) -> Optional[datetime]:
    """Read a database time (datetime or SQLite text) as a naive wall-clock time.

    The time zone is dropped without converting: ``requested_at`` is written by the
    database's own CURRENT_TIMESTAMP, so comparing it with that same clock's "now"
    keeps day, week and month boundaries in the database's time zone on every engine.
    """
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip()[:19])
        except ValueError:
            return None
    return value.replace(tzinfo=None) if isinstance(value, datetime) else None


def period_starts(now: datetime) -> Dict[str, tuple]:
    """Start of the current and the previous day, week (Monday) and month.

    :param now: Current time on the database clock.
    :return: Dict of stat key to ``(current_start, previous_start)``.
    """
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = today - timedelta(days=today.weekday())
    month = today.replace(day=1)
    previous_month = (month - timedelta(days=1)).replace(day=1)
    return {
        'today': (today, today - timedelta(days=1)),
        'this_week': (week, week - timedelta(days=7)),
        'this_month': (month, previous_month),
    }


def period_counts(timestamps, now: datetime) -> Dict[str, Dict[str, int]]:
    """Count requests in the current day, week and month, and in the previous ones.

    Comparing a half-finished week with a whole previous week would always look like a
    drop, so each previous period is cut at the same elapsed time as the current one.

    :param timestamps: Request times on the database clock.
    :param now: Current time on the same clock.
    :return: ``{'current': {...}, 'previous': {...}}``, each keyed by
        'today', 'this_week' and 'this_month'.
    """
    current, previous = {}, {}
    for key, (start, previous_start) in period_starts(now).items():
        # Both windows include their "now", so a request exactly one period ago counts.
        same_point = previous_start + (now - start)
        current[key] = sum(1 for moment in timestamps if start <= moment <= now)
        previous[key] = sum(1 for moment in timestamps
                            if previous_start <= moment < start and moment <= same_point)
    return {'current': current, 'previous': previous}


class AiSearchMixin:
    def set_ai_feedback(self, tmdb_id: str, media_type: str, feedback: str,
                        title: str = None, year: int = None, rationale: str = None) -> None:
        """Insert or update a like/dislike feedback for an AI search result.

        :param feedback: 'like' or 'dislike'.
        """
        if feedback not in ('like', 'dislike'):
            raise ValueError("feedback must be 'like' or 'dislike'")
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if self.db_type in ('mysql', 'mariadb'):
                cursor.execute(
                    f"REPLACE INTO ai_search_feedback (tmdb_id, media_type, feedback, title, year, rationale) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                    (str(tmdb_id), media_type, feedback, title, year, rationale),
                )
            else:
                cursor.execute(
                    f"INSERT INTO ai_search_feedback (tmdb_id, media_type, feedback, title, year, rationale) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}) ON CONFLICT(tmdb_id, media_type) DO UPDATE SET feedback=excluded.feedback, title=excluded.title, year=excluded.year, rationale=excluded.rationale, created_at=CURRENT_TIMESTAMP",
                    (str(tmdb_id), media_type, feedback, title, year, rationale),
                )
            conn.commit()

    def delete_ai_feedback(self, tmdb_id: str, media_type: str) -> None:
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM ai_search_feedback WHERE tmdb_id = {placeholder} AND media_type = {placeholder}",
                (str(tmdb_id), media_type),
            )
            conn.commit()

    def get_all_ai_feedback(self):
        """Return list of all feedback rows as dicts (tmdb_id, media_type, feedback, title, year)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tmdb_id, media_type, feedback, title, year FROM ai_search_feedback")
            rows = cursor.fetchall()
            out = []
            for r in rows:
                out.append({
                    'tmdb_id': str(r[0]),
                    'media_type': r[1],
                    'feedback': r[2],
                    'title': r[3],
                    'year': r[4],
                })
            return out

    def get_ai_dislike_ids(self, media_type: str = None) -> set:
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if media_type:
                cursor.execute(
                    f"SELECT tmdb_id FROM ai_search_feedback WHERE feedback = 'dislike' AND media_type = {placeholder}",
                    (media_type,),
                )
            else:
                cursor.execute("SELECT tmdb_id FROM ai_search_feedback WHERE feedback = 'dislike'")
            return {str(r[0]) for r in cursor.fetchall()}

    def get_ai_likes(self, media_type: str = None):
        """Return liked items as list of {title, year, media_type} dicts."""
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if media_type:
                cursor.execute(
                    f"SELECT title, year, media_type FROM ai_search_feedback WHERE feedback = 'like' AND media_type = {placeholder} AND title IS NOT NULL",
                    (media_type,),
                )
            else:
                cursor.execute("SELECT title, year, media_type FROM ai_search_feedback WHERE feedback = 'like' AND title IS NOT NULL")
            return [{'title': r[0], 'year': r[1], 'media_type': r[2]} for r in cursor.fetchall()]

    def get_ai_dislikes(self, media_type: str = None):
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if media_type:
                cursor.execute(
                    f"SELECT title, year, media_type FROM ai_search_feedback WHERE feedback = 'dislike' AND media_type = {placeholder} AND title IS NOT NULL",
                    (media_type,),
                )
            else:
                cursor.execute("SELECT title, year, media_type FROM ai_search_feedback WHERE feedback = 'dislike' AND title IS NOT NULL")
            return [{'title': r[0], 'year': r[1], 'media_type': r[2]} for r in cursor.fetchall()]

    def record_ai_seen(self, items) -> None:
        """Record a batch of (tmdb_id, media_type) tuples as already-recommended."""
        if not items:
            return
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
        rows = [(str(t), m) for t, m in items if t]
        if not rows:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if self.db_type in ('mysql', 'mariadb'):
                cursor.executemany(
                    f"REPLACE INTO ai_search_seen (tmdb_id, media_type) VALUES ({placeholder}, {placeholder})",
                    rows,
                )
            else:
                cursor.executemany(
                    f"INSERT INTO ai_search_seen (tmdb_id, media_type) VALUES ({placeholder}, {placeholder}) ON CONFLICT(tmdb_id, media_type) DO UPDATE SET last_seen=CURRENT_TIMESTAMP",
                    rows,
                )
            conn.commit()

    def get_ai_seen_ids(self, media_type: str = None) -> set:
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if media_type:
                cursor.execute(
                    f"SELECT tmdb_id FROM ai_search_seen WHERE media_type = {placeholder}",
                    (media_type,),
                )
            else:
                cursor.execute("SELECT tmdb_id FROM ai_search_seen")
            return {str(r[0]) for r in cursor.fetchall()}

    def clear_ai_seen(self, media_type: str = None) -> int:
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if media_type:
                cursor.execute(
                    f"DELETE FROM ai_search_seen WHERE media_type = {placeholder}",
                    (media_type,),
                )
            else:
                cursor.execute("DELETE FROM ai_search_seen")
            count = cursor.rowcount
            conn.commit()
            return count

    # Recent AI searches kept per user, and the longest query stored (fits MySQL's VARCHAR(512)).
    AI_SEARCH_HISTORY_LIMIT = 5
    AI_SEARCH_QUERY_MAX = 500

    def _history_placeholder(self) -> str:
        return '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'

    def add_ai_search_history(self, user_id: int, query: str) -> None:
        """Record a search as the user's most recent, keeping only the newest few.

        A repeated query moves to the top instead of appearing twice.

        :param user_id: SuggestArr account id.
        :param query: The search text as typed.
        """
        query = (query or '').strip()[:self.AI_SEARCH_QUERY_MAX]
        if not query:
            return
        ph = self._history_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM ai_search_history WHERE user_id = {ph} AND query = {ph}", (user_id, query))
            cursor.execute(f"INSERT INTO ai_search_history (user_id, query) VALUES ({ph}, {ph})", (user_id, query))
            cursor.execute(f"SELECT id FROM ai_search_history WHERE user_id = {ph} ORDER BY id DESC", (user_id,))
            stale = [row[0] for row in cursor.fetchall()[self.AI_SEARCH_HISTORY_LIMIT:]]
            if stale:
                cursor.execute(f"DELETE FROM ai_search_history WHERE id IN ({','.join([ph] * len(stale))})", tuple(stale))
            conn.commit()

    def get_ai_search_history(self, user_id: int) -> List[str]:
        """Return the user's recent searches, newest first.

        :param user_id: SuggestArr account id.
        :return: Up to AI_SEARCH_HISTORY_LIMIT query strings.
        """
        ph = self._history_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT query FROM ai_search_history WHERE user_id = {ph} ORDER BY id DESC LIMIT {ph}",
                (user_id, self.AI_SEARCH_HISTORY_LIMIT),
            )
            return [row[0] for row in cursor.fetchall()]

    def clear_ai_search_history(self, user_id: int) -> None:
        """Forget all recent searches of one user.

        :param user_id: SuggestArr account id.
        """
        ph = self._history_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM ai_search_history WHERE user_id = {ph}", (user_id,))
            conn.commit()

    def get_ai_search_requests(self, page: int = 1, per_page: int = 12, sort_by: str = 'date-desc') -> Dict[str, Any]:
        """Get requests made via AI Search, paginated and sorted.

        :param page: Page number (1-based).
        :param per_page: Results per page.
        :param sort_by: Sort key - one of 'date-desc', 'date-asc', 'title-asc', 'title-desc'.
        :return: Dict with 'data', 'total', 'total_pages', 'current_page', 'per_page'.
        """
        self.logger.debug("Retrieving AI search requests: page=%d, per_page=%d, sort_by=%s", page, per_page, sort_by)

        sort_mapping = {
            'date-desc': 'r.requested_at DESC',
            'date-asc': 'r.requested_at ASC',
            'title-asc': 'm.title ASC',
            'title-desc': 'm.title DESC',
        }
        order_by_clause = sort_mapping.get(sort_by, 'r.requested_at DESC')
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'

        count_query = """
            SELECT COUNT(*)
            FROM requests r
            JOIN metadata m ON r.tmdb_request_id = m.media_id AND r.media_type = m.media_type
            WHERE r.requested_by = 'SuggestArr'
            AND r.tmdb_source_id = 'ai_search'
        """

        select_query = f"""
            SELECT
                r.tmdb_request_id, r.media_type, r.requested_at, r.rationale,
                m.title, m.overview, m.poster_path, m.release_date, m.rating,
                m.backdrop_path, m.logo_path
            FROM requests r
            JOIN metadata m ON r.tmdb_request_id = m.media_id AND r.media_type = m.media_type
            WHERE r.requested_by = 'SuggestArr'
            AND r.tmdb_source_id = 'ai_search'
            ORDER BY {order_by_clause}
            LIMIT {placeholder} OFFSET {placeholder}
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(count_query)
            total = (cursor.fetchone() or [0])[0]

            offset = (page - 1) * per_page
            cursor.execute(select_query, (per_page, offset))
            rows = cursor.fetchall()

        items = []
        for row in rows:
            items.append({
                "request_id": row[0],
                "media_type": row[1],
                "requested_at": row[2],
                "rationale": row[3],
                "title": row[4],
                "overview": row[5],
                "poster_path": row[6],
                "release_date": row[7],
                "rating": round(row[8], 2) if row[8] is not None else None,
                "backdrop_path": row[9],
                "logo_path": row[10],
            })

        total_pages = max(1, (total + per_page - 1) // per_page)
        return {
            "data": items,
            "total": total,
            "total_pages": total_pages,
            "current_page": page,
            "per_page": per_page,
        }

    def get_requests_stats(self) -> Dict[str, Any]:
        """Get statistics about requests: total, today, this week, and this month counts."""
        self.logger.debug("Retrieving request statistics")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total requests query
            total_query = """
                SELECT COUNT(*) FROM requests
                WHERE requested_by = 'SuggestArr'
            """

            if self.db_type in ['mysql', 'postgres']:
                total_query = total_query.replace("?", "%s")

            cursor.execute(total_query)
            total_result = cursor.fetchone()
            total = total_result[0] if total_result else 0

            # Period counts and their trend baseline come from one query and one clock,
            # the database's own, which is also what wrote requested_at.
            cursor.execute("SELECT CURRENT_TIMESTAMP")
            now = _wall_clock(cursor.fetchone()[0])
            since = min(previous for _, previous in period_starts(now).values())
            ph = '%s' if self.db_type in ['mysql', 'mariadb', 'postgres'] else '?'
            cursor.execute(
                f"SELECT requested_at FROM requests WHERE requested_by = 'SuggestArr' AND requested_at >= {ph}",
                (since.strftime('%Y-%m-%d %H:%M:%S'),),
            )
            moments = [moment for moment in (_wall_clock(row[0]) for row in cursor.fetchall()) if moment]
            counts = period_counts(moments, now)

            return {
                "total": total,
                "approved": 0,  # Not handled on your side
                "pending": 0,   # Not handled on your side
                **counts['current'],
                "previous": counts['previous'],
            }
    
