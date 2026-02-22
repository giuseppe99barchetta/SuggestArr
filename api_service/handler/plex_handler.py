import asyncio
import re
import unicodedata

from api_service.services.jellyseer.seer_client import SeerClient
from api_service.services.plex.plex_client import PlexClient
from api_service.services.tmdb.tmdb_client import TMDbClient
from api_service.config.config import load_env_vars
from api_service.services.llm.llm_service import get_recommendations_from_history

def to_ascii(value):
    """
    Apply Unicode NFKD normalization and handle None.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    return unicodedata.normalize('NFKD', value)

class PlexHandler:
    def __init__(self, plex_client: PlexClient, seer_client: SeerClient, tmdb_client: TMDbClient, logger, max_similar_movie, max_similar_tv, library_anime_map=None, use_llm=None, request_delay=0):
        """
        Initialize PlexHandler with clients and parameters.
        :param plex_client: Plex API client
        :param seer_client: Seer API client
        :param tmdb_client: TMDb API client
        :param logger: Logger instance
        :param max_similar_movie: Max number of similar movies to request
        :param max_similar_tv: Max number of similar TV shows to request
        :param library_anime_map: Dict mapping library section ID to is_anime boolean
        :param use_llm: Override for LLM mode. If None, falls back to global ENABLE_ADVANCED_ALGORITHM setting.
        :param request_delay: Seconds to wait between consecutive Jellyseerr requests (0 = concurrent).
        """
        self.plex_client = plex_client
        self.seer_client = seer_client
        self.tmdb_client = tmdb_client
        self.logger = logger
        self.max_similar_movie = max_similar_movie
        self.max_similar_tv = max_similar_tv
        self.request_count = 0
        self.existing_content = plex_client.existing_content
        self.library_anime_map = library_anime_map or {}
        self.request_delay = request_delay

        if use_llm is not None:
            self.use_llm = use_llm
        else:
            config = load_env_vars()
            self.use_llm = config.get('ENABLE_ADVANCED_ALGORITHM', False)


    async def process_recent_items(self):
        """Process recently watched items for Plex (without user context)."""
        self.logger.info("Fetching recently watched content from Plex")
        recent_items_response = await self.plex_client.get_recent_items()

        if isinstance(recent_items_response, list):
            tasks = []
            for response_item in recent_items_response:
                title = response_item.get('title', response_item.get('grandparentTitle'))
                if title is not None and isinstance(title, str):
                    title = to_ascii(title)
                # Look up anime status from the item's library section ID
                library_section_id = str(response_item.get('librarySectionID', ''))
                is_anime = self.library_anime_map.get(library_section_id, False)
                self.logger.info(f"Processing item: {title} (anime={is_anime})")
                tasks.append(self.process_item(response_item, title, is_anime))

            if tasks:
                if self.use_llm:
                    self.logger.info("Advanced Algorithm enabled. Generating recommendations using LLM.")
                    movie_history, tv_history = [], []
                    for response_item in recent_items_response:
                        item_type_raw = response_item.get('type', '').lower()
                        if item_type_raw == 'episode':
                            title = response_item.get('grandparentTitle')
                            media_type = 'tv'
                        else:
                            title = response_item.get('title')
                            media_type = 'movie'
                        year = response_item.get('year')
                        if title:
                            entry = {"title": title, "year": year}
                            if media_type == 'movie':
                                movie_history.append(entry)
                            else:
                                tv_history.append(entry)

                    llm_tasks = []
                    if movie_history and self.max_similar_movie > 0:
                        llm_tasks.append(self.process_llm_recommendations(movie_history, 'movie', self.max_similar_movie))
                    if tv_history and self.max_similar_tv > 0:
                        llm_tasks.append(self.process_llm_recommendations(tv_history, 'tv', self.max_similar_tv))
                    if llm_tasks:
                        await asyncio.gather(*llm_tasks)
                else:
                    await asyncio.gather(*tasks)
                
                self.logger.info(f"Total media requested: {self.request_count}")
            else:
                self.logger.warning("No recent items found in Plex response")
        else:
            self.logger.warning("Unexpected response format: expected a list")

    async def _resolve_llm_source(self, source_title: str, item_type: str) -> dict:
        """Resolve an LLM-suggested source title to a TMDB metadata object.

        Strips episode notation (e.g. "Dan Da Dan - S02E12" → "Dan Da Dan") before
        searching, so that series-level titles are looked up correctly on TMDB.

        :param source_title: The title of the watched item that inspired the recommendation.
        :param item_type: 'movie' or 'tv'.
        :return: TMDB metadata dict, or a fallback sentinel dict if not found.
        """
        if source_title:
            # Strip episode codes like "- S02E12" or "- s02e12" that may appear in titles
            clean_title = re.sub(r'\s*[-–]\s*S\d+E\d+.*', '', source_title, flags=re.IGNORECASE).strip()
            if item_type == 'movie':
                results = await self.tmdb_client.search_movie(clean_title)
            else:
                results = await self.tmdb_client.search_tv(clean_title)
            if results:
                self.logger.debug(f"Resolved LLM source '{clean_title}' to TMDB ID {results[0].get('id')}")
                return results[0]
            self.logger.warning(f"Could not resolve LLM source title '{clean_title}' on TMDB.")
        return {"id": 0, "name": "LLM Recommendation"}

    async def process_llm_recommendations(self, history_items, item_type, max_results):
        """Pass history to LLM, resolve TMDb IDs in parallel, and request them."""
        if max_results <= 0:
            return

        self.logger.info(f"Delegating {max_results} {item_type} recommendations to LLM service.")

        llm_recommendations = await get_recommendations_from_history(history_items, max_results, item_type)

        if not llm_recommendations:
            self.logger.warning("LLM returned no recommendations.")
            return

        search_fn = self.tmdb_client.search_movie if item_type == 'movie' else self.tmdb_client.search_tv

        async def resolve(rec):
            """Fetch TMDB data for the recommended item and its source in parallel."""
            rec_results, source_obj = await asyncio.gather(
                search_fn(rec.get("title"), rec.get("year")),
                self._resolve_llm_source(rec.get("source_title"), item_type),
            )
            return rec, rec_results, source_obj

        resolved = await asyncio.gather(*[resolve(rec) for rec in llm_recommendations])

        request_tasks = []
        for rec, rec_results, source_obj in resolved:
            if not rec_results:
                continue
            best_match = rec_results[0]
            best_match['rationale'] = rec.get('rationale')
            request_tasks.append(self.request_similar_media([best_match], item_type, 1, source_obj))

        if request_tasks:
            self.logger.info(f"LLM matched {len(request_tasks)} {item_type} items to TMDb.")
            await asyncio.gather(*request_tasks)

    async def process_item(self, item, title, is_anime=False):
        """Process an individual item (movie or TV show episode)."""
        self.logger.debug(f"Processing item: {item}")

        item_type = item['type'].lower()

        if (item_type == 'movie' and self.max_similar_movie > 0) or (item_type == 'episode' and self.max_similar_tv > 0):
            try:
                key = self.extract_rating_key(item, item_type)
                self.logger.debug(f"Extracted key: {key} for item type: {item_type}")
                if key:
                    if item_type == 'movie':
                        await self.process_movie(key, title, is_anime)
                    elif item_type == 'episode':
                        await self.process_episode(key, title, is_anime)
                else:
                    raise ValueError(f"Missing key for {item_type} '{title}'. Cannot process this item. Skipping.")
            except Exception as e:
                self.logger.warning(f"Error while processing item: {str(e)}")

    def extract_rating_key(self, item, item_type):
        """Extract the appropriate key depending on the item type."""
        key = item.get('key') if item_type == 'movie' else item.get('grandparentKey') if item_type == 'episode' else None
        self.logger.debug(f"Extracted rating key: {key} for item type: {item_type}")
        return key if key else None

    async def process_movie(self, movie_key, title, is_anime=False):
        """Find similar movies via TMDb and request them via Seer."""
        self.logger.debug(f"Processing movie with key: {movie_key} - {title}")
        source_tmbd_id = await self.plex_client.get_metadata_provider_id(movie_key)
        self.logger.debug(f"TMDb ID retrieved: {source_tmbd_id}")

        if source_tmbd_id:
            source_tmdb_obj = await self.tmdb_client.get_metadata(source_tmbd_id, 'movie')
            self.logger.info(f"TMDb metadata: {source_tmdb_obj}")
            if not source_tmdb_obj:
                self.logger.warning(f"Failed to fetch TMDb metadata for movie '{title}' (ID: {source_tmbd_id}). Skipping.")
                return
            similar_movies = await self.tmdb_client.find_similar_movies(source_tmbd_id)
            self.logger.debug(f"Found similar movies: {similar_movies}")
            await self.request_similar_media(similar_movies, 'movie', self.max_similar_movie, source_tmdb_obj, is_anime)
        else:
            self.logger.warning(f"Error while processing item: 'tmdb_id' not found for movie '{title}'. Skipping.")

    async def process_episode(self, show_key, title, is_anime=False):
        """Process a TV show episode by finding similar TV shows via TMDb."""
        self.logger.debug(f"Processing episode with show key: {show_key} - {title}")
        if show_key:
            source_tmbd_id = await self.plex_client.get_metadata_provider_id(show_key)
            self.logger.debug(f"TMDb ID retrieved: {source_tmbd_id}")

            if source_tmbd_id:
                source_tmdb_obj = await self.tmdb_client.get_metadata(source_tmbd_id, 'tv')
                self.logger.debug(f"TMDb metadata: {source_tmdb_obj}")
                if not source_tmdb_obj:
                    self.logger.warning(f"Failed to fetch TMDb metadata for TV show '{title}' (ID: {source_tmbd_id}). Skipping.")
                    return
                similar_tvshows = await self.tmdb_client.find_similar_tvshows(source_tmbd_id)
                self.logger.debug(f"Found {len(similar_tvshows)} similar TV shows")
                await self.request_similar_media(similar_tvshows, 'tv', self.max_similar_tv, source_tmdb_obj, is_anime)
            else:
                self.logger.warning(f"Error while processing item: 'tmdb_id' not found for tv show '{title}'. Skipping.")

    async def request_similar_media(self, media_ids, media_type, max_items, source_tmdb_obj, is_anime=False):
        """Request similar media (movie/TV show) via Overseer."""
        self.logger.debug(f"Requesting {max_items} similar media (anime={is_anime})")
        if not media_ids:
            self.logger.info("No media IDs provided for similar media request.")
            return

        if not isinstance(source_tmdb_obj, dict):
            self.logger.warning(f"Invalid source_tmdb_obj (type: {type(source_tmdb_obj).__name__}), skipping similar media request.")
            return

        tasks = []
        for media in media_ids[:max_items]:
            if not isinstance(media, dict):
                self.logger.warning(f"Skipping invalid media item (type: {type(media).__name__}): {media}")
                continue
            media_id = media.get('id')
            media_title = media.get('title') or media.get('name') or 'Unknown'
            if media_title is not None and isinstance(media_title, str):
                media_title = to_ascii(media_title)
            self.logger.debug(f"Processing similar media: '{media_title}' with ID: '{media_id}'")

            # Check if already downloaded, requested, or in an excluded streaming service
            already_requested = await self.seer_client.check_already_requested(media_id, media_type)
            self.logger.debug(f"Already requested: {already_requested}")
            if already_requested:
                self.logger.info(f"Skipping [{media_type}, {media_title}]: already requested.")
                continue

            already_downloaded = await self.seer_client.check_already_downloaded(media_id, media_type, self.existing_content)
            self.logger.debug(f"Already downloaded: {already_downloaded}")
            if already_downloaded:
                self.logger.info(f"Skipping [{media_type}, {media_title}]: already downloaded.")
                continue

            in_excluded_streaming_service, provider = await self.tmdb_client.get_watch_providers(source_tmdb_obj['id'], media_type)
            self.logger.debug(f"In excluded streaming service: {in_excluded_streaming_service}, Provider: {provider}")
            if in_excluded_streaming_service:
                self.logger.info(f"Skipping [{media_type}, {media_title}]: excluded by streaming service: {provider}")
                continue

            media_to_send = dict(media)
            if 'title' in media_to_send and media_to_send['title'] is not None and isinstance(media_to_send['title'], str):
                media_to_send['title'] = to_ascii(media_to_send['title'])

            # Add to tasks if it passes all checks
            tasks.append(self._request_media_and_log(media_type, media_to_send, source_tmdb_obj, is_anime))

        if self.request_delay > 0:
            for task in tasks:
                await task
                await asyncio.sleep(self.request_delay)
        else:
            await asyncio.gather(*tasks)

    async def _request_media_and_log(self, media_type, media, source_tmdb_obj, is_anime=False):
        """Helper method to request media and log the result."""
        self.logger.debug(f"Requesting media: {media} of type: {media_type} (anime={is_anime})")
        if await self.seer_client.request_media(media_type, media, source_tmdb_obj, is_anime=is_anime, rationale=media.get('rationale')):
            self.request_count += 1
            title_for_log = media.get('title') or media.get('name') or ''
            if title_for_log is not None and isinstance(title_for_log, str):
                title_for_log = to_ascii(title_for_log)
            self.logger.info(f"Requested {media_type}: {title_for_log}{' [Anime]' if is_anime else ''}")
