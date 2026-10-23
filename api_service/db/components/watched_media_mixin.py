"""Persistent, user-managed watch-history seeds for recommendations."""

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

WATCHED_MEDIA_COLUMNS = ('id, tmdb_id, media_type, title, year, rating, source, created_at, updated_at, '
                         'excluded, watched_at')


class WatchedMediaMixin:
    """Store CSV, manual and re-rated media-server titles against a media identity."""

    def _watched_media_placeholder(self) -> str:
        return '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'

    @staticmethod
    def _normalise_rating(value: Any) -> Optional[float]:
        if value in (None, ''):
            return None
        try:
            rating = float(value)
        except (TypeError, ValueError):
            raise ValueError('rating must be a number from 0 to 10')
        if not 0 <= rating <= 10:
            raise ValueError('rating must be a number from 0 to 10')
        return rating

    def upsert_watched_media(self, media_user_identity_id: int, tmdb_id: Any,
                             media_type: str, title: str, year: Any = None,
                             rating: Any = None, source: str = 'manual') -> Dict[str, Any]:
        """Create or update one user-managed watched title."""
        media_type = str(media_type or '').lower()
        if media_type not in {'movie', 'tv'}:
            raise ValueError("media_type must be 'movie' or 'tv'")
        tmdb_id = str(tmdb_id or '').strip()
        title = str(title or '').strip()
        if not tmdb_id.isdigit() or not title:
            raise ValueError('tmdb_id and title are required')
        try:
            year = int(year) if year not in (None, '') else None
        except (TypeError, ValueError):
            raise ValueError('year must be a four-digit number')
        if year is not None and not 1800 <= year <= 3000:
            raise ValueError('year must be a four-digit number')
        rating = self._normalise_rating(rating)
        source = source if source in {'csv_import', 'manual'} else 'manual'
        ph = self._watched_media_placeholder()
        values = (media_user_identity_id, tmdb_id, media_type, title[:500], year, rating, source)
        if self.db_type == 'sqlite':
            query = f"""
                INSERT INTO watched_media
                    (media_user_identity_id, tmdb_id, media_type, title, year, rating, source)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                ON CONFLICT(media_user_identity_id, tmdb_id, media_type) DO UPDATE SET
                    title=excluded.title, year=excluded.year, rating=excluded.rating,
                    source=excluded.source, updated_at=CURRENT_TIMESTAMP
            """
        elif self.db_type == 'postgres':
            query = f"""
                INSERT INTO watched_media
                    (media_user_identity_id, tmdb_id, media_type, title, year, rating, source)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                ON CONFLICT (media_user_identity_id, tmdb_id, media_type) DO UPDATE SET
                    title=EXCLUDED.title, year=EXCLUDED.year, rating=EXCLUDED.rating,
                    source=EXCLUDED.source, updated_at=CURRENT_TIMESTAMP
            """
        else:
            query = f"""
                INSERT INTO watched_media
                    (media_user_identity_id, tmdb_id, media_type, title, year, rating, source)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                ON DUPLICATE KEY UPDATE title=VALUES(title), year=VALUES(year),
                    rating=VALUES(rating), source=VALUES(source), updated_at=CURRENT_TIMESTAMP
            """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()
        return self.get_watched_media_item(media_user_identity_id, tmdb_id, media_type)

    def get_watched_media_item(self, media_user_identity_id: int, tmdb_id: str,
                               media_type: str) -> Optional[Dict[str, Any]]:
        ph = self._watched_media_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT {WATCHED_MEDIA_COLUMNS} "
                f"FROM watched_media WHERE media_user_identity_id={ph} AND tmdb_id={ph} AND media_type={ph}",
                (media_user_identity_id, str(tmdb_id), media_type),
            )
            row = cursor.fetchone()
        return self._watched_media_row(row) if row else None

    @staticmethod
    def _watched_media_row(row) -> Dict[str, Any]:
        return {
            'id': row[0], 'tmdb_id': str(row[1]), 'media_type': row[2], 'title': row[3],
            'year': row[4], 'rating': row[5], 'source': row[6],
            'created_at': row[7], 'updated_at': row[8], 'excluded': bool(row[9]),
            'watched_at': row[10],
        }

    def list_watched_media(self, media_user_identity_id: int, limit: int = 500) -> List[Dict[str, Any]]:
        """Return a user's titles, most recently played or edited first."""
        ph = self._watched_media_placeholder()
        limit = max(1, min(int(limit), 10000))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT {WATCHED_MEDIA_COLUMNS} "
                f"FROM watched_media WHERE media_user_identity_id={ph} "
                f"ORDER BY COALESCE(watched_at, updated_at) DESC, id DESC LIMIT {ph}",
                (media_user_identity_id, limit),
            )
            return [self._watched_media_row(row) for row in cursor.fetchall()]

    def update_watched_media(self, media_user_identity_id: int, item_id: int,
                             changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Change the rating and/or exclusion flag of one title, keeping its source.

        Args:
            media_user_identity_id: Owner of the row; other users' rows are never touched.
            item_id: Primary key of the watched title.
            changes: Any of ``rating`` (0-10 or None to clear) and ``excluded`` (bool).

        Returns:
            The updated row, or None when it does not belong to this identity.

        Raises:
            ValueError: When no supported field is given or a value is invalid.
        """
        ph = self._watched_media_placeholder()
        assignments, values = [], []
        if 'rating' in changes:
            assignments.append(f'rating={ph}')
            values.append(self._normalise_rating(changes['rating']))
        if 'excluded' in changes:
            if not isinstance(changes['excluded'], bool):
                raise ValueError('excluded must be true or false')
            assignments.append(f'excluded={ph}')
            values.append(int(changes['excluded']))
        if not assignments:
            raise ValueError('Nothing to update: send rating and/or excluded')
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE watched_media SET {', '.join(assignments)}, updated_at=CURRENT_TIMESTAMP "
                f"WHERE id={ph} AND media_user_identity_id={ph}",
                (*values, item_id, media_user_identity_id),
            )
            conn.commit()
            cursor.execute(
                f"SELECT {WATCHED_MEDIA_COLUMNS} "
                f"FROM watched_media WHERE id={ph} AND media_user_identity_id={ph}",
                (item_id, media_user_identity_id),
            )
            row = cursor.fetchone()
        return self._watched_media_row(row) if row else None

    def latest_server_play(self, media_user_identity_id: int) -> Optional[datetime]:
        """Return the newest stored media-server play, or None before the first sync."""
        ph = self._watched_media_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT MAX(watched_at) FROM watched_media WHERE media_user_identity_id={ph}",
                           (media_user_identity_id,))
            row = cursor.fetchone()
        value = row[0] if row else None
        if value is None or isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))

    def record_server_plays(self, media_user_identity_id: int, titles: Iterable[Dict[str, Any]]) -> int:
        """Store media-server plays without touching ratings, exclusions or sources.

        Args:
            media_user_identity_id: Owner of the plays.
            titles: ``{tmdb_id, media_type, title, year, watched_at}`` dicts, ``watched_at``
                being a naive UTC datetime.

        Returns:
            Number of titles added for the first time.
        """
        ph = self._watched_media_placeholder()
        titles = list(titles)
        if not titles:
            return 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT media_type, tmdb_id FROM watched_media WHERE media_user_identity_id={ph}",
                           (media_user_identity_id,))
            existing = {(row[0], str(row[1])) for row in cursor.fetchall()}
            added = 0
            for title in titles:
                key = (title['media_type'], str(title['tmdb_id']))
                if key in existing:
                    # Only move the play date forward; a rating or exclusion stays as the user left it.
                    cursor.execute(
                        f"UPDATE watched_media SET watched_at={ph} WHERE media_user_identity_id={ph} "
                        f"AND media_type={ph} AND tmdb_id={ph} AND (watched_at IS NULL OR watched_at < {ph})",
                        (title['watched_at'], media_user_identity_id, key[0], key[1], title['watched_at']),
                    )
                    continue
                cursor.execute(
                    f"INSERT INTO watched_media (media_user_identity_id, tmdb_id, media_type, title, year, "
                    f"source, watched_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, 'server', {ph})",
                    (media_user_identity_id, key[1], key[0], str(title['title'])[:500], title.get('year'),
                     title['watched_at']),
                )
                existing.add(key)
                added += 1
            conn.commit()
        return added

    def delete_watched_media(self, media_user_identity_id: int, item_id: int) -> bool:
        ph = self._watched_media_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM watched_media WHERE id={ph} AND media_user_identity_id={ph}",
                (item_id, media_user_identity_id),
            )
            deleted = cursor.rowcount > 0
            conn.commit()
        return deleted

    def get_watched_media_seeds(self, media_user_identity_id: int) -> List[Dict[str, Any]]:
        """Return normalized seeds and watched IDs for the recommendation handlers."""
        seeds = []
        for item in self.list_watched_media(media_user_identity_id, limit=10000):
            rating = item['rating']
            # Untouched server plays reach the handlers from the server itself.
            if item['source'] == 'server' and rating is None and not item['excluded']:
                continue
            signal = 'recent_watch'
            if rating is not None and rating >= 7:
                signal = 'positive'
            elif rating is not None and rating <= 4:
                signal = 'negative'
            updated_at = item.get('watched_at') or item.get('updated_at')
            try:
                if isinstance(updated_at, datetime):
                    seed_date = int(updated_at.timestamp())
                else:
                    seed_date = int(datetime.fromisoformat(str(updated_at)).timestamp())
            except (TypeError, ValueError, OverflowError):
                seed_date = 0
            seeds.append({
                'tmdb_id': item['tmdb_id'], 'media_type': item['media_type'],
                'title': item['title'], 'year': item['year'], 'rating': rating,
                'preference_signal': signal, 'source_origin': item['source'],
                'date': seed_date, 'excluded': item['excluded'],
            })
        return seeds
