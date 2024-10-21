"""
This module automates the process of retrieving recently watched movies and TV shows
from Jellyfin, finding similar content via TMDb, and requesting the content via Jellyseer.

Classes:
    - JellyfinClient: A client to interact with the Jellyfin API.
    - JellyseerClient: A client to interact with the Jellyseer API.
    - TMDbClient: A client to interact with the TMDb API.
    - ContentAutomation: A class that handles the automation of movie and TV show processing.
"""


import os
import asyncio
from dotenv import load_dotenv

from jellyfin.jellyfin_client import JellyfinClient
from jellyseer.jellyseer_client import JellyseerClient
from tmdb.tmdb_client import TMDbClient
from config.config import load_env_vars
from config.logger_manager import LoggerManager

class ContentAutomation:
    """
    This class handles the automation process of fetching recently watched items from Jellyfin,
    finding similar content via TMDb, and requesting the content via Jellyseer.
    """

    def __init__(self):
        """
        Initialize the clients for Jellyfin, TMDb, and Jellyseer.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        env_vars = load_env_vars()

        jellyfin_api_url = env_vars['JELLYFIN_API_URL']
        jellyfin_token = env_vars['JELLYFIN_TOKEN']
        jellyseer_api_url = env_vars['JELLYSEER_API_URL']
        jellyseer_token = env_vars['JELLYSEER_TOKEN']
        tmdb_api_key = env_vars['TMDB_API_KEY']
        jellyseer_user_name = env_vars['JELLYSEER_USER_NAME']
        jellyseer_user_psw = env_vars['JELLYSEER_USER_PSW']
        jellyfin_max_content = env_vars['MAX_CONTENT_CHECKS']
        jellyfin_library_filter = env_vars['JELLYFIN_LIBRARIES']

        self.jellyfin_client = JellyfinClient(
            jellyfin_api_url,
            jellyfin_token,
            jellyfin_max_content,
            jellyfin_library_filter
        )
        self.jellyseer_client = JellyseerClient(
            jellyseer_api_url,
            jellyseer_token,
            jellyseer_user_name,
            jellyseer_user_psw
        )
        self.tmdb_client = TMDbClient(
            tmdb_api_key
        )

        self.max_similar_movie = min(int(os.getenv('MAX_SIMILAR_MOVIE', '3')), 20)
        self.max_similar_tv = min(int(os.getenv('MAX_SIMILAR_TV', '2')), 20)

        self.processed_series = set()  # To track series already processed

    async def run(self):
        """Main entry point to start the automation process."""
        users = await self.jellyfin_client.get_all_users()
        load_dotenv(override=True)
        await self.jellyseer_client.init()
        tasks = [self.process_user_recent_items(user) for user in users]
        await asyncio.gather(*tasks)

    async def process_user_recent_items(self, user):
        """Process the recently watched items (movies and TV shows) for a specific Jellyfin user."""
        user_id = user['Id']
        self.logger.info(
            "Fetching recently watched content for user: %s (%s)", user['Name'], user_id
        )

        recent_items_by_library = await self.jellyfin_client.get_recent_items(user_id)

        if recent_items_by_library:
            tasks = []

            for library_id, items in recent_items_by_library.items():
                self.logger.info("Processing items for library: %s", library_id)
                for item in items:
                    tasks.append(self.process_item(user_id, item))

            await asyncio.gather(*tasks)

    async def process_item(self, user_id, item):
        """Process an individual item (either a movie or TV show)."""
        item_type = item['Type']
        item_id = item['Id']

        if item_type.lower() == 'movie':
            await self.process_movie(user_id, item_id)
        elif item_type.lower() == 'episode':
            await self.process_episode(user_id, item)

    async def process_movie(self, user_id, item_id):
        """Process a movie by finding similar movies via TMDb and requesting them via Jellyseer."""
        tmdb_id = await self.jellyfin_client.get_item_provider_id(user_id, item_id)
        self.logger.info("Processing movie: %s (TMDB id)", tmdb_id)
        if tmdb_id:
            similar_movies = await self.tmdb_client.find_similar_movies(tmdb_id)
            for similar_movie_id in similar_movies[:self.max_similar_movie]:
                if not await self.jellyseer_client.check_already_requested(similar_movie_id, 'movie'):
                    await self.jellyseer_client.request_media('movie', similar_movie_id)
                    self.logger.info("Requested download for movie with ID: %s", similar_movie_id)


    async def process_episode(self, user_id, item):
        """
        Process a TV show episode by finding similar TV shows 
        via TMDb and requesting them via Jellyseer.
        """
        series_id = item.get('SeriesId')
        series_name = item.get('SeriesName')
        if series_id and series_id not in self.processed_series:
            self.logger.info("Processing series: %s (Series ID: %s)", series_name, series_id)
            self.processed_series.add(series_id)

            tvdb_id = await self.jellyfin_client.get_item_provider_id(user_id, series_id, provider='Tvdb')
            if tvdb_id:
                await self.request_similar_tv_shows(tvdb_id, series_name)

    async def request_similar_tv_shows(self, tvdb_id, series_name):
        """Request similar TV shows via Jellyseer after finding them through TMDb."""
        self.logger.info("TVDb ID for series '%s': %s", series_name, tvdb_id)
        tmdb_id = await self.tmdb_client.find_tmdb_id_from_tvdb(tvdb_id)

        if tmdb_id:
            similar_tvshows = await self.tmdb_client.find_similar_tvshows(tmdb_id)
            if similar_tvshows:
                self.logger.info("Found %d similar TV shows for '%s'", len(similar_tvshows), series_name)
                for similar_tvshow_id in similar_tvshows[:self.max_similar_tv]:
                    if not await self.jellyseer_client.check_already_requested(similar_tvshow_id, 'tv'):
                        await self.jellyseer_client.request_media('tv', similar_tvshow_id)
                        self.logger.info("Requested download for TV show with ID: %s", similar_tvshow_id)
            else:
                self.logger.warning("No similar TV shows found for '%s'", series_name)
        else:
            self.logger.warning("Could not find TMDb ID for series '%s'", series_name)
