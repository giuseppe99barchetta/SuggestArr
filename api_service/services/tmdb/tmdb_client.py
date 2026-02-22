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

    def __init__(self, api_key, search_size, tmdb_threshold, tmdb_min_votes,
                include_no_ratings, filter_release_year, filter_language, filter_genre,
                filter_region_provider, filter_streaming_services, filter_min_runtime=None,
                rating_source='tmdb', imdb_threshold=None, imdb_min_votes=None,
                omdb_client=None
                ):
        """
        Initializes the TMDbClient with the provided API key.
        :param api_key: API key to authenticate requests to TMDb.
        :param filter_min_runtime: Minimum runtime in minutes; items shorter than this are excluded.
        :param rating_source: Which rating source to use for filtering ('tmdb', 'imdb', or 'both').
        :param imdb_threshold: Minimum IMDB rating threshold (0-100 scale).
        :param imdb_min_votes: Minimum IMDB vote count.
        :param omdb_client: OmdbClient instance for IMDB rating lookups, or None.
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
        self.region_provider = filter_region_provider
        self.excluded_streaming_services = filter_streaming_services
        self.filter_min_runtime = int(filter_min_runtime) if filter_min_runtime else None
        self.rating_source = rating_source
        self.imdb_threshold = int(imdb_threshold) if imdb_threshold is not None else 60
        self.imdb_min_votes = int(imdb_min_votes) if imdb_min_votes is not None else 100
        self.omdb_client = omdb_client
        self.tmdb_api_url = "https://api.themoviedb.org/3"
        self.logger.debug("TMDbClient initialized with API key: ***")

    async def _fetch_recommendations(self, content_id, content_type):
        """
        Fetches recommendations for a specific movie or TV show by applying filters.
        """
        self.logger.debug("Fetching recommendations for %s with ID %s", content_type, content_id)
        search = []
        for page in range(1, self.pages + 1):
            self.logger.debug("Fetching page %d of recommendations", page)
            data = await self._fetch_page_data(content_id, content_type, page)
            if not data:
                self.logger.debug("No data returned for page %d", page)
                break

            for item in data['results']:
                if self._apply_filters(item, content_type):
                    needs_detail_call = self.filter_min_runtime or self.rating_source in ('imdb', 'both')
                    imdb_id = None

                    if needs_detail_call:
                        details = await self._get_item_details(item['id'], content_type)
                        runtime = details.get('runtime') if details else None
                        imdb_id = details.get('imdb_id') if details else None

                        if self.filter_min_runtime and runtime is not None and runtime < self.filter_min_runtime:
                            self._log_exclusion_reason(
                                item,
                                f"runtime {runtime}min below minimum {self.filter_min_runtime}min",
                                content_type
                            )
                            continue

                    if self.rating_source in ('imdb', 'both') and self.omdb_client:
                        if imdb_id:
                            imdb_data = await self.omdb_client.get_rating(imdb_id)
                            if not self._apply_imdb_filter(imdb_data, item, content_type):
                                continue
                        elif self.include_no_ratings:
                            self._log_exclusion_reason(item, "no IMDB ID found", content_type)
                            continue

                    search.append(self._format_result(item, content_type))

                # Stop if we reach the search size limit
                if len(search) >= self.search_size:
                    self.logger.debug("Reached search size limit of %d", self.search_size)
                    break

            if len(search) >= self.search_size:
                break

            # Sleep to avoid rate limiting
            if page < self.pages:
                self.logger.debug("Sleeping for %f seconds to avoid rate limiting", RATE_LIMIT_SLEEP)
                await asyncio.sleep(RATE_LIMIT_SLEEP)

        self.logger.debug("Returning %d recommendations", len(search))
        return search[:self.search_size]

    async def _fetch_page_data(self, content_id, content_type, page):
        """
        Fetches a single page of recommendations from TMDb API.
        """
        url = f"{self.tmdb_api_url}/{content_type}/{content_id}/recommendations?api_key={self.api_key}&page={page}"
        self.logger.debug("Fetching data from URL: %s", url)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status in HTTP_OK:
                        self.logger.debug("Successfully fetched data for page %d", page)
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
        self.logger.debug("Fetching metadata for %s with ID %s", content_type, tmdb_id)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as details_response:
                    if details_response.status in HTTP_OK:
                        data = await details_response.json()
                        metadata = self._format_result(data, content_type)
                        self.logger.debug("Successfully fetched metadata for %s with ID %s", content_type, tmdb_id)
                    else:
                        self.logger.error("Failed to retrieve metadata for TMDb ID %s: %d", tmdb_id, details_response.status)
                        return None

                # Fetch images for logo
                async with session.get(images_url, timeout=REQUEST_TIMEOUT) as images_response:
                    if images_response.status in HTTP_OK:
                        images_data = await images_response.json()
                        logos = images_data.get("logos", [])
                        logo_path = logos[0]["file_path"] if logos else None
                        if logo_path:
                            metadata["logo_path"] = f"https://image.tmdb.org/t/p/w500{logo_path}"
                        self.logger.debug("Successfully fetched logo for %s with ID %s", content_type, tmdb_id)
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

        When rating_source is 'imdb', TMDB vote_average/vote_count checks are skipped
        (IMDB rating will be checked separately via OMDb). All other TMDB filters
        (language, genre, year, streaming) are always applied.
        """
        # Support both raw TMDB API keys (vote_average / vote_count) and the
        # formatted keys produced by _format_result (rating / votes) so that
        # _apply_filters works correctly whether called on raw or formatted items.
        rating = item.get('vote_average') if item.get('vote_average') is not None else item.get('rating')
        votes = item.get('vote_count') if item.get('vote_count') is not None else item.get('votes')

        # Only apply TMDB rating/votes filters when TMDB ratings are used
        if self.rating_source != 'imdb':
            # Exclude items that have no rating data only when the user has opted out
            # of including unrated content (include_no_ratings=False means "require ratings").
            if not self.include_no_ratings and (rating is None or votes is None):
                self._log_exclusion_reason(item, "missing rating or votes", content_type)
                return False

        original_language = item.get('original_language')
        
        if self.language_filter:
            selected_language_ids = []
            selected_language_names = []
            for lang in self.language_filter:
                if isinstance(lang, dict):
                    selected_language_ids.append(lang.get('id', lang.get('iso_639_1')))
                    selected_language_names.append(lang.get('english_name', lang.get('name', str(lang))))
                else:
                    selected_language_ids.append(lang)
                    selected_language_names.append(str(lang))
            
            if original_language not in selected_language_ids:
                names_str = ', '.join(selected_language_names)
                self._log_exclusion_reason(
                    item,
                    f"language '{original_language}' not in selected languages: {names_str}",
                    content_type
                )
                return False

        if self.rating_source != 'imdb':
            if rating is not None and rating < self.tmdb_threshold / 10:
                self._log_exclusion_reason(item, f"TMDB rating below threshold of {int(self.tmdb_threshold)}%", content_type)
                return False

            if votes is not None and votes < self.tmdb_min_votes:
                self._log_exclusion_reason(item, f"TMDB votes below minimum threshold of {self.tmdb_min_votes}", content_type)
                return False

        release_date = item.get('release_date') if content_type == 'movie' else item.get('first_air_date')
        if release_date and int(release_date[:4]) < self.release_year_filter:
            self._log_exclusion_reason(item, f"release year {release_date[:4]} before {self.release_year_filter}", content_type)
            return False

        item_genres = item.get('genre_ids', [])
        
        if self.genre_filter:
            genre_ids_to_exclude = []
            excluded_genres_names = []
            
            for genre in self.genre_filter:
                if isinstance(genre, dict):
                    genre_id = genre.get('id')
                    genre_ids_to_exclude.append(genre_id)
                    if genre_id in item_genres:
                        excluded_genres_names.append(genre.get('name', str(genre_id)))
                else:
                    # Primitive integer
                    try:
                        genre_id = int(genre)
                        genre_ids_to_exclude.append(genre_id)
                        if genre_id in item_genres:
                            excluded_genres_names.append(str(genre_id))
                    except (ValueError, TypeError):
                        pass

            if any(genre_id in item_genres for genre_id in genre_ids_to_exclude):
                self._log_exclusion_reason(item, f"excluded genres: {', '.join(excluded_genres_names)}", content_type)
                return False

        return True

    async def _get_item_details(self, content_id, content_type):
        """
        Fetches runtime and IMDB ID for a movie or TV show from TMDb in a single call.

        For movies, uses the standard details endpoint which includes both 'runtime'
        and 'imdb_id'. For TV shows, the details endpoint provides 'episode_run_time'
        but not the IMDB ID — a separate '/external_ids' call is made to retrieve it.

        :param content_id: The TMDb ID of the content item.
        :param content_type: Either 'movie' or 'tv'.
        :return: dict with 'runtime' (int|None) and 'imdb_id' (str|None), or empty dict on error.
        """
        url = f"{self.tmdb_api_url}/{content_type}/{content_id}?api_key={self.api_key}"
        self.logger.debug("Fetching details for %s ID %s", content_type, content_id)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status in HTTP_OK:
                        data = await response.json()
                        if content_type == 'movie':
                            return {
                                'runtime': data.get('runtime'),
                                'imdb_id': data.get('imdb_id'),
                            }
                        else:
                            run_times = data.get('episode_run_time', [])
                            runtime = run_times[0] if run_times else None
                            # TV details don't include imdb_id; fetch from external_ids
                            imdb_id = await self._get_tv_imdb_id(content_id)
                            return {'runtime': runtime, 'imdb_id': imdb_id}
                    else:
                        self.logger.warning("Failed to fetch details for %s ID %s: HTTP %d",
                                            content_type, content_id, response.status)
        except aiohttp.ClientError as e:
            self.logger.warning("Error fetching details for %s ID %s: %s",
                                content_type, content_id, str(e))
        return {}

    async def _get_tv_imdb_id(self, tv_id):
        """
        Fetches the IMDB ID for a TV show from TMDb's external_ids endpoint.

        :param tv_id: The TMDb ID of the TV show.
        :return: IMDB ID string (e.g. 'tt1234567') or None if not available.
        """
        url = f"{self.tmdb_api_url}/tv/{tv_id}/external_ids?api_key={self.api_key}"
        self.logger.debug("Fetching external IDs for TV ID %s", tv_id)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status in HTTP_OK:
                        data = await response.json()
                        return data.get('imdb_id')
                    else:
                        self.logger.warning("Failed to fetch external IDs for TV ID %s: HTTP %d",
                                            tv_id, response.status)
        except aiohttp.ClientError as e:
            self.logger.warning("Error fetching external IDs for TV ID %s: %s", tv_id, str(e))
        return None

    def _apply_imdb_filter(self, imdb_data, item, content_type):
        """
        Checks IMDB rating and vote count against configured thresholds.

        Args:
            imdb_data (dict | None): Result from OmdbClient.get_rating(); may be None.
            item (dict): The TMDb recommendation item (used for logging).
            content_type (str): 'movie' or 'tv'.

        Returns:
            bool: True if the item passes IMDB filters, False if it should be excluded.
        """
        if imdb_data is None:
            if self.include_no_ratings:
                self._log_exclusion_reason(item, "no IMDB rating data available", content_type)
                return False
            return True

        imdb_rating = imdb_data.get('imdb_rating')
        imdb_votes = imdb_data.get('imdb_votes')

        if imdb_rating is not None and imdb_rating < self.imdb_threshold / 10:
            self._log_exclusion_reason(
                item,
                f"IMDB rating {imdb_rating} below threshold of {self.imdb_threshold / 10:.1f}",
                content_type
            )
            return False

        if imdb_votes is not None and imdb_votes < self.imdb_min_votes:
            self._log_exclusion_reason(
                item,
                f"IMDB votes {imdb_votes} below minimum of {self.imdb_min_votes}",
                content_type
            )
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
            'poster_path': f"https://image.tmdb.org/t/p/w500{item.get('poster_path', 0)}" if item.get('poster_path') else None,
            'overview': item.get('overview'),
            'genre_ids': item.get('genre_ids', []),
            'backdrop_path': f"https://image.tmdb.org/t/p/w1280/{item.get('backdrop_path', 0)}" if item.get('backdrop_path') else None
        }


    async def find_similar_movies(self, movie_id):
        """
        Finds movies similar to the one with the given movie_id.
        """
        self.logger.debug("Finding similar movies for movie ID %s", movie_id)
        return await self._fetch_recommendations(movie_id, 'movie')

    async def find_similar_tvshows(self, tvshow_id):
        """
        Finds TV shows similar to the one with the given tvshow_id.
        """
        self.logger.debug("Finding similar TV shows for TV show ID %s", tvshow_id)
        return await self._fetch_recommendations(tvshow_id, 'tv')

    async def find_tmdb_id_from_tvdb(self, tvdb_id):
        """
        Finds the TMDb ID for a TV show using its TVDb ID asynchronously.
        :param tvdb_id: The TVDb ID to convert to TMDb ID.
        :return: The TMDb ID corresponding to the provided TVDb ID, or None if not found.
        """
        url = f"{self.tmdb_api_url}/find/{tvdb_id}?api_key={self.api_key}&external_source=tvdb_id"
        self.logger.debug("Finding TMDb ID for TVDb ID %s", tvdb_id)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status in HTTP_OK:
                        data = await response.json()
                        if 'tv_results' in data and data['tv_results']:
                            self.logger.debug("Found TMDb ID %s for TVDb ID %s", data['tv_results'][0]['id'], tvdb_id)
                            return data['tv_results'][0]['id']
                        self.logger.warning("No results found on TMDb for TVDb ID: %s", tvdb_id)
                    else:
                        self.logger.error("Error converting TVDb ID to TMDb ID: %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while converting TVDb ID: %s", str(e))

        return None
    
    async def get_watch_providers(self, content_id, content_type):
        """
        Retrieves the streaming providers for a specific movie or TV show.

        :param content_id: The TMDb ID of the movie or TV show.
        :param content_type: The type of content ('movie' or 'tv').
        :return: A tuple (is_excluded, provider_name), where:
                 - is_excluded: True if the content is in an excluded streaming service, False otherwise.
                 - provider_name: The name of the excluded streaming provider, or None if not excluded.
        """
        # Check if region_provider and excluded_streaming_services are set
        if not self.region_provider or not self.excluded_streaming_services:
            self.logger.debug("Skipping watch providers check: region_provider or excluded_streaming_services not set.")
            return False, None
        
        url = f"{self.tmdb_api_url}/{content_type}/{content_id}/watch/providers?api_key={self.api_key}"
        self.logger.debug("Fetching watch providers for %s with ID %s", content_type, content_id)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status in HTTP_OK:
                        data = await response.json()
                        if "results" in data and self.region_provider in data["results"]:
                            providers = data["results"][self.region_provider]['flatrate']
                            for provider in providers:
                                if any(provider['provider_id'] == excluded['provider_id'] for excluded in self.excluded_streaming_services):
                                    self.logger.debug("Content ID %s is in excluded streaming service: %s", content_id, provider['provider_name'])
                                    return True, provider['provider_name']
                        else:
                            self.logger.debug("No watch providers found for content ID %s in region %s.", content_id, self.region_provider)
                            return False, None
                    else:
                        self.logger.error("Failed to retrieve watch providers for content ID %s: %d", content_id, response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while fetching watch providers: %s", str(e))

        return False, None

    async def search_movie(self, title, year=None):
        """
        Search for a movie by title and optionally release year.
        :param title: Movie title.
        :param year: Release year (optional).
        :return: List of formatted search results or empty list.
        """
        import urllib.parse
        encoded_title = urllib.parse.quote(str(title))
        url = f"{self.tmdb_api_url}/search/movie?api_key={self.api_key}&query={encoded_title}"
        if year:
            url += f"&year={year}"
            
        self.logger.debug("Searching TMDb for movie: %s (Year: %s)", title, year)
        return await self._execute_search(url, 'movie')

    async def search_tv(self, title, year=None):
        """
        Search for a TV show by name and optionally first air year.
        :param title: TV show name.
        :param year: First air year (optional).
        :return: List of formatted search results or empty list.
        """
        import urllib.parse
        encoded_title = urllib.parse.quote(str(title))
        url = f"{self.tmdb_api_url}/search/tv?api_key={self.api_key}&query={encoded_title}"
        if year:
            url += f"&first_air_date_year={year}"
            
        self.logger.debug("Searching TMDb for TV show: %s (Year: %s)", title, year)
        return await self._execute_search(url, 'tv')

    async def _execute_search(self, url, content_type):
        """Helper to execute search and format results."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    if response.status in HTTP_OK:
                        data = await response.json()
                        results = []
                        for item in data.get('results', []):
                            # Ensure we don't crash if format_result fails on missing keys
                            try:
                                results.append(self._format_result(item, content_type))
                            except Exception as e:
                                self.logger.warning("Failed to format search result: %s", str(e))
                        return results
                    else:
                        self.logger.error("Error searching TMDb: %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while searching TMDb: %s", str(e))
        return []

