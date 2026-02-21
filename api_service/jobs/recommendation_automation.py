"""
Recommendation Automation for executing recommendation jobs.
Processes user watch history and finds similar content via TMDb.
"""
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.db.job_repository import JobRepository
from api_service.handler.jellyfin_handler import JellyfinHandler
from api_service.handler.plex_handler import PlexHandler
from api_service.services.jellyfin.jellyfin_client import JellyfinClient
from api_service.services.jellyseer.seer_client import SeerClient
from api_service.services.plex.plex_client import PlexClient
from api_service.services.tmdb.tmdb_client import TMDbClient


@dataclass
class ExecutionResult:
    """Result of a job execution."""
    success: bool
    results_count: int
    requested_count: int
    error_message: Optional[str] = None


class RecommendationAutomation:
    """
    Automates the process of retrieving watched content from Jellyfin/Plex,
    finding similar content via TMDb, and requesting it via Jellyseer/Overseer.

    This is similar to ContentAutomation but configured per-job with:
    - Specific user IDs to monitor
    - Custom filters
    - Scheduled execution via JobManager
    """

    def __init__(self):
        """Initialize with logger only. Use create() for full initialization."""
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.job_id: Optional[int] = None
        self.job_data: Optional[Dict[str, Any]] = None
        self.repository: Optional[JobRepository] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.media_handler = None
        self.env_vars: Optional[Dict[str, Any]] = None

    @classmethod
    async def create(cls, job_id: int) -> 'RecommendationAutomation':
        """
        Async factory method to create and initialize RecommendationAutomation.

        Args:
            job_id: ID of the recommendation job to execute.

        Returns:
            Initialized RecommendationAutomation instance.

        Raises:
            ValueError: If job not found.
        """
        instance = cls()
        instance.job_id = job_id
        instance.repository = JobRepository()
        instance.db_manager = DatabaseManager()

        # Load job data
        instance.job_data = instance.repository.get_job(job_id)
        if not instance.job_data:
            raise ValueError(f"Job not found: {job_id}")

        if instance.job_data.get('job_type') != 'recommendation':
            raise ValueError(f"Job {job_id} is not a recommendation job")

        instance.logger.info(f"Initializing RecommendationAutomation for job: {instance.job_data['name']}")

        # Load environment variables
        instance.env_vars = load_env_vars()

        # Initialize components based on job configuration
        await instance._initialize_components()

        instance.logger.info("RecommendationAutomation initialized successfully")
        return instance

    async def _initialize_components(self):
        """Initialize all required components for the recommendation job."""
        job_filters = self.job_data.get('filters', {})
        job_user_ids = self.job_data.get('user_ids', [])
        media_type = self.job_data.get('media_type', 'both')
        max_results = self.job_data.get('max_results', 20)

        # Get global settings but allow job to override some
        selected_service = self.env_vars['SELECTED_SERVICE']

        # Number of seasons filter - job setting overrides global
        number_of_seasons = job_filters.get('min_seasons')
        if number_of_seasons is None:
            number_of_seasons = self.env_vars.get('FILTER_NUM_SEASONS') or "all"

        # Exclusion settings - job overrides global
        exclude_downloaded = job_filters.get('exclude_downloaded')
        if exclude_downloaded is None:
            exclude_downloaded = self.env_vars.get('EXCLUDE_DOWNLOADED', True)

        exclude_requested = job_filters.get('exclude_requested')
        if exclude_requested is None:
            exclude_requested = self.env_vars.get('EXCLUDE_REQUESTED', True)

        # Get similar content limits from job filters or use defaults
        max_similar_movie = job_filters.get('max_similar_movie', int(self.env_vars.get('MAX_SIMILAR_MOVIE', '3')))
        max_similar_tv = job_filters.get('max_similar_tv', int(self.env_vars.get('MAX_SIMILAR_TV', '2')))
        max_content = job_filters.get('max_content', int(self.env_vars.get('MAX_CONTENT_CHECKS', '10')))
        search_size = job_filters.get('search_size', int(self.env_vars.get('SEARCH_SIZE', '20')))

        # TMDB filters from job configuration
        tmdb_threshold = job_filters.get('vote_average_gte', int(self.env_vars.get('FILTER_TMDB_THRESHOLD') or 60))
        # Convert 0-10 scale to 0-100 if needed
        if tmdb_threshold <= 10:
            tmdb_threshold = int(tmdb_threshold * 10)
        tmdb_min_votes = job_filters.get('vote_count_gte', int(self.env_vars.get('FILTER_TMDB_MIN_VOTES') or 20))

        # Include no rating - job overrides global
        include_no_ratings = job_filters.get('include_no_rating')
        if include_no_ratings is None:
            include_no_ratings = self.env_vars.get('FILTER_INCLUDE_NO_RATING', True) == True

        filter_release_year = job_filters.get('release_year_gte', int(self.env_vars.get('FILTER_RELEASE_YEAR') or 0))

        # Language filter
        filter_language = []
        if job_filters.get('with_original_language'):
            filter_language = [job_filters['with_original_language']]
        elif self.env_vars.get('FILTER_LANGUAGE'):
            filter_language = self.env_vars.get('FILTER_LANGUAGE', [])
            if not isinstance(filter_language, list):
                filter_language = []

        # Genre exclude filter
        filter_genre = job_filters.get('without_genres', [])
        if not filter_genre:
            filter_genre_raw = self.env_vars.get('FILTER_GENRES_EXCLUDE', [])
            filter_genre = filter_genre_raw if isinstance(filter_genre_raw, list) else []

        # Streaming provider region - job overrides global
        filter_region_provider = job_filters.get('watch_region')
        if not filter_region_provider:
            filter_region_provider = self.env_vars.get('FILTER_REGION_PROVIDER', None)

        # Streaming services - job overrides global
        filter_streaming_services = job_filters.get('with_watch_providers')
        if not filter_streaming_services:
            filter_streaming_raw = self.env_vars.get('FILTER_STREAMING_SERVICES', [])
            filter_streaming_services = filter_streaming_raw if isinstance(filter_streaming_raw, list) else []

        # LLM enhancement - job setting overrides global; verify LLM is actually configured
        job_use_llm = job_filters.get('use_llm', None)
        if job_use_llm:
            from api_service.services.llm.llm_service import get_llm_client
            if not get_llm_client():
                self.logger.warning("Job has AI enhancement enabled but LLM is not configured. Falling back to standard algorithm.")
                job_use_llm = False

        # Anime profile configuration
        anime_profile_config_raw = self.env_vars.get('SEER_ANIME_PROFILE_CONFIG', {})
        anime_profile_config = anime_profile_config_raw if isinstance(anime_profile_config_raw, dict) else {}

        # Initialize Jellyseer client
        self.logger.info("Initializing Jellyseer client")
        seer_client = SeerClient(
            self.env_vars['SEER_API_URL'],
            self.env_vars['SEER_TOKEN'],
            self.env_vars['SEER_USER_NAME'],
            self.env_vars['SEER_USER_PSW'],
            self.env_vars['SEER_SESSION_TOKEN'],
            number_of_seasons,
            exclude_downloaded,
            exclude_requested,
            anime_profile_config
        )
        await seer_client.init()

        # Initialize TMDb client with job-specific filters
        self.logger.info("Initializing TMDb client with job filters")
        tmdb_client = TMDbClient(
            self.env_vars['TMDB_API_KEY'],
            search_size,
            tmdb_threshold,
            tmdb_min_votes,
            include_no_ratings,
            filter_release_year,
            filter_language,
            filter_genre,
            filter_region_provider,
            filter_streaming_services
        )

        # Determine which users to process
        selected_users = self._get_selected_users(job_user_ids)

        # Initialize media service handler
        if selected_service in ('jellyfin', 'emby'):
            await self._init_jellyfin_handler(
                seer_client, tmdb_client, max_similar_movie, max_similar_tv,
                selected_users, max_content, job_use_llm
            )
        elif selected_service == 'plex':
            await self._init_plex_handler(
                seer_client, tmdb_client, max_similar_movie, max_similar_tv,
                selected_users, max_content, job_use_llm
            )
        else:
            raise ValueError(f"Unsupported service: {selected_service}")

    def _get_selected_users(self, job_user_ids: List) -> List[Dict]:
        """
        Get the list of users to process based on job configuration.

        Args:
            job_user_ids: User IDs configured for this job (empty = all users)

        Returns:
            List of user dicts to process
        """
        # Get global selected users from config
        selected_users_raw = self.env_vars.get('SELECTED_USERS') or []
        if not isinstance(selected_users_raw, list):
            selected_users_raw = []

        # Normalize users to dict format
        all_users = []
        for user in selected_users_raw:
            if isinstance(user, dict) and 'id' in user:
                all_users.append(user)
            elif isinstance(user, str):
                all_users.append({'id': user, 'name': user})

        # If job specifies specific users, filter to only those
        if job_user_ids:
            job_user_id_set = set(str(uid) for uid in job_user_ids)
            return [u for u in all_users if str(u['id']) in job_user_id_set]

        # Otherwise return all users
        return all_users

    async def _init_jellyfin_handler(
        self, seer_client, tmdb_client, max_similar_movie, max_similar_tv,
        selected_users, max_content, use_llm=None
    ):
        """Initialize Jellyfin handler."""
        self.logger.info("Initializing Jellyfin client")

        jellyfin_libraries_raw = self.env_vars.get('JELLYFIN_LIBRARIES')
        jellyfin_libraries = jellyfin_libraries_raw if isinstance(jellyfin_libraries_raw, list) else []

        jellyfin_client = JellyfinClient(
            self.env_vars['JELLYFIN_API_URL'],
            self.env_vars['JELLYFIN_TOKEN'],
            max_content,
            jellyfin_libraries
        )
        await jellyfin_client.init_existing_content()

        # Build library anime map
        jellyfin_anime_map = {}
        for lib in jellyfin_libraries:
            if isinstance(lib, dict) and lib.get('name'):
                jellyfin_anime_map[lib['name']] = lib.get('is_anime', False)

        self.media_handler = JellyfinHandler(
            jellyfin_client, seer_client, tmdb_client, self.logger,
            max_similar_movie, max_similar_tv,
            selected_users, jellyfin_anime_map, use_llm=use_llm
        )
        self.logger.info("Jellyfin handler initialized")

    async def _init_plex_handler(
        self, seer_client, tmdb_client, max_similar_movie, max_similar_tv,
        selected_users, max_content, use_llm=None
    ):
        """Initialize Plex handler."""
        self.logger.info("Initializing Plex client")

        plex_libraries_raw = self.env_vars.get('PLEX_LIBRARIES')
        plex_libraries = plex_libraries_raw if isinstance(plex_libraries_raw, list) else []

        plex_client = PlexClient(
            api_url=self.env_vars['PLEX_API_URL'],
            token=self.env_vars['PLEX_TOKEN'],
            max_content=max_content,
            library_ids=plex_libraries,
            user_ids=selected_users
        )
        await plex_client.init_existing_content()

        # Build library anime map
        plex_anime_map = {}
        for lib in plex_libraries:
            if isinstance(lib, dict) and lib.get('id'):
                plex_anime_map[str(lib['id'])] = lib.get('is_anime', False)

        self.media_handler = PlexHandler(
            plex_client, seer_client, tmdb_client, self.logger,
            max_similar_movie, max_similar_tv,
            plex_anime_map, use_llm=use_llm
        )
        self.logger.info("Plex handler initialized")

    async def run(self) -> ExecutionResult:
        """
        Execute the recommendation job.

        Returns:
            ExecutionResult with execution details.
        """
        if not self.job_data:
            return ExecutionResult(
                success=False,
                results_count=0,
                requested_count=0,
                error_message="Job not initialized"
            )

        self.logger.info(f"Starting recommendation job: {self.job_data['name']}")
        exec_id = self.repository.log_execution_start(self.job_id)

        try:
            # Get initial request count
            initial_count = self._get_request_count()

            # Process recent items (this is the main recommendation logic)
            await self.media_handler.process_recent_items()

            # Calculate how many new requests were made
            final_count = self._get_request_count()
            requested_count = max(0, final_count - initial_count)

            # For results_count, we use the number of items processed
            # This is an estimate since handlers don't return this directly
            results_count = requested_count  # Approximation

            self.logger.info(f"Job completed: approximately {requested_count} new requests")

            # Log success
            self.repository.log_execution_end(
                exec_id=exec_id,
                status='completed',
                results_count=results_count,
                requested_count=requested_count
            )

            return ExecutionResult(
                success=True,
                results_count=results_count,
                requested_count=requested_count
            )

        except Exception as e:
            error_msg = str(e) if str(e) else type(e).__name__
            self.logger.error(f"Job failed: {error_msg}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")

            # Log failure
            self.repository.log_execution_end(
                exec_id=exec_id,
                status='failed',
                results_count=0,
                requested_count=0,
                error_message=error_msg
            )

            return ExecutionResult(
                success=False,
                results_count=0,
                requested_count=0,
                error_message=error_msg
            )

    def _get_request_count(self) -> int:
        """Get current request count from database."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM requests")
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception:
            return 0


async def execute_recommendation_job(job_id: int) -> ExecutionResult:
    """
    Execute a recommendation job by ID.
    This is the function to be called by JobManager.

    Args:
        job_id: ID of the job to execute.

    Returns:
        ExecutionResult with execution details.
    """
    logger = LoggerManager.get_logger("RecommendationJobExecutor")
    logger.info(f"Starting execution of recommendation job: {job_id}")

    try:
        automation = await RecommendationAutomation.create(job_id)
        result = await automation.run()
        return result
    except Exception as e:
        logger.error(f"Failed to execute job {job_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return ExecutionResult(
            success=False,
            results_count=0,
            requested_count=0,
            error_message=str(e)
        )
