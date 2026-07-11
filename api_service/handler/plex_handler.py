import asyncio
import unicodedata

from api_service.handler.base_handler import BaseMediaHandler
from api_service.services.plex.plex_client import PlexClient, normalize_guid_provider_id
from api_service.db.database_manager import DatabaseManager

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
    def __init__(self, plex_client: PlexClient, seer_client, tmdb_client, logger, max_similar_movie, max_similar_tv, library_anime_map=None, use_llm=None, request_delay=0, honor_seer_discovery=False, seer_discovered_ids=None, dry_run=False, max_total_requests=None, trakt_augmentor=None, selected_users=None, max_content=10):
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
        :param max_content: Max seeds to process after merging Trakt + Plex sources.
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
            max_total_requests=max_total_requests,
            trakt_augmentor=trakt_augmentor,
            max_content=max_content,
        )
        self.plex_client = plex_client
        self.selected_users = selected_users or []
        self._populate_existing_content_sets()
    
    def _populate_existing_content_sets(self):
        """Extract existing content from Plex client."""
        if self.plex_client.existing_content:
            for media_type, items in self.plex_client.existing_content.items():
                normalized_ids = set()
                for item in items:
                    tmdb_id = item.get('tmdb_id')
                    if not tmdb_id:
                        continue
                    normalized_ids.add(
                        normalize_guid_provider_id(f'tmdb://{tmdb_id}', 'tmdb') or str(tmdb_id)
                    )
                self.existing_content_sets[media_type] = normalized_ids


    async def process_recent_items(self):
        """Process recently watched items for Plex, merged with Trakt seeds."""
        # 1. Collect Trakt seeds (doesn't process them yet).
        trakt_seeds = await self._collect_trakt_seeds()

        # 2. Fetch Plex recent items and resolve their TMDB IDs.
        self.logger.info("Fetching recently watched content from Plex")
        recent_items_response = await self.plex_client.get_recent_items()

        if not isinstance(recent_items_response, list) or not recent_items_response:
            if trakt_seeds:
                trakt_seeds = self._merge_seeds(trakt_seeds)
                await self._process_merged_seeds(trakt_seeds)
            else:
                self.logger.warning("No recent items found in Plex response")
            return

        # Resolve all Plex items to seed dicts in parallel.
        plex_seeds = await asyncio.gather(*[
            self._plex_item_to_seed(item) for item in recent_items_response
        ])
        plex_seeds = [s for s in plex_seeds if s is not None]

        # 3. Merge Trakt + Plex seeds, sort by date, dedup, cap.
        all_seeds = trakt_seeds + plex_seeds
        merged = self._merge_seeds(all_seeds)
        if not merged:
            return

        self.logger.info("Processing %d merged seeds (Trakt + Plex)", len(merged))
        await self._process_merged_seeds(merged)

    async def _plex_item_to_seed(self, item):
        """Resolve a Plex response item to a normalized seed dict or None."""
        item_type = item.get('type', '').lower()
        title = item.get('grandparentTitle') if item_type == 'episode' else item.get('title')
        if not title:
            return None

        key = item.get('key') if item_type == 'movie' else item.get('grandparentKey')
        if not key:
            return None

        try:
            tmdb_id = await self.plex_client.get_metadata_provider_id(key)
        except Exception:
            self.logger.warning("Failed to resolve TMDB ID for Plex item '%s'", title)
            return None
        if not tmdb_id:
            return None

        media_type = 'movie' if item_type == 'movie' else 'tv'
        library_section_id = str(item.get('librarySectionID', ''))
        is_anime = self.library_anime_map.get(library_section_id, False)

        # Parse date: prefer viewedAt, fall back to addedAt, then 0.
        date = 0
        for field in ('viewedAt', 'addedAt', 'updatedAt', 'originallyAvailableAt'):
            val = item.get(field)
            if val:
                try:
                    from datetime import datetime as dt
                    date = int(dt.fromisoformat(str(val).replace('Z', '+00:00')).timestamp())
                except (ValueError, TypeError):
                    pass
                break

        source_obj = None
        try:
            source_obj = await self.tmdb_client.get_metadata(tmdb_id, media_type)
        except (AttributeError, Exception):
            pass
        return {
            'tmdb_id': str(tmdb_id), 'media_type': media_type,
            'title': title, 'year': item.get('year'),
            'date': date, 'source_obj': source_obj, 'is_anime': is_anime,
            'user_id': item.get('_user_id'),
        }

    async def _collect_trakt_seeds(self):
        """Fetch Trakt seeds for all linked users, return list without processing."""
        if not self.trakt_augmentor or not self.selected_users:
            return []

        db = DatabaseManager()
        all_seeds = []
        for media_user in self.selected_users:
            external_id = str(media_user.get('id')) if isinstance(media_user, dict) else str(media_user)
            external_username = media_user.get('name') if isinstance(media_user, dict) else None
            identity = db.upsert_media_user_identity(
                provider="plex", external_user_id=external_id, external_username=external_username,
            )
            seeds = await self._augment_user_trakt(identity["id"])
            if seeds:
                for seed in seeds:
                    seed['user_id'] = external_id
                all_seeds.extend(seeds)

        for s in all_seeds:
            s.setdefault('date', s.get('watched_at', 0))

        return all_seeds

    async def _process_merged_seeds(self, seeds):
        """Process merged seeds: dispatch to LLM or non-LLM path."""
        if not seeds:
            return

        if self.use_llm:
            movie_history = [
                {"title": s["title"], "year": s.get("year"), "type": "movie", "source_origin": s.get("source_origin")}
                for s in seeds if s.get("media_type") == "movie"
            ]
            tv_history = [
                {"title": s["title"], "year": s.get("year"), "type": "tv", "source_origin": s.get("source_origin")}
                for s in seeds if s.get("media_type") == "tv"
            ]
            tasks = []
            if movie_history and self.max_similar_movie > 0:
                tasks.append(self.process_llm_recommendations(movie_history, 'movie', self.max_similar_movie))
            if tv_history and self.max_similar_tv > 0:
                tasks.append(self.process_llm_recommendations(tv_history, 'tv', self.max_similar_tv))
            if tasks:
                await asyncio.gather(*tasks)
        else:
            await asyncio.gather(*[
                self._process_seed(seed) for seed in seeds
            ])

    async def _process_seed(self, seed):
        """Find similar media for one TMDB-resolved seed and request via Seer."""
        tmdb_id = seed.get("tmdb_id")
        media_type = seed.get("media_type")
        if not tmdb_id:
            return
        source_obj = seed.get("source_obj")
        source_origin = seed.get("source_origin")
        is_anime = seed.get("is_anime", False)
        user_id = seed.get("user_id")
        if media_type == "movie" and self.max_similar_movie > 0:
            if not source_obj:
                source_obj = await self.tmdb_client.get_metadata(tmdb_id, "movie")
            if not source_obj:
                return
            self._mark_source_origin(source_obj, source_origin)
            similar = await self.tmdb_client.find_similar_movies(tmdb_id, dry_run=self.dry_run)
            await self.request_similar_media(similar, "movie", self.max_similar_movie, source_obj, is_anime, user_id)
        elif media_type == "tv" and self.max_similar_tv > 0:
            if not source_obj:
                source_obj = await self.tmdb_client.get_metadata(tmdb_id, "tv")
            if not source_obj:
                return
            self._mark_source_origin(source_obj, source_origin)
            similar = await self.tmdb_client.find_similar_tvshows(tmdb_id, dry_run=self.dry_run)
            await self.request_similar_media(similar, "tv", self.max_similar_tv, source_obj, is_anime, user_id)

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

    async def request_similar_media(self, media_ids, media_type, max_items, source_tmdb_obj, is_anime=False, user_id=None):
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
                self.logger.info(f"Skipping [{media_type}, {media_title}]: already requested (batch check).")
                continue

            # Check optimized local content set
            if media_id in local_content_set:
                self.logger.info(f"Skipping [{media_type}, {media_title}]: already downloaded (local set check).")
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

            tasks.append(self._request_media_and_log(media_type, media_to_send, source_tmdb_obj, is_anime, user_id))

        if self.request_delay > 0:
            for task in tasks:
                await task
                await asyncio.sleep(self.request_delay)
        else:
            if tasks:
                await asyncio.gather(*tasks)

    async def _request_media_and_log(self, media_type, media, source_tmdb_obj, is_anime=False, user_id=None):
        """Helper method to request media and log the result."""
        if not user_id and len(self.selected_users or []) == 1:
            selected = self.selected_users[0]
            user_id = selected.get('id') if isinstance(selected, dict) else selected
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
        user = {'id': user_id} if user_id else None
        if await self.seer_client.request_media(media_type, media, source_tmdb_obj, user=user, is_anime=is_anime, rationale=media.get('rationale')):
            self.request_count += 1
            title_for_log = media.get('title') or media.get('name') or ''
            if title_for_log is not None and isinstance(title_for_log, str):
                title_for_log = to_ascii(title_for_log)
            self.logger.info(f"Requested {media_type}: {title_for_log}{' [Anime]' if is_anime else ''}")
        else:
            await self._release_request_slot()
