import asyncio

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.handler.jellyfin_handler import JellyfinHandler
from api_service.handler.plex_handler import PlexHandler
from api_service.services.jellyfin.jellyfin_client import JellyfinClient
from api_service.services.jellyseer.seer_client import SeerClient
from api_service.services.plex.plex_client import PlexClient
from api_service.services.tmdb.tmdb_client import TMDbClient


class ContentAutomation:
    """
    Automates the process of retrieving recent movies/TV shows from Jellyfin/Plex,
    finding similar content via TMDb, and requesting content via Jellyseer/Overseer.
    """

    def __new__(cls):
        """Override to prevent direct instantiation and enforce use of `create`."""
        instance = super(ContentAutomation, cls).__new__(cls)
        instance.logger = LoggerManager.get_logger(cls.__name__)
        return instance

    @classmethod
    async def create(cls):
        """Async factory method to initialize ContentAutomation asynchronously."""
        instance = cls.__new__(cls)
        env_vars = load_env_vars()

        instance.selected_service = env_vars['SELECTED_SERVICE']
        instance.max_content = env_vars.get('MAX_CONTENT_CHECKS', 10)
        instance.max_similar_movie = min(int(env_vars.get('MAX_SIMILAR_MOVIE', '3')), 20)
        instance.max_similar_tv = min(int(env_vars.get('MAX_SIMILAR_TV', '2')), 20)
        instance.search_size = min(int(env_vars.get('SEARCH_SIZE', '20')), 100)
        instance.number_of_seasons = env_vars.get('FILTER_NUM_SEASONS') or "all"
        instance.selected_users = env_vars.get('SELECTED_USERS') or []
        
        # TMDB filters
        tmdb_threshold = int(env_vars.get('FILTER_TMDB_THRESHOLD') or 60)
        tmdb_min_votes = int(env_vars.get('FILTER_TMDB_MIN_VOTES') or 20)
        include_no_ratings = env_vars.get('FILTER_INCLUDE_NO_RATING', True) == True
        filter_release_year = int(env_vars.get('FILTER_RELEASE_YEAR') or 0)
        filter_language = env_vars.get('FILTER_LANGUAGE', [])
        filter_genre = env_vars.get('FILTER_GENRES_EXCLUDE', [])

        # Overseer/Jellyseer client
        jellyseer_client = SeerClient(
            env_vars['SEER_API_URL'],
            env_vars['SEER_TOKEN'],
            env_vars['SEER_USER_NAME'],
            env_vars['SEER_USER_PSW'],
            env_vars['SEER_SESSION_TOKEN'],
            instance.number_of_seasons
        )
        await jellyseer_client.reset_cycle_cache()
        await jellyseer_client.init()

        # TMDb client
        tmdb_client = TMDbClient(
            env_vars['TMDB_API_KEY'],
            instance.search_size,
            tmdb_threshold,
            tmdb_min_votes,
            include_no_ratings,
            filter_release_year,
            filter_language,
            filter_genre
        )

        # Initialize media service handler (Jellyfin or Plex)
        if instance.selected_service in ('jellyfin', 'emby'):
            jellyfin_client = JellyfinClient(
                env_vars['JELLYFIN_API_URL'],
                env_vars['JELLYFIN_TOKEN'],
                instance.max_content,
                env_vars.get('JELLYFIN_LIBRARIES')
            )
            await jellyfin_client.init_existing_content()
            instance.media_handler = JellyfinHandler(
                jellyfin_client, jellyseer_client, tmdb_client, instance.logger, instance.max_similar_movie, instance.max_similar_tv, instance.selected_users
            )

        elif instance.selected_service == 'plex':
            plex_client = PlexClient(
                api_url=env_vars['PLEX_API_URL'],
                token=env_vars['PLEX_TOKEN'],
                max_content=instance.max_content,
                library_ids=env_vars.get('PLEX_LIBRARIES'),
                user_ids=instance.selected_users
            )
            await plex_client.init_existing_content()
            instance.media_handler = PlexHandler(plex_client, jellyseer_client, tmdb_client, instance.logger, instance.max_similar_movie, instance.max_similar_tv)

        return instance

    async def run(self):
        """Main entry point to start the automation process."""
        await self.media_handler.process_recent_items()
