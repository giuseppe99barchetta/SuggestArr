import asyncio
import re

from api_service.services.jellyfin.jellyfin_client import JellyfinClient
from api_service.services.jellyseer.seer_client import SeerClient
from api_service.services.tmdb.tmdb_client import TMDbClient
from api_service.config.config import load_env_vars
from api_service.services.llm.llm_service import get_llm_client, get_recommendations_from_history

class JellyfinHandler:
    def __init__(self, jellyfin_client:JellyfinClient, jellyseer_client:SeerClient, tmdb_client:TMDbClient, logger, max_similar_movie, max_similar_tv, selected_users, library_anime_map=None, use_llm=None, request_delay=0, dry_run=False):
        """
        Initialize JellyfinHandler with clients and parameters.
        :param jellyfin_client: Jellyfin API client
        :param jellyseer_client: Jellyseer API client
        :param tmdb_client: TMDb API client
        :param logger: Logger instance
        :param max_similar_movie: Max number of similar movies to request
        :param max_similar_tv: Max number of similar TV shows to request
        :param selected_users: List of selected users
        :param library_anime_map: Dict mapping library name to is_anime boolean
        :param use_llm: Override for LLM mode. If None, falls back to global ENABLE_ADVANCED_ALGORITHM setting.
        :param request_delay: Seconds to wait between consecutive Jellyseerr requests (0 = concurrent).
        :param dry_run: If True, simulate requests without touching download clients.
        """
        self.jellyfin_client = jellyfin_client
        self.jellyseer_client = jellyseer_client
        self.tmdb_client = tmdb_client
        self.logger = logger
        self.max_similar_movie = max_similar_movie
        self.max_similar_tv = max_similar_tv
        self.processed_series = set()
        self.request_count = 0
        self.existing_content = jellyfin_client.existing_content
        self.selected_users = selected_users
        self.library_anime_map = library_anime_map or {}
        self.request_delay = request_delay
        self.dry_run = dry_run
        self.dry_run_items = []

        if use_llm is not None:
            self.use_llm = use_llm
        else:
            config = load_env_vars()
            if config.get('ENABLE_ADVANCED_ALGORITHM', False):
                if get_llm_client() is not None:
                    self.use_llm = True
                else:
                    self.logger.warning(
                        "ENABLE_ADVANCED_ALGORITHM is True but LLM is not configured. "
                        "AI-powered recommendations will be disabled."
                    )
                    self.use_llm = False
            else:
                self.use_llm = False


    async def process_recent_items(self):
        """Process recently watched items for all Jellyfin users."""
        self.logger.debug("Starting process_recent_items")
        users = self.selected_users if len(self.selected_users) > 0 else await self.jellyfin_client.get_all_users()
        self.logger.debug(f"Users to process: {users}")
        tasks = [self.process_user_recent_items(user) for user in users]
        await asyncio.gather(*tasks)
        self.logger.info(f"Total media requested: {self.request_count}")

    async def process_user_recent_items(self, user):
        """Process recently watched items for a specific Jellyfin user."""
        if not isinstance(user, dict):
            self.logger.error(f"Invalid user object (not a dict): {user}")
            return
        user_name = user.get('name', user.get('id', 'Unknown'))
        self.logger.info(f"Fetching content for user: {user_name}")
        recent_items_by_library = await self.jellyfin_client.get_recent_items(user)
        self.logger.debug(f"Recent items for user {user['name']}: {recent_items_by_library}")

        if recent_items_by_library:
            tasks = []
            if self.use_llm:
                self.logger.info("Advanced Algorithm enabled. Generating recommendations using LLM.")
                # We extract all recently watched items across libraries for the LLM
                all_recent_items = []
                for library_name, items in recent_items_by_library.items():
                    all_recent_items.extend(items)
                
                history_items = []
                for item in all_recent_items:
                    item_type_raw = item.get('Type', '').lower()
                    if item_type_raw == 'episode':
                        # Use the series name, not the individual episode title
                        title = item.get('SeriesName') or item.get('Name')
                        media_type = 'tv'
                    else:
                        title = item.get('Name')
                        media_type = 'movie'
                    year = item.get('ProductionYear')
                    if title:
                        history_items.append({
                            "title": title,
                            "year": year,
                            "type": media_type,
                        })
                
                if history_items:
                    # Filter history list for movies vs tv to feed to LLM
                    movie_history = [h for h in history_items if h['type'] == 'movie']
                    tv_history = [h for h in history_items if h['type'] == 'tv']
                    
                    if movie_history:
                        tasks.append(self.process_llm_recommendations(user, movie_history, 'movie', self.max_similar_movie))
                    if tv_history:
                        tasks.append(self.process_llm_recommendations(user, tv_history, 'tv', self.max_similar_tv))
            else:
                for library_name, items in recent_items_by_library.items():
                    is_anime = self.library_anime_map.get(library_name, False)
                    self.logger.debug(f"Processing library: {library_name} (anime={is_anime}) with items: {items}")
                    tasks.extend([self.process_item(user, item, is_anime) for item in items])
                    
            if tasks:
                await asyncio.gather(*tasks)

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

    async def process_llm_recommendations(self, user, history_items, item_type, max_results):
        """Pass history to LLM, resolve TMDb IDs in parallel, and request them."""
        if max_results <= 0:
            return

        self.logger.info(f"Delegating {max_results} {item_type} recommendations to LLM service for user {user['name']}.")

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
            request_tasks.append(self.request_similar_media([best_match], item_type, 1, source_obj, user))

        if request_tasks:
            self.logger.info(f"LLM matched {len(request_tasks)} {item_type} items to TMDb for user {user['name']}.")
            await asyncio.gather(*request_tasks)

    async def process_item(self, user, item, is_anime=False):
        """Process an individual item (movie or TV show episode)."""
        self.logger.debug(f"Processing item: {item}")
        item_type = item['Type'].lower()
        if item_type == 'movie' and self.max_similar_movie > 0:
            await self.process_movie(user, item, is_anime)
        elif item_type == 'episode' and self.max_similar_tv > 0:
            await self.process_episode(user, item, is_anime)

    async def process_movie(self, user, item, is_anime=False):
        provider_ids = item.get("ProviderIds", {})
        source_tmdb_id = provider_ids.get("Tmdb")

        if not source_tmdb_id:
            self.logger.debug("Movie skipped: no TMDb ID")
            return

        source_tmdb_obj = await self.tmdb_client.get_metadata(source_tmdb_id, 'movie')
        if not source_tmdb_obj:
            self.logger.warning(f"Movie skipped: failed to fetch TMDb metadata for ID {source_tmdb_id}")
            return
        similar_movies = await self.tmdb_client.find_similar_movies(source_tmdb_id, dry_run=self.dry_run)

        await self.request_similar_media(
            similar_movies,
            'movie',
            self.max_similar_movie,
            source_tmdb_obj,
            user,
            is_anime
        )

    async def process_episode(self, user, item, is_anime=False):
        series_id = item.get("SeriesId")

        if not series_id or series_id in self.processed_series:
            return

        self.processed_series.add(series_id)

        provider_ids = item.get("SeriesProviderIds") or item.get("ProviderIds", {})
        source_tmdb_id = provider_ids.get("Tmdb")

        if not source_tmdb_id:
            self.logger.debug("Series skipped: no TMDb ID")
            return

        source_tmdb_obj = await self.tmdb_client.get_metadata(source_tmdb_id, 'tv')
        if not source_tmdb_obj:
            self.logger.warning(f"Series skipped: failed to fetch TMDb metadata for ID {source_tmdb_id}")
            return
        similar_tvshows = await self.tmdb_client.find_similar_tvshows(source_tmdb_id, dry_run=self.dry_run)

        await self.request_similar_media(
            similar_tvshows,
            'tv',
            self.max_similar_tv,
            source_tmdb_obj,
            user,
            is_anime
        )

    async def request_similar_media(self, media_ids, media_type, max_items, source_tmdb_obj, user, is_anime=False):
        """Request similar media (movie/TV show) via Jellyseer."""
        self.logger.debug(f"Requesting {max_items} similar media (anime={is_anime})")
        if not media_ids:
            self.logger.debug("No similar media found after filtering for source %s.", source_tmdb_obj.get('id') if isinstance(source_tmdb_obj, dict) else '?')
            return

        if not isinstance(source_tmdb_obj, dict):
            self.logger.warning(f"Invalid source_tmdb_obj (type: {type(source_tmdb_obj).__name__}), skipping similar media request.")
            return

        if self.dry_run:
            # In dry-run mode, process all candidates (not just max_items) so the user
            # can see every potential recommendation alongside its filter results.
            for media in media_ids:
                if not isinstance(media, dict):
                    continue
                media_id = media.get('id')
                media_title = media.get('title') or media.get('name') or 'Unknown'

                already_requested = await self.jellyseer_client.check_already_requested(media_id, media_type)
                already_downloaded = await self.jellyseer_client.check_already_downloaded(media_id, media_type, self.existing_content)
                in_excluded_streaming_service, provider = await self.tmdb_client.get_watch_providers(source_tmdb_obj['id'], media_type)

                # Merge streaming result into the filter_results dict from TMDb
                filter_results = media.get('filter_results', {'passed': True})
                filter_results['streaming'] = {
                    'passed': not in_excluded_streaming_service,
                    'label': 'Streaming',
                    'reason': f'Excluded: {provider}' if in_excluded_streaming_service else None,
                }
                if in_excluded_streaming_service:
                    filter_results['passed'] = False

                # would_request = passes all configured filters AND not already in library
                would_request = (
                    filter_results['passed']
                    and not already_requested
                    and not already_downloaded
                )

                title = media.get('title') or media.get('name') or 'Unknown'
                self.logger.info(f"[DRY RUN] {'Would request' if would_request else 'Would skip'} {media_type}: {title}")
                self.dry_run_items.append({
                    'tmdb_id': media.get('id'),
                    'media_type': media_type,
                    'title': title,
                    'release_date': media.get('release_date') or media.get('first_air_date'),
                    'poster_path': media.get('poster_path'),
                    'vote_average': media.get('vote_average') or media.get('rating'),
                    'vote_count': media.get('vote_count') or media.get('votes'),
                    'overview': media.get('overview'),
                    'rationale': media.get('rationale'),
                    'filter_results': filter_results,
                    'already_requested': already_requested,
                    'already_downloaded': already_downloaded,
                    'would_request': would_request,
                })
                if would_request:
                    self.request_count += 1
            return

        tasks = []
        for media in media_ids[:max_items]:
            if not isinstance(media, dict):
                self.logger.warning(f"Skipping invalid media item (type: {type(media).__name__}): {media}")
                continue
            media_id = media.get('id')
            media_title = media.get('title') or media.get('name') or 'Unknown'

            self.logger.debug(f"Processing similar media: '{media_title}' with ID: '{media_id}'")

            # Check if already downloaded, requested, or in an excluded streaming service
            already_requested = await self.jellyseer_client.check_already_requested(media_id, media_type)
            self.logger.debug(f"Already requested check for {media_title}: {already_requested}")
            if already_requested:
                self.logger.debug(f"Skipping [{media_type}, {media_title}]: already requested.")
                continue

            already_downloaded = await self.jellyseer_client.check_already_downloaded(media_id, media_type, self.existing_content)
            self.logger.debug(f"Already downloaded check for {media_title}: {already_downloaded}")
            if already_downloaded:
                self.logger.debug(f"Skipping [{media_type}, {media_title}]: already downloaded.")
                continue

            in_excluded_streaming_service, provider = await self.tmdb_client.get_watch_providers(source_tmdb_obj['id'], media_type)
            self.logger.debug(f"Excluded streaming service check for {media_title}: {in_excluded_streaming_service}, {provider}")
            if in_excluded_streaming_service:
                self.logger.debug(f"Skipping [{media_type}, {media_title}]: excluded by streaming service: {provider}")
                continue

            # Add to tasks if it passes all checks
            tasks.append(self._request_media_and_log(media_type, media, source_tmdb_obj, user, is_anime))

        if self.request_delay > 0:
            for task in tasks:
                await task
                await asyncio.sleep(self.request_delay)
        else:
            await asyncio.gather(*tasks)

    async def _request_media_and_log(self, media_type, media, source_tmdb_obj, user, is_anime=False):
        """Helper method to request media and log the result."""
        self.logger.debug(f"Requesting media: {media} (anime={is_anime})")
        if self.dry_run:
            title = media.get('title') or media.get('name') or 'Unknown'
            self.logger.info(f"[DRY RUN] Would request {media_type}: {title}")
            self.dry_run_items.append({
                'tmdb_id': media.get('id'),
                'media_type': media_type,
                'title': title,
                'release_date': media.get('release_date') or media.get('first_air_date'),
                'poster_path': media.get('poster_path'),
                'vote_average': media.get('vote_average'),
                'vote_count': media.get('vote_count'),
                'overview': media.get('overview'),
                'rationale': media.get('rationale'),
            })
            self.request_count += 1
            return
        if await self.jellyseer_client.request_media(media_type=media_type, media=media, source=source_tmdb_obj, user=user, is_anime=is_anime, rationale=media.get('rationale')):
            self.request_count += 1
            self.logger.info(f"Requested {media_type}: {media.get('title') or media.get('name') or 'Unknown'}")
