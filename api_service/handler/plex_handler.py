import asyncio

from api_service.services.jellyseer.seer_client import SeerClient
from api_service.services.plex.plex_client import PlexClient
from api_service.services.tmdb.tmdb_client import TMDbClient

class PlexHandler:
    def __init__(self, plex_client: PlexClient, jellyseer_client: SeerClient, tmdb_client: TMDbClient, logger, max_similar_movie, max_similar_tv):
        """
        Initialize PlexHandler with clients and parameters.
        :param plex_client: Plex API client
        :param jellyseer_client: Jellyseer API client
        :param tmdb_client: TMDb API client
        :param logger: Logger instance
        :param max_similar_movie: Max number of similar movies to request
        :param max_similar_tv: Max number of similar TV shows to request
        """
        self.plex_client = plex_client
        self.jellyseer_client = jellyseer_client
        self.tmdb_client = tmdb_client
        self.logger = logger
        self.max_similar_movie = max_similar_movie
        self.max_similar_tv = max_similar_tv
        self.request_count = 0
        self.existing_content = plex_client.existing_content

    async def process_recent_items(self):
        """Process recently watched items for Plex (without user context)."""
        self.logger.info("Fetching recently watched content from Plex")
        recent_items_response = await self.plex_client.get_recent_items()

        if isinstance(recent_items_response, list):
            tasks = []
            for response_item in recent_items_response:
                title = response_item.get('title', response_item.get('grandparentTitle'))
                self.logger.info(f"Processing item: {title}")
                tasks.append(self.process_item(response_item, title))  # No user context needed for Plex

            if tasks:
                await asyncio.gather(*tasks)
                self.logger.info(f"Total media requested: {self.request_count}")
            else:
                self.logger.warning("No recent items found in Plex response")
        else:
            self.logger.warning("Unexpected response format: expected a list")

    async def process_item(self, item, title):
        """Process an individual item (movie or TV show episode)."""
        self.logger.debug(f"Processing item: {item}")

        item_type = item['type'].lower()

        if (item_type == 'movie' and self.max_similar_movie > 0) or (item_type == 'episode' and self.max_similar_tv > 0):
            try:
                key = self.extract_rating_key(item, item_type)
                self.logger.debug(f"Extracted key: {key} for item type: {item_type}")
                if key:
                    if item_type == 'movie':
                        await self.process_movie(key, title)
                    elif item_type == 'episode':
                        await self.process_episode(key, title)
                else:
                    raise ValueError(f"Missing key for {item_type} '{title}'. Cannot process this item. Skipping.")
            except Exception as e:
                self.logger.warning(f"Error while processing item: {str(e)}")

    def extract_rating_key(self, item, item_type):
        """Extract the appropriate key depending on the item type."""
        key = item.get('key') if item_type == 'movie' else item.get('grandparentKey') if item_type == 'episode' else None
        self.logger.debug(f"Extracted rating key: {key} for item type: {item_type}")
        return key if key else None

    async def process_movie(self, movie_key, title):
        """Find similar movies via TMDb and request them via Jellyseer."""
        self.logger.debug(f"Processing movie with key: {movie_key} - {title}")
        source_tmbd_id = await self.plex_client.get_metadata_provider_id(movie_key)
        self.logger.debug(f"TMDb ID retrieved: {source_tmbd_id}")
        source_tmdb_obj = await self.tmdb_client.get_metadata(source_tmbd_id, 'movie')
        self.logger.info(f"TMDb metadata: {source_tmdb_obj}")

        if source_tmbd_id:
            similar_movies = await self.tmdb_client.find_similar_movies(source_tmbd_id)
            self.logger.debug(f"Found similar movies: {similar_movies}")
            await self.request_similar_media(similar_movies, 'movie', self.max_similar_movie, source_tmdb_obj)
        else:
            self.logger.warning(f"Error while processing item: 'tmdb_id' not found for movie '{title}'. Skipping.")

    async def process_episode(self, show_key, title):
        """Process a TV show episode by finding similar TV shows via TMDb."""
        self.logger.debug(f"Processing episode with show key: {show_key} - {title}")
        if show_key:
            source_tmbd_id = await self.plex_client.get_metadata_provider_id(show_key)
            self.logger.debug(f"TMDb ID retrieved: {source_tmbd_id}")
            source_tmdb_obj = await self.tmdb_client.get_metadata(source_tmbd_id, 'tv')
            self.logger.debug(f"TMDb metadata: {source_tmdb_obj}")

            if source_tmbd_id:
                similar_tvshows = await self.tmdb_client.find_similar_tvshows(source_tmbd_id)
                self.logger.debug(f"Found {len(similar_tvshows)} similar TV shows")
                await self.request_similar_media(similar_tvshows, 'tv', self.max_similar_tv, source_tmdb_obj)
            else:
                self.logger.warning(f"Error while processing item: 'tmdb_id' not found for tv show '{title}'. Skipping.")

    async def request_similar_media(self, media_ids, media_type, max_items, source_tmdb_obj):
        """Request similar media (movie/TV show) via Overseer."""
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
            self.logger.debug(f"Already requested: {already_requested}")
            if already_requested:
                self.logger.info(f"Skipping [{media_type}, {media_title}]: already requested.")
                continue

            already_downloaded = await self.jellyseer_client.check_already_downloaded(media_id, media_type, self.existing_content)
            self.logger.debug(f"Already downloaded: {already_downloaded}")
            if already_downloaded:
                self.logger.info(f"Skipping [{media_type}, {media_title}]: already downloaded.")
                continue

            in_excluded_streaming_service, provider = await self.tmdb_client.get_watch_providers(source_tmdb_obj['id'], media_type)
            self.logger.debug(f"In excluded streaming service: {in_excluded_streaming_service}, Provider: {provider}")
            if in_excluded_streaming_service:
                self.logger.info(f"Skipping [{media_type}, {media_title}]: excluded by streaming service: {provider}")
                continue

            # Add to tasks if it passes all checks
            tasks.append(self._request_media_and_log(media_type, media, source_tmdb_obj))

        await asyncio.gather(*tasks)

    async def _request_media_and_log(self, media_type, media, source_tmdb_obj):
        """Helper method to request media and log the result."""
        self.logger.debug(f"Requesting media: {media} of type: {media_type}")
        if await self.jellyseer_client.request_media(media_type, media, source_tmdb_obj):
            self.request_count += 1
            self.logger.info(f"Requested {media_type}: {media['title']}")
