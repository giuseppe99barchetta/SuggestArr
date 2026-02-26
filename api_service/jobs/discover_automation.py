"""
Discover Automation for executing discover jobs.
Fetches content from TMDb discover API and requests it via Jellyseer/Overseer.
"""
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.db.job_repository import JobRepository
from api_service.services.jellyseer.seer_client import SeerClient
from api_service.services.tmdb.tmdb_discover import TMDbDiscover


@dataclass
class ExecutionResult:
    """Result of a job execution."""
    success: bool
    results_count: int
    requested_count: int
    error_message: Optional[str] = None
    dry_run_items: Optional[List[Dict[str, Any]]] = None


class DiscoverAutomation:
    """
    Automates the process of discovering content via TMDb filters
    and requesting it via Jellyseer/Overseer.
    """

    def __init__(self):
        """Initialize with logger only. Use create() for full initialization."""
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.job_id: Optional[int] = None
        self.job_data: Optional[Dict[str, Any]] = None
        self.seer_client: Optional[SeerClient] = None
        self.tmdb_discover: Optional[TMDbDiscover] = None
        self.repository: Optional[JobRepository] = None
        self.db_manager: Optional[DatabaseManager] = None

    @classmethod
    async def create(cls, job_id: int) -> 'DiscoverAutomation':
        """
        Async factory method to create and initialize DiscoverAutomation.

        Args:
            job_id: ID of the discover job to execute.

        Returns:
            Initialized DiscoverAutomation instance.

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

        instance.logger.info(f"Initializing DiscoverAutomation for job: {instance.job_data['name']}")

        # Load environment variables
        env_vars = load_env_vars()

        # Initialize Seer client
        number_of_seasons = env_vars.get('FILTER_NUM_SEASONS') or "all"
        exclude_downloaded = env_vars.get('EXCLUDE_DOWNLOADED', True)
        exclude_requested = env_vars.get('EXCLUDE_REQUESTED', True)
        anime_profile_config = env_vars.get('SEER_ANIME_PROFILE_CONFIG', {})
        if not isinstance(anime_profile_config, dict):
            anime_profile_config = {}

        instance.seer_client = SeerClient(
            env_vars['SEER_API_URL'],
            env_vars['SEER_TOKEN'],
            env_vars['SEER_USER_NAME'],
            env_vars['SEER_USER_PSW'],
            env_vars['SEER_SESSION_TOKEN'],
            number_of_seasons,
            exclude_downloaded,
            exclude_requested,
            anime_profile_config
        )
        await instance.seer_client.init()

        # Initialize OmdbClient if API key is available (used for per-job IMDB filtering)
        omdb_api_key = env_vars.get('OMDB_API_KEY', '')
        omdb_client = None
        if omdb_api_key:
            from api_service.services.omdb.omdb_client import OmdbClient
            omdb_client = OmdbClient(omdb_api_key)
            instance.logger.debug("OmdbClient initialized for discover job IMDB filtering")

        # Initialize TMDb Discover client
        instance.tmdb_discover = TMDbDiscover(env_vars['TMDB_API_KEY'], omdb_client=omdb_client)

        instance.logger.info("DiscoverAutomation initialized successfully")
        return instance

    async def run(self, dry_run: bool = False) -> ExecutionResult:
        """
        Execute the discover job.

        Args:
            dry_run: If True, simulate execution without making actual requests.
                     Returns items that would be queued without touching download clients.

        Returns:
            ExecutionResult with execution details. When dry_run=True, dry_run_items
            contains the list of media that would have been requested.
        """
        if not self.job_data:
            return ExecutionResult(
                success=False,
                results_count=0,
                requested_count=0,
                error_message="Job not initialized"
            )

        self.logger.info(f"{'[DRY RUN] ' if dry_run else ''}Starting discover job: {self.job_data['name']}")
        exec_id = None if dry_run else self.repository.log_execution_start(self.job_id)

        try:
            from contextlib import AsyncExitStack
            async with AsyncExitStack() as stack:
                if self.seer_client:
                    await stack.enter_async_context(self.seer_client)
                if self.tmdb_discover:
                    await stack.enter_async_context(self.tmdb_discover)
                    if self.tmdb_discover.omdb_client:
                        await stack.enter_async_context(self.tmdb_discover.omdb_client)

                # Fetch discover results
                results = await self.fetch_discover_results()
            results_count = len(results)

            self.logger.info(f"Discovered {results_count} items")

            # Filter and (optionally) request content
            requested_count, dry_run_items = await self.filter_and_request(results, dry_run=dry_run)

            self.logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Job completed: "
                f"{results_count} found, {requested_count} {'would be ' if dry_run else ''}requested"
            )

            if not dry_run:
                self.repository.log_execution_end(
                    exec_id=exec_id,
                    status='completed',
                    results_count=results_count,
                    requested_count=requested_count
                )

            return ExecutionResult(
                success=True,
                results_count=results_count,
                requested_count=requested_count,
                dry_run_items=dry_run_items
            )

        except Exception as e:
            error_msg = str(e) if str(e) else type(e).__name__
            self.logger.error(f"Job failed: {error_msg}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")

            if not dry_run and exec_id is not None:
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

    async def fetch_discover_results(self) -> List[Dict[str, Any]]:
        """
        Fetch content from TMDb discover API using job filters.

        Returns:
            List of discovered content items.
        """
        filters = self.job_data.get('filters', {})
        media_type = self.job_data.get('media_type', 'movie')
        max_results = self.job_data.get('max_results', 20)

        self.logger.debug(f"Fetching {media_type} with filters: {filters}")

        if media_type == 'movie':
            return await self.tmdb_discover.discover_movies(filters, max_results)
        else:
            return await self.tmdb_discover.discover_tv(filters, max_results)

    async def filter_and_request(
        self, results: List[Dict[str, Any]], dry_run: bool = False
    ):
        """
        Filter discovered content and request via Seer (or simulate in dry-run mode).

        Args:
            results: List of discovered content items.
            dry_run: If True, collect qualifying items without making any requests.

        Returns:
            Tuple of (requested_count, dry_run_items).
            dry_run_items is a list of normalised item dicts when dry_run=True, else None.
        """
        requested_count = 0
        dry_run_items: Optional[List[Dict[str, Any]]] = [] if dry_run else None
        media_type = self.job_data.get('media_type', 'movie')

        for item in results:
            tmdb_id = item['id']
            title = item.get('title', 'Unknown')

            try:
                # Check if already in database (already requested before)
                if self.db_manager.check_request_exists(media_type, str(tmdb_id)):
                    self.logger.debug(f"Skipping {title}: already requested")
                    continue

                # Check if already downloaded via Seer
                is_downloaded = await self.seer_client.check_already_downloaded(
                    tmdb_id, media_type
                )
                if is_downloaded:
                    self.logger.debug(f"Skipping {title}: already downloaded")
                    continue

                # Check if already requested in Seer
                is_already_requested = await self.seer_client.check_already_requested(
                    tmdb_id, media_type
                )
                if is_already_requested:
                    self.logger.debug(f"Skipping {title}: already requested in Seer")
                    continue

                if dry_run:
                    self.logger.info(f"[DRY RUN] Would request {media_type}: {title} (ID: {tmdb_id})")
                    dry_run_items.append(self._format_dry_run_item(media_type, item))
                    requested_count += 1
                    continue

                # Request the content
                self.logger.info(f"Requesting {media_type}: {title} (ID: {tmdb_id})")
                success = await self.seer_client.request_media(media_type, item, source=None, user=None)

                if success:
                    requested_count += 1
                    self.logger.info(f"Successfully requested: {title}")
                else:
                    self.logger.warning(f"Failed to request: {title}")

            except Exception as e:
                self.logger.error(f"Error processing {title}: {str(e)}")
                continue

        return requested_count, dry_run_items

    @staticmethod
    def _format_dry_run_item(media_type: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalise a TMDb item dict for dry-run output.

        Args:
            media_type: 'movie' or 'tv'.
            item: Raw TMDb item dict.

        Returns:
            Normalised dict with consistent field names.
        """
        return {
            'tmdb_id': item.get('id'),
            'media_type': media_type,
            'title': item.get('title') or item.get('name'),
            'release_date': item.get('release_date') or item.get('first_air_date'),
            'poster_path': item.get('poster_path'),
            'vote_average': item.get('vote_average'),
            'vote_count': item.get('vote_count'),
            'overview': item.get('overview'),
        }

    async def _save_metadata(self, item: Dict[str, Any], media_type: str) -> None:
        """
        Save metadata for a content item.

        Args:
            item: Content item dictionary.
            media_type: 'movie' or 'tv'.
        """
        try:
            metadata = {
                'id': item['id'],
                'title': item.get('title', 'Unknown'),
                'overview': item.get('overview', ''),
                'release_date': item.get('release_date'),
                'poster_path': item.get('poster_path', ''),
                'rating': item.get('rating'),
                'votes': item.get('votes'),
                'origin_country': item.get('origin_country', []),
                'genre_ids': item.get('genre_ids', []),
                'backdrop_path': item.get('backdrop_path', ''),
            }
            self.db_manager.save_metadata(metadata, media_type)
        except Exception as e:
            self.logger.warning(f"Failed to save metadata for {item.get('title')}: {str(e)}")


async def execute_discover_job(job_id: int) -> ExecutionResult:
    """
    Execute a discover job by ID.
    This is the function to be called by JobManager.

    Args:
        job_id: ID of the job to execute.

    Returns:
        ExecutionResult with execution details.
    """
    logger = LoggerManager.get_logger("DiscoverJobExecutor")
    logger.info(f"Starting execution of discover job: {job_id}")

    try:
        automation = await DiscoverAutomation.create(job_id)
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
