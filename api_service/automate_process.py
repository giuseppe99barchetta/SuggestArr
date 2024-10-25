import asyncio

from config.config import load_env_vars
from config.logger_manager import LoggerManager
from handler.jellyfin_handler import JellyfinHandler
from handler.plex_handler import PlexHandler
from services.jellyfin.jellyfin_client import JellyfinClient
from services.jellyseer.seer_client import SeerClient
from services.plex.plex_client import PlexClient
from services.tmdb.tmdb_client import TMDbClient


class ContentAutomation:
    """
    Automates the process of retrieving recent movies/TV shows from Jellyfin/Plex,
    finding similar content via TMDb, and requesting content via Jellyseer/Overseer.
    """

    def __init__(self):
        """
        Initialize clients for Jellyfin/Plex, TMDb, and Jellyseer/Overseer based on the selected service.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        env_vars = load_env_vars()
        
        self.selected_service = env_vars['SELECTED_SERVICE']
        self.max_content = env_vars.get('MAX_CONTENT_CHECKS', 10)
        self.max_similar_movie = min(int(env_vars.get('MAX_SIMILAR_MOVIE', '3')), 20)
        self.max_similar_tv = min(int(env_vars.get('MAX_SIMILAR_TV', '2')), 20)

        # Overseer/Jellyseer client
        jellyseer_client = SeerClient(
            env_vars['SEER_API_URL'],
            env_vars['SEER_TOKEN'],
            env_vars['SEER_USER_NAME'],
            env_vars['SEER_USER_PSW']
        )
        
        asyncio.run(jellyseer_client.init())

        # TMDb client
        tmdb_client = TMDbClient(env_vars['TMDB_API_KEY'])

        # Initialize media service handler (Jellyfin or Plex)
        if self.selected_service in ('jellyfin', 'emby') :
            jellyfin_client = JellyfinClient(
                env_vars['JELLYFIN_API_URL'],
                env_vars['JELLYFIN_TOKEN'],
                self.max_content,
                env_vars.get('JELLYFIN_LIBRARIES')
            )
            self.media_handler = JellyfinHandler(jellyfin_client, jellyseer_client, tmdb_client, self.logger, self.max_similar_movie, self.max_similar_tv)

        elif self.selected_service == 'plex':
            plex_client = PlexClient(
                api_url=env_vars['PLEX_API_URL'],
                token=env_vars['PLEX_TOKEN'],
                max_content=self.max_content,
                library_ids=env_vars.get('PLEX_LIBRARIES')
            )
            self.media_handler = PlexHandler(plex_client, jellyseer_client, tmdb_client, self.logger, self.max_similar_movie, self.max_similar_tv)

    async def run(self):
        """Main entry point to start the automation process."""
        await self.media_handler.process_recent_items()
