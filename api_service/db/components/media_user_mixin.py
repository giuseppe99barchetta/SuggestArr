import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

class MediaUserMixin:
    @staticmethod
    def _coerce_trakt_expires_at(expires_at: Any) -> Any:
        """Normalize datetime expiry values while leaving epoch values intact."""
        if isinstance(expires_at, datetime):
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            return int(expires_at.astimezone(timezone.utc).timestamp())
        return expires_at

    # ---- media_user_identities ------------------------------------------------
    # A media-server user is identified by (provider, external_user_id); the
    # identity row is the anchor that Trakt account links and sources hang off.

    def upsert_media_user_identity(
        self, provider: str, external_user_id: str, external_username: Optional[str] = None
    ) -> Dict[str, Any]:
        ph = self._ph()
        provider = str(provider).lower()
        external_user_id = str(external_user_id)
        if self.db_type == 'sqlite':
            query = (
                f"INSERT INTO media_user_identities (provider, external_user_id, external_username) "
                f"VALUES ({ph}, {ph}, {ph}) "
                f"ON CONFLICT(provider, external_user_id) DO UPDATE SET "
                f"external_username = COALESCE(excluded.external_username, media_user_identities.external_username)"
            )
        elif self.db_type == 'postgres':
            query = (
                f"INSERT INTO media_user_identities (provider, external_user_id, external_username) "
                f"VALUES ({ph}, {ph}, {ph}) "
                f"ON CONFLICT (provider, external_user_id) DO UPDATE SET "
                f"external_username = COALESCE(EXCLUDED.external_username, media_user_identities.external_username)"
            )
        else:
            query = (
                f"INSERT INTO media_user_identities (provider, external_user_id, external_username) "
                f"VALUES ({ph}, {ph}, {ph}) "
                f"ON DUPLICATE KEY UPDATE "
                f"external_username = COALESCE(VALUES(external_username), external_username)"
            )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (provider, external_user_id, external_username))
            conn.commit()
        return self.get_media_user_identity(provider, external_user_id)

    def get_media_user_identity(self, provider: str, external_user_id: str) -> Dict[str, Any]:
        ph = self._ph()
        query = (
            f"SELECT id, provider, external_user_id, external_username, created_at "
            f"FROM media_user_identities WHERE provider = {ph} AND external_user_id = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (provider.lower(), str(external_user_id)))
            row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Media user identity not found: {provider}/{external_user_id}")
        return {"id": row[0], "provider": row[1], "external_user_id": row[2],
                "external_username": row[3], "created_at": row[4]}

    def get_media_user_identity_by_id(self, identity_id: int) -> Optional[Dict[str, Any]]:
        ph = self._ph()
        query = (
            f"SELECT id, provider, external_user_id, external_username, created_at "
            f"FROM media_user_identities WHERE id = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (identity_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        return {"id": row[0], "provider": row[1], "external_user_id": row[2],
                "external_username": row[3], "created_at": row[4]}

    def get_all_media_user_identities(self) -> List[Dict[str, Any]]:
        """Return all media-user identity rows ordered by provider and external id."""
        query = (
            "SELECT id, provider, external_user_id, external_username, created_at "
            "FROM media_user_identities ORDER BY provider, external_user_id"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "provider": row[1],
                "external_user_id": row[2],
                "external_username": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]

    # ---- trakt_account_links --------------------------------------------------

    def upsert_trakt_account_link(
        self,
        media_user_identity_id: int,
        trakt_user_id: Optional[str],
        trakt_username: Optional[str],
        token_source: str = "manual_oauth",
        status: str = "connected",
    ) -> int:
        ph = self._ph()
        columns = (
            "(media_user_identity_id, trakt_user_id, trakt_username, token_source, "
            "status, updated_at)"
        )
        values = f"({ph}, {ph}, {ph}, {ph}, {ph}, CURRENT_TIMESTAMP)"
        if self.db_type == 'sqlite':
            query = (
                f"INSERT INTO trakt_account_links {columns} VALUES {values} "
                f"ON CONFLICT(media_user_identity_id) DO UPDATE SET "
                f"trakt_user_id = excluded.trakt_user_id, "
                f"trakt_username = excluded.trakt_username, "
                f"token_source = excluded.token_source, "
                f"status = excluded.status, "
                f"last_error = NULL, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        elif self.db_type == 'postgres':
            query = (
                f"INSERT INTO trakt_account_links {columns} VALUES {values} "
                f"ON CONFLICT (media_user_identity_id) DO UPDATE SET "
                f"trakt_user_id = EXCLUDED.trakt_user_id, "
                f"trakt_username = EXCLUDED.trakt_username, "
                f"token_source = EXCLUDED.token_source, "
                f"status = EXCLUDED.status, "
                f"last_error = NULL, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        else:
            query = (
                f"INSERT INTO trakt_account_links {columns} VALUES {values} "
                f"ON DUPLICATE KEY UPDATE "
                f"trakt_user_id = VALUES(trakt_user_id), "
                f"trakt_username = VALUES(trakt_username), "
                f"token_source = VALUES(token_source), "
                f"status = VALUES(status), "
                f"last_error = NULL, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                media_user_identity_id, trakt_user_id, trakt_username, token_source, status,
            ))
            conn.commit()
            # Re-SELECT the id rather than trusting cursor.lastrowid: on the
            # ON CONFLICT DO UPDATE (re-link) path no row is inserted, so
            # lastrowid is 0 on a fresh SQLite connection, which would break the
            # foreign-keyed token upsert that follows.
            cursor.execute(
                f"SELECT id FROM trakt_account_links WHERE media_user_identity_id = {ph}",
                (media_user_identity_id,),
            )
            return cursor.fetchone()[0]

    def _row_to_trakt_link(self, row) -> Dict[str, Any]:
        status = row[5] or "connected"
        return {
            "id": row[0], "media_user_identity_id": row[1], "trakt_user_id": row[2],
            "trakt_username": row[3], "token_source": row[4], "status": status,
            "last_synced_at": row[6], "last_error": row[7],
            "created_at": row[8], "updated_at": row[9],
            "connected": status == "connected",
        }

    _TRAKT_LINK_COLUMNS = (
        "id, media_user_identity_id, trakt_user_id, trakt_username, token_source, "
        "status, last_synced_at, last_error, created_at, updated_at"
    )

    def get_trakt_account_link(self, media_user_identity_id: int) -> Optional[Dict[str, Any]]:
        ph = self._ph()
        query = (
            f"SELECT {self._TRAKT_LINK_COLUMNS} FROM trakt_account_links "
            f"WHERE media_user_identity_id = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (media_user_identity_id,))
            row = cursor.fetchone()
        return self._row_to_trakt_link(row) if row else None

    def get_trakt_account_link_by_id(self, link_id: int) -> Optional[Dict[str, Any]]:
        ph = self._ph()
        query = f"SELECT {self._TRAKT_LINK_COLUMNS} FROM trakt_account_links WHERE id = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (link_id,))
            row = cursor.fetchone()
        return self._row_to_trakt_link(row) if row else None

    def mark_trakt_account_link_error(
        self, media_user_identity_id: int, status: str, last_error: Optional[str]
    ) -> bool:
        ph = self._ph()
        query = (
            f"UPDATE trakt_account_links SET status = {ph}, last_error = {ph}, "
            f"updated_at = CURRENT_TIMESTAMP WHERE media_user_identity_id = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status, last_error, media_user_identity_id))
            updated = cursor.rowcount
            conn.commit()
        return updated > 0

    def unlink_trakt_account(self, media_user_identity_id: int) -> bool:
        ph = self._ph()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Explicitly remove dependent OAuth tokens first. The FK declares
            # ON DELETE CASCADE, but we do not rely on runtime FK enforcement
            # (PRAGMA foreign_keys) being on, so clean up the child rows here.
            cursor.execute(
                f"DELETE FROM trakt_oauth_tokens WHERE link_id IN "
                f"(SELECT id FROM trakt_account_links WHERE media_user_identity_id = {ph})",
                (media_user_identity_id,),
            )
            cursor.execute(
                f"DELETE FROM trakt_account_links WHERE media_user_identity_id = {ph}",
                (media_user_identity_id,),
            )
            deleted = cursor.rowcount
            conn.commit()
        return deleted > 0

    def get_all_trakt_account_link_statuses(self) -> List[Dict[str, Any]]:
        query = f"SELECT {self._TRAKT_LINK_COLUMNS} FROM trakt_account_links"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
        return [self._row_to_trakt_link(row) for row in rows]

    # ---- trakt_oauth_tokens ---------------------------------------------------

    def upsert_trakt_oauth_tokens(
        self, link_id: int, access_token: str, refresh_token: str, expires_at: Any
    ) -> None:
        ph = self._ph()
        expires_at = self._coerce_trakt_expires_at(expires_at)
        columns = "(link_id, access_token, refresh_token, expires_at, updated_at)"
        values = f"({ph}, {ph}, {ph}, {ph}, CURRENT_TIMESTAMP)"
        if self.db_type == 'sqlite':
            query = (
                f"INSERT INTO trakt_oauth_tokens {columns} VALUES {values} "
                f"ON CONFLICT(link_id) DO UPDATE SET "
                f"access_token = excluded.access_token, "
                f"refresh_token = excluded.refresh_token, "
                f"expires_at = excluded.expires_at, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        elif self.db_type == 'postgres':
            query = (
                f"INSERT INTO trakt_oauth_tokens {columns} VALUES {values} "
                f"ON CONFLICT (link_id) DO UPDATE SET "
                f"access_token = EXCLUDED.access_token, "
                f"refresh_token = EXCLUDED.refresh_token, "
                f"expires_at = EXCLUDED.expires_at, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        else:
            query = (
                f"INSERT INTO trakt_oauth_tokens {columns} VALUES {values} "
                f"ON DUPLICATE KEY UPDATE "
                f"access_token = VALUES(access_token), "
                f"refresh_token = VALUES(refresh_token), "
                f"expires_at = VALUES(expires_at), "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (link_id, access_token, refresh_token, expires_at))
            conn.commit()

    def get_trakt_oauth_tokens(self, link_id: int) -> Optional[Dict[str, Any]]:
        ph = self._ph()
        query = (
            f"SELECT access_token, refresh_token, expires_at "
            f"FROM trakt_oauth_tokens WHERE link_id = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (link_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        return {"access_token": row[0], "refresh_token": row[1], "expires_at": row[2]}

    def update_trakt_oauth_tokens(
        self, link_id: int, access_token: str, refresh_token: str, expires_at: Any
    ) -> bool:
        ph = self._ph()
        expires_at = self._coerce_trakt_expires_at(expires_at)
        query = (
            f"UPDATE trakt_oauth_tokens SET access_token = {ph}, refresh_token = {ph}, "
            f"expires_at = {ph}, updated_at = CURRENT_TIMESTAMP WHERE link_id = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (access_token, refresh_token, expires_at, link_id))
            updated = cursor.rowcount
            conn.commit()
        return updated > 0

    def delete_trakt_oauth_tokens(self, link_id: int) -> bool:
        ph = self._ph()
        query = f"DELETE FROM trakt_oauth_tokens WHERE link_id = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (link_id,))
            deleted = cursor.rowcount
            conn.commit()
        return deleted > 0

    # ---- trakt_sources --------------------------------------------------------

    def upsert_trakt_source(
        self,
        media_user_identity_id: int,
        source_type: str,
        source_key: str,
        enabled: bool = True,
        use_as_seed: bool = True,
        use_as_exclusion: bool = True,
        **kwargs,
    ) -> None:
        ph = self._ph()
        list_id = kwargs.get("list_id")
        list_slug = kwargs.get("list_slug")
        username = kwargs.get("username")
        columns = (
            "(media_user_identity_id, source_type, source_key, list_id, list_slug, username, "
            "enabled, use_as_seed, use_as_exclusion, updated_at)"
        )
        values = f"({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, CURRENT_TIMESTAMP)"
        if self.db_type == 'sqlite':
            query = (
                f"INSERT INTO trakt_sources {columns} VALUES {values} "
                f"ON CONFLICT(media_user_identity_id, source_type, source_key) DO UPDATE SET "
                f"list_id = excluded.list_id, list_slug = excluded.list_slug, "
                f"username = excluded.username, enabled = excluded.enabled, "
                f"use_as_seed = excluded.use_as_seed, "
                f"use_as_exclusion = excluded.use_as_exclusion, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        elif self.db_type == 'postgres':
            query = (
                f"INSERT INTO trakt_sources {columns} VALUES {values} "
                f"ON CONFLICT (media_user_identity_id, source_type, source_key) DO UPDATE SET "
                f"list_id = EXCLUDED.list_id, list_slug = EXCLUDED.list_slug, "
                f"username = EXCLUDED.username, enabled = EXCLUDED.enabled, "
                f"use_as_seed = EXCLUDED.use_as_seed, "
                f"use_as_exclusion = EXCLUDED.use_as_exclusion, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        else:
            query = (
                f"INSERT INTO trakt_sources {columns} VALUES {values} "
                f"ON DUPLICATE KEY UPDATE "
                f"list_id = VALUES(list_id), list_slug = VALUES(list_slug), "
                f"username = VALUES(username), enabled = VALUES(enabled), "
                f"use_as_seed = VALUES(use_as_seed), "
                f"use_as_exclusion = VALUES(use_as_exclusion), "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                media_user_identity_id, source_type, source_key, list_id, list_slug, username,
                int(enabled), int(use_as_seed), int(use_as_exclusion),
            ))
            conn.commit()

    def _row_to_trakt_source(self, r) -> Dict[str, Any]:
        return {
            "id": r[0], "media_user_identity_id": r[1], "source_type": r[2], "source_key": r[3],
            "list_id": r[4], "list_slug": r[5], "username": r[6],
            "enabled": bool(r[7]), "use_as_seed": bool(r[8]), "use_as_exclusion": bool(r[9]),
            "created_at": r[10], "updated_at": r[11],
        }

    _TRAKT_SOURCE_COLUMNS = (
        "id, media_user_identity_id, source_type, source_key, list_id, list_slug, "
        "username, enabled, use_as_seed, use_as_exclusion, created_at, updated_at"
    )

    def get_trakt_sources(self, media_user_identity_id: int) -> List[Dict[str, Any]]:
        ph = self._ph()
        query = (
            f"SELECT {self._TRAKT_SOURCE_COLUMNS} FROM trakt_sources "
            f"WHERE media_user_identity_id = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (media_user_identity_id,))
            rows = cursor.fetchall()
        return [self._row_to_trakt_source(r) for r in rows]

    def get_enabled_trakt_sources(self, media_user_identity_id: int) -> List[Dict[str, Any]]:
        ph = self._ph()
        query = (
            f"SELECT {self._TRAKT_SOURCE_COLUMNS} FROM trakt_sources "
            f"WHERE media_user_identity_id = {ph} AND enabled = 1"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (media_user_identity_id,))
            rows = cursor.fetchall()
        return [self._row_to_trakt_source(r) for r in rows]

    def create_user_media_profile(
        self,
        user_id: int,
        provider: str,
        external_user_id: str,
        external_username: str,
        access_token: Optional[str] = None,
    ) -> None:
        """
        Insert or replace a media profile link for a SuggestArr user.

        The UNIQUE (user_id, provider) constraint ensures only one link per
        provider per user.  A second call for the same user+provider updates
        the existing record in-place (preserving the row id).

        Args:
            user_id:           Primary key of the auth user.
            provider:          One of 'jellyfin', 'plex', 'emby'.
            external_user_id:  The user's ID on the external media server.
            external_username: Human-readable name on the external server.
            access_token:      Optional token for the external server (nullable).
        """
        ph = self._ph()
        if self.db_type == 'sqlite':
            query = (
                f"INSERT INTO user_media_profiles "
                f"(user_id, provider, external_user_id, external_username, access_token) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}) "
                f"ON CONFLICT(user_id, provider) DO UPDATE SET "
                f"external_user_id = excluded.external_user_id, "
                f"external_username = excluded.external_username, "
                f"access_token = excluded.access_token, "
                f"created_at = CURRENT_TIMESTAMP"
            )
        elif self.db_type == 'postgres':
            query = (
                f"INSERT INTO user_media_profiles "
                f"(user_id, provider, external_user_id, external_username, access_token) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}) "
                f"ON CONFLICT (user_id, provider) DO UPDATE SET "
                f"external_user_id = EXCLUDED.external_user_id, "
                f"external_username = EXCLUDED.external_username, "
                f"access_token = EXCLUDED.access_token, "
                f"created_at = CURRENT_TIMESTAMP"
            )
        else:
            # MySQL / MariaDB
            query = (
                f"INSERT INTO user_media_profiles "
                f"(user_id, provider, external_user_id, external_username, access_token) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}) "
                f"ON DUPLICATE KEY UPDATE "
                f"external_user_id = VALUES(external_user_id), "
                f"external_username = VALUES(external_username), "
                f"access_token = VALUES(access_token), "
                f"created_at = CURRENT_TIMESTAMP"
            )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id, provider, external_user_id, external_username, access_token))
            conn.commit()

    def get_user_media_profiles(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Return all media profile links for a SuggestArr user.

        Access tokens are intentionally excluded from the result so they are
        never serialised into API responses.

        Args:
            user_id: Primary key of the auth user.

        Returns:
            list[dict]: Each dict has keys id, provider, external_username,
                        created_at.
        """
        ph = self._ph()
        query = (
            f"SELECT id, provider, external_user_id, external_username, created_at "
            f"FROM user_media_profiles WHERE user_id = {ph} ORDER BY provider"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "provider": row[1],
                "external_user_id": row[2],
                "external_username": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]

    def get_user_media_profile_token(self, user_id: int, provider: str) -> Optional[str]:
        """
        Retrieve the access token for a specific media profile link.

        This method is intentionally separate from get_user_media_profiles so
        that tokens are only fetched when explicitly needed (not on every list).

        Args:
            user_id:  Primary key of the auth user.
            provider: Provider name ('jellyfin', 'plex', 'emby').

        Returns:
            str | None: Raw access token, or None if no link exists.
        """
        ph = self._ph()
        query = (
            f"SELECT access_token FROM user_media_profiles "
            f"WHERE user_id = {ph} AND provider = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id, provider))
            row = cursor.fetchone()
        return row[0] if row else None

    def delete_user_media_profile(self, user_id: int, provider: str) -> bool:
        """
        Remove a media profile link.

        Args:
            user_id:  Primary key of the auth user.
            provider: Provider to unlink ('jellyfin', 'plex', 'emby').

        Returns:
            bool: True if a row was deleted, False if no link existed.
        """
        ph = self._ph()
        query = f"DELETE FROM user_media_profiles WHERE user_id = {ph} AND provider = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id, provider))
            deleted = cursor.rowcount
            conn.commit()
        return deleted > 0
