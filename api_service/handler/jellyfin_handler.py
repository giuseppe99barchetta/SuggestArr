import asyncio

from api_service.handler.base_handler import BaseMediaHandler
from api_service.services.jellyfin.jellyfin_client import JellyfinClient

class JellyfinHandler(BaseMediaHandler):
    def __init__(self, jellyfin_client:JellyfinClient, seer_client, tmdb_client, logger, max_similar_movie, max_similar_tv, selected_users, library_anime_map=None, use_llm=None, request_delay=0, honor_seer_discovery=False, seer_discovered_ids=None, dry_run=False, max_total_requests=None):
        """
        Initialize JellyfinHandler with clients and parameters.
        :param jellyfin_client: Jellyfin API client
        :param seer_client: Seer API client
        :param tmdb_client: TMDb API client
        :param logger: Logger instance
        :param max_similar_movie: Max number of similar movies to request
        :param max_similar_tv: Max number of similar TV shows to request
        :param selected_users: List of selected users
        :param library_anime_map: Dict mapping library name to is_anime boolean
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
        self.jellyfin_client = jellyfin_client
        self.selected_users = selected_users
        self.processed_series = set()
        self._populate_existing_content_sets()
    
    def _populate_existing_content_sets(self):
        """Extract existing content from Jellyfin client."""
        if self.jellyfin_client.existing_content:
            for media_type, items in self.jellyfin_client.existing_content.items():
                self.existing_content_sets[media_type] = {
                    str(item.get('tmdb_id')) for item in items if item.get('tmdb_id')
                }


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

    async def _request_llm_recommendation(self, media, item_type, source_obj, user):
        """Request a single LLM recommendation via Jellyfin."""
        await self.request_similar_media([media], item_type, 1, source_obj, user)

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
            provider_ids = await self.jellyfin_client.get_series_provider_ids(series_id)
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
        """Request similar media (movie/TV show) via the Seer service."""
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
                if not media_id:
                    continue
                
                # Deduplicate dry-run items
                dry_run_key = (str(media_id), media_type)
                if dry_run_key in self._dry_run_processed_ids:
                    continue
                self._dry_run_processed_ids.add(dry_run_key)
                media_title = media.get('title') or media.get('name') or 'Unknown'

                already_requested = await self.seer_client.check_already_requested(media_id, media_type)
                already_downloaded = await self.seer_client.check_already_downloaded(media_id, media_type, self.existing_content_sets)
                excluded_by_discovery = (
                    self.honor_seer_discovery
                    and str(media_id) in self.seer_discovered_ids
                )
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

        # 2. Get watch providers once
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

            # Add to tasks if it passes all checks
            tasks.append(self._request_media_and_log(media_type, media, source_tmdb_obj, user, is_anime))

        if self.request_delay > 0:
            for task in tasks:
                await task
                await asyncio.sleep(self.request_delay)
        else:
            if tasks:
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
        if not await self._reserve_request_slot():
            self.logger.info(
                "Skipping %s: job max_results limit reached (%s)",
                media.get('title') or media.get('name') or 'Unknown',
                self.max_total_requests,
            )
            return
        if await self.seer_client.request_media(media_type=media_type, media=media, source=source_tmdb_obj, user=user, is_anime=is_anime, rationale=media.get('rationale')):
            self.request_count += 1
            self.logger.info(f"Requested {media_type}: {media.get('title') or media.get('name') or 'Unknown'}")
        else:
            await self._release_request_slot()
