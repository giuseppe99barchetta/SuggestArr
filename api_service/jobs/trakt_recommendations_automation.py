"""
Trakt Recommendations Automation for executing trakt_recommendations jobs.
Fetches personalized recommendations from Trakt and requests them via Seer.
"""
import traceback
from typing import Any, Dict, List, Optional

from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.db.job_repository import JobRepository
from api_service.jobs.discover_automation import ExecutionResult
from api_service.jobs.recommendation_automation import (
    _resolve_honor_seer_discovery,
    _resolve_year_range_filters,
)
from api_service.services.config_service import ConfigService
from api_service.services.filter_normalization import normalize_filters
from api_service.services.request_sources import TRAKT_RECOMMENDATIONS_SOURCE
from api_service.services.seer.seer_client import SeerClient
from api_service.services.trakt.media_user_augmentor import TraktAccountResolver
from api_service.services.trakt.trakt_client import TraktClient
from api_service.services.tmdb.tmdb_client import TMDbClient
from api_service.utils.tmdb_images import tmdb_image_url


class TraktRecommendationsAutomation:
    """Automates fetching Trakt personalized recommendations and requesting via Seer."""

    def __init__(self):
        """Initialize with logger only. Use create() for full initialization."""
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.job_id: Optional[int] = None
        self.job_data: Optional[Dict[str, Any]] = None
        self.seer_client: Optional[SeerClient] = None
        self.tmdb_client: Optional[TMDbClient] = None
        self.trakt_client: Optional[TraktClient] = None
        self.repository: Optional[JobRepository] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.local_content: Dict[str, set[str]] = {}
        self.seer_discovered_ids: set[str] = set()
        self.env_vars: Dict[str, Any] = {}

    @classmethod
    async def create(cls, job_id: int, dry_run: bool = False, overrides=None) -> "TraktRecommendationsAutomation":
        """Create and initialize TraktRecommendationsAutomation for a job.

        Args:
            job_id: ID of the trakt_recommendations job to execute.
            dry_run: If True, skip request-cache sync during initialization.

        Returns:
            Initialized TraktRecommendationsAutomation instance.

        Raises:
            ValueError: If the job is missing or misconfigured.
        """
        instance = cls()
        instance.job_id = job_id
        instance.repository = JobRepository()
        instance.db_manager = DatabaseManager()
        instance.env_vars = ConfigService.get_runtime_config()

        instance.job_data = instance.repository.get_job(job_id)
        if not instance.job_data:
            raise ValueError(f"Job not found: {job_id}")
        if overrides:
            instance.job_data.update(overrides)
        if instance.job_data.get("job_type") != "trakt_recommendations":
            raise ValueError(f"Job {job_id} is not a trakt_recommendations job")

        instance.logger.info(
            "Initializing TraktRecommendationsAutomation for job: %s",
            instance.job_data["name"],
        )
        await instance._initialize_components(dry_run=dry_run)
        instance.logger.info("TraktRecommendationsAutomation initialized successfully")
        return instance

    async def _initialize_components(self, dry_run: bool = False) -> None:
        """Initialize Seer, Trakt, and TMDb clients from job configuration."""
        job_filters = self.job_data.get("filters", {})
        normalized_filters = normalize_filters(job_filters)

        number_of_seasons = self.env_vars.get("FILTER_NUM_SEASONS") or "all"
        request_first_season_only = job_filters.get("request_first_season_only")
        if request_first_season_only is None:
            request_first_season_only = self.env_vars.get("REQUEST_FIRST_SEASON_ONLY", False)

        exclude_downloaded = job_filters.get("exclude_downloaded")
        if exclude_downloaded is None:
            exclude_downloaded = self.env_vars.get("EXCLUDE_DOWNLOADED", True)
        exclude_requested = job_filters.get("exclude_requested")
        if exclude_requested is None:
            exclude_requested = self.env_vars.get("EXCLUDE_REQUESTED", True)

        anime_profile_config = self.env_vars.get("SEER_ANIME_PROFILE_CONFIG", {})
        if not isinstance(anime_profile_config, dict):
            anime_profile_config = {}

        self.seer_client = SeerClient(
            self.env_vars["SEER_API_URL"],
            self.env_vars["SEER_TOKEN"],
            self.env_vars["SEER_USER_NAME"],
            self.env_vars["SEER_USER_PSW"],
            self.env_vars["SEER_SESSION_TOKEN"],
            number_of_seasons,
            exclude_downloaded,
            exclude_requested,
            anime_profile_config,
            request_first_season_only,
            queue_context={**self.job_data, 'job_id': self.job_id},
        )
        if dry_run:
            self.logger.info("Dry-run mode: skipping Seer request cache sync.")
        else:
            await self.seer_client.init()
        self.local_content = await self._load_existing_content()
        if _resolve_honor_seer_discovery(job_filters, self.env_vars):
            self.seer_discovered_ids = self._get_seer_discovered_tmdb_ids()

        self.trakt_client = self._build_trakt_client()

        search_size = int(job_filters.get("search_size") or self.env_vars.get("SEARCH_SIZE") or 20)
        tmdb_threshold = normalized_filters.get("min_rating")
        if tmdb_threshold is None:
            tmdb_threshold = int(self.env_vars.get("FILTER_TMDB_THRESHOLD") or 60)
        if tmdb_threshold <= 10:
            tmdb_threshold = int(tmdb_threshold * 10)
        tmdb_min_votes = job_filters.get(
            "vote_count_gte",
            int(self.env_vars.get("FILTER_TMDB_MIN_VOTES") or 20),
        )
        include_no_ratings = job_filters.get("include_no_rating")
        if include_no_ratings is None:
            include_no_ratings = self.env_vars.get("FILTER_INCLUDE_NO_RATING", True) is True

        filter_release_year, filter_release_year_to = _resolve_year_range_filters(
            {**job_filters, **normalized_filters},
            self.env_vars,
        )

        filter_language = []
        if "with_original_language" in job_filters:
            filter_language = ([normalized_filters["language"]]
                               if normalized_filters.get("language") else [])
        elif normalized_filters.get("language"):
            filter_language = [normalized_filters["language"]]
        elif self.env_vars.get("FILTER_LANGUAGE"):
            filter_language = self.env_vars.get("FILTER_LANGUAGE", [])
            if not isinstance(filter_language, list):
                filter_language = []

        filter_genre = job_filters.get("without_genres", [])
        if not filter_genre:
            filter_genre_raw = self.env_vars.get("FILTER_GENRES_EXCLUDE", [])
            filter_genre = filter_genre_raw if isinstance(filter_genre_raw, list) else []

        filter_region_provider = job_filters.get("watch_region") or self.env_vars.get(
            "FILTER_REGION_PROVIDER"
        )
        filter_streaming_services = job_filters.get("with_watch_providers")
        if not filter_streaming_services:
            filter_streaming_raw = self.env_vars.get("FILTER_STREAMING_SERVICES", [])
            filter_streaming_services = (
                filter_streaming_raw if isinstance(filter_streaming_raw, list) else []
            )

        filter_min_runtime = job_filters.get("min_runtime")
        if filter_min_runtime is None:
            filter_min_runtime = self.env_vars.get("FILTER_MIN_RUNTIME")

        rating_source = job_filters.get("rating_source", self.env_vars.get("FILTER_RATING_SOURCE", "tmdb"))
        job_imdb_rating = job_filters.get("imdb_rating_gte")
        if job_imdb_rating is not None:
            imdb_threshold = int(float(job_imdb_rating) * 10)
        else:
            raw = self.env_vars.get("FILTER_IMDB_THRESHOLD")
            imdb_threshold = int(raw) if raw is not None else None

        job_imdb_min_votes = job_filters.get("imdb_min_votes")
        imdb_min_votes = (
            int(job_imdb_min_votes)
            if job_imdb_min_votes is not None
            else (
                int(self.env_vars.get("FILTER_IMDB_MIN_VOTES"))
                if self.env_vars.get("FILTER_IMDB_MIN_VOTES") is not None
                else None
            )
        )

        omdb_client = None
        if rating_source in ("imdb", "both"):
            omdb_api_key = self.env_vars.get("OMDB_API_KEY", "")
            if omdb_api_key:
                from api_service.services.omdb.omdb_client import OmdbClient

                omdb_client = OmdbClient(omdb_api_key)

        job_include_tvod = job_filters.get("include_tvod")
        filter_include_tvod = (
            bool(job_include_tvod)
            if job_include_tvod is not None
            else (self.env_vars.get("FILTER_INCLUDE_TVOD", False) is True)
        )

        self.tmdb_client = TMDbClient(
            self.env_vars["TMDB_API_KEY"],
            search_size,
            tmdb_threshold,
            tmdb_min_votes,
            include_no_ratings,
            filter_release_year,
            filter_language,
            filter_genre,
            filter_region_provider,
            filter_streaming_services,
            filter_min_runtime,
            rating_source=rating_source,
            imdb_threshold=imdb_threshold,
            imdb_min_votes=imdb_min_votes,
            omdb_client=omdb_client,
            include_tvod=filter_include_tvod,
            filter_release_year_to=filter_release_year_to,
            filter_genres_include=normalized_filters.get("genres"),
        )

    def _get_seer_discovered_tmdb_ids(self) -> set[str]:
        """Return TMDb IDs discovered/requested directly in Seer."""
        query = "SELECT DISTINCT tmdb_request_id FROM requests WHERE requested_by = 'Seer'"
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                return {str(row[0]) for row in cursor.fetchall()}
        except Exception as exc:
            self.logger.warning("Could not load Seer discovery IDs: %s", exc)
            return set()

    async def _load_existing_content(self) -> Dict[str, set[str]]:
        """Load existing Plex/Jellyfin TMDB IDs for downloaded-content checks."""
        provider = str(self.env_vars.get("SELECTED_SERVICE") or "").lower()
        max_content = int(self.env_vars.get("MAX_CONTENT_CHECK") or self.env_vars.get("MAX_CONTENT") or 10)

        if provider == "jellyfin":
            from api_service.services.jellyfin.jellyfin_client import JellyfinClient

            jellyfin_libraries_raw = self.env_vars.get("JELLYFIN_LIBRARIES")
            jellyfin_libraries = jellyfin_libraries_raw if isinstance(jellyfin_libraries_raw, list) else []
            client = JellyfinClient(
                self.env_vars.get("JELLYFIN_API_URL"),
                self.env_vars.get("JELLYFIN_TOKEN"),
                max_content,
                jellyfin_libraries,
            )
            try:
                await client.init_existing_content()
                return self._existing_content_to_sets(client.existing_content)
            finally:
                await client.close()

        if provider == "plex":
            from api_service.services.plex.plex_client import PlexClient, normalize_guid_provider_id

            plex_libraries_raw = self.env_vars.get("PLEX_LIBRARIES")
            plex_libraries = plex_libraries_raw if isinstance(plex_libraries_raw, list) else []
            client = PlexClient(
                api_url=self.env_vars.get("PLEX_API_URL"),
                token=self.env_vars.get("PLEX_TOKEN"),
                max_content=max_content,
                library_ids=plex_libraries,
            )
            try:
                await client.init_existing_content()
                existing = self._existing_content_to_sets(client.existing_content)
                return {
                    media_type: {
                        normalize_guid_provider_id(f"tmdb://{tmdb_id}", "tmdb") or str(tmdb_id)
                        for tmdb_id in ids
                    }
                    for media_type, ids in existing.items()
                }
            finally:
                await client.close()

        return {}

    @staticmethod
    def _existing_content_to_sets(existing_content: Optional[Dict[str, Any]]) -> Dict[str, set[str]]:
        """Normalize client existing-content maps into media-type keyed TMDB ID sets."""
        content_sets: Dict[str, set[str]] = {}
        if not existing_content:
            return content_sets

        for media_type, items in existing_content.items():
            ids = set()
            for item in items or []:
                if isinstance(item, dict) and item.get("tmdb_id"):
                    ids.add(str(item["tmdb_id"]))
                elif item:
                    ids.add(str(item))
            if ids:
                content_sets[media_type] = ids
        return content_sets

    def _build_trakt_client(self) -> TraktClient:
        """Resolve the linked Trakt account for the configured media user."""
        user_ids = self.job_data.get("user_ids") or []
        if len(user_ids) != 1:
            raise ValueError("Trakt recommendations job requires exactly one linked media user")

        provider = str(self.env_vars.get("SELECTED_SERVICE") or "").lower()
        external_user_id = str(user_ids[0])
        identity = self.db_manager.get_media_user_identity(provider, external_user_id)
        resolved = TraktAccountResolver(self.db_manager).resolve(identity["id"])
        if not resolved:
            raise ValueError(
                f"Media user {external_user_id} has no connected Trakt account"
            )

        integrations = self.env_vars.get("integrations") or {}
        trakt_cfg = integrations.get("trakt") if isinstance(integrations.get("trakt"), dict) else {}
        client_id = str(self.env_vars.get("TRAKT_CLIENT_ID") or trakt_cfg.get("client_id") or "").strip()
        client_secret = str(
            self.env_vars.get("TRAKT_CLIENT_SECRET") or trakt_cfg.get("client_secret") or ""
        ).strip()
        if not client_id or not client_secret:
            raise ValueError("Trakt app credentials are not configured")

        return TraktClient(
            client_id,
            client_secret,
            access_token=resolved.get("access_token", ""),
            refresh_token=resolved.get("refresh_token", ""),
            expires_at=resolved.get("expires_at"),
            db=self.db_manager,
            link_id=resolved["id"],
            token_source=resolved.get("token_source", "manual_oauth"),
        )

    async def run(self, dry_run: bool = False) -> ExecutionResult:
        """Execute the Trakt recommendations job.

        Args:
            dry_run: When True, simulate without enqueueing requests.

        Returns:
            ExecutionResult with execution details.
        """
        if not self.job_data:
            return ExecutionResult(
                success=False,
                results_count=0,
                requested_count=0,
                error_message="Job not initialized",
            )

        self.logger.info(
            "%sStarting trakt recommendations job: %s",
            "[DRY RUN] " if dry_run else "",
            self.job_data["name"],
        )
        exec_id = None if dry_run else self.repository.log_execution_start(self.job_id)

        try:
            from contextlib import AsyncExitStack

            async with AsyncExitStack() as stack:
                if self.seer_client:
                    await stack.enter_async_context(self.seer_client)
                if self.tmdb_client:
                    await stack.enter_async_context(self.tmdb_client)
                    if self.tmdb_client.omdb_client:
                        await stack.enter_async_context(self.tmdb_client.omdb_client)
                if self.trakt_client:
                    await stack.enter_async_context(self.trakt_client)

                results = await self.fetch_trakt_recommendations()
            results_count = len(results)
            self.logger.info("Fetched %d Trakt recommendations after filtering", results_count)

            requested_count, dry_run_items = await self.filter_and_request(results, dry_run=dry_run)

            if not dry_run:
                self.repository.log_execution_end(
                    exec_id=exec_id,
                    status="completed",
                    results_count=results_count,
                    requested_count=requested_count,
                )

            return ExecutionResult(
                success=True,
                results_count=results_count,
                requested_count=requested_count,
                dry_run_items=dry_run_items,
            )
        except Exception as exc:
            error_msg = str(exc) if str(exc) else type(exc).__name__
            self.logger.error("Job failed: %s", error_msg)
            self.logger.error("Traceback: %s", traceback.format_exc())

            if not dry_run and exec_id is not None:
                self.repository.log_execution_end(
                    exec_id=exec_id,
                    status="failed",
                    results_count=0,
                    requested_count=0,
                    error_message=error_msg,
                )

            return ExecutionResult(
                success=False,
                results_count=0,
                requested_count=0,
                error_message=error_msg,
            )

    async def fetch_trakt_recommendations(self) -> List[Dict[str, Any]]:
        """Fetch and filter Trakt recommendations for the configured media types."""
        job_filters = self.job_data.get("filters", {})
        media_type = self.job_data.get("media_type", "movie")
        max_results = int(self.job_data.get("max_results") or 20)
        fetch_limit = max(max_results * 3, max_results)

        ignore_collected = bool(job_filters.get("ignore_collected", True))
        ignore_watched = bool(job_filters.get("ignore_watched", True))

        media_types = ["movie", "tv"] if media_type == "both" else [media_type]
        per_type_limit = fetch_limit if len(media_types) == 1 else max(fetch_limit // 2, max_results)

        raw_items: List[Dict[str, Any]] = []
        for item_type in media_types:
            trakt_items = await self.trakt_client.get_recommendations(
                item_type,
                limit=per_type_limit,
                ignore_collected=ignore_collected,
                ignore_watched=ignore_watched,
            )
            for item in trakt_items:
                raw_items.append({**item, "media_type": item_type})

        filtered: List[Dict[str, Any]] = []
        for item in raw_items:
            enriched = await self._enrich_and_filter_item(item)
            if enriched:
                filtered.append(enriched)
            if len(filtered) >= max_results:
                break
        return filtered[:max_results]

    async def _enrich_and_filter_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetch TMDb metadata and apply configured quality filters."""
        media_type = item["media_type"]
        tmdb_id = int(item["tmdb_id"])

        details = await self._fetch_tmdb_details(tmdb_id, media_type)
        if not details:
            self.logger.debug("Skipping %s: TMDb details unavailable", item.get("title"))
            return None

        filter_result = self.tmdb_client._apply_filters(details, media_type)
        if not filter_result["passed"]:
            return None

        needs_detail_call = (
            self.tmdb_client.filter_min_runtime
            or self.tmdb_client.rating_source in ("imdb", "both")
        )
        if needs_detail_call:
            extra = await self.tmdb_client._get_item_details(tmdb_id, media_type)
            runtime = extra.get("runtime") if extra else None
            imdb_id = extra.get("imdb_id") if extra else None

            if self.tmdb_client.filter_min_runtime:
                if runtime is None or runtime < self.tmdb_client.filter_min_runtime:
                    return None

            if self.tmdb_client.rating_source in ("imdb", "both") and self.tmdb_client.omdb_client:
                if not imdb_id:
                    if not self.tmdb_client.include_no_ratings:
                        return None
                else:
                    imdb_data = await self.tmdb_client.omdb_client.get_rating(imdb_id)
                    if not self.tmdb_client._apply_imdb_filter(imdb_data, details, media_type):
                        return None

        excluded, provider = await self.tmdb_client.get_watch_providers(tmdb_id, media_type)
        if excluded:
            self.logger.debug(
                "Skipping %s: available on excluded streaming provider %s",
                item.get("title"),
                provider,
            )
            return None

        return details

    async def _fetch_tmdb_details(self, tmdb_id: int, media_type: str) -> Optional[Dict[str, Any]]:
        """Load TMDb details for a recommendation item."""
        url = f"{self.tmdb_client.tmdb_api_url}/{media_type}/{tmdb_id}"
        params = {"api_key": self.tmdb_client.api_key}
        try:
            session = await self.tmdb_client._get_session()
            async with session.get(url, params=params, timeout=self.tmdb_client.REQUEST_TIMEOUT) as response:
                if response.status not in {200, 201}:
                    return None
                data = await response.json()
        except Exception as exc:
            self.logger.debug("TMDb details fetch failed for %s %s: %s", media_type, tmdb_id, exc)
            return None

        return {
            "id": data.get("id", tmdb_id),
            "title": data.get("title") or data.get("name") or "",
            "vote_average": data.get("vote_average"),
            "vote_count": data.get("vote_count"),
            "rating": data.get("vote_average"),
            "votes": data.get("vote_count"),
            "genre_ids": [genre["id"] for genre in data.get("genres", []) if genre.get("id")],
            "release_date": data.get("release_date") or data.get("first_air_date"),
            "first_air_date": data.get("first_air_date"),
            "original_language": data.get("original_language"),
            "poster_path": tmdb_image_url(data.get("poster_path"), "w500"),
            "backdrop_path": tmdb_image_url(data.get("backdrop_path"), "w1280"),
            "overview": data.get("overview"),
            "media_type": media_type,
        }

    async def filter_and_request(
        self,
        results: List[Dict[str, Any]],
        dry_run: bool = False,
    ):
        """Filter discovered content and request via Seer."""
        requested_count = 0
        dry_run_items: Optional[List[Dict[str, Any]]] = [] if dry_run else None

        for item in results:
            media_type = item.get("media_type") or self.job_data.get("media_type", "movie")
            tmdb_id = item["id"]
            title = item.get("title") or item.get("name") or "Unknown"

            try:
                if self.db_manager.check_request_exists(media_type, str(tmdb_id)):
                    continue

                if str(tmdb_id) in self.seer_discovered_ids:
                    continue

                if await self.seer_client.check_already_downloaded(
                    tmdb_id,
                    media_type,
                    self.local_content,
                ):
                    continue

                if await self.seer_client.check_already_requested(tmdb_id, media_type):
                    continue

                if dry_run:
                    dry_run_items.append(self._format_dry_run_item(media_type, item))
                    requested_count += 1
                    continue

                success = await self.seer_client.request_media(
                    media_type,
                    item,
                    source={"id": TRAKT_RECOMMENDATIONS_SOURCE},
                    user={"id": str(self.job_data["user_ids"][0])},
                )
                if success:
                    requested_count += 1
            except Exception as exc:
                self.logger.error("Error processing %s: %s", title, exc)
                continue

        return requested_count, dry_run_items

    @staticmethod
    def _format_dry_run_item(media_type: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize an item dict for dry-run output."""
        return {
            "tmdb_id": item.get("id"),
            "media_type": media_type,
            "title": item.get("title") or item.get("name"),
            "release_date": item.get("release_date") or item.get("first_air_date"),
            "poster_path": item.get("poster_path"),
            "vote_average": item.get("vote_average"),
            "vote_count": item.get("vote_count"),
            "overview": item.get("overview"),
        }


async def execute_trakt_recommendations_job(job_id: int, overrides=None) -> ExecutionResult:
    """Execute a trakt_recommendations job by ID."""
    logger = LoggerManager.get_logger("TraktRecommendationsJobExecutor")
    logger.info("Starting execution of trakt recommendations job: %s", job_id)

    try:
        automation = await TraktRecommendationsAutomation.create(job_id, overrides=overrides)
        return await automation.run()
    except Exception as exc:
        logger.error("Failed to execute job %s: %s", job_id, exc)
        logger.error("Traceback: %s", traceback.format_exc())
        return ExecutionResult(
            success=False,
            results_count=0,
            requested_count=0,
            error_message=str(exc),
        )
