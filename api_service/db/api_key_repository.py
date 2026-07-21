"""Persistence for public API keys.  Raw keys are deliberately never stored."""
from datetime import datetime, timedelta, timezone


class ApiKeyRepository:
    def __init__(self, database):
        self.db = database

    def _ph(self):
        return '%s' if self.db.db_type in ('mysql', 'mariadb', 'postgres') else '?'

    def create_key(self, user_id, name, key_id, secret_hash, prefix, expires_at=None):
        ph = self._ph()
        query = f"INSERT INTO api_keys (user_id, name, key_id, secret_hash, prefix, expires_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})"
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id, name, key_id, secret_hash, prefix, expires_at))
            if self.db.db_type == 'postgres':
                cursor.execute(f"SELECT id FROM api_keys WHERE key_id = {ph}", (key_id,))
                key_id_db = cursor.fetchone()[0]
            else:
                key_id_db = cursor.lastrowid
            conn.commit()
        return int(key_id_db)

    def list_keys_for_user(self, user_id, include_revoked=False):
        ph = self._ph()
        where = f"user_id = {ph}" + ("" if include_revoked else " AND revoked_at IS NULL")
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT id, name, prefix, created_at, last_used_at, expires_at, revoked_at FROM api_keys WHERE {where} ORDER BY id DESC", (user_id,))
            rows = cursor.fetchall()
        return [dict(zip(('id', 'name', 'prefix', 'created_at', 'last_used_at', 'expires_at', 'revoked_at'), row)) for row in rows]

    def get_key_by_public_id(self, key_id):
        ph = self._ph()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT id, user_id, name, key_id, secret_hash, prefix, last_used_at, expires_at, revoked_at FROM api_keys WHERE key_id = {ph}", (key_id,))
            row = cursor.fetchone()
        return dict(zip(('id', 'user_id', 'name', 'key_id', 'secret_hash', 'prefix', 'last_used_at', 'expires_at', 'revoked_at'), row)) if row else None

    def revoke_key(self, user_id, api_key_row_id):
        ph = self._ph()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE api_keys SET revoked_at = COALESCE(revoked_at, {ph}) WHERE id = {ph} AND user_id = {ph}", (datetime.now(timezone.utc).replace(tzinfo=None), api_key_row_id, user_id))
            matched = cursor.rowcount
            conn.commit()
        return bool(matched)

    def count_active_keys_for_user(self, user_id):
        ph = self._ph()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM api_keys WHERE user_id = {ph} AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > {ph})", (user_id, datetime.now(timezone.utc).replace(tzinfo=None)))
            return int(cursor.fetchone()[0])

    def touch_last_used(self, api_key_row_id, used_at=None):
        ph = self._ph()
        used_at = used_at or datetime.now(timezone.utc).replace(tzinfo=None)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE api_keys SET last_used_at = {ph} WHERE id = {ph} AND (last_used_at IS NULL OR last_used_at < {ph})", (used_at, api_key_row_id, used_at - timedelta(minutes=5)))
            conn.commit()
