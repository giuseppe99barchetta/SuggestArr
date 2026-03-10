"""
TMDb Discover API client for searching content with filters.
Provides functionality to discover movies and TV shows using various filter criteria.
"""
import aiohttp
import asyncio
from typing import Any, Dict, List, Optional

from api_service.config.logger_manager import LoggerManager
from api_service.services.filter_normalization import build_tmdb_params, normalize_filters

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

    def __init__(self, api_key: str, omdb_client=None):
        """
        Initialize the TMDb Discover client.

        Args:
            api_key: TMDb API key for authentication.
            omdb_client: Optional OmdbClient for per-job IMDB rating filtering.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.api_key = api_key
        self.omdb_client = omdb_client
        self.tmdb_api_url = "https://api.themoviedb.org/3"
        self.session = None
        self.logger.debug("TMDbDiscover initialized")

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

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
        normalized_filters = normalize_filters(filters)
        self.logger.debug(f"Discovering movies with normalized filters: {normalized_filters}")
        return await self._discover('movie', {**(filters or {}), **normalized_filters}, max_results)

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
        normalized_filters = normalize_filters(filters)
        self.logger.debug(f"Discovering TV shows with normalized filters: {normalized_filters}")
        return await self._discover('tv', {**(filters or {}), **normalized_filters}, max_results)

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

        # Extract per-job IMDB filter params (not sent to TMDB API)
        rating_source = filters.get('rating_source', 'tmdb')
        imdb_rating_gte = filters.get('imdb_rating_gte')   # 0–10 scale from the UI slider
        imdb_min_votes = filters.get('imdb_min_votes')
        include_no_rating = filters.get('include_no_rating', True)
        use_imdb = rating_source in ('imdb', 'both') and self.omdb_client is not None

        if use_imdb:
            self.logger.info(
                "IMDB filtering enabled for %s discover (source=%s, rating>=%s, votes>=%s)",
                media_type, rating_source, imdb_rating_gte, imdb_min_votes
            )

        for page in range(1, pages_needed + 1):
            self.logger.debug(f"Fetching discover page {page} for {media_type}")

            data = await self._fetch_discover_page(media_type, filters, page)
            if not data or 'results' not in data:
                self.logger.warning(f"No data returned for page {page}")
                break

            for item in data['results']:
                if use_imdb:
                    imdb_id = await self._get_imdb_id(item['id'], media_type)
                    if imdb_id:
                        imdb_data = await self.omdb_client.get_rating(imdb_id)
                        if not self._check_imdb_filter(
                            imdb_data, item, imdb_rating_gte, imdb_min_votes, include_no_rating
                        ):
                            continue
                    elif not include_no_rating:
                        title = item.get('title') or item.get('name', 'Unknown')
                        self.logger.debug("Excluding %s: no IMDB ID found in TMDB data", title)
                        continue

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
        normalized_filters = normalize_filters(filters)
        merged_filters = {**(filters or {}), **normalized_filters}

        query_params = self._build_query_params(merged_filters)
        query_params['page'] = page
        query_params['api_key'] = self.api_key

        self.logger.debug("Discover filters: %s", merged_filters)
        self.logger.debug("TMDb params: %s", query_params)

        # Build query string
        query_string = '&'.join(f"{k}={v}" for k, v in query_params.items())
        url = f"{self.tmdb_api_url}/discover/{media_type}?{query_string}"

        self.logger.debug(f"Fetching URL: {url[:100]}...")

        try:
            session = await self._get_session()
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

    async def _get_imdb_id(self, tmdb_id: int, media_type: str) -> Optional[str]:
        """
        Fetch IMDB ID from TMDB for a movie or TV show.

        Args:
            tmdb_id: TMDB content ID.
            media_type: 'movie' or 'tv'.

        Returns:
            IMDB ID string (e.g. 'tt0816692') or None if unavailable.
        """
        try:
            if media_type == 'movie':
                url = f"{self.tmdb_api_url}/movie/{tmdb_id}?api_key={self.api_key}"
            else:
                url = f"{self.tmdb_api_url}/tv/{tmdb_id}/external_ids?api_key={self.api_key}"

            session = await self._get_session()
            async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                if response.status in HTTP_OK:
                    data = await response.json()
                    return data.get('imdb_id')
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.logger.debug("Failed to fetch IMDB ID for %s %s: %s", media_type, tmdb_id, e)
        return None

    def _check_imdb_filter(
        self,
        imdb_data: Optional[Dict[str, Any]],
        item: Dict[str, Any],
        imdb_rating_gte: Optional[float],
        imdb_min_votes: Optional[int],
        include_no_rating: bool
    ) -> bool:
        """
        Return True if item should be included based on IMDB rating data.

        Args:
            imdb_data: Dict with 'imdb_rating' and 'imdb_votes', or None.
            item: Raw TMDB result item (for logging).
            imdb_rating_gte: Minimum IMDB rating on 0–10 scale, or None.
            imdb_min_votes: Minimum IMDB vote count, or None.
            include_no_rating: If True, pass through items with no IMDB data.

        Returns:
            True if the item passes the filter, False otherwise.
        """
        title = item.get('title') or item.get('name', 'Unknown')

        if not imdb_data:
            if include_no_rating:
                return True
            self.logger.debug("Excluding %s: no IMDB rating data available", title)
            return False

        rating = imdb_data.get('imdb_rating', 0)
        votes = imdb_data.get('imdb_votes', 0)

        if imdb_rating_gte is not None and rating < float(imdb_rating_gte):
            self.logger.debug(
                "Excluding %s: IMDB rating %.1f below threshold %.1f", title, rating, imdb_rating_gte
            )
            return False

        if imdb_min_votes is not None and votes < int(imdb_min_votes):
            self.logger.debug(
                "Excluding %s: IMDB votes %d below minimum %d", title, votes, imdb_min_votes
            )
            return False

        return True

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
        normalized_filters = normalize_filters(filters)

        # Canonical filters are converted centrally, then adapted to TMDb API key format.
        canonical_tmdb_params = build_tmdb_params(normalized_filters)
        tmdb_key_mapping = {
            'primary_release_date_gte': 'primary_release_date.gte',
            'primary_release_date_lte': 'primary_release_date.lte',
            'vote_average_gte': 'vote_average.gte',
            'with_original_language': 'with_original_language',
            'with_genres': 'with_genres',
        }
        for source_key, target_key in tmdb_key_mapping.items():
            if source_key in canonical_tmdb_params:
                params[target_key] = canonical_tmdb_params[source_key]

        year_from = normalized_filters.get('year_from')
        if year_from is not None and 'first_air_date_gte' not in filters:
            params['first_air_date.gte'] = f"{year_from}-01-01"

        year_to = normalized_filters.get('year_to')
        if year_to is not None and 'first_air_date_lte' not in filters:
            params['first_air_date.lte'] = f"{year_to}-12-31"

        # Determine if TMDB rating/vote filters should be skipped
        # (when IMDB-only source is selected, TMDB rating checks are replaced by IMDB checks)
        rating_source = filters.get('rating_source', 'tmdb')
        skip_tmdb_rating = rating_source == 'imdb'
        if skip_tmdb_rating:
            params.pop('vote_average.gte', None)

        # Direct parameter mapping (internal IMDB keys are intentionally excluded)
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
            if skip_tmdb_rating and filter_key in ('vote_average_gte', 'vote_count_gte'):
                continue
            if filter_key not in filters:
                continue

            value = filters[filter_key]
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue

            if filter_key == 'with_original_language':
                normalized = self._normalize_language_code(value)
                if not normalized:
                    continue
                params[api_key] = normalized
                continue

            params[api_key] = value

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

    @staticmethod
    def _normalize_language_code(value: Any) -> Optional[str]:
        """Normalize language filter values to ISO 639-1/2 code when possible."""
        if isinstance(value, dict):
            for key in ('iso_639_1', 'id', 'code'):
                if key in value:
                    return TMDbDiscover._normalize_language_code(value.get(key))
            return None

        if isinstance(value, list):
            if not value:
                return None
            return TMDbDiscover._normalize_language_code(value[0])

        if not isinstance(value, str):
            return None

        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized in ('any language', 'any', 'all'):
            return None
        if not normalized.isalpha() or len(normalized) not in (2, 3):
            return None
        return normalized

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
            session = await self._get_session()
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
            session = await self._get_session()
            async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                if response.status in HTTP_OK:
                    return await response.json()
                else:
                    self.logger.error(f"Error fetching languages: {response.status}")
        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error fetching languages: {str(e)}")

        return []

    async def get_watch_regions(self) -> List[Dict[str, Any]]:
        """
        Get the list of available watch provider regions from TMDb.

        Returns:
            List of region dicts with iso_3166_1 and english_name keys.
        """
        url = f"{self.tmdb_api_url}/watch/providers/regions?api_key={self.api_key}"

        try:
            session = await self._get_session()
            async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                if response.status in HTTP_OK:
                    data = await response.json()
                    return sorted(data.get('results', []), key=lambda x: x.get('english_name', ''))
                else:
                    self.logger.error(f"Error fetching watch regions: {response.status}")
        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error fetching watch regions: {str(e)}")

        return []

    async def get_streaming_providers(self, region: str) -> List[Dict[str, Any]]:
        """
        Get the list of available streaming providers for a region from TMDb.

        Args:
            region: ISO 3166-1 region code (e.g. 'IT', 'US').

        Returns:
            List of provider dicts with provider_id and provider_name keys.
        """
        url = f"{self.tmdb_api_url}/watch/providers/movie?api_key={self.api_key}&watch_region={region}"

        try:
            session = await self._get_session()
            async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                if response.status in HTTP_OK:
                    data = await response.json()
                    return sorted(
                        data.get('results', []),
                        key=lambda x: x.get('display_priority', 999)
                    )
                else:
                    self.logger.error(f"Error fetching streaming providers: {response.status}")
        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error fetching streaming providers: {str(e)}")

        return []
