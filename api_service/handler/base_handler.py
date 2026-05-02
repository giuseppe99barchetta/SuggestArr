"""
Base media handler with shared logic for Plex and Jellyfin handlers.
"""
import asyncio
import re
from abc import ABC, abstractmethod
from api_service.services.llm.llm_service import is_llm_configured, get_recommendations_from_history
from api_service.config.config import load_env_vars


class BaseMediaHandler(ABC):
    """
    Abstract base class for media handlers (Plex, Jellyfin).
    
    Provides shared functionality for:
    - LLM source resolution
    - LLM recommendation processing
    - Initialization of common attributes
    
    Subclasses must:
    1. Call super().__init__() with required parameters
    2. Call self._populate_existing_content_sets() after initializing their client
    3. Implement _populate_existing_content_sets() to extract client-specific content
    4. Implement _request_llm_recommendation() for handler-specific request logic
    """
    
    def __init__(self, seer_client, tmdb_client, logger,
                 max_similar_movie, max_similar_tv, library_anime_map=None,
                 use_llm=None, request_delay=0, honor_seer_discovery=False,
                 seer_discovered_ids=None, dry_run=False, max_total_requests=None):
        """
        Initialize base media handler.
        
        Args:
            seer_client: Seer service API client
            tmdb_client: TMDb API client
            logger: Logger instance
            max_similar_movie: Max number of similar movies to request
            max_similar_tv: Max number of similar TV shows to request
            library_anime_map: Dict mapping library identifiers to is_anime boolean
            use_llm: Override for LLM mode
            request_delay: Seconds to wait between consecutive requests
            honor_seer_discovery: Whether to honor Seer discovery
            seer_discovered_ids: Set of already discovered item IDs
            dry_run: Whether to simulate requests
            max_total_requests: Maximum requestable items for the whole run
        """
        self.seer_client = seer_client
        self.tmdb_client = tmdb_client
        self.logger = logger
        self.max_similar_movie = max_similar_movie
        self.max_similar_tv = max_similar_tv
        self.request_count = 0
        
        # Optimization: Pre-process existing_content into sets for O(1) lookups
        # Subclass must call _populate_existing_content_sets() after initialization
        self.existing_content_sets = {}
        
        self.library_anime_map = library_anime_map or {}
        self.request_delay = request_delay
        self.honor_seer_discovery = bool(honor_seer_discovery)
        self.seer_discovered_ids = {
            str(item_id) for item_id in (seer_discovered_ids or set())
        }
        self.dry_run = dry_run
        self.dry_run_items = []
        self._dry_run_processed_ids = set()
        self.max_total_requests = int(max_total_requests) if max_total_requests else None
        self._request_slots_reserved = 0
        self._request_limit_lock = asyncio.Lock()
        
        # Determine LLM mode
        if use_llm is not None:
            self.use_llm = use_llm
        else:
            config = load_env_vars()
            if config.get('ENABLE_ADVANCED_ALGORITHM', False):
                if is_llm_configured(config):
                    self.use_llm = True
                else:
                    self.logger.warning(
                        "ENABLE_ADVANCED_ALGORITHM is True but LLM is not configured. "
                        "AI-powered recommendations will be disabled."
                    )
                    self.use_llm = False
            else:
                self.use_llm = False

    def _has_request_capacity(self):
        """Return whether this run can still request more media."""
        return self.max_total_requests is None or self._request_slots_reserved < self.max_total_requests

    async def _reserve_request_slot(self):
        """Reserve one request slot if the job-level cap allows it."""
        if self.max_total_requests is None:
            return True

        async with self._request_limit_lock:
            if self._request_slots_reserved >= self.max_total_requests:
                return False
            self._request_slots_reserved += 1
            return True

    async def _release_request_slot(self):
        """Release a previously reserved request slot."""
        if self.max_total_requests is None:
            return

        async with self._request_limit_lock:
            self._request_slots_reserved = max(self._request_slots_reserved - 1, 0)
    
    @abstractmethod
    def _populate_existing_content_sets(self):
        """
        Populate existing_content_sets from client-specific existing content.
        
        Must be implemented by subclasses to extract existing content from 
        Plex or Jellyfin clients and convert to sets for fast lookups.
        
        Example implementation for PlexHandler:
            if self.plex_client.existing_content:
                for media_type, items in self.plex_client.existing_content.items():
                    self.existing_content_sets[media_type] = {
                        str(item.get('tmdb_id')) for item in items if item.get('tmdb_id')
                    }
        """
        pass
    
    async def _resolve_llm_source(self, source_title: str, item_type: str) -> dict:
        """
        Resolve an LLM-suggested source title to a TMDB metadata object.
        
        Strips episode notation (e.g. "Dan Da Dan - S02E12" → "Dan Da Dan") 
        before searching, so that series-level titles are looked up correctly on TMDB.
        
        Args:
            source_title: The title of the watched item that inspired the recommendation
            item_type: 'movie' or 'tv'
            
        Returns:
            TMDB metadata dict, or a fallback sentinel dict if not found
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
    
    async def process_llm_recommendations(self, user_or_history_items, history_items_or_item_type, item_type_or_max_results, max_results=None):
        """
        Pass history to LLM, resolve TMDb IDs in parallel, and request them.
        
        Args:
            user_or_history_items: User object (new call form) or history items (legacy call form)
            history_items_or_item_type: History items (new call form) or item_type (legacy call form)
            item_type_or_max_results: Item type (new call form) or max_results (legacy call form)
            max_results: Maximum recommendations to process (new call form only)
        """
        if max_results is None:
            # Backward-compatible call form:
            # process_llm_recommendations(history_items, item_type, max_results)
            user = None
            history_items = user_or_history_items
            item_type = history_items_or_item_type
            max_results = item_type_or_max_results
        else:
            # New call form:
            # process_llm_recommendations(user, history_items, item_type, max_results)
            user = user_or_history_items
            history_items = history_items_or_item_type
            item_type = item_type_or_max_results

        if max_results <= 0:
            return
        
        self.logger.info(f"Delegating {max_results} {item_type} recommendations to LLM service.")
        
        llm_recommendations = await get_recommendations_from_history(
            history_items,
            max_results,
            item_type,
            filters={
                "with_original_language": self.tmdb_client.language_filter,
                "release_year_gte": self.tmdb_client.release_year_filter,
                "release_year_lte": self.tmdb_client.release_year_filter_to,
                "vote_average_gte": self.tmdb_client.tmdb_threshold / 10 if self.tmdb_client.tmdb_threshold else None,
            },
        )
        
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
            filter_result = self.tmdb_client._apply_filters(best_match, item_type)
            best_match['filter_results'] = filter_result
            
            if not filter_result.get('passed', False):
                self.logger.info(
                    "Skipping LLM %s recommendation '%s': failed configured filters (%s)",
                    item_type,
                    best_match.get('title') or best_match.get('name') or 'Unknown',
                    ', '.join(k for k, v in filter_result.items() 
                             if k != 'passed' and isinstance(v, dict) and v.get('passed') is False)
                )
                continue
            
            best_match['rationale'] = rec.get('rationale')
            if user is None:
                request_tasks.append(self._request_llm_recommendation(best_match, item_type, source_obj))
            else:
                request_tasks.append(self._request_llm_recommendation(best_match, item_type, source_obj, user))
        
        if request_tasks:
            self.logger.info(f"LLM matched {len(request_tasks)} {item_type} items to TMDb.")
            await asyncio.gather(*request_tasks)
    
    @abstractmethod
    async def _request_llm_recommendation(self, media, item_type, source_obj, user=None):
        """
        Request a single LLM recommendation.
        
        Must be implemented by subclasses to handle Plex/Jellyfin-specific request logic.
        
        Args:
            media: Media item dict from TMDb search
            item_type: 'movie' or 'tv'
            source_obj: Source TMDB metadata object
            user: Optional user context for handlers that require user-specific requests
        """
        pass
