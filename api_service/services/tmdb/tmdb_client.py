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

    def __init__(self, api_key, search_size, tmdb_threshold, tmdb_min_votes, include_no_ratings, filter_release_year, filter_language, filter_genre):
        """
        Initializes the TMDbClient with the provided API key.
        :param api_key: API key to authenticate requests to TMDb.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.api_key = api_key
        self.search_size = search_size
        self.tmdb_threshold = tmdb_threshold
        self.tmdb_min_votes = tmdb_min_votes
        self.include_no_ratings = include_no_ratings
        self.language_filter = filter_language
        self.release_year_filter = filter_release_year
        self.genre_filter = filter_genre
        self.pages = (self.search_size + CONTENT_PER_PAGE - 1) // CONTENT_PER_PAGE
        self.tmdb_api_url = "https://api.themoviedb.org/3"

    async def _fetch_recommendations(self, content_id, content_type):
        """
        Fetches recommendations for a specific movie or TV show by applying filters.
        """
        search = []
        for page in range(1, self.pages + 1):
            data = await self._fetch_page_data(content_id, content_type, page)
            if not data:
                break

            for item in data['results']:
                if self._apply_filters(item, content_type):
                    search.append(self._format_result(item, content_type))

                # Stop if we reach the search size limit
                if len(search) >= self.search_size:
                    break

            if len(search) >= self.search_size:
                break

            # Sleep to avoid rate limiting
            if page < self.pages:
                await asyncio.sleep(RATE_LIMIT_SLEEP)

        return search[:self.search_size]

    async def _fetch_page_data(self, content_id, content_type, page):
        """
        Fetches a single page of recommendations from TMDb API.
        """
        url = f"{self.tmdb_api_url}/{content_type}/{content_id}/recommendations?api_key={self.api_key}&page={page}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status in HTTP_OK:
                        return await response.json()
                    else:
                        self.logger.error("Error retrieving %s recommendations: %d", content_type, response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while requesting %s recommendations: %s", content_type, str(e))
        return None
    
    async def get_metadata(self, tmdb_id, content_type):
        """
        Fetch metadata for a movie or TV show by its TMDb ID.
        :param tmdb_id: The TMDb ID of the movie or TV show.
        :param content_type: The type of content ('movie' or 'tv').
        :return: A dictionary with metadata details or None if not found.
        """
        url = f"{self.tmdb_api_url}/{content_type}/{tmdb_id}?api_key={self.api_key}"
        images_url = f"{self.tmdb_api_url}/{content_type}/{tmdb_id}/images?api_key={self.api_key}&include_image_language=en,null"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as details_response:
                    if details_response.status in HTTP_OK:
                        data = await details_response.json()
                        metadata = self._format_result(data, content_type)
                    else:
                        self.logger.error("Failed to retrieve metadata for TMDb ID %s: %d", tmdb_id, details_response.status)
                        return None

                # Fetch images for logo
                async with session.get(images_url, timeout=REQUEST_TIMEOUT) as images_response:
                    if images_response.status in HTTP_OK:
                        images_data = await images_response.json()
                        logos = images_data.get("logos", [])
                        logo_path = logos[0]["file_path"] if logos else None
                        metadata["logo_path"] = f"https://image.tmdb.org/t/p/w500{logo_path}"
                    else:
                        self.logger.warning("Failed to retrieve logos for TMDb ID %s: %d", tmdb_id, images_response.status)
                        metadata["logo_path"] = None

            return metadata

        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while fetching metadata for TMDb ID %s: %s", tmdb_id, str(e))
        
        return None

    def _apply_filters(self, item, content_type):
        """
        Applies rating, country, release year, and genre filters to a content item.
        Returns True if the item passes all filters, False otherwise.
        """
        rating = item.get('vote_average')
        votes = item.get('vote_count')

        if self.include_no_ratings and (rating is None or votes is None):
            self._log_exclusion_reason(item, "missing rating or votes", content_type)
            return False
        
        original_language = item.get('original_language')
        selected_language_ids = [lang['id'] for lang in self.language_filter] if self.language_filter else []
        if self.language_filter and original_language not in selected_language_ids:
            selected_language_names = ', '.join([lang['english_name'] for lang in self.language_filter])
            self._log_exclusion_reason(
                item,
                f"language '{original_language}' not in selected languages: {selected_language_names}",
                content_type
            )
            return False

        if rating is not None and rating < self.tmdb_threshold / 10:
            self._log_exclusion_reason(item, f"rating below threshold of {int(self.tmdb_threshold)}%", content_type)
            return False

        if votes is not None and votes < self.tmdb_min_votes:
            self._log_exclusion_reason(item, f"votes below minimum threshold of {self.tmdb_min_votes}", content_type)
            return False

        release_date = item.get('release_date') if content_type == 'movie' else item.get('first_air_date')
        if release_date and int(release_date[:4]) < self.release_year_filter:
            self._log_exclusion_reason(item, f"release year {release_date[:4]} before {self.release_year_filter}", content_type)
            return False

        item_genres = item.get('genre_ids', [])
        genre_ids_to_exclude = [genre['id'] for genre in self.genre_filter]
        if any(genre_id in item_genres for genre_id in genre_ids_to_exclude):
            excluded_genres = [genre['name'] for genre in self.genre_filter if genre['id'] in item_genres]
            self._log_exclusion_reason(item, f"excluded genres: {', '.join(excluded_genres)}", content_type)
            return False

        return True

    def _log_exclusion_reason(self, item, reason, content_type):
        """
        Logs the reason for excluding a content item.
        """
        title = item.get('title' if content_type == 'movie' else 'name')
        self.logger.info(f"Excluding {title} due to {reason}.")

    def _format_result(self, item, content_type):
        """
        Formats a content item for the final search result.
        """
        return {
            'id': item['id'],
            'title': item['title' if content_type == 'movie' else 'name'],
            'rating': item.get('vote_average'),
            'votes': item.get('vote_count'),
            'release_date': item.get('release_date') if content_type == 'movie' else item.get('first_air_date'),
            'origin_country': item.get('origin_country', []),
            'original_language': item.get('original_language', ''),
            'poster_path': f"https://image.tmdb.org/t/p/w500{item.get('poster_path', 0)}",
            'overview': item.get('overview'),
            'genre_ids': item.get('genre_ids', []),
            'backdrop_path': f"https://image.tmdb.org/t/p/w1280/{item.get('backdrop_path', 0)}" if item.get('backdrop_path') else None
        }


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
