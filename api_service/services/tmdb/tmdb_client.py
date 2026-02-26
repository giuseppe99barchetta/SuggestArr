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
                omdb_client=None, include_tvod=False
                ):
        """
        Initializes the TMDbClient with the provided API key.
        :param api_key: API key to authenticate requests to TMDb.
        :param filter_min_runtime: Minimum runtime in minutes; items shorter than this are excluded.
        :param rating_source: Which rating source to use for filtering ('tmdb', 'imdb', or 'both').
        :param imdb_threshold: Minimum IMDB rating threshold (0-100 scale).
        :param imdb_min_votes: Minimum IMDB vote count.
        :param omdb_client: OmdbClient instance for IMDB rating lookups, or None.
        :param include_tvod: If True, also check rent/buy availability when matching streaming providers.
                             If False (default), only subscription-based (flatrate) providers are checked.
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
        self.include_tvod = include_tvod
        self.tmdb_api_url = "https://api.themoviedb.org/3"
        self.session = None
        self.logger.debug("TMDbClient initialized with API key: ***")

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

    async def _fetch_recommendations(self, content_id, content_type, dry_run=False):
        """
        Fetches recommendations for a specific movie or TV show by applying filters.

        :param dry_run: When True, returns ALL candidates (including those that fail filters)
                        with a 'filter_results' dict attached to each item so the caller can
                        display which filters passed or failed. The search_size cap is not
                        applied in dry-run mode (all items from the fetched pages are returned).
        """
        self.logger.debug("Fetching recommendations for %s with ID %s (dry_run=%s)", content_type, content_id, dry_run)
        search = []
        for page in range(1, self.pages + 1):
            self.logger.debug("Fetching page %d of recommendations", page)
            data = await self._fetch_page_data(content_id, content_type, page)
            if not data:
                self.logger.debug("No data returned for page %d", page)
                break

            for item in data['results']:
                filter_result = self._apply_filters(item, content_type)
                core_passed = filter_result['passed']

                # In normal mode skip failing items early (no detail API calls wasted)
                if not dry_run and not core_passed:
                    continue

                needs_detail_call = self.filter_min_runtime or self.rating_source in ('imdb', 'both')
                runtime = None
                imdb_id = None

                # Only make detail API calls when the item passes core filters or we're in
                # dry-run mode (so we can show runtime/IMDB results for passing items).
                if needs_detail_call and (core_passed or dry_run):
                    details = await self._get_item_details(item['id'], content_type)
                    runtime = details.get('runtime') if details else None
                    imdb_id = details.get('imdb_id') if details else None

                # Runtime check
                if self.filter_min_runtime:
                    if runtime is not None:
                        runtime_passed = runtime >= self.filter_min_runtime
                        if dry_run:
                            filter_result['runtime'] = {
                                'passed': runtime_passed, 'label': 'Runtime',
                                'value': f'{runtime}min',
                                'reason': f'Below {self.filter_min_runtime}min' if not runtime_passed else None,
                            }
                            if not runtime_passed:
                                filter_result['passed'] = False
                        elif not runtime_passed:
                            self._log_exclusion_reason(
                                item,
                                f"runtime {runtime}min below minimum {self.filter_min_runtime}min",
                                content_type,
                            )
                            continue
                    elif dry_run and core_passed:
                        filter_result['runtime'] = {'passed': None, 'label': 'Runtime', 'reason': 'Unknown runtime'}

                # IMDB rating check
                if self.rating_source in ('imdb', 'both') and self.omdb_client:
                    if imdb_id:
                        imdb_data = await self.omdb_client.get_rating(imdb_id)
                        if dry_run:
                            imdb_result = self._get_imdb_filter_result(imdb_data)
                            filter_result['imdb_rating'] = imdb_result
                            if not imdb_result['passed']:
                                filter_result['passed'] = False
                        elif not self._apply_imdb_filter(imdb_data, item, content_type):
                            continue
                    else:
                        if not self.include_no_ratings:
                            if dry_run:
                                filter_result['imdb_rating'] = {
                                    'passed': False, 'label': 'IMDB',
                                    'reason': 'No IMDB ID found',
                                }
                                filter_result['passed'] = False
                            else:
                                self._log_exclusion_reason(item, "no IMDB ID found", content_type)
                                continue
                        elif dry_run and core_passed:
                            filter_result['imdb_rating'] = {
                                'passed': None, 'label': 'IMDB',
                                'reason': 'No IMDB ID',
                            }

                formatted = self._format_result(item, content_type)
                if dry_run:
                    formatted['filter_results'] = filter_result
                search.append(formatted)

                # Stop once we reach the target in normal mode
                if not dry_run and len(search) >= self.search_size:
                    self.logger.debug("Reached search size limit of %d", self.search_size)
                    break

            if not dry_run and len(search) >= self.search_size:
                break

            # Sleep to avoid rate limiting
            if page < self.pages:
                self.logger.debug("Sleeping for %f seconds to avoid rate limiting", RATE_LIMIT_SLEEP)
                await asyncio.sleep(RATE_LIMIT_SLEEP)

        self.logger.debug("Returning %d recommendations (dry_run=%s)", len(search), dry_run)
        return search if dry_run else search[:self.search_size]

    async def _fetch_page_data(self, content_id, content_type, page):
        """
        Fetches a single page of recommendations from TMDb API.
        """
        url = f"{self.tmdb_api_url}/{content_type}/{content_id}/recommendations?api_key={self.api_key}&page={page}"
        self.logger.debug("Fetching data from URL: %s", url.replace(self.api_key, "***"))
        try:
            session = await self._get_session()
            async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                if response.status in HTTP_OK:
                    self.logger.debug("Successfully fetched data for page %d", page)
                    return await response.json()
                else:
                    self.logger.error("Error retrieving %s recommendations: %d", content_type, response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while requesting %s recommendations: %s", content_type, str(e).replace(self.api_key, "***"))
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
            session = await self._get_session()
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
            self.logger.error("An error occurred while fetching metadata for TMDb ID %s: %s", tmdb_id, str(e).replace(self.api_key, "***"))
        
        return None

    def _apply_filters(self, item, content_type):
        """
        Applies rating, language, release year, and genre filters to a content item.
        Returns a dict with per-filter results and an overall 'passed' key.

        Each filter entry has at minimum {'passed': bool|None, 'label': str}.
        Optional keys: 'value' (current value), 'reason' (why it failed).
        'passed' is None when the filter is not configured / not applicable.

        When rating_source is 'imdb', TMDB vote_average/vote_count checks are skipped
        (IMDB rating will be checked separately via OMDb). All other TMDB filters
        (language, genre, year) are always applied.
        """
        results = {}
        overall = True

        # Support both raw TMDB API keys (vote_average / vote_count) and the
        # formatted keys produced by _format_result (rating / votes).
        rating = item.get('vote_average') if item.get('vote_average') is not None else item.get('rating')
        votes = item.get('vote_count') if item.get('vote_count') is not None else item.get('votes')

        # TMDB rating / votes — only when TMDB ratings are used
        if self.rating_source != 'imdb':
            if not self.include_no_ratings and (rating is None or votes is None):
                self._log_exclusion_reason(item, "missing rating or votes", content_type)
                results['tmdb_rating'] = {'passed': False, 'label': 'Rating', 'reason': 'Missing rating/votes'}
                overall = False
            else:
                rating_pass = rating is None or rating >= self.tmdb_threshold / 10
                votes_pass = votes is None or votes >= self.tmdb_min_votes

                if not rating_pass:
                    self._log_exclusion_reason(item, f"TMDB rating below threshold of {int(self.tmdb_threshold)}%", content_type)
                    results['tmdb_rating'] = {
                        'passed': False, 'label': 'Rating',
                        'value': round(rating, 1),
                        'reason': f'Below {self.tmdb_threshold}%',
                    }
                    overall = False
                else:
                    results['tmdb_rating'] = {
                        'passed': True, 'label': 'Rating',
                        'value': round(rating, 1) if rating is not None else None,
                    }

                if not votes_pass:
                    self._log_exclusion_reason(item, f"TMDB votes below minimum threshold of {self.tmdb_min_votes}", content_type)
                    results['tmdb_votes'] = {
                        'passed': False, 'label': 'Votes',
                        'value': votes,
                        'reason': f'Below {self.tmdb_min_votes}',
                    }
                    overall = False
                else:
                    results['tmdb_votes'] = {
                        'passed': True, 'label': 'Votes',
                        'value': votes,
                    }

        # Language filter
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
                    content_type,
                )
                results['language'] = {
                    'passed': False, 'label': 'Language',
                    'value': original_language,
                    'reason': f'Not in [{names_str}]',
                }
                overall = False
            else:
                results['language'] = {'passed': True, 'label': 'Language', 'value': original_language}

        # Release year filter
        release_date = item.get('release_date') if content_type == 'movie' else item.get('first_air_date')
        if release_date:
            year_str = release_date[:4]
            if int(year_str) < self.release_year_filter:
                self._log_exclusion_reason(item, f"release year {year_str} before {self.release_year_filter}", content_type)
                results['release_year'] = {
                    'passed': False, 'label': 'Year',
                    'value': year_str,
                    'reason': f'Before {self.release_year_filter}',
                }
                overall = False
            else:
                results['release_year'] = {'passed': True, 'label': 'Year', 'value': year_str}

        # Genre exclusion filter
        if self.genre_filter:
            item_genres = item.get('genre_ids', [])
            genre_ids_to_exclude = []
            excluded_genres_names = []

            for genre in self.genre_filter:
                if isinstance(genre, dict):
                    genre_id = genre.get('id')
                    genre_ids_to_exclude.append(genre_id)
                    if genre_id in item_genres:
                        excluded_genres_names.append(genre.get('name', str(genre_id)))
                else:
                    try:
                        genre_id = int(genre)
                        genre_ids_to_exclude.append(genre_id)
                        if genre_id in item_genres:
                            excluded_genres_names.append(str(genre_id))
                    except (ValueError, TypeError):
                        pass

            if any(genre_id in item_genres for genre_id in genre_ids_to_exclude):
                self._log_exclusion_reason(item, f"excluded genres: {', '.join(excluded_genres_names)}", content_type)
                results['genres'] = {
                    'passed': False, 'label': 'Genres',
                    'reason': f'Excluded: {", ".join(excluded_genres_names)}',
                }
                overall = False
            else:
                results['genres'] = {'passed': True, 'label': 'Genres'}

        results['passed'] = overall
        return results

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
            session = await self._get_session()
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
                                content_type, content_id, str(e).replace(self.api_key, "***"))
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
            session = await self._get_session()
            async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                if response.status in HTTP_OK:
                    data = await response.json()
                    return data.get('imdb_id')
                else:
                    self.logger.warning("Failed to fetch external IDs for TV ID %s: HTTP %d",
                                        tv_id, response.status)
        except aiohttp.ClientError as e:
            self.logger.warning("Error fetching external IDs for TV ID %s: %s", tv_id, str(e).replace(self.api_key, "***"))
        return None

    def _get_imdb_filter_result(self, imdb_data):
        """
        Returns a filter-result dict for the IMDB rating check (used in dry-run mode).

        :param imdb_data: Result from OmdbClient.get_rating(); may be None.
        :return: dict with 'passed' (bool|None), 'label', and optional 'value'/'reason'.
        """
        if imdb_data is None:
            if not self.include_no_ratings:
                return {'passed': False, 'label': 'IMDB', 'reason': 'No IMDB data available'}
            return {'passed': None, 'label': 'IMDB', 'reason': 'No data (allowed)'}

        imdb_rating = imdb_data.get('imdb_rating')
        imdb_votes = imdb_data.get('imdb_votes')

        if imdb_rating is not None and imdb_rating < self.imdb_threshold / 10:
            return {
                'passed': False, 'label': 'IMDB',
                'value': imdb_rating,
                'reason': f'Below {self.imdb_threshold / 10:.1f}',
            }

        if imdb_votes is not None and imdb_votes < self.imdb_min_votes:
            return {
                'passed': False, 'label': 'IMDB Votes',
                'value': imdb_votes,
                'reason': f'Below {self.imdb_min_votes}',
            }

        return {'passed': True, 'label': 'IMDB', 'value': imdb_rating}

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
            if not self.include_no_ratings:
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


    async def find_similar_movies(self, movie_id, dry_run=False):
        """
        Finds movies similar to the one with the given movie_id.

        :param dry_run: When True, returns all candidates with filter metadata attached.
        """
        self.logger.debug("Finding similar movies for movie ID %s (dry_run=%s)", movie_id, dry_run)
        return await self._fetch_recommendations(movie_id, 'movie', dry_run=dry_run)

    async def find_similar_tvshows(self, tvshow_id, dry_run=False):
        """
        Finds TV shows similar to the one with the given tvshow_id.

        :param dry_run: When True, returns all candidates with filter metadata attached.
        """
        self.logger.debug("Finding similar TV shows for TV show ID %s (dry_run=%s)", tvshow_id, dry_run)
        return await self._fetch_recommendations(tvshow_id, 'tv', dry_run=dry_run)

    async def find_tmdb_id_from_tvdb(self, tvdb_id):
        """
        Finds the TMDb ID for a TV show using its TVDb ID asynchronously.
        :param tvdb_id: The TVDb ID to convert to TMDb ID.
        :return: The TMDb ID corresponding to the provided TVDb ID, or None if not found.
        """
        url = f"{self.tmdb_api_url}/find/{tvdb_id}?api_key={self.api_key}&external_source=tvdb_id"
        self.logger.debug("Finding TMDb ID for TVDb ID %s", tvdb_id)
        try:
            session = await self._get_session()
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
            self.logger.error("An error occurred while converting TVDb ID: %s", str(e).replace(self.api_key, "***"))

        return None
    
    async def get_watch_providers(self, content_id, content_type):
        """
        Retrieves the streaming providers for a specific movie or TV show.

        By default only subscription-based (flatrate) providers are checked.
        When include_tvod=True, rent and buy availability types are also checked.

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

        # Build a set of excluded provider IDs once for O(1) lookups
        excluded_ids = {str(e['provider_id']) for e in self.excluded_streaming_services}

        try:
            session = await self._get_session()
            async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                if response.status in HTTP_OK:
                    data = await response.json()
                    if "results" in data and self.region_provider in data["results"]:
                        region_data = data["results"][self.region_provider]

                        if self.logger.isEnabledFor(10):  # DEBUG level
                            self.logger.debug(
                                "watch_providers | content=%s/%s region=%s excluded_ids=%s raw=%s",
                                content_type, content_id, self.region_provider,
                                excluded_ids, region_data,
                            )

                        # Build the list of availability types to check.
                        # Always include subscription (flatrate); optionally include
                        # pay-per-view types (rent/buy) when include_tvod is enabled.
                        availability_types = ["flatrate"]
                        if self.include_tvod:
                            availability_types.extend(["rent", "buy"])

                        for availability_type in availability_types:
                            for provider in region_data.get(availability_type, []):
                                if str(provider['provider_id']) in excluded_ids:
                                    self.logger.debug(
                                        "Content ID %s excluded via '%s': provider=%s (id=%s)",
                                        content_id, availability_type,
                                        provider['provider_name'], provider['provider_id'],
                                    )
                                    return True, provider['provider_name']

                        self.logger.debug(
                            "Content ID %s not matched in any availability type for region %s. "
                            "Checked types: %s. Counts — flatrate:%d rent:%d buy:%d",
                            content_id, self.region_provider,
                            availability_types,
                            len(region_data.get('flatrate', [])),
                            len(region_data.get('rent', [])),
                            len(region_data.get('buy', [])),
                        )
                    else:
                        self.logger.debug("No watch providers found for content ID %s in region %s.", content_id, self.region_provider)
                        return False, None
                else:
                    self.logger.error("Failed to retrieve watch providers for content ID %s: %d", content_id, response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while fetching watch providers: %s", str(e).replace(self.api_key, "***"))

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
            session = await self._get_session()
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
            self.logger.error("An error occurred while searching TMDb: %s", str(e).replace(self.api_key, "***"))
        return []

