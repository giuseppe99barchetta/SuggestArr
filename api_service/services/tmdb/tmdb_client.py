"""
This module provides a client for interacting with The Movie Database (TMDb) API.
It includes functionality to retrieve similar movies, similar TV shows, and convert
TVDb IDs to TMDb IDs.

Classes:
    - TMDbClient: A class to interact with the TMDb API.
"""

import aiohttp
import asyncio
from api_service.config.logger_manager import LoggerManager

# Constants for HTTP status codes and timeout
HTTP_OK = {200, 201}
REQUEST_TIMEOUT = 10   # Timeout in seconds for HTTP requests
CONTENT_PER_PAGE = 20  # Number of content items per page in TMDb API responses
RATE_LIMIT_SLEEP = 0.3 # Delay between requests to avoid rate limiting

class TMDbClient:
    """
    A client to interact with The Movie Database (TMDb) API to retrieve information
    related to movies, TV shows, and external IDs.
    """

    def __init__(self, api_key, search_size):
        """
        Initializes the TMDbClient with the provided API key.
        :param api_key: API key to authenticate requests to TMDb.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.api_key = api_key
        self.search_size = search_size
        self.pages = (self.search_size + CONTENT_PER_PAGE - 1) // CONTENT_PER_PAGE
        self.tmdb_api_url = "https://api.themoviedb.org/3"

    async def _fetch_recommendations(self, content_id, content_type):
        """
        Helper method to fetch recommendations for either movies or TV shows.
        :param content_id: The ID of the movie or TV show.
        :param content_type: 'movie' or 'tv' to specify the type of content.
        :return: A list of recommendations with IDs and titles.
        """
        search = []
        for page in range(1, self.pages + 1):
            url = f"{self.tmdb_api_url}/{content_type}/{content_id}/recommendations?api_key={self.api_key}&page={page}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                        if response.status in HTTP_OK:
                            data = await response.json()
                            search.extend([
                                {'id': item['id'], 'title': item['title' if content_type == 'movie' else 'name']}
                                for item in data['results']
                            ])
                            if data['total_pages'] == page:
                                break
                        else:
                            self.logger.error("Error retrieving %s recommendations: %d", content_type, response.status)
            except aiohttp.ClientError as e:
                self.logger.error("An error occurred while requesting %s recommendations: %s", content_type, str(e))

            # Sleep to avoid rate limiting, except on the last request
            if page < self.pages:
                await asyncio.sleep(RATE_LIMIT_SLEEP)
        
        return search[:self.search_size]

    async def find_similar_movies(self, movie_id):
        """
        Finds movies similar to the one with the given movie_id.
        """
        return await self._fetch_recommendations(movie_id, 'movie')

    async def find_similar_tvshows(self, tvshow_id):
        """
        Finds TV shows similar to the one with the given tvshow_id.
        """
        return await self._fetch_recommendations(tvshow_id, 'tv')

    async def find_tmdb_id_from_tvdb(self, tvdb_id):
        """
        Finds the TMDb ID for a TV show using its TVDb ID asynchronously.
        :param tvdb_id: The TVDb ID to convert to TMDb ID.
        :return: The TMDb ID corresponding to the provided TVDb ID, or None if not found.
        """
        url = f"{self.tmdb_api_url}/find/{tvdb_id}?api_key={self.api_key}&external_source=tvdb_id"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status in HTTP_OK:
                        data = await response.json()
                        if 'tv_results' in data and data['tv_results']:
                            return data['tv_results'][0]['id']
                        self.logger.warning("No results found on TMDb for TVDb ID: %s", tvdb_id)
                    else:
                        self.logger.error("Error converting TVDb ID to TMDb ID: %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while converting TVDb ID: %s", str(e))

        return None
