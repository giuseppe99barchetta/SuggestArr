"""Activities-gated synchronization of a user's Simkl library into a local cache.

Simkl has no per-event history endpoint like Trakt's ``/sync/history``; the only
way to read what someone has watched is to pull whole library buckets. Polling
those on a timer gets the app's ``client_id`` suspended without warning, so this
module is the single place that talks to them, and it does so only when
``/sync/activities`` says something actually changed.

Everything downstream (seeds, exclusions, the unwatched gate) reads the cache
this module maintains, never the API.
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.simkl.simkl_client import (
    SimklAuthError,
    SimklClient,
    SimklClientIdError,
    SimklError,
)

# Statuses worth caching. plantowatch is deliberately absent: treating a
# wishlist entry as watched would suppress the exact titles a user wants.
CACHED_STATUSES = ("watching", "completed", "hold", "dropped")

# A title being worked through is a far better recommendation seed than one
# finished long ago, so seeds span both. Exclusions stay strict: only a
# finished title should suppress a recommendation.
SEED_STATUSES = ("watching", "completed")
EXCLUSION_STATUSES = ("completed",)


class SimklWatchHistorySync:
    """Keeps ``simkl_watched_cache`` fresh for one linked Simkl account."""

    # Floor on how often any caller can cause outbound Simkl traffic. Several
    # call sites enter this layer per job run (seeds, exclusions, the unwatched
    # gate) and cron accepts schedules as tight as */10, so the bound has to be
    # wall-clock rather than per-call.
    ACTIVITIES_COOLDOWN_SECONDS = 900

    # TMDb tolerates parallelism, but the fallback is a best-effort enrichment
    # of someone else's sync, so it stays well under any rate limit.
    TVDB_LOOKUP_CONCURRENCY = 5
    TVDB_LOOKUP_TIMEOUT = 10

    def __init__(
        self,
        client_id: str,
        db: Optional[DatabaseManager] = None,
        logger=None,
        tmdb_api_key: str = "",
    ):
        self.client_id = (client_id or "").strip()
        self.db = db or DatabaseManager()
        self.logger = logger or LoggerManager.get_logger("SimklWatchHistorySync")
        self.tmdb_api_key = (tmdb_api_key or "").strip()
        # A title unmapped in "watching" is still unmapped in "completed", and
        # a failed lookup is worth remembering too: retrying it once per bucket
        # multiplies the cost of exactly the libraries that need it most.
        self._tvdb_to_tmdb: dict[str, Optional[str]] = {}

    async def ensure_synced(self, link: dict, access_token: str) -> bool:
        """Bring the cache up to date if needed.

        Args:
            link: A ``simkl_account_links`` row.
            access_token: The user's Simkl token.

        Returns:
            bool: True when the cache is usable. False only when a sync was
            required and failed in a way that leaves nothing to serve.
        """
        link_id = link["id"]
        state = self.db.get_simkl_sync_state(link_id)
        now = int(time.time())

        last_check = state.get("last_activities_check_at") or 0
        if last_check and (now - int(last_check)) < self.ACTIVITIES_COOLDOWN_SECONDS:
            self.logger.debug(
                "Simkl link %s inside the activities cooldown; serving cache", link_id
            )
            return True

        try:
            async with SimklClient(
                self.client_id, access_token=access_token, link_id=link_id
            ) as client:
                return await self._sync_with_client(client, link_id, state)
        except (SimklAuthError, SimklClientIdError):
            raise
        except SimklError as exc:
            self.logger.warning("Simkl sync failed for link %s: %s", link_id, exc)
            # Stale data still beats no data; the cache is only unusable when
            # it is also empty.
            return bool(self.db.get_simkl_watched_cache(link_id))

    async def _sync_with_client(
        self, client: SimklClient, link_id: int, state: dict
    ) -> bool:
        activities = await client.get_activities()
        self.db.update_simkl_sync_state(link_id, mark_activities_check=True)

        stored = state.get("activities") or {}
        first_sync = not state.get("last_full_sync_at")

        pulls = self._plan_pulls(activities, stored, first_sync)
        reconciles = self._plan_reconciles(activities, stored) if not first_sync else []

        if not pulls and not reconciles:
            self.logger.debug("Simkl link %s: no activity change, cache is current", link_id)
            # An account whose lists are all empty plans no pulls, so this is
            # also the path a first sync of an empty library takes. It still
            # has to be recorded, or the UI reads "linked but never synced"
            # forever instead of "linked, and there is genuinely nothing here".
            if first_sync:
                self.db.update_simkl_sync_state(
                    link_id, activities=activities, mark_full_sync=True
                )
            return True

        total = 0
        dropped = 0
        for media_type, status, date_from in pulls:
            entries = await client.get_all_items(media_type, status, date_from=date_from)
            items, missed = self._normalize_entries(entries, media_type)
            items = await self._resolve_missing_tmdb_ids(items)
            usable = [i for i in items if i.get("tmdb_id")]
            dropped += missed + (len(items) - len(usable))
            total += self.db.upsert_simkl_watched_cache(link_id, usable)

        swept = []
        skipped_sweeps = []
        for media_type in reconciles:
            entries = await client.get_all_items(media_type, "", ids_only=True)
            present = self._extract_simkl_ids(entries, media_type)
            if present is None:
                # Entries came back but none carried a readable id, so the id
                # set cannot be trusted. Reconciling against it would delete
                # rows the user still has, and deltas only re-add a title once
                # its own timestamp moves, so the loss would outlive the bad
                # response.
                self.logger.warning(
                    "Simkl link %s: none of the %d %s entries carried a readable id; "
                    "skipping the removal sweep rather than dropping the cache",
                    link_id, len(entries), media_type,
                )
                skipped_sweeps.append(media_type)
                continue
            removed = self.db.reconcile_simkl_watched_cache(link_id, media_type, present)
            swept.append(media_type)
            if removed:
                self.logger.info(
                    "Simkl link %s: dropped %d %s no longer in the library",
                    link_id, removed, media_type,
                )

        # Only now that every pull succeeded is it safe to advance the stored
        # timestamps. Saving after a partial failure would permanently skip the
        # deltas belonging to whichever bucket failed.
        self.db.update_simkl_sync_state(
            link_id,
            activities=self._activities_to_store(activities, stored, skipped_sweeps),
            mark_full_sync=first_sync or bool(swept),
        )

        if dropped:
            self.logger.info(
                "Simkl link %s: %d entries had no resolvable TMDb id and were skipped",
                link_id, dropped,
            )
        self.logger.info("Simkl link %s: cached %d entries", link_id, total)
        return True

    def _plan_pulls(
        self, activities: dict, stored: dict, first_sync: bool
    ) -> list[tuple[str, str, Optional[str]]]:
        """Decide which ``(type, status)`` buckets to fetch, and from when.

        Each bucket is gated on its own timestamp rather than the payload-wide
        ``all`` value, so a change to one list never re-pulls the others.
        """
        pulls: list[tuple[str, str, Optional[str]]] = []
        for media_type, statuses in SimklClient.STATUSES_BY_TYPE.items():
            activities_key = SimklClient.ACTIVITIES_KEY_BY_TYPE[media_type]
            current_bucket = activities.get(activities_key) or {}
            stored_bucket = stored.get(activities_key) or {}
            for status in statuses:
                if status not in CACHED_STATUSES:
                    continue
                current = current_bucket.get(status)
                if not current:
                    # Simkl reports null for a bucket the user has never used.
                    continue
                if first_sync:
                    pulls.append((media_type, status, None))
                    continue
                previous = stored_bucket.get(status)
                if previous != current:
                    pulls.append((media_type, status, previous))
        return pulls

    @classmethod
    def _extract_simkl_ids(cls, entries: list, media_type: str) -> Optional[list[str]]:
        """Pull the Simkl ids out of an ``ids_only`` response.

        Returns:
            The ids found, or None when entries were returned but not one of
            them could be read. An empty list means the library really is
            empty, which the caller may act on; None means the response shape
            was not understood, which it must not.
        """
        ids = [
            str(cls._media_object(entry, media_type).get("ids", {}).get("simkl"))
            for entry in entries or []
            if isinstance(entry, dict)
            and cls._media_object(entry, media_type).get("ids", {}).get("simkl")
        ]
        if entries and not ids:
            return None
        return ids

    @staticmethod
    def _activities_to_store(
        activities: dict, stored: dict, skipped_sweeps: list[str]
    ) -> dict:
        """Hold back the removal clock for any type whose sweep was skipped.

        ``removed_from_list`` advancing is the only signal that a sweep is due.
        Persisting the new value for a type we declined to sweep would consume
        that signal, so the removal would never be noticed again.
        """
        if not skipped_sweeps:
            return activities

        held = dict(activities)
        for media_type in skipped_sweeps:
            key = SimklClient.ACTIVITIES_KEY_BY_TYPE[media_type]
            bucket = dict(held.get(key) or {})
            previous = (stored.get(key) or {}).get("removed_from_list")
            if previous is None:
                bucket.pop("removed_from_list", None)
            else:
                bucket["removed_from_list"] = previous
            held[key] = bucket
        return held

    @staticmethod
    def _plan_reconciles(activities: dict, stored: dict) -> list[str]:
        """Return types whose ``removed_from_list`` timestamp advanced.

        Deletions never appear in a ``date_from`` delta, so the only way to
        notice one is a full id sweep. Driving that off an actual removal
        signal keeps it rare, where a periodic sweep would reintroduce the
        untriggered polling this module exists to avoid.
        """
        types = []
        for media_type, activities_key in SimklClient.ACTIVITIES_KEY_BY_TYPE.items():
            current = (activities.get(activities_key) or {}).get("removed_from_list")
            previous = (stored.get(activities_key) or {}).get("removed_from_list")
            if current and current != previous:
                types.append(media_type)
        return types

    # ---- Normalization --------------------------------------------------------

    @staticmethod
    def _media_object(entry: dict, media_type: str) -> dict:
        """Unwrap an entry's media object.

        Anime entries nest under ``show`` exactly as TV does, so the key
        follows the shape rather than the requested type.
        """
        if media_type == "movies":
            return entry.get("movie") or {}
        return entry.get("show") or entry.get("movie") or {}

    def _normalize_entries(
        self, entries: list, media_type: str
    ) -> tuple[list[dict[str, Any]], int]:
        """Flatten Simkl entries into cache rows.

        Returns:
            tuple: the normalized rows, and a count of entries skipped for
            having no usable media object at all.
        """
        items: list[dict[str, Any]] = []
        skipped = 0
        for entry in entries or []:
            if not isinstance(entry, dict):
                skipped += 1
                continue
            media = self._media_object(entry, media_type)
            ids = media.get("ids") or {}
            simkl_id = ids.get("simkl")
            if not simkl_id:
                skipped += 1
                continue

            items.append({
                "simkl_id": str(simkl_id),
                "simkl_type": media_type,
                "media_type": self._resolve_media_type(entry, media_type),
                "status": entry.get("status") or "",
                "tmdb_id": str(ids["tmdb"]) if ids.get("tmdb") else None,
                "tvdb_id": str(ids["tvdb"]) if ids.get("tvdb") else None,
                "title": media.get("title") or "",
                "year": media.get("year"),
                "last_watched_at": self._parse_iso(entry.get("last_watched_at"))
                or self._parse_iso(entry.get("added_to_watchlist_at")),
            })
        return items, skipped

    @staticmethod
    def _resolve_media_type(entry: dict, media_type: str) -> str:
        """Map a Simkl type onto the app's ``movie``/``tv`` vocabulary."""
        if media_type == "movies":
            return "movie"
        if media_type == "anime":
            return "movie" if str(entry.get("anime_type") or "").lower() == "movie" else "tv"
        return "tv"

    async def _resolve_missing_tmdb_ids(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Fill in TMDb ids via TVDb for entries Simkl didn't map.

        Anime is the main reason to link Simkl alongside Trakt, and OVAs,
        specials, and shorts are the entries most likely to arrive without a
        TMDb id. Recovering them through TVDb keeps that library from silently
        vanishing.

        A first sync of a large anime library can leave hundreds of entries
        unmapped, so the lookups share one session and run in a bounded pool
        rather than one-at-a-time. Results are memoized for the lifetime of the
        sync because the same title reappears across status buckets.
        """
        missing = [i for i in items if not i.get("tmdb_id") and i.get("tvdb_id")]
        if not missing or not self.tmdb_api_key:
            return items

        semaphore = asyncio.Semaphore(self.TVDB_LOOKUP_CONCURRENCY)
        timeout = aiohttp.ClientTimeout(total=self.TVDB_LOOKUP_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async def resolve(item):
                tvdb_id = item["tvdb_id"]
                if tvdb_id in self._tvdb_to_tmdb:
                    resolved = self._tvdb_to_tmdb[tvdb_id]
                else:
                    async with semaphore:
                        resolved = await self._find_tmdb_from_tvdb(session, tvdb_id)
                    self._tvdb_to_tmdb[tvdb_id] = resolved
                if resolved:
                    item["tmdb_id"] = str(resolved)

            await asyncio.gather(*(resolve(item) for item in missing))
        return items

    async def _find_tmdb_from_tvdb(self, session, tvdb_id: str) -> Optional[str]:
        url = f"https://api.themoviedb.org/3/find/{tvdb_id}"
        params = {"api_key": self.tmdb_api_key, "external_source": "tvdb_id"}
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                data = await response.json()
            for key in ("tv_results", "movie_results"):
                results = data.get(key) or []
                if results:
                    return results[0].get("id")
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            self.logger.debug("TVDb->TMDb lookup failed for %s: %s", tvdb_id, exc)
        return None

    @staticmethod
    def _parse_iso(value: Optional[str]) -> int:
        """Convert a Simkl ISO 8601 timestamp to epoch seconds."""
        if not value:
            return 0
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except (ValueError, TypeError):
            return 0
