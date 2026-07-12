import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from api_service.exceptions.database_exceptions import DatabaseError
class AuthMixin:
    def _ph(self) -> str:
        """Return the SQL placeholder character for the current DB type."""
        return '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'

    @staticmethod
    def _utc_naive(dt: datetime) -> datetime:
        """Return a naive UTC datetime safe for all DB backends.

        MySQL DATETIME rejects timezone offsets; stripping tzinfo after
        normalising to UTC gives a value every backend accepts.
        """
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    def get_auth_user_count(self) -> int:
        """
        Return the total number of SuggestArr auth accounts.

        Used by the setup-mode check in the auth middleware: if the count is 0
        the system is in first-run mode and all routes are temporarily public.

        Returns:
            int: Number of rows in the auth_users table.
        """
        ph = self._ph()
        query = "SELECT COUNT(*) FROM auth_users"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def create_auth_user(self, username: str, password_hash: str, role: str = 'user') -> int:
        """
        Insert a new SuggestArr auth account and return its primary key.

        Args:
            username:      Unique login name.
            password_hash: bcrypt hash string produced by AuthService.hash_password.
            role:          'admin' or 'user' (default 'user').

        Returns:
            int: The new row's primary key (id).

        Raises:
            DatabaseError: If the username already exists or the insert fails.
        """
        ph = self._ph()

        if self.db_type == 'postgres':
            query = (
                f"INSERT INTO auth_users (username, password_hash, role) "
                f"VALUES ({ph}, {ph}, {ph}) RETURNING id"
            )
        else:
            query = (
                f"INSERT INTO auth_users (username, password_hash, role) "
                f"VALUES ({ph}, {ph}, {ph})"
            )

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (username, password_hash, role))
                if self.db_type == 'postgres':
                    row = cursor.fetchone()
                    new_id = row[0]
                else:
                    new_id = cursor.lastrowid
                conn.commit()
                self.logger.info("Created auth user: %s (role=%s)", username, role)
                return int(new_id)
        except Exception as exc:
            raise DatabaseError(
                error=f"Failed to create auth user: {exc}",
                db_type=self.db_type,
            ) from exc

    def get_auth_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Look up a SuggestArr auth user by their login name.

        Args:
            username: Login name to search for (case-sensitive).

        Returns:
            dict | None: Row as a dict with keys id, username, password_hash,
                         role, is_active, last_login - or None if not found.
        """
        ph = self._ph()
        query = (
            f"SELECT id, username, password_hash, role, is_active, last_login "
            f"FROM auth_users WHERE username = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (username,))
            row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "role": row[3],
            "is_active": bool(row[4]),
            "last_login": row[5],
        }

    def get_auth_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Look up a SuggestArr auth user by their primary key.

        Args:
            user_id: Integer primary key from the auth_users table.

        Returns:
            dict | None: Same shape as get_auth_user_by_username, or None.
        """
        ph = self._ph()
        
        # Try to select with new columns first, fall back to old schema if they don't exist
        try:
            query = (
                f"SELECT id, username, password_hash, role, is_active, last_login, "
                f"can_manage_ai, visible_tabs, seer_user_id "
                f"FROM auth_users WHERE id = {ph}"
            )
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (user_id,))
                row = cursor.fetchone()
            if row is None:
                return None
            return {
                "id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "role": row[3],
                "is_active": bool(row[4]),
                "last_login": row[5],
                "can_manage_ai": row[6] if len(row) > 6 else 0,
                "visible_tabs": row[7] if len(row) > 7 else 'requests,jobs,profile',
                "seer_user_id": row[8] if len(row) > 8 else None,
            }
        except Exception as e:
            # Fall back to old schema without new columns (for migration compatibility)
            if 'can_manage_ai' in str(e) or 'visible_tabs' in str(e):
                self.logger.debug("New auth_users columns not yet migrated, using fallback query")
                query = (
                    f"SELECT id, username, password_hash, role, is_active, last_login "
                    f"FROM auth_users WHERE id = {ph}"
                )
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(query, (user_id,))
                    row = cursor.fetchone()
                if row is None:
                    return None
                return {
                    "id": row[0],
                    "username": row[1],
                    "password_hash": row[2],
                    "role": row[3],
                    "is_active": bool(row[4]),
                    "last_login": row[5],
                    "can_manage_ai": 0,
                    "visible_tabs": 'requests,jobs,profile',
                }
            else:
                # Different error, re-raise
                raise

    def update_last_login(self, user_id: int) -> None:
        """
        Record the current UTC timestamp as the last successful login time.

        Args:
            user_id: Primary key of the auth user who just logged in.
        """
        ph = self._ph()
        now = self._utc_naive(datetime.now(timezone.utc))
        query = f"UPDATE auth_users SET last_login = {ph} WHERE id = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (now, user_id))
            conn.commit()

    # ---------------------------------------------------------------------------
    # Refresh-token methods
    # ---------------------------------------------------------------------------

    def store_refresh_token(self, user_id: int, token_hash: str, expires_at: datetime) -> None:
        """
        Persist the SHA-256 hash of a newly issued refresh token.

        Only the hash is stored, never the raw token, so a database dump does
        not yield usable refresh tokens.

        Args:
            user_id:    Primary key of the owning auth user.
            token_hash: SHA-256 hex digest of the raw refresh token.
            expires_at: Expiry timestamp (timezone-aware recommended).
        """
        ph = self._ph()
        if expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        query = (
            f"INSERT INTO refresh_tokens (user_id, token_hash, expires_at) "
            f"VALUES ({ph}, {ph}, {ph})"
        )
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (user_id, token_hash, expires_at))
                conn.commit()
        except Exception as exc:
            raise DatabaseError(
                error=f"Failed to store refresh token: {exc}",
                db_type=self.db_type,
            ) from exc

    def get_refresh_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a non-revoked refresh token record by its hash.

        Args:
            token_hash: SHA-256 hex digest of the raw token received from the cookie.

        Returns:
            dict | None: Row with keys id, user_id, expires_at - or None if
                         not found or already revoked.
        """
        ph = self._ph()
        query = (
            f"SELECT id, user_id, expires_at FROM refresh_tokens "
            f"WHERE token_hash = {ph} AND revoked = 0"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (token_hash,))
            row = cursor.fetchone()
        if row is None:
            return None
        return {"id": row[0], "user_id": row[1], "expires_at": row[2]}

    def revoke_refresh_token(self, token_hash: str) -> None:
        """
        Mark a refresh token as revoked so it can no longer be used.

        Called on logout.  The row is kept (not deleted) so that token-reuse
        attacks (presenting a revoked token) can be detected in the future.

        Args:
            token_hash: SHA-256 hex digest of the token to invalidate.
        """
        ph = self._ph()
        query = f"UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (token_hash,))
            conn.commit()

    def cleanup_expired_refresh_tokens(self) -> int:
        """
        Delete refresh tokens that have expired or been revoked.

        Intended to be called periodically (e.g. daily) to keep the table small.

        Returns:
            int: Number of rows deleted.
        """
        ph = self._ph()
        now = self._utc_naive(datetime.now(timezone.utc))
        query = (
            f"DELETE FROM refresh_tokens "
            f"WHERE expires_at < {ph} OR revoked = 1"
        )
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (now,))
                deleted = cursor.rowcount
                conn.commit()
                if deleted:
                    self.logger.debug("Cleaned up %d expired/revoked refresh tokens.", deleted)
                return deleted
        except Exception as exc:
            self.logger.error("Failed to clean up refresh tokens: %s", exc)
            return 0

    # ---------------------------------------------------------------------------
    # Auth user management methods
    # ---------------------------------------------------------------------------

    def get_all_auth_users(self) -> List[Dict[str, Any]]:
        """
        Return all SuggestArr auth users, excluding password hashes.

        Returns:
            list[dict]: Each dict has keys id, username, role, is_active,
                        created_at, last_login, can_manage_ai, visible_tabs.
        """
        # Try to select with new columns first, fall back to old schema if they don't exist
        try:
            query = (
                "SELECT id, username, role, is_active, created_at, last_login, "
                "can_manage_ai, visible_tabs, seer_user_id "
                "FROM auth_users ORDER BY id"
            )
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "username": row[1],
                    "role": row[2],
                    "is_active": bool(row[3]),
                    "created_at": row[4],
                    "last_login": row[5],
                    "can_manage_ai": row[6] if len(row) > 6 else 0,
                    "visible_tabs": row[7] if len(row) > 7 else 'requests,jobs,profile',
                    "seer_user_id": row[8] if len(row) > 8 else None,
                }
                for row in rows
            ]
        except Exception as e:
            # Fall back to old schema without new columns (for migration compatibility)
            if 'can_manage_ai' in str(e) or 'visible_tabs' in str(e):
                self.logger.debug("New auth_users columns not yet migrated, using fallback query")
                query = (
                    "SELECT id, username, role, is_active, created_at, last_login "
                    "FROM auth_users ORDER BY id"
                )
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(query)
                    rows = cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "username": row[1],
                        "role": row[2],
                        "is_active": bool(row[3]),
                        "created_at": row[4],
                        "last_login": row[5],
                        "can_manage_ai": 0,
                        "visible_tabs": 'requests,jobs,profile',
                    }
                    for row in rows
                ]
            else:
                # Different error, re-raise
                raise

    def update_auth_user(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update allowed fields of an auth user record.

        Allowed fields: 'role', 'is_active', 'can_manage_ai', 'visible_tabs'.

        Args:
            user_id: Primary key of the user to update.
            updates: Dict containing any subset of allowed fields.

        Returns:
            bool: True if a row was updated, False if the user was not found.
        """
        allowed = {'role', 'is_active', 'can_manage_ai', 'visible_tabs', 'seer_user_id'}
        fields = {k: v for k, v in updates.items() if k in allowed}
        if not fields:
            return False
        ph = self._ph()
        set_clause = ", ".join(f"{k} = {ph}" for k in fields)
        query = f"UPDATE auth_users SET {set_clause} WHERE id = {ph}"
        values = list(fields.values()) + [user_id]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, values)
            updated = cursor.rowcount
            conn.commit()
        return updated > 0

    def update_auth_user_profile(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update a user's own profile fields: username and/or password_hash.

        This is intentionally separate from update_auth_user (which handles
        admin-level role/active changes) so that the two call-sites stay
        clearly distinct.

        Args:
            user_id: Primary key of the user to update.
            updates: Dict containing any subset of {'username', 'password_hash'}.

        Returns:
            bool: True if a row was updated, False if the user was not found.

        Raises:
            Exception: Propagates DB-level unique-constraint violations
                       (e.g. duplicate username) so the caller can handle them.
        """
        allowed = {'username', 'password_hash'}
        fields = {k: v for k, v in updates.items() if k in allowed}
        if not fields:
            return False
        ph = self._ph()
        set_clause = ", ".join(f"{k} = {ph}" for k in fields)
        query = f"UPDATE auth_users SET {set_clause} WHERE id = {ph}"
        values = list(fields.values()) + [user_id]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, values)
            updated = cursor.rowcount
            conn.commit()
        return updated > 0

    def delete_auth_user(self, user_id: int) -> bool:
        """
        Permanently delete a SuggestArr auth user.

        Cascade deletes their refresh_tokens and user_media_profiles.

        Args:
            user_id: Primary key of the user to remove.

        Returns:
            bool: True if a row was deleted, False if the user was not found.
        """
        ph = self._ph()
        query = f"DELETE FROM auth_users WHERE id = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            deleted = cursor.rowcount
            conn.commit()
        return deleted > 0

    def get_admin_count(self) -> int:
        """
        Count active admin accounts.

        Used to prevent removing the last active admin.

        Returns:
            int: Number of auth_users rows where role='admin' AND is_active=1.
        """
        query = "SELECT COUNT(*) FROM auth_users WHERE role = 'admin' AND is_active = 1"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
        return row[0] if row else 0

    # ---------------------------------------------------------------------------
    # User media profile methods
    # ---------------------------------------------------------------------------

