"""
TMDb Discover API client for searching content with filters.
Provides functionality to discover movies and TV shows using various filter criteria.
"""
import aiohttp
import asyncio
from typing import Any, Dict, List, Optional

from api_service.config.logger_manager import LoggerManager

# Constants
HTTP_OK = {200, 201}
REQUEST_TIMEOUT = 10
CONTENT_PER_PAGE = 20
RATE_LIMIT_SLEEP = 0.3


class TMDbDiscover:
    """
    Client for TMDb Discover API endpoints.
    Allows searching for movies and TV shows using various filters.
    """

    def __init__(self, api_key: str):
        """
        Initialize the TMDb Discover client.

        Args:
            api_key: TMDb API key for authentication.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.api_key = api_key
        self.tmdb_api_url = "https://api.themoviedb.org/3"
        self.logger.debug("TMDbDiscover initialized")

    async def discover_movies(
        self,
        filters: Dict[str, Any],
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Discover movies using the TMDb Discover API with filters.

        Args:
            filters: Dictionary of filter parameters.
            max_results: Maximum number of results to return.

        Returns:
            List of movie dictionaries matching the filters.
        """
        self.logger.debug(f"Discovering movies with filters: {filters}")
        return await self._discover('movie', filters, max_results)

    async def discover_tv(
        self,
        filters: Dict[str, Any],
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Discover TV shows using the TMDb Discover API with filters.

        Args:
            filters: Dictionary of filter parameters.
            max_results: Maximum number of results to return.

        Returns:
            List of TV show dictionaries matching the filters.
        """
        self.logger.debug(f"Discovering TV shows with filters: {filters}")
        return await self._discover('tv', filters, max_results)

    async def _discover(
        self,
        media_type: str,
        filters: Dict[str, Any],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Internal method to perform discover API calls.

        Args:
            media_type: 'movie' or 'tv'.
            filters: Dictionary of filter parameters.
            max_results: Maximum number of results to return.

        Returns:
            List of content dictionaries.
        """
        results = []
        pages_needed = (max_results + CONTENT_PER_PAGE - 1) // CONTENT_PER_PAGE

        for page in range(1, pages_needed + 1):
            self.logger.debug(f"Fetching discover page {page} for {media_type}")

            data = await self._fetch_discover_page(media_type, filters, page)
            if not data or 'results' not in data:
                self.logger.warning(f"No data returned for page {page}")
                break

            for item in data['results']:
                formatted = self._format_result(item, media_type)
                results.append(formatted)

                if len(results) >= max_results:
                    break

            if len(results) >= max_results:
                break

            # Check if there are more pages
            if page >= data.get('total_pages', 1):
                break

            # Rate limit delay
            if page < pages_needed:
                await asyncio.sleep(RATE_LIMIT_SLEEP)

        self.logger.info(f"Discovered {len(results)} {media_type} items")
        return results[:max_results]

    async def _fetch_discover_page(
        self,
        media_type: str,
        filters: Dict[str, Any],
        page: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a single page from the TMDb Discover API.

        Args:
            media_type: 'movie' or 'tv'.
            filters: Dictionary of filter parameters.
            page: Page number to fetch.

        Returns:
            API response data or None on error.
        """
        query_params = self._build_query_params(filters)
        query_params['page'] = page
        query_params['api_key'] = self.api_key

        # Build query string
        query_string = '&'.join(f"{k}={v}" for k, v in query_params.items())
        url = f"{self.tmdb_api_url}/discover/{media_type}?{query_string}"

        self.logger.debug(f"Fetching URL: {url[:100]}...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status in HTTP_OK:
                        return await response.json()
                    else:
                        self.logger.error(
                            f"Error fetching discover {media_type}: {response.status}"
                        )
        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error during discover: {str(e)}")
        except asyncio.TimeoutError:
            self.logger.error("Timeout during discover request")

        return None

    def _build_query_params(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build TMDb API query parameters from filter dictionary.

        Supported filters:
        - vote_average_gte: Minimum rating (0-10)
        - vote_average_lte: Maximum rating (0-10)
        - vote_count_gte: Minimum vote count
        - primary_release_date_gte: Release date from (YYYY-MM-DD)
        - primary_release_date_lte: Release date to (YYYY-MM-DD)
        - first_air_date_gte: First air date from (YYYY-MM-DD) for TV
        - first_air_date_lte: First air date to (YYYY-MM-DD) for TV
        - with_genres: Include genres (comma-separated IDs)
        - without_genres: Exclude genres (comma-separated IDs)
        - with_original_language: Language code (en, it, ja, etc.)
        - sort_by: Sort order (popularity.desc, vote_average.desc, etc.)
        - include_adult: Include adult content (default False)

        Args:
            filters: Dictionary of filter parameters.

        Returns:
            Dictionary of TMDb API query parameters.
        """
        params = {}

        # Direct parameter mapping
        param_mapping = {
            'vote_average_gte': 'vote_average.gte',
            'vote_average_lte': 'vote_average.lte',
            'vote_count_gte': 'vote_count.gte',
            'vote_count_lte': 'vote_count.lte',
            'primary_release_date_gte': 'primary_release_date.gte',
            'primary_release_date_lte': 'primary_release_date.lte',
            'first_air_date_gte': 'first_air_date.gte',
            'first_air_date_lte': 'first_air_date.lte',
            'with_original_language': 'with_original_language',
            'sort_by': 'sort_by',
            'include_adult': 'include_adult',
            'with_runtime_gte': 'with_runtime.gte',
            'with_runtime_lte': 'with_runtime.lte',
            'min_runtime': 'with_runtime.gte',
        }

        for filter_key, api_key in param_mapping.items():
            if filter_key in filters and filters[filter_key] is not None:
                params[api_key] = filters[filter_key]

        # Handle genres (can be list or comma-separated string)
        if 'with_genres' in filters and filters['with_genres']:
            genres = filters['with_genres']
            if isinstance(genres, list):
                params['with_genres'] = ','.join(str(g) for g in genres)
            else:
                params['with_genres'] = str(genres)

        if 'without_genres' in filters and filters['without_genres']:
            genres = filters['without_genres']
            if isinstance(genres, list):
                params['without_genres'] = ','.join(str(g) for g in genres)
            else:
                params['without_genres'] = str(genres)

        # Default sort if not specified
        if 'sort_by' not in params:
            params['sort_by'] = 'popularity.desc'

        # Default to exclude adult content
        if 'include_adult' not in params:
            params['include_adult'] = 'false'

        self.logger.debug(f"Built query params: {params}")
        return params

    def _format_result(self, item: Dict[str, Any], media_type: str) -> Dict[str, Any]:
        """
        Format a TMDb API result item.

        Args:
            item: Raw API result item.
            media_type: 'movie' or 'tv'.

        Returns:
            Formatted result dictionary.
        """
        return {
            'id': item['id'],
            'title': item.get('title') if media_type == 'movie' else item.get('name'),
            'media_type': media_type,
            'rating': item.get('vote_average'),
            'votes': item.get('vote_count'),
            'release_date': (
                item.get('release_date') if media_type == 'movie'
                else item.get('first_air_date')
            ),
            'origin_country': item.get('origin_country', []),
            'original_language': item.get('original_language', ''),
            'poster_path': (
                f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}"
                if item.get('poster_path') else None
            ),
            'backdrop_path': (
                f"https://image.tmdb.org/t/p/w1280{item.get('backdrop_path')}"
                if item.get('backdrop_path') else None
            ),
            'overview': item.get('overview'),
            'genre_ids': item.get('genre_ids', []),
            'popularity': item.get('popularity'),
        }

    async def get_genres(self, media_type: str) -> List[Dict[str, Any]]:
        """
        Get the list of available genres from TMDb.

        Args:
            media_type: 'movie' or 'tv'.

        Returns:
            List of genre dictionaries with id and name.
        """
        url = f"{self.tmdb_api_url}/genre/{media_type}/list?api_key={self.api_key}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status in HTTP_OK:
                        data = await response.json()
                        return data.get('genres', [])
                    else:
                        self.logger.error(f"Error fetching genres: {response.status}")
        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error fetching genres: {str(e)}")

        return []

    async def get_languages(self) -> List[Dict[str, Any]]:
        """
        Get the list of available languages from TMDb.

        Returns:
            List of language dictionaries.
        """
        url = f"{self.tmdb_api_url}/configuration/languages?api_key={self.api_key}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status in HTTP_OK:
                        return await response.json()
                    else:
                        self.logger.error(f"Error fetching languages: {response.status}")
        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error fetching languages: {str(e)}")

        return []
