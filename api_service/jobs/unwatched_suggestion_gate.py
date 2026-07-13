"""Scheduled-job gate for stale, unwatched SuggestArr requests."""
from datetime import datetime, timedelta, timezone

from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.config_service import ConfigService


class UnwatchedSuggestionGate:
    def __init__(self):
        self.db = DatabaseManager()
        self.logger = LoggerManager.get_logger(self.__class__.__name__)

    async def allowed_slices(self, job):
        """Return runnable ``{media_type, user_ids}`` slices; fail open on provider errors."""
        if not job.get("prevent_suggestions_if_unwatched") or job.get("job_type") == "discover":
            return None
        users = [str(value) for value in job.get("user_ids") or []]
        if not users:
            return None
        types = ["movie", "tv"] if job.get("media_type") == "both" else [job["media_type"]]
        try:
            watched = await self._watched_ids(users)
        except Exception as exc:
            self.logger.warning("Could not evaluate unwatched suggestions; allowing job %s: %s", job["id"], exc)
            return None

        slices = []
        for media_type in types:
            for user in users:
                if self._is_allowed(job, user, media_type, watched.get(user, {}).get(media_type, set())):
                    slices.append({"media_type": media_type, "user_ids": [user]})
        return slices

    def _is_allowed(self, job, user_id, media_type, watched_ids):
        ph = "%s" if self.db.db_type in ("mysql", "mariadb", "postgres") else "?"
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT reset_at FROM unwatched_suggestion_cycles WHERE job_id={ph} AND user_id={ph} AND media_type={ph}",
                (job["id"], user_id, media_type),
            )
            row = cursor.fetchone()
            reset_at = row[0] if row else None
            query = f"SELECT tmdb_request_id, requested_at FROM requests WHERE requested_by='SuggestArr' AND user_id={ph} AND media_type={ph}"
            params = [user_id, media_type]
            if reset_at:
                query += f" AND requested_at > {ph}"
                params.append(reset_at)
            query += " ORDER BY requested_at ASC"
            cursor.execute(query, tuple(params))
            requests = cursor.fetchall()

            if any(str(item[0]) in watched_ids for item in requests):
                cursor.execute(
                    f"DELETE FROM unwatched_suggestion_cycles WHERE job_id={ph} AND user_id={ph} AND media_type={ph}",
                    (job["id"], user_id, media_type),
                )
                cursor.execute(
                    f"INSERT INTO unwatched_suggestion_cycles (job_id,user_id,media_type,reset_at) VALUES ({ph},{ph},{ph},CURRENT_TIMESTAMP)",
                    (job["id"], user_id, media_type),
                )
                conn.commit()
                return True
            if not requests:
                return True
            requested_at = requests[0][1]
            if isinstance(requested_at, str):
                requested_at = datetime.fromisoformat(requested_at.replace("Z", "+00:00"))
            if requested_at.tzinfo is None:
                requested_at = requested_at.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < requested_at + timedelta(days=int(job.get("unwatched_suggestion_days") or 7))

    async def _watched_ids(self, user_ids):
        config = ConfigService.get_runtime_config()
        service = config.get("SELECTED_SERVICE")
        watched = {user: {"movie": set(), "tv": set()} for user in user_ids}
        if service in ("jellyfin", "emby"):
            from api_service.services.jellyfin.jellyfin_client import JellyfinClient
            client = JellyfinClient(config.get("JELLYFIN_API_URL"), config.get("JELLYFIN_TOKEN"), 100, config.get("JELLYFIN_LIBRARIES") or [])
            async with client:
                for user in user_ids:
                    groups = await client.get_recent_items({"id": user, "name": user})
                    for items in (groups or {}).values():
                        for item in items:
                            media_type = "tv" if item.get("Type") == "Episode" else "movie"
                            ids = item.get("SeriesProviderIds") if media_type == "tv" else item.get("ProviderIds")
                            tmdb_id = (ids or {}).get("Tmdb")
                            if tmdb_id:
                                watched[user][media_type].add(str(tmdb_id))
        elif service == "plex":
            from api_service.services.plex.plex_client import PlexClient
            for user in user_ids:
                client = PlexClient(config.get("PLEX_TOKEN"), config.get("PLEX_API_URL"), 100, config.get("PLEX_LIBRARIES") or [], user_ids=[user])
                async with client:
                    for item in await client.get_recent_items():
                        media_type = "tv" if item.get("type") == "episode" else "movie"
                        key = item.get("grandparentKey") if media_type == "tv" else item.get("key")
                        tmdb_id = await client.get_metadata_provider_id(key) if key else None
                        if tmdb_id:
                            watched[user][media_type].add(str(tmdb_id))

        from api_service.services.trakt.media_user_augmentor import TraktWatchHistorySource
        source = TraktWatchHistorySource(
            config.get("TRAKT_CLIENT_ID", ""), config.get("TRAKT_CLIENT_SECRET", ""), self.db
        )
        for user in user_ids:
            try:
                identity = self.db.get_media_user_identity(service, user)
            except ValueError:
                continue
            trakt = await source.get_watched_ids(identity["id"])
            for media_type in ("movie", "tv"):
                watched[user][media_type].update(trakt.get(media_type, set()))
        return watched
