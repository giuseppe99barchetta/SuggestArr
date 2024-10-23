import asyncio

from jellyseer.seer_client import SeerClient
from plex.plex_client import PlexClient
from tmdb.tmdb_client import TMDbClient

class PlexHandler:
    def __init__(self, plex_client:PlexClient, jellyseer_client:SeerClient, tmdb_client:TMDbClient, logger, max_similar_movie, max_similar_tv):
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

    async def process_recent_items(self):
        """Process recently watched items for Plex (without user context)."""
        self.logger.info("Fetching recently watched content from Plex")
        recent_items_response = await self.plex_client.get_recent_items()

        if isinstance(recent_items_response, list):
            tasks = []
            for response_item in recent_items_response:
                title = response_item.get('title', response_item.get('grandparentTitle'))
                self.logger.info(f"Processing item: {title}")
                tasks.append(self.process_item(None, response_item))  # No user context needed for Plex

            if tasks:
                await asyncio.gather(*tasks)
                self.logger.info(f"Total media requested: {self.request_count}")
            else:
                self.logger.warning("No recent items found in Plex response")
        else:
            self.logger.warning("Unexpected response format: expected a list")

    async def process_item(self, user_id, item):
        """Process an individual item (movie or TV show episode)."""
        item_type = item['type'].lower()
        if item_type == 'movie' and self.max_similar_movie > 0:
            await self.process_movie(user_id, item['key'].replace('/library/metadata/', ''))
        elif item_type == 'episode' and self.max_similar_tv > 0:
            await self.process_episode(user_id, item)

    async def process_movie(self, user_id, item_id):
        """Find similar movies via TMDb and request them via Jellyseer."""
        tmdb_id = await self.plex_client.get_metadata_provider_id(item_id)
        if tmdb_id:
            similar_movies = await self.tmdb_client.find_similar_movies(tmdb_id)
            await self.request_similar_media(similar_movies, 'movie', self.max_similar_movie)

    async def process_episode(self, user_id, item):
        """Process a TV show episode by finding similar TV shows via TMDb."""
        series_id = item.get('grandparentKey').replace('/library/metadata/', '')
        if series_id:
            tvdb_id = await self.plex_client.get_metadata_provider_id(series_id)
            if tvdb_id:
                similar_tvshows = await self.tmdb_client.find_similar_tvshows(tvdb_id)
                await self.request_similar_media(similar_tvshows, 'tv', self.max_similar_tv)

    async def request_similar_media(self, media_ids, media_type, max_items):
        """Request similar media (movie/TV show) via Jellyseer."""
        if media_ids:
            for media in media_ids[:max_items]:
                if not await self.jellyseer_client.check_already_requested(media['id'], media_type):
                    await self.jellyseer_client.request_media(media_type, media['id'])
                    self.request_count += 1
                    self.logger.info(f"Requested {media_type}: {media['title']}")
                else:
                    self.logger.info(f"Skipping [{media_type}, {media['title']}]: already requested.")
