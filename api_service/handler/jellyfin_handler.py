import asyncio

from api_service.services.jellyfin.jellyfin_client import JellyfinClient
from api_service.services.jellyseer.seer_client import SeerClient
from api_service.services.tmdb.tmdb_client import TMDbClient

class JellyfinHandler:
    def __init__(self, jellyfin_client:JellyfinClient, jellyseer_client:SeerClient, tmdb_client:TMDbClient, logger, max_similar_movie, max_similar_tv):
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

    async def process_recent_items(self):
        """Process recently watched items for all Jellyfin users."""
        users = await self.jellyfin_client.get_all_users()
        tasks = [self.process_user_recent_items(user) for user in users]
        await asyncio.gather(*tasks)
        self.logger.info(f"Total media requested: {self.request_count}")

    async def process_user_recent_items(self, user):
        """Process recently watched items for a specific Jellyfin user."""
        self.logger.info(f"Fetching content for user: {user['Name']} ({user['Id']})")
        recent_items_by_library = await self.jellyfin_client.get_recent_items(user)

        if recent_items_by_library:
            tasks = []
            for library_name, items in recent_items_by_library.items():
                self.logger.info(f"Processing items for library: {library_name}")
                tasks.extend([self.process_item(user['Id'], item) for item in items])
            await asyncio.gather(*tasks)

    async def process_item(self, user_id, item):
        """Process an individual item (movie or TV show episode)."""
        item_type = item['Type'].lower()
        if item_type == 'movie' and self.max_similar_movie > 0:
            await self.process_movie(user_id, item['Id'])
        elif item_type == 'episode' and self.max_similar_tv > 0:
            await self.process_episode(user_id, item)

    async def process_movie(self, user_id, item_id):
        """Find similar movies via TMDb and request them via Jellyseer."""
        tmdb_id = await self.jellyfin_client.get_item_provider_id(user_id, item_id)
        if tmdb_id:
            similar_movies = await self.tmdb_client.find_similar_movies(tmdb_id)
            await self.request_similar_media(similar_movies, 'movie', self.max_similar_movie)

    async def process_episode(self, user_id, item):
        """Process a TV show episode by finding similar TV shows via TMDb."""
        series_id = item.get('SeriesId')
        if series_id and series_id not in self.processed_series:
            self.processed_series.add(series_id)
            tvdb_id = await self.jellyfin_client.get_item_provider_id(user_id, series_id, provider='Tmdb')
            if tvdb_id:
                similar_tvshows = await self.tmdb_client.find_similar_tvshows(tvdb_id)
                await self.request_similar_media(similar_tvshows, 'tv', self.max_similar_tv)

    async def request_similar_media(self, media_ids, media_type, max_items):
        """Request similar media (movie/TV show) via Jellyseer."""
        if not media_ids:
            self.logger.info("No media IDs provided for similar media request.")
            return

        tasks = []
        for media in media_ids[:max_items]:
            media_id = media['id']
            media_title = media['title']

            # Check if already downloaded or requested
            already_requested = await self.jellyseer_client.check_already_requested(media_id, media_type)
            already_downloaded = await self.jellyseer_client.check_already_downloaded(media_id, media_type, self.existing_content)

            if not already_requested and not already_downloaded:
                tasks.append(self._request_media_and_log(media_type, media_id, media_title))
            else:
                self.logger.info(f"Skipping [{media_type}, {media_title}]: already requested or downloaded.")

        await asyncio.gather(*tasks)

    async def _request_media_and_log(self, media_type, media_id, media_title):
        """Helper method to request media and log the result."""
        await self.jellyseer_client.request_media(media_type, media_id)
        self.request_count += 1
        self.logger.info(f"Requested {media_type}: {media_title}")
