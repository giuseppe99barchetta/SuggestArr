import asyncio
import unicodedata

from api_service.handler.base_handler import BaseMediaHandler
from api_service.services.plex.plex_client import PlexClient

def to_ascii(value):
    """
    Apply Unicode NFKD normalization and handle None.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    return unicodedata.normalize('NFKD', value)

class PlexHandler(BaseMediaHandler):
    def __init__(self, plex_client: PlexClient, seer_client, tmdb_client, logger, max_similar_movie, max_similar_tv, library_anime_map=None, use_llm=None, request_delay=0, honor_seer_discovery=False, seer_discovered_ids=None, dry_run=False, max_total_requests=None):
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
        :param request_delay: Seconds to wait between consecutive Seer service requests (0 = concurrent).
        :param dry_run: If True, simulate requests without touching download clients.
        :param max_total_requests: Max number of items to request for the whole run.
        """
        super().__init__(
            seer_client=seer_client,
            tmdb_client=tmdb_client,
            logger=logger,
            max_similar_movie=max_similar_movie,
            max_similar_tv=max_similar_tv,
            library_anime_map=library_anime_map,
            use_llm=use_llm,
            request_delay=request_delay,
            honor_seer_discovery=honor_seer_discovery,
            seer_discovered_ids=seer_discovered_ids,
            dry_run=dry_run,
            max_total_requests=max_total_requests
        )
        self.plex_client = plex_client
        self._populate_existing_content_sets()
    
    def _populate_existing_content_sets(self):
        """Extract existing content from Plex client."""
        if self.plex_client.existing_content:
            for media_type, items in self.plex_client.existing_content.items():
                self.existing_content_sets[media_type] = {
                    str(item.get('tmdb_id')) for item in items if item.get('tmdb_id')
                }


    async def process_recent_items(self):
        """Process recently watched items for Plex (without user context)."""
        self.logger.info("Fetching recently watched content from Plex")
        recent_items_response = await self.plex_client.get_recent_items()

        if isinstance(recent_items_response, list):
            for response_item in recent_items_response:
                title = response_item.get('title', response_item.get('grandparentTitle'))
                if title is not None and isinstance(title, str):
                    title = to_ascii(title)
                # Look up anime status from the item's library section ID
                library_section_id = str(response_item.get('librarySectionID', ''))
                is_anime = self.library_anime_map.get(library_section_id, False)
                self.logger.info(f"Processing item: {title} (anime={is_anime})")

            if recent_items_response:
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
                    tasks = []
                    for response_item in recent_items_response:
                        title = response_item.get('title', response_item.get('grandparentTitle'))
                        if title is not None and isinstance(title, str):
                            title = to_ascii(title)
                        library_section_id = str(response_item.get('librarySectionID', ''))
                        is_anime = self.library_anime_map.get(library_section_id, False)
                        tasks.append(self.process_item(response_item, title, is_anime))
                    if tasks:
                        await asyncio.gather(*tasks)
                
                self.logger.info(f"Total media requested: {self.request_count}")
            else:
                self.logger.warning("No recent items found in Plex response")
        else:
            self.logger.warning("Unexpected response format: expected a list")

    async def _request_llm_recommendation(self, media, item_type, source_obj):
        """Request a single LLM recommendation via Plex."""
        await self.request_similar_media([media], item_type, 1, source_obj)

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
            similar_movies = await self.tmdb_client.find_similar_movies(source_tmbd_id, dry_run=self.dry_run)
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
                similar_tvshows = await self.tmdb_client.find_similar_tvshows(source_tmbd_id, dry_run=self.dry_run)
                self.logger.debug(f"Found {len(similar_tvshows)} similar TV shows")
                await self.request_similar_media(similar_tvshows, 'tv', self.max_similar_tv, source_tmdb_obj, is_anime)
            else:
                self.logger.warning(f"Error while processing item: 'tmdb_id' not found for tv show '{title}'. Skipping.")

    async def request_similar_media(self, media_ids, media_type, max_items, source_tmdb_obj, is_anime=False):
        """Request similar media (movie/TV show) via the Seer service."""
        self.logger.debug(f"Requesting {max_items} similar media (anime={is_anime})")
        if not media_ids:
            self.logger.debug("No similar media found after filtering for source %s.", source_tmdb_obj.get('id') if isinstance(source_tmdb_obj, dict) else '?')
            return

        if not isinstance(source_tmdb_obj, dict):
            self.logger.warning(f"Invalid source_tmdb_obj (type: {type(source_tmdb_obj).__name__}), skipping similar media request.")
            return

        if self.dry_run:
            # In dry-run mode, process all candidates so the user can see every potential
            # recommendation alongside its filter results.
            for media in media_ids:
                if not isinstance(media, dict):
                    continue
                media_id = media.get('id')
                if not media_id:
                    continue
                
                # Deduplicate dry-run items
                dry_run_key = (str(media_id), media_type)
                if dry_run_key in self._dry_run_processed_ids:
                    continue
                self._dry_run_processed_ids.add(dry_run_key)

                already_requested = await self.seer_client.check_already_requested(media_id, media_type)
                already_downloaded = await self.seer_client.check_already_downloaded(media_id, media_type, self.existing_content_sets)
                excluded_by_discovery = (
                    self.honor_seer_discovery
                    and str(media_id) in self.seer_discovered_ids
                )
                in_excluded_streaming_service, provider = await self.tmdb_client.get_watch_providers(source_tmdb_obj['id'], media_type)

                filter_results = media.get('filter_results', {'passed': True})
                filter_results['streaming'] = {
                    'passed': not in_excluded_streaming_service,
                    'label': 'Streaming',
                    'reason': f'Excluded: {provider}' if in_excluded_streaming_service else None,
                }
                if in_excluded_streaming_service:
                    filter_results['passed'] = False

                base_would_request = (
                    filter_results['passed']
                    and not already_requested
                    and not already_downloaded
                    and not excluded_by_discovery
                )
                would_request = base_would_request and await self._reserve_request_slot()
                if base_would_request and not would_request:
                    filter_results['request_limit'] = {
                        'passed': False,
                        'label': 'Request limit',
                        'reason': f'Max Results reached ({self.max_total_requests})',
                    }

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
                    'excluded_by_seer_discovery': excluded_by_discovery,
                    'would_request': would_request,
                    'source': {
                        'tmdb_id': source_tmdb_obj.get('id'),
                        'title': source_tmdb_obj.get('title') or source_tmdb_obj.get('name', ''),
                        'poster_path': source_tmdb_obj.get('poster_path'),
                        'media_type': media_type,
                    },
                })
                if would_request:
                    self.request_count += 1
            return

        # Non-dry-run optimization: Batch check and avoid redundant API calls
        remaining_capacity = None
        if self.max_total_requests is not None:
            remaining_capacity = max(self.max_total_requests - self.request_count, 0)
            if remaining_capacity <= 0:
                return
        item_limit = min(max_items, remaining_capacity) if remaining_capacity is not None else max_items
        media_to_process = media_ids[:item_limit]
        if not media_to_process:
            return

        # 1. Batch check already requested in DB
        tmdb_ids_to_check = [str(m.get('id')) for m in media_to_process if m.get('id')]
        already_requested_set = await self.seer_client.check_requests_exist_batch(media_type, tmdb_ids_to_check)

        # 2. Get watch providers once (if source is not ai_search/fallback)
        in_excluded_streaming_service = False
        provider = None
        if source_tmdb_obj.get('id') != 0:
            in_excluded_streaming_service, provider = await self.tmdb_client.get_watch_providers(source_tmdb_obj['id'], media_type)
        
        if in_excluded_streaming_service:
            self.logger.info(f"Skipping all similar {media_type} for source {source_tmdb_obj.get('id')}: source is on excluded service {provider}")
            return

        tasks = []
        local_content_set = self.existing_content_sets.get(media_type, set())

        for media in media_to_process:
            if not isinstance(media, dict):
                continue
            
            media_id = str(media.get('id'))
            media_title = media.get('title') or media.get('name') or 'Unknown'
            if media_title is not None and isinstance(media_title, str):
                media_title = to_ascii(media_title)

            # Check batch results
            if media_id in already_requested_set:
                self.logger.debug(f"Skipping [{media_type}, {media_title}]: already requested (batch check).")
                continue

            # Check optimized local content set
            if media_id in local_content_set:
                self.logger.debug(f"Skipping [{media_type}, {media_title}]: already downloaded (local set check).")
                continue

            if self.honor_seer_discovery and media_id in self.seer_discovered_ids:
                self.logger.debug(
                    "Skipping [%s, %s]: already discovered/requested in Seer.",
                    media_type,
                    media_title,
                )
                continue

            media_to_send = dict(media)
            if 'title' in media_to_send and isinstance(media_to_send['title'], str):
                media_to_send['title'] = to_ascii(media_to_send['title'])

            tasks.append(self._request_media_and_log(media_type, media_to_send, source_tmdb_obj, is_anime))

        if self.request_delay > 0:
            for task in tasks:
                await task
                await asyncio.sleep(self.request_delay)
        else:
            if tasks:
                await asyncio.gather(*tasks)

    async def _request_media_and_log(self, media_type, media, source_tmdb_obj, is_anime=False):
        """Helper method to request media and log the result."""
        self.logger.debug(f"Requesting media: {media} of type: {media_type} (anime={is_anime})")
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
        if not await self._reserve_request_slot():
            self.logger.info(
                "Skipping %s: job max_results limit reached (%s)",
                media.get('title') or media.get('name') or 'Unknown',
                self.max_total_requests,
            )
            return
        if await self.seer_client.request_media(media_type, media, source_tmdb_obj, is_anime=is_anime, rationale=media.get('rationale')):
            self.request_count += 1
            title_for_log = media.get('title') or media.get('name') or ''
            if title_for_log is not None and isinstance(title_for_log, str):
                title_for_log = to_ascii(title_for_log)
            self.logger.info(f"Requested {media_type}: {title_for_log}{' [Anime]' if is_anime else ''}")
        else:
            await self._release_request_slot()
