"""Cached TMDb titles and overviews per display language.

`metadata` holds one title per item, in TMDb's default language.  People who
read in another language get theirs from here; each (item, language) is
fetched from TMDb once.
"""

from typing import Dict, Iterable, Optional, Tuple


class TranslationMixin:
    def _translation_placeholder(self):
        return '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'

    def get_translations(self, keys: Iterable[Tuple[str, str]], language: str) -> Dict[Tuple[str, str], dict]:
        """
        Look up cached translations.

        Args:
            keys: (media_id, media_type) pairs.
            language: TMDb language code, e.g. 'de' or 'pt-BR'.

        Returns:
            dict: {(media_id, media_type): {'title': ..., 'overview': ..., 'fetched_at': ...}}
            for the pairs that are cached.
        """
        keys = list({(str(media_id), media_type) for media_id, media_type in keys})
        if not keys:
            return {}
        ph = self._translation_placeholder()
        found = {}
        # Chunked, so a long page cannot exceed a database's parameter limit.
        for start in range(0, len(keys), 200):
            chunk = keys[start:start + 200]
            condition = ' OR '.join([f'(media_id={ph} AND media_type={ph})'] * len(chunk))
            params = [value for pair in chunk for value in pair]
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT media_id, media_type, title, overview, fetched_at FROM metadata_translations "
                    f"WHERE language={ph} AND ({condition})",
                    (language, *params),
                )
                for media_id, media_type, title, overview, fetched_at in cursor.fetchall():
                    found[(str(media_id), media_type)] = {'title': title, 'overview': overview,
                                                          'fetched_at': fetched_at}
        return found

    def save_translation(self, media_id: str, media_type: str, language: str,
                         title: Optional[str], overview: Optional[str]) -> None:
        """Store (or replace) one translation."""
        ph = self._translation_placeholder()
        params = (str(media_id), media_type, language, title, overview)
        if self.db_type == 'postgres':
            query = (f"INSERT INTO metadata_translations (media_id, media_type, language, title, overview) "
                     f"VALUES ({ph},{ph},{ph},{ph},{ph}) ON CONFLICT (media_id, media_type, language) "
                     f"DO UPDATE SET title=EXCLUDED.title, overview=EXCLUDED.overview, fetched_at=CURRENT_TIMESTAMP")
        elif self.db_type in ('mysql', 'mariadb'):
            query = (f"INSERT INTO metadata_translations (media_id, media_type, language, title, overview) "
                     f"VALUES ({ph},{ph},{ph},{ph},{ph}) ON DUPLICATE KEY UPDATE "
                     f"title=VALUES(title), overview=VALUES(overview), fetched_at=CURRENT_TIMESTAMP")
        else:
            query = (f"INSERT OR REPLACE INTO metadata_translations "
                     f"(media_id, media_type, language, title, overview, fetched_at) "
                     f"VALUES ({ph},{ph},{ph},{ph},{ph},CURRENT_TIMESTAMP)")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()

    def get_user_language(self, user_id: int) -> Optional[str]:
        """The display language a SuggestArr user chose, or None for the default."""
        ph = self._translation_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT language FROM auth_users WHERE id={ph}", (user_id,))
            row = cursor.fetchone()
        return row[0] if row and row[0] else None
