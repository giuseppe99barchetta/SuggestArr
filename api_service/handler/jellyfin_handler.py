import asyncio

from api_service.services.jellyfin.jellyfin_client import JellyfinClient
from api_service.services.jellyseer.seer_client import SeerClient
from api_service.services.tmdb.tmdb_client import TMDbClient

class JellyfinHandler:
    def __init__(self, jellyfin_client:JellyfinClient, jellyseer_client:SeerClient, tmdb_client:TMDbClient, logger, max_similar_movie, max_similar_tv, selected_users):
        """
        Initialize JellyfinHandler with clients and parameters.
        :param jellyfin_client: Jellyfin API client
        :param jellyseer_client: Jellyseer API client
        :param tmdb_client: TMDb API client
        :param logger: Logger instance
        :param max_similar_movie: Max number of similar movies to request
        :param max_similar_tv: Max number of similar TV shows to request
        """
        self.jellyfin_client = jellyfin_client
        self.jellyseer_client = jellyseer_client
        self.tmdb_client = tmdb_client
        self.logger = logger
        self.max_similar_movie = max_similar_movie
        self.max_similar_tv = max_similar_tv
        self.processed_series = set()
        self.request_count = 0
        self.existing_content = jellyfin_client.existing_content
        self.selected_users = selected_users

    async def process_recent_items(self):
        """Process recently watched items for all Jellyfin users."""
        self.logger.debug("Starting process_recent_items")
        users = self.selected_users if len(self.selected_users) > 0 else await self.jellyfin_client.get_all_users()
        self.logger.debug(f"Users to process: {users}")
        tasks = [self.process_user_recent_items(user) for user in users]
        await asyncio.gather(*tasks)
        self.logger.info(f"Total media requested: {self.request_count}")

    async def process_user_recent_items(self, user):
        """Process recently watched items for a specific Jellyfin user."""
        self.logger.info(f"Fetching content for user: {user['name']}")
        recent_items_by_library = await self.jellyfin_client.get_recent_items(user)
        self.logger.debug(f"Recent items for user {user['name']}: {recent_items_by_library}")

        if recent_items_by_library:
            tasks = []
            for library_name, items in recent_items_by_library.items():
                self.logger.debug(f"Processing library: {library_name} with items: {items}")
                tasks.extend([self.process_item(user['id'], item) for item in items])
            await asyncio.gather(*tasks)

    async def process_item(self, user_id, item):
        """Process an individual item (movie or TV show episode)."""
        self.logger.debug(f"Processing item: {item}")
        item_type = item['Type'].lower()
        if item_type == 'movie' and self.max_similar_movie > 0:
            await self.process_movie(user_id, item['Id'])
        elif item_type == 'episode' and self.max_similar_tv > 0:
            await self.process_episode(user_id, item)

    async def process_movie(self, user_id, item_id):
        """Find similar movies via TMDb and request them via Jellyseer."""
        self.logger.debug(f"Processing movie with ID: {item_id}")
        source_tmbd_id = await self.jellyfin_client.get_item_provider_id(user_id, item_id)
        self.logger.debug(f"TMDb ID for movie: {source_tmbd_id}")
        source_tmdb_obj = await self.tmdb_client.get_metadata(source_tmbd_id, 'movie')
        if source_tmbd_id:
            similar_movies = await self.tmdb_client.find_similar_movies(source_tmbd_id)
            self.logger.debug(f"Similar movies found: {similar_movies}")
            await self.request_similar_media(similar_movies, 'movie', self.max_similar_movie, source_tmdb_obj)

    async def process_episode(self, user_id, item):
        """Process a TV show episode by finding similar TV shows via TMDb."""
        self.logger.debug(f"Processing episode: {item}")
        series_id = item.get('SeriesId')
        if series_id and series_id not in self.processed_series:
            self.processed_series.add(series_id)
            source_tmbd_id = await self.jellyfin_client.get_item_provider_id(user_id, series_id, provider='Tmdb')
            self.logger.debug(f"TMDb ID for series: {source_tmbd_id}")
            source_tmdb_obj = await self.tmdb_client.get_metadata(source_tmbd_id, 'tv')
            if source_tmbd_id:
                similar_tvshows = await self.tmdb_client.find_similar_tvshows(source_tmbd_id)
                self.logger.debug(f"Similar TV shows found: {similar_tvshows}")
                await self.request_similar_media(similar_tvshows, 'tv', self.max_similar_tv, source_tmdb_obj)

    async def request_similar_media(self, media_ids, media_type, max_items, source_tmdb_obj):
        """Request similar media (movie/TV show) via Jellyseer."""
        self.logger.debug(f"Requesting {max_items} similar media")
        if not media_ids:
            self.logger.info("No media IDs provided for similar media request.")
            return

        tasks = []
        for media in media_ids[:max_items]:
            media_id = media['id']
            media_title = media['title']
            
            self.logger.debug(f"Processing similar media: '{media_title}' with ID: '{media_id}'")

            # Check if already downloaded, requested, or in an excluded streaming service
            already_requested = await self.jellyseer_client.check_already_requested(media_id, media_type)
            self.logger.debug(f"Already requested check for {media_title}: {already_requested}")
            if already_requested:
                self.logger.info(f"Skipping [{media_type}, {media_title}]: already requested.")
                continue
            
            already_downloaded = await self.jellyseer_client.check_already_downloaded(media_id, media_type, self.existing_content)
            self.logger.debug(f"Already downloaded check for {media_title}: {already_downloaded}")
            if already_downloaded:
                self.logger.info(f"Skipping [{media_type}, {media_title}]: already downloaded.")
                continue
            
            in_excluded_streaming_service, provider = await self.tmdb_client.get_watch_providers(source_tmdb_obj['id'], media_type)
            self.logger.debug(f"Excluded streaming service check for {media_title}: {in_excluded_streaming_service}, {provider}")
            if in_excluded_streaming_service:
                self.logger.info(f"Skipping [{media_type}, {media_title}]: excluded by streaming service: {provider}")
                continue
            
            # Add to tasks if it passes all checks
            tasks.append(self._request_media_and_log(media_type, media, source_tmdb_obj))

        await asyncio.gather(*tasks)

    async def _request_media_and_log(self, media_type, media, source_tmdb_obj):
        """Helper method to request media and log the result."""
        self.logger.debug(f"Requesting media: {media}")
        await self.jellyseer_client.request_media(media_type, media, source_tmdb_obj)
        self.request_count += 1
        self.logger.info(f"Requested {media_type}: {media['title']}")
