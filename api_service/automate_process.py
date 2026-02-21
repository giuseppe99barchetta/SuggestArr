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
        instance.logger.info("Initializing ContentAutomation")
        env_vars = load_env_vars()

        instance.selected_service = env_vars['SELECTED_SERVICE']
        instance.max_content = env_vars.get('MAX_CONTENT_CHECKS', 10)
        instance.max_similar_movie = min(int(env_vars.get('MAX_SIMILAR_MOVIE', '3')), 20)
        instance.max_similar_tv = min(int(env_vars.get('MAX_SIMILAR_TV', '2')), 20)
        instance.search_size = min(int(env_vars.get('SEARCH_SIZE', '20')), 100)
        instance.number_of_seasons = env_vars.get('FILTER_NUM_SEASONS') or "all"

        # Ensure selected_users is always a list and normalize mixed types
        selected_users_raw = env_vars.get('SELECTED_USERS') or []
        if not isinstance(selected_users_raw, list):
            instance.logger.warning(f"SELECTED_USERS is not a list (type: {type(selected_users_raw)}), using empty list")
            instance.selected_users = []
        else:
            # Normalize mixed types: convert strings to dict format, keep dicts as is
            normalized_users = []
            for user in selected_users_raw:
                if isinstance(user, dict):
                    # Already a dict, ensure it has required keys
                    if 'id' in user:
                        normalized_users.append(user)
                    else:
                        instance.logger.warning(f"User dict missing 'id' key: {user}")
                elif isinstance(user, str):
                    # Convert string ID to dict format
                    normalized_users.append({'id': user, 'name': user})
                    instance.logger.debug(f"Normalized string user ID '{user}' to dict format")
                else:
                    instance.logger.warning(f"Invalid user type: {type(user)} - {user}")

            instance.selected_users = normalized_users
            instance.logger.debug(f"Normalized selected users: {instance.selected_users}")

        instance.logger.info(f"Configuration: service={instance.selected_service}, max_content={instance.max_content}, "
                           f"max_similar_movie={instance.max_similar_movie}, max_similar_tv={instance.max_similar_tv}")
        instance.logger.debug(f"Selected users: {instance.selected_users}")
        
        # TMDB filters
        tmdb_threshold = int(env_vars.get('FILTER_TMDB_THRESHOLD') or 60)
        tmdb_min_votes = int(env_vars.get('FILTER_TMDB_MIN_VOTES') or 20)
        include_no_ratings = env_vars.get('FILTER_INCLUDE_NO_RATING', True) == True
        filter_release_year = int(env_vars.get('FILTER_RELEASE_YEAR') or 0)

        # Ensure list fields are always lists
        filter_language_raw = env_vars.get('FILTER_LANGUAGE', [])
        filter_language = filter_language_raw if isinstance(filter_language_raw, list) else []

        filter_genre_raw = env_vars.get('FILTER_GENRES_EXCLUDE', [])
        filter_genre = filter_genre_raw if isinstance(filter_genre_raw, list) else []

        filter_region_provider = env_vars.get('FILTER_REGION_PROVIDER', None)

        filter_streaming_raw = env_vars.get('FILTER_STREAMING_SERVICES', [])
        filter_streaming_services = filter_streaming_raw if isinstance(filter_streaming_raw, list) else []

        filter_min_runtime = env_vars.get('FILTER_MIN_RUNTIME', None)

        exclude_downloaded = env_vars.get('EXCLUDE_DOWNLOADED', True)
        exclude_requested = env_vars.get('EXCLUDE_REQUESTED', True)

        # Anime profile configuration
        anime_profile_config_raw = env_vars.get('SEER_ANIME_PROFILE_CONFIG', {})
        anime_profile_config = anime_profile_config_raw if isinstance(anime_profile_config_raw, dict) else {}

        # Overseer/Jellyseer client
        instance.logger.info("Initializing Jellyseer client")
        seer_client = SeerClient(
            env_vars['SEER_API_URL'],
            env_vars['SEER_TOKEN'],
            env_vars['SEER_USER_NAME'],
            env_vars['SEER_USER_PSW'],
            env_vars['SEER_SESSION_TOKEN'],
            instance.number_of_seasons,
            exclude_downloaded,
            exclude_requested,
            anime_profile_config
        )
        await seer_client.init()
        instance.logger.info("Jellyseer client initialized successfully")

        # TMDb client
        instance.logger.info("Initializing TMDb client")
        tmdb_client = TMDbClient(
            env_vars['TMDB_API_KEY'],
            instance.search_size,
            tmdb_threshold,
            tmdb_min_votes,
            include_no_ratings,
            filter_release_year,
            filter_language,
            filter_genre,
            filter_region_provider,
            filter_streaming_services,
            filter_min_runtime
        )
        instance.logger.info("TMDb client initialized successfully")

        # Initialize media service handler (Jellyfin or Plex)
        if instance.selected_service in ('jellyfin', 'emby'):
            instance.logger.info(f"Initializing {instance.selected_service.upper()} client")

            # Ensure JELLYFIN_LIBRARIES is a list
            jellyfin_libraries_raw = env_vars.get('JELLYFIN_LIBRARIES')
            jellyfin_libraries = jellyfin_libraries_raw if isinstance(jellyfin_libraries_raw, list) else []
            if not isinstance(jellyfin_libraries_raw, list) and jellyfin_libraries_raw is not None:
                instance.logger.warning(f"JELLYFIN_LIBRARIES is not a list (type: {type(jellyfin_libraries_raw)}), using empty list")

            jellyfin_client = JellyfinClient(
                env_vars['JELLYFIN_API_URL'],
                env_vars['JELLYFIN_TOKEN'],
                instance.max_content,
                jellyfin_libraries
            )
            await jellyfin_client.init_existing_content()

            # Build library anime map: library name -> is_anime
            jellyfin_anime_map = {}
            for lib in jellyfin_libraries:
                if isinstance(lib, dict) and lib.get('name'):
                    jellyfin_anime_map[lib['name']] = lib.get('is_anime', False)

            instance.media_handler = JellyfinHandler(
                jellyfin_client, seer_client, tmdb_client, instance.logger,
                instance.max_similar_movie, instance.max_similar_tv,
                instance.selected_users, jellyfin_anime_map
            )
            instance.logger.info(f"{instance.selected_service.upper()} client initialized successfully")

        elif instance.selected_service == 'plex':
            instance.logger.info("Initializing Plex client")

            # Ensure PLEX_LIBRARIES is a list
            plex_libraries_raw = env_vars.get('PLEX_LIBRARIES')
            plex_libraries = plex_libraries_raw if isinstance(plex_libraries_raw, list) else []
            if not isinstance(plex_libraries_raw, list) and plex_libraries_raw is not None:
                instance.logger.warning(f"PLEX_LIBRARIES is not a list (type: {type(plex_libraries_raw)}), using empty list")

            plex_client = PlexClient(
                api_url=env_vars['PLEX_API_URL'],
                token=env_vars['PLEX_TOKEN'],
                max_content=instance.max_content,
                library_ids=plex_libraries,
                user_ids=instance.selected_users
            )
            await plex_client.init_existing_content()

            # Build library anime map: library section ID -> is_anime
            plex_anime_map = {}
            for lib in plex_libraries:
                if isinstance(lib, dict) and lib.get('id'):
                    plex_anime_map[str(lib['id'])] = lib.get('is_anime', False)

            instance.media_handler = PlexHandler(
                plex_client, seer_client, tmdb_client, instance.logger,
                instance.max_similar_movie, instance.max_similar_tv,
                plex_anime_map
            )
            instance.logger.info("Plex client initialized successfully")
        else:
            instance.logger.warning(f"Unknown selected service: {instance.selected_service}")
            raise ValueError(f"Unsupported service: {instance.selected_service}")

        return instance

    async def run(self):
        """Main entry point to start the automation process."""
        self.logger.info("Starting content automation process")
        try:
            await self.media_handler.process_recent_items()
            self.logger.info("Content automation process completed successfully")
        except Exception as e:
            self.logger.error(f"Content automation process failed: {str(e)}", exc_info=True)
            raise
