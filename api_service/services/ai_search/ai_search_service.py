"""
AI Search Service — orchestrates LLM query interpretation, TMDB search/discover,
rating filtering, and history-based deduplication to power the AI Search tab.
"""

import asyncio
from typing import Any, Dict, List, Optional

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.services.llm.llm_service import interpret_search_query
from api_service.services.tmdb.tmdb_client import TMDbClient
from api_service.services.tmdb.tmdb_discover import TMDbDiscover

logger = LoggerManager.get_logger("AiSearchService")

# Maximum number of results from TMDB discover when used as fallback/supplement
_DISCOVER_MAX = 10
# Maximum total results returned to the caller
_RESULTS_MAX = 12


class AiSearchService:
    """Provides semantic AI-powered movie and TV show search.

    Flow:
    1. Fetch viewing history from the configured media server (Jellyfin / Plex).
    2. Send query + history to the LLM to obtain structured discover params and
       a ranked list of specific title suggestions.
    3. In parallel: run TMDB Discover with the extracted params AND resolve each
       suggested title via TMDB search.
    4. Merge, deduplicate, apply rating filters, and exclude already-watched titles.
    5. Return results sorted with AI suggestions first, followed by discover results.
    """

    def __init__(self):
        """Initialise AiSearchService from the current application configuration."""
        self.config = load_env_vars()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        media_type: str = "movie",
        user_ids: Optional[List] = None,
        max_results: int = _RESULTS_MAX,
        use_history: bool = True,
        exclude_watched: bool = True,
    ) -> Dict[str, Any]:
        """Execute an AI-powered search.

        :param query: Natural language description of desired content.
        :param media_type: 'movie', 'tv', or 'both'.
        :param user_ids: Optional list of media-server user IDs to scope history.
        :param max_results: Maximum number of results to return.
        :param use_history: Whether to fetch and pass viewing history to the LLM.
        :param exclude_watched: Whether to exclude already-watched titles from results.
        :return: Dict with 'results', 'query_interpretation', and 'total'.
        """
        if media_type == "both":
            movie_task = self._search_single(query, "movie", user_ids, max_results, use_history, exclude_watched)
            tv_task = self._search_single(query, "tv", user_ids, max_results, use_history, exclude_watched)
            movie_res, tv_res = await asyncio.gather(movie_task, tv_task)

            # Interleave: AI movie, AI tv, discover movie, discover tv …
            ai_movies = [r for r in movie_res["results"] if r.get("source") == "ai_suggestion"]
            ai_tv = [r for r in tv_res["results"] if r.get("source") == "ai_suggestion"]
            disc_movies = [r for r in movie_res["results"] if r.get("source") == "discover"]
            disc_tv = [r for r in tv_res["results"] if r.get("source") == "discover"]

            merged: List[Dict] = []
            for pair in zip(ai_movies, ai_tv):
                merged.extend(pair)
            for pair in zip(disc_movies, disc_tv):
                merged.extend(pair)

            # Append leftovers
            for lst in (ai_movies, ai_tv, disc_movies, disc_tv):
                for item in lst:
                    if item not in merged:
                        merged.append(item)

            return {
                "results": merged[:max_results],
                "query_interpretation": {
                    "movie": movie_res.get("query_interpretation", {}),
                    "tv": tv_res.get("query_interpretation", {}),
                },
                "total": len(merged[:max_results]),
            }

        return await self._search_single(query, media_type, user_ids, max_results, use_history, exclude_watched)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _search_single(
        self,
        query: str,
        media_type: str,
        user_ids: Optional[List],
        max_results: int,
        use_history: bool = True,
        exclude_watched: bool = True,
    ) -> Dict[str, Any]:
        """Run the full search pipeline for a single media type."""
        # 1. Fetch history (best-effort — never crash the search if unavailable)
        history: List[Dict] = []
        if use_history:
            try:
                history = await self._get_history(user_ids)
            except Exception as exc:
                logger.warning("Could not fetch viewing history: %s", exc)

        watched_titles = {
            (item.get("title") or item.get("name") or "").strip().lower()
            for item in history
        }

        # 2. LLM interpretation
        interpretation = interpret_search_query(query, history, media_type)
        discover_params = interpretation.get("discover_params", {})
        suggested_titles = interpretation.get("suggested_titles", [])

        # 3. Build TMDb clients from config
        tmdb_client = self._make_tmdb_client()
        tmdb_api_key = self.config.get("TMDB_API_KEY", "")
        discover_client = TMDbDiscover(api_key=tmdb_api_key)

        # 4. Convert genre names → IDs for discover
        tmdb_filters = await self._build_discover_filters(
            discover_params, media_type, discover_client
        )

        # 5. Run discover + title searches in parallel
        discover_task = self._run_discover(
            media_type, tmdb_filters, discover_client, _DISCOVER_MAX
        )
        title_tasks = [
            self._resolve_suggested_title(t, media_type, tmdb_client)
            for t in suggested_titles
        ]
        results_bundle = await asyncio.gather(discover_task, *title_tasks)

        discover_results: List[Dict] = results_bundle[0]
        title_results: List[Optional[Dict]] = list(results_bundle[1:])

        # 6. Build AI-suggestion items (with rationale), then filter & dedup
        seen_ids: set = set()
        final: List[Dict] = []

        for tmdb_item, suggestion in zip(title_results, suggested_titles):
            if tmdb_item is None:
                continue
            item_id = tmdb_item.get("id")
            if not item_id or item_id in seen_ids:
                continue
            if exclude_watched and self._is_watched(tmdb_item, watched_titles):
                continue
            if not tmdb_client._apply_filters(tmdb_item, media_type):
                continue
            seen_ids.add(item_id)
            tmdb_item["rationale"] = suggestion.get("rationale", "")
            tmdb_item["source"] = "ai_suggestion"
            tmdb_item["media_type"] = media_type
            final.append(tmdb_item)

        for item in discover_results:
            item_id = item.get("id")
            if not item_id or item_id in seen_ids:
                continue
            if exclude_watched and self._is_watched(item, watched_titles):
                continue
            seen_ids.add(item_id)
            item["rationale"] = ""
            item["source"] = "discover"
            item["media_type"] = media_type
            final.append(item)

        return {
            "results": final[:max_results],
            "query_interpretation": discover_params,
            "total": len(final[:max_results]),
        }

    async def _run_discover(
        self,
        media_type: str,
        filters: Dict,
        client: TMDbDiscover,
        max_results: int,
    ) -> List[Dict]:
        """Run TMDbDiscover for the given media type and filter dict."""
        try:
            if media_type == "movie":
                return await client.discover_movies(filters, max_results)
            return await client.discover_tv(filters, max_results)
        except Exception as exc:
            logger.warning("TMDB discover failed: %s", exc)
            return []

    async def _resolve_suggested_title(
        self, suggestion: Dict, media_type: str, tmdb_client: TMDbClient
    ) -> Optional[Dict]:
        """Look up a specific suggested title on TMDB and return the first match."""
        title = suggestion.get("title", "")
        year = suggestion.get("year")
        if not title:
            return None
        try:
            if media_type == "movie":
                results = await tmdb_client.search_movie(title, year)
            else:
                results = await tmdb_client.search_tv(title, year)
            return results[0] if results else None
        except Exception as exc:
            logger.warning("TMDB search failed for '%s': %s", title, exc)
            return None

    async def _build_discover_filters(
        self,
        discover_params: Dict,
        media_type: str,
        discover_client: TMDbDiscover,
    ) -> Dict:
        """Convert LLM discover_params (genre names, year range, etc.) to TMDB filter dict."""
        filters: Dict[str, Any] = {}

        genre_names: List[str] = discover_params.get("genres") or []
        if genre_names:
            try:
                all_genres = await discover_client.get_genres(media_type)
                name_to_id = {g["name"].lower(): g["id"] for g in all_genres}
                genre_ids = [
                    name_to_id[name.lower()]
                    for name in genre_names
                    if name.lower() in name_to_id
                ]
                if genre_ids:
                    filters["with_genres"] = ",".join(str(g) for g in genre_ids)
            except Exception as exc:
                logger.warning("Could not resolve genre names to IDs: %s", exc)

        year_from = discover_params.get("year_from")
        year_to = discover_params.get("year_to")
        if year_from:
            if media_type == "movie":
                filters["primary_release_date.gte"] = f"{year_from}-01-01"
            else:
                filters["first_air_date.gte"] = f"{year_from}-01-01"
        if year_to:
            if media_type == "movie":
                filters["primary_release_date.lte"] = f"{year_to}-12-31"
            else:
                filters["first_air_date.lte"] = f"{year_to}-12-31"

        lang = discover_params.get("original_language")
        if lang:
            filters["with_original_language"] = lang

        sort_by = discover_params.get("sort_by", "popularity.desc")
        filters["sort_by"] = sort_by

        return filters

    async def _get_history(self, user_ids: Optional[List]) -> List[Dict]:
        """Fetch and normalise the user's viewing history from Jellyfin or Plex.

        :param user_ids: Optional list of user dicts or IDs to scope the fetch.
        :return: Flat list of dicts with 'title', 'year', and 'type'.
        """
        selected_service = self.config.get("SELECTED_SERVICE", "").lower()
        history: List[Dict] = []

        if selected_service in ("jellyfin", "emby"):
            history = await self._get_jellyfin_history(user_ids)
        elif selected_service == "plex":
            history = await self._get_plex_history(user_ids)
        else:
            logger.info("No media service configured; skipping history fetch.")

        return history

    async def _get_jellyfin_history(self, user_ids: Optional[List]) -> List[Dict]:
        """Fetch history from Jellyfin."""
        from api_service.services.jellyfin.jellyfin_client import JellyfinClient

        api_url = self.config.get("JELLYFIN_API_URL", "")
        token = self.config.get("JELLYFIN_TOKEN", "")
        if not api_url or not token:
            logger.warning("Jellyfin not configured; skipping history fetch.")
            return []

        raw_libraries = self.config.get("JELLYFIN_LIBRARIES", [])
        libraries = raw_libraries if isinstance(raw_libraries, list) else []

        client = JellyfinClient(
            api_url=api_url,
            token=token,
            max_content=20,
            library_ids=libraries,
        )

        # Determine which users to query
        if user_ids:
            users = [
                u if isinstance(u, dict) else {"id": u, "name": str(u)}
                for u in user_ids
            ]
        else:
            try:
                users = await client.get_all_users()
            except Exception as exc:
                logger.warning("Could not fetch Jellyfin users: %s", exc)
                return []

        history: List[Dict] = []
        for user in users:
            try:
                items_by_library = await client.get_recent_items(user)
                for items in items_by_library.values():
                    for item in items:
                        item_type_raw = item.get("Type", "").lower()
                        if item_type_raw == "episode":
                            title = item.get("SeriesName") or item.get("Name")
                            media_type = "tv"
                        else:
                            title = item.get("Name")
                            media_type = "movie"
                        year = item.get("ProductionYear")
                        if title:
                            history.append({"title": title, "year": year, "type": media_type})
            except Exception as exc:
                logger.warning("Error fetching history for Jellyfin user %s: %s", user, exc)

        return history

    async def _get_plex_history(self, user_ids: Optional[List]) -> List[Dict]:
        """Fetch history from Plex."""
        from api_service.services.plex.plex_client import PlexClient

        token = self.config.get("PLEX_TOKEN", "")
        api_url = self.config.get("PLEX_API_URL", "")
        if not token:
            logger.warning("Plex not configured; skipping history fetch.")
            return []

        raw_libraries = self.config.get("PLEX_LIBRARIES", [])
        libraries = raw_libraries if isinstance(raw_libraries, list) else []

        client = PlexClient(
            token=token,
            api_url=api_url,
            max_content=20,
            library_ids=libraries,
            user_ids=user_ids or [],
        )

        try:
            items = await client.get_recent_items()
        except Exception as exc:
            logger.warning("Error fetching Plex history: %s", exc)
            return []

        history: List[Dict] = []
        for item in items:
            if item.get("type") == "episode":
                title = item.get("grandparentTitle") or item.get("title")
                media_type = "tv"
            else:
                title = item.get("title")
                media_type = "movie"
            year = item.get("year")
            if title:
                history.append({"title": title, "year": year, "type": media_type})

        return history

    def _make_tmdb_client(self) -> TMDbClient:
        """Instantiate TMDbClient from the current configuration."""
        c = self.config
        tmdb_threshold = int(c.get("FILTER_TMDB_THRESHOLD") or 60)
        tmdb_min_votes = int(c.get("FILTER_TMDB_MIN_VOTES") or 20)
        include_no_ratings = c.get("FILTER_INCLUDE_NO_RATING", True) is True
        filter_release_year = int(c.get("FILTER_RELEASE_YEAR") or 0)
        filter_language = c.get("FILTER_LANGUAGE", []) or []
        filter_genre = c.get("FILTER_GENRES_EXCLUDE", []) or []
        filter_min_runtime = c.get("FILTER_MIN_RUNTIME")
        rating_source = c.get("FILTER_RATING_SOURCE", "tmdb")
        imdb_threshold = c.get("FILTER_IMDB_THRESHOLD")
        imdb_min_votes = c.get("FILTER_IMDB_MIN_VOTES")

        omdb_client = None
        if rating_source in ("imdb", "both") and c.get("OMDB_API_KEY"):
            from api_service.services.omdb.omdb_client import OmdbClient
            omdb_client = OmdbClient(c["OMDB_API_KEY"])

        return TMDbClient(
            api_key=c.get("TMDB_API_KEY", ""),
            search_size=20,
            tmdb_threshold=tmdb_threshold,
            tmdb_min_votes=tmdb_min_votes,
            include_no_ratings=include_no_ratings,
            filter_release_year=filter_release_year,
            filter_language=filter_language,
            filter_genre=filter_genre,
            filter_region_provider=None,
            filter_streaming_services=None,
            filter_min_runtime=filter_min_runtime,
            rating_source=rating_source,
            imdb_threshold=imdb_threshold,
            imdb_min_votes=imdb_min_votes,
            omdb_client=omdb_client,
        )

    @staticmethod
    def _is_watched(item: Dict, watched_titles: set) -> bool:
        """Return True if the item title matches a known watched title."""
        title = (item.get("title") or item.get("name") or "").strip().lower()
        if not title:
            return False
        for watched in watched_titles:
            if not watched:
                continue
            if title == watched:
                return True
            if len(watched) >= 5 and watched in title:
                return True
            if len(title) >= 5 and title in watched:
                return True
        return False
