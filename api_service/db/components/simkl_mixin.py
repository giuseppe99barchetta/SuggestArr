"""Database access for Simkl account links, tokens, sources, and the watch cache.

Mirrors :class:`~api_service.db.components.media_user_mixin.MediaUserMixin`'s
Trakt half, hanging off the same ``media_user_identities`` anchor, with two
structural differences: there is no refresh token to store, and a local cache
of the user's Simkl library backs every read so that jobs never poll Simkl's
library endpoints directly.
"""
import json
import time
from typing import Any, Dict, List, Optional, Sequence


class SimklMixin:
    # ---- simkl_account_links --------------------------------------------------

    def upsert_simkl_account_link(
        self,
        media_user_identity_id: int,
        simkl_user_id: Optional[str],
        simkl_username: Optional[str],
        token_source: str = "manual_oauth",
        status: str = "connected",
    ) -> int:
        ph = self._ph()
        columns = (
            "(media_user_identity_id, simkl_user_id, simkl_username, token_source, "
            "status, updated_at)"
        )
        values = f"({ph}, {ph}, {ph}, {ph}, {ph}, CURRENT_TIMESTAMP)"
        if self.db_type == 'sqlite':
            query = (
                f"INSERT INTO simkl_account_links {columns} VALUES {values} "
                f"ON CONFLICT(media_user_identity_id) DO UPDATE SET "
                f"simkl_user_id = excluded.simkl_user_id, "
                f"simkl_username = excluded.simkl_username, "
                f"token_source = excluded.token_source, "
                f"status = excluded.status, "
                f"last_error = NULL, "
                f"pending_user_code = NULL, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        elif self.db_type == 'postgres':
            query = (
                f"INSERT INTO simkl_account_links {columns} VALUES {values} "
                f"ON CONFLICT (media_user_identity_id) DO UPDATE SET "
                f"simkl_user_id = EXCLUDED.simkl_user_id, "
                f"simkl_username = EXCLUDED.simkl_username, "
                f"token_source = EXCLUDED.token_source, "
                f"status = EXCLUDED.status, "
                f"last_error = NULL, "
                f"pending_user_code = NULL, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        else:
            query = (
                f"INSERT INTO simkl_account_links {columns} VALUES {values} "
                f"ON DUPLICATE KEY UPDATE "
                f"simkl_user_id = VALUES(simkl_user_id), "
                f"simkl_username = VALUES(simkl_username), "
                f"token_source = VALUES(token_source), "
                f"status = VALUES(status), "
                f"last_error = NULL, "
                f"pending_user_code = NULL, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                media_user_identity_id, simkl_user_id, simkl_username, token_source, status,
            ))
            conn.commit()
            # Re-SELECT rather than trusting lastrowid: on the re-link path no
            # row is inserted, so lastrowid would be 0 and break the
            # foreign-keyed token upsert that follows.
            cursor.execute(
                f"SELECT id FROM simkl_account_links WHERE media_user_identity_id = {ph}",
                (media_user_identity_id,),
            )
            return cursor.fetchone()[0]

    _SIMKL_LINK_COLUMNS = (
        "id, media_user_identity_id, simkl_user_id, simkl_username, token_source, "
        "status, last_synced_at, last_error, activities_json, last_full_sync_at, "
        "last_activities_check_at, pending_user_code, created_at, updated_at"
    )

    def _row_to_simkl_link(self, row) -> Dict[str, Any]:
        status = row[5] or "connected"
        return {
            "id": row[0], "media_user_identity_id": row[1], "simkl_user_id": row[2],
            "simkl_username": row[3], "token_source": row[4], "status": status,
            "last_synced_at": row[6], "last_error": row[7],
            "activities_json": row[8],
            "last_full_sync_at": row[9], "last_activities_check_at": row[10],
            "pending_user_code": row[11],
            "created_at": row[12], "updated_at": row[13],
            "connected": status == "connected",
        }

    def get_simkl_account_link(self, media_user_identity_id: int) -> Optional[Dict[str, Any]]:
        ph = self._ph()
        query = (
            f"SELECT {self._SIMKL_LINK_COLUMNS} FROM simkl_account_links "
            f"WHERE media_user_identity_id = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (media_user_identity_id,))
            row = cursor.fetchone()
        return self._row_to_simkl_link(row) if row else None

    def get_simkl_account_link_by_id(self, link_id: int) -> Optional[Dict[str, Any]]:
        ph = self._ph()
        query = f"SELECT {self._SIMKL_LINK_COLUMNS} FROM simkl_account_links WHERE id = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (link_id,))
            row = cursor.fetchone()
        return self._row_to_simkl_link(row) if row else None

    def mark_simkl_account_link_error(
        self, media_user_identity_id: int, status: str, last_error: Optional[str]
    ) -> bool:
        """Set a link's failure status.

        ``needs_reauth`` is terminal and self-healing only via a re-link, so it
        is never overwritten by a later generic ``error``: doing so would erase
        the one state that tells the UI to prompt for a new PIN.
        """
        ph = self._ph()
        query = (
            f"UPDATE simkl_account_links SET status = {ph}, last_error = {ph}, "
            f"updated_at = CURRENT_TIMESTAMP WHERE media_user_identity_id = {ph}"
        )
        params: Sequence[Any] = (status, last_error, media_user_identity_id)
        if status != "needs_reauth":
            query += " AND status <> 'needs_reauth'"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            updated = cursor.rowcount
            conn.commit()
        return updated > 0

    def unlink_simkl_account(self, media_user_identity_id: int) -> bool:
        """Delete a link and everything hanging off it.

        Child rows are removed explicitly rather than relying on FK cascade,
        matching the Trakt unlink, because runtime FK enforcement is not
        guaranteed to be on. The watch cache goes too: it is a per-title record
        of everything the user has watched, and keeping it after an unlink
        would both contradict the intent and let stale data re-attach on a
        later re-link.
        """
        ph = self._ph()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM simkl_watched_cache WHERE link_id IN "
                f"(SELECT id FROM simkl_account_links WHERE media_user_identity_id = {ph})",
                (media_user_identity_id,),
            )
            cursor.execute(
                f"DELETE FROM simkl_oauth_tokens WHERE link_id IN "
                f"(SELECT id FROM simkl_account_links WHERE media_user_identity_id = {ph})",
                (media_user_identity_id,),
            )
            cursor.execute(
                f"DELETE FROM simkl_account_links WHERE media_user_identity_id = {ph}",
                (media_user_identity_id,),
            )
            deleted = cursor.rowcount
            conn.commit()
        return deleted > 0

    def get_all_simkl_account_link_statuses(self) -> List[Dict[str, Any]]:
        query = f"SELECT {self._SIMKL_LINK_COLUMNS} FROM simkl_account_links"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
        return [self._row_to_simkl_link(row) for row in rows]

    # ---- pending PIN ----------------------------------------------------------

    def set_simkl_pending_user_code(
        self, media_user_identity_id: int, user_code: Optional[str]
    ) -> None:
        """Bind an in-flight PIN to the identity that requested it.

        The poll endpoint reads the code from here rather than from the request
        body, so a caller cannot submit an arbitrary code and bind whichever
        Simkl account happened to authorize it to someone else's media user.
        """
        ph = self._ph()
        # The link row may not exist yet on a first link, so create a
        # placeholder in the pending state to hang the code off.
        existing = self.get_simkl_account_link(media_user_identity_id)
        if not existing:
            self.upsert_simkl_account_link(
                media_user_identity_id, None, None, status="pending",
            )
        query = (
            f"UPDATE simkl_account_links SET pending_user_code = {ph}, "
            f"updated_at = CURRENT_TIMESTAMP WHERE media_user_identity_id = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_code, media_user_identity_id))
            conn.commit()

    def get_simkl_pending_user_code(self, media_user_identity_id: int) -> Optional[str]:
        link = self.get_simkl_account_link(media_user_identity_id)
        return (link or {}).get("pending_user_code") or None

    # ---- simkl_oauth_tokens ---------------------------------------------------

    def upsert_simkl_oauth_tokens(
        self, link_id: int, access_token: str, expires_at: Any = None
    ) -> None:
        ph = self._ph()
        expires_at = self._coerce_trakt_expires_at(expires_at)
        columns = "(link_id, access_token, expires_at, updated_at)"
        values = f"({ph}, {ph}, {ph}, CURRENT_TIMESTAMP)"
        if self.db_type == 'sqlite':
            query = (
                f"INSERT INTO simkl_oauth_tokens {columns} VALUES {values} "
                f"ON CONFLICT(link_id) DO UPDATE SET "
                f"access_token = excluded.access_token, "
                f"expires_at = excluded.expires_at, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        elif self.db_type == 'postgres':
            query = (
                f"INSERT INTO simkl_oauth_tokens {columns} VALUES {values} "
                f"ON CONFLICT (link_id) DO UPDATE SET "
                f"access_token = EXCLUDED.access_token, "
                f"expires_at = EXCLUDED.expires_at, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        else:
            query = (
                f"INSERT INTO simkl_oauth_tokens {columns} VALUES {values} "
                f"ON DUPLICATE KEY UPDATE "
                f"access_token = VALUES(access_token), "
                f"expires_at = VALUES(expires_at), "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (link_id, access_token, expires_at))
            conn.commit()

    def get_simkl_oauth_tokens(self, link_id: int) -> Optional[Dict[str, Any]]:
        ph = self._ph()
        query = f"SELECT access_token, expires_at FROM simkl_oauth_tokens WHERE link_id = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (link_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        return {"access_token": row[0], "expires_at": row[1]}

    def delete_simkl_oauth_tokens(self, link_id: int) -> bool:
        ph = self._ph()
        query = f"DELETE FROM simkl_oauth_tokens WHERE link_id = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (link_id,))
            deleted = cursor.rowcount
            conn.commit()
        return deleted > 0

    # ---- simkl_sources --------------------------------------------------------

    def upsert_simkl_source(
        self,
        media_user_identity_id: int,
        source_type: str,
        source_key: str,
        enabled: bool = True,
        use_as_seed: bool = True,
        use_as_exclusion: bool = True,
    ) -> None:
        ph = self._ph()
        columns = (
            "(media_user_identity_id, source_type, source_key, "
            "enabled, use_as_seed, use_as_exclusion, updated_at)"
        )
        values = f"({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, CURRENT_TIMESTAMP)"
        if self.db_type == 'sqlite':
            query = (
                f"INSERT INTO simkl_sources {columns} VALUES {values} "
                f"ON CONFLICT(media_user_identity_id, source_type, source_key) DO UPDATE SET "
                f"enabled = excluded.enabled, "
                f"use_as_seed = excluded.use_as_seed, "
                f"use_as_exclusion = excluded.use_as_exclusion, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        elif self.db_type == 'postgres':
            query = (
                f"INSERT INTO simkl_sources {columns} VALUES {values} "
                f"ON CONFLICT (media_user_identity_id, source_type, source_key) DO UPDATE SET "
                f"enabled = EXCLUDED.enabled, "
                f"use_as_seed = EXCLUDED.use_as_seed, "
                f"use_as_exclusion = EXCLUDED.use_as_exclusion, "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        else:
            query = (
                f"INSERT INTO simkl_sources {columns} VALUES {values} "
                f"ON DUPLICATE KEY UPDATE "
                f"enabled = VALUES(enabled), "
                f"use_as_seed = VALUES(use_as_seed), "
                f"use_as_exclusion = VALUES(use_as_exclusion), "
                f"updated_at = CURRENT_TIMESTAMP"
            )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                media_user_identity_id, source_type, source_key,
                int(enabled), int(use_as_seed), int(use_as_exclusion),
            ))
            conn.commit()

    _SIMKL_SOURCE_COLUMNS = (
        "id, media_user_identity_id, source_type, source_key, "
        "enabled, use_as_seed, use_as_exclusion, created_at, updated_at"
    )

    @staticmethod
    def _row_to_simkl_source(r) -> Dict[str, Any]:
        return {
            "id": r[0], "media_user_identity_id": r[1], "source_type": r[2], "source_key": r[3],
            "enabled": bool(r[4]), "use_as_seed": bool(r[5]), "use_as_exclusion": bool(r[6]),
            "created_at": r[7], "updated_at": r[8],
        }

    def get_simkl_sources(self, media_user_identity_id: int) -> List[Dict[str, Any]]:
        ph = self._ph()
        query = (
            f"SELECT {self._SIMKL_SOURCE_COLUMNS} FROM simkl_sources "
            f"WHERE media_user_identity_id = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (media_user_identity_id,))
            rows = cursor.fetchall()
        return [self._row_to_simkl_source(r) for r in rows]

    def get_enabled_simkl_sources(self, media_user_identity_id: int) -> List[Dict[str, Any]]:
        ph = self._ph()
        query = (
            f"SELECT {self._SIMKL_SOURCE_COLUMNS} FROM simkl_sources "
            f"WHERE media_user_identity_id = {ph} AND enabled = 1"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (media_user_identity_id,))
            rows = cursor.fetchall()
        return [self._row_to_simkl_source(r) for r in rows]

    # ---- simkl_watched_cache --------------------------------------------------

    def upsert_simkl_watched_cache(self, link_id: int, items: List[Dict[str, Any]]) -> int:
        """Insert or refresh cached library rows for one link.

        Args:
            link_id: Owning ``simkl_account_links`` row.
            items: Normalized entries with ``simkl_id``, ``simkl_type``,
                ``media_type``, ``status``, ``tmdb_id``, ``title``, ``year``,
                and ``last_watched_at`` (epoch seconds).

        Returns:
            int: Number of rows written.
        """
        if not items:
            return 0
        ph = self._ph()
        columns = (
            "(link_id, simkl_id, simkl_type, media_type, status, tmdb_id, title, year, "
            "last_watched_at, updated_at)"
        )
        values = f"({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, CURRENT_TIMESTAMP)"
        if self.db_type == 'sqlite':
            query = (
                f"INSERT INTO simkl_watched_cache {columns} VALUES {values} "
                f"ON CONFLICT(link_id, simkl_type, simkl_id) DO UPDATE SET "
                f"media_type = excluded.media_type, status = excluded.status, "
                f"tmdb_id = excluded.tmdb_id, title = excluded.title, year = excluded.year, "
                f"last_watched_at = excluded.last_watched_at, updated_at = CURRENT_TIMESTAMP"
            )
        elif self.db_type == 'postgres':
            query = (
                f"INSERT INTO simkl_watched_cache {columns} VALUES {values} "
                f"ON CONFLICT (link_id, simkl_type, simkl_id) DO UPDATE SET "
                f"media_type = EXCLUDED.media_type, status = EXCLUDED.status, "
                f"tmdb_id = EXCLUDED.tmdb_id, title = EXCLUDED.title, year = EXCLUDED.year, "
                f"last_watched_at = EXCLUDED.last_watched_at, updated_at = CURRENT_TIMESTAMP"
            )
        else:
            query = (
                f"INSERT INTO simkl_watched_cache {columns} VALUES {values} "
                f"ON DUPLICATE KEY UPDATE "
                f"media_type = VALUES(media_type), status = VALUES(status), "
                f"tmdb_id = VALUES(tmdb_id), title = VALUES(title), year = VALUES(year), "
                f"last_watched_at = VALUES(last_watched_at), updated_at = CURRENT_TIMESTAMP"
            )
        params = [
            (
                link_id,
                str(item.get("simkl_id")),
                item.get("simkl_type"),
                item.get("media_type"),
                item.get("status"),
                item.get("tmdb_id"),
                item.get("title"),
                item.get("year"),
                item.get("last_watched_at"),
            )
            for item in items
        ]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params)
            conn.commit()
        return len(params)

    def get_simkl_watched_cache(
        self, link_id: int, statuses: Optional[Sequence[str]] = None
    ) -> List[Dict[str, Any]]:
        """Return cached rows for a link, newest watch first.

        Args:
            link_id: Owning ``simkl_account_links`` row.
            statuses: Restrict to these Simkl statuses. Seeds pass
                ``("watching", "completed")``; exclusions pass ``("completed",)``.
        """
        ph = self._ph()
        query = (
            "SELECT simkl_id, simkl_type, media_type, status, tmdb_id, title, year, "
            f"last_watched_at FROM simkl_watched_cache WHERE link_id = {ph}"
        )
        params: List[Any] = [link_id]
        if statuses:
            placeholders = ", ".join([ph] * len(statuses))
            query += f" AND status IN ({placeholders})"
            params.extend(statuses)
        query += " ORDER BY last_watched_at DESC"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
        return [
            {
                "simkl_id": r[0], "simkl_type": r[1], "media_type": r[2], "status": r[3],
                "tmdb_id": r[4], "title": r[5], "year": r[6], "last_watched_at": r[7],
            }
            for r in rows
        ]

    def clear_simkl_watched_cache(self, link_id: int) -> int:
        ph = self._ph()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM simkl_watched_cache WHERE link_id = {ph}", (link_id,))
            deleted = cursor.rowcount
            conn.commit()
        return deleted

    def reconcile_simkl_watched_cache(
        self, link_id: int, simkl_type: str, present_ids: Sequence[str]
    ) -> int:
        """Drop cached rows of one type that Simkl no longer reports.

        Deletions are invisible to ``date_from`` deltas, so this runs after a
        full ids-only pull to remove titles the user un-marked. The diff is
        computed in Python rather than as a ``NOT IN`` clause because a library
        can hold several hundred ids per type.
        """
        ph = self._ph()
        keep = {str(i) for i in present_ids}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT simkl_id FROM simkl_watched_cache "
                f"WHERE link_id = {ph} AND simkl_type = {ph}",
                (link_id, simkl_type),
            )
            existing = {str(r[0]) for r in cursor.fetchall()}
            stale = sorted(existing - keep)
            if not stale:
                return 0
            for chunk_start in range(0, len(stale), 500):
                chunk = stale[chunk_start:chunk_start + 500]
                placeholders = ", ".join([ph] * len(chunk))
                cursor.execute(
                    f"DELETE FROM simkl_watched_cache WHERE link_id = {ph} "
                    f"AND simkl_type = {ph} AND simkl_id IN ({placeholders})",
                    (link_id, simkl_type, *chunk),
                )
            conn.commit()
        return len(stale)

    # ---- sync state -----------------------------------------------------------

    def get_simkl_sync_state(self, link_id: int) -> Dict[str, Any]:
        """Return the stored activities payload and sync clocks for a link."""
        link = self.get_simkl_account_link_by_id(link_id)
        if not link:
            return {"activities": {}, "last_full_sync_at": None, "last_activities_check_at": None}
        raw = link.get("activities_json")
        try:
            activities = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            activities = {}
        return {
            "activities": activities if isinstance(activities, dict) else {},
            "last_full_sync_at": link.get("last_full_sync_at"),
            "last_activities_check_at": link.get("last_activities_check_at"),
        }

    def update_simkl_sync_state(
        self,
        link_id: int,
        *,
        activities: Optional[Dict[str, Any]] = None,
        mark_full_sync: bool = False,
        mark_activities_check: bool = False,
    ) -> None:
        """Persist sync bookkeeping.

        ``activities`` is stored verbatim, nulls included, and should only be
        written after every ``(type, status)`` pull for this run succeeded:
        saving it after a partial failure would permanently skip the deltas
        that failed.
        """
        ph = self._ph()
        assignments = []
        params: List[Any] = []
        now = int(time.time())
        if activities is not None:
            assignments.append(f"activities_json = {ph}")
            params.append(json.dumps(activities))
            assignments.append("last_synced_at = CURRENT_TIMESTAMP")
        if mark_full_sync:
            assignments.append(f"last_full_sync_at = {ph}")
            params.append(now)
        if mark_activities_check:
            assignments.append(f"last_activities_check_at = {ph}")
            params.append(now)
        if not assignments:
            return
        assignments.append("updated_at = CURRENT_TIMESTAMP")
        params.append(link_id)
        query = f"UPDATE simkl_account_links SET {', '.join(assignments)} WHERE id = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            conn.commit()
