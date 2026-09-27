"""Persistent, user-managed watch-history seeds for recommendations."""

from datetime import datetime
from typing import Any, Dict, List, Optional


class WatchedMediaMixin:
    """Store CSV and manually-added watched titles against a media identity."""

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
                f"SELECT id, tmdb_id, media_type, title, year, rating, source, created_at, updated_at "
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
            'created_at': row[7], 'updated_at': row[8],
        }

    def list_watched_media(self, media_user_identity_id: int, limit: int = 500) -> List[Dict[str, Any]]:
        ph = self._watched_media_placeholder()
        limit = max(1, min(int(limit), 1000))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT id, tmdb_id, media_type, title, year, rating, source, created_at, updated_at "
                f"FROM watched_media WHERE media_user_identity_id={ph} "
                f"ORDER BY updated_at DESC, id DESC LIMIT {ph}",
                (media_user_identity_id, limit),
            )
            return [self._watched_media_row(row) for row in cursor.fetchall()]

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
        for item in self.list_watched_media(media_user_identity_id, limit=1000):
            rating = item['rating']
            signal = 'recent_watch'
            if rating is not None and rating >= 7:
                signal = 'positive'
            elif rating is not None and rating <= 4:
                signal = 'negative'
            updated_at = item.get('updated_at')
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
                'date': seed_date,
            })
        return seeds
