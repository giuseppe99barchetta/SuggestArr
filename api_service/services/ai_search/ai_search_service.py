"""
AI Search Service — orchestrates LLM query interpretation, TMDB search/discover,
rating filtering, and history-based deduplication to power the AI Search tab.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from api_service.config.logger_manager import LoggerManager
from api_service.services.config_service import ConfigService
from api_service.services.filter_normalization import build_tmdb_params, normalize_filters
from api_service.services.llm.llm_service import interpret_search_query
from api_service.services.tmdb.tmdb_client import TMDbClient
from api_service.services.tmdb.tmdb_discover import TMDbDiscover

logger = LoggerManager.get_logger("AiSearchService")

# Maximum total results returned to the caller
_RESULTS_MAX = 12
_DISCOVER_MIN_RATING = 6.0
_DISCOVER_MIN_VOTES = 200
_DISCOVER_SORT_BY = "popularity.desc"


class AiSearchService:
    """Provides semantic AI-powered movie and TV show search.

    Flow:
    1. Fetch viewing history from the configured media server (Jellyfin / Plex).
    2. Send query + history to the LLM to obtain a ranked list of specific title
       suggestions (plus discover_params used for the interpretation bar).
    3. Resolve each suggested title on TMDB in parallel.
    4. Apply rating filters, exclude already-watched/requested titles, deduplicate.
    5. Return AI-curated results only — no generic Discover fallback.
    """

    def __init__(self):
        """Initialise AiSearchService from the current application configuration.

        Uses get_runtime_config() so that DB-backed integration credentials
        (TMDB_API_KEY, JELLYFIN_TOKEN, SEER_TOKEN, etc.) are always present
        even after a config import that only writes keys to the DB.
        """
        self.config = ConfigService.get_runtime_config()

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
        :return: Dict with 'results', 'ai_reasoning', and 'total'.
        """
        if media_type == "both":
            movie_task = self._search_single(query, "movie", user_ids, max_results, use_history, exclude_watched)
            tv_task = self._search_single(query, "tv", user_ids, max_results, use_history, exclude_watched)
            movie_res, tv_res = await asyncio.gather(movie_task, tv_task)

            # Interleave: AI movie, AI tv, …
            ai_movies = movie_res["results"]
            ai_tv = tv_res["results"]

            merged: List[Dict] = []
            for pair in zip(ai_movies, ai_tv):
                merged.extend(pair)

            # Append leftovers (when one list is longer than the other)
            for lst in (ai_movies, ai_tv):
                for item in lst:
                    if item not in merged:
                        merged.append(item)

            ai_reasoning = {
                "movie": movie_res.get("ai_reasoning", {}),
                "tv": tv_res.get("ai_reasoning", {}),
            }

            return {
                "results": merged[:max_results],
                "ai_reasoning": ai_reasoning,
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

        # 2. Fetch already-requested TMDB IDs to exclude from results (best-effort)
        already_requested: set = set()
        try:
            from api_service.db.database_manager import DatabaseManager  # local import avoids circular deps
            already_requested = DatabaseManager().get_requested_tmdb_ids()
        except Exception as exc:
            logger.warning("Could not fetch already-requested IDs: %s", exc)

        # 3. LLM interpretation — request enough suggestions to fill max_results after
        # filtering; ask for slightly more than needed to absorb TMDB lookup misses.
        llm_suggestions_count = max(max_results, 12)
        interpretation = await interpret_search_query(
            query, history, media_type, max_suggestions=llm_suggestions_count
        )
        ai_reasoning = self._build_ai_reasoning(interpretation)
        discover_params = interpretation.get("discover_params", {})
        prepared_discover_filters = self._prepare_tmdb_discover_filters(discover_params)
        tmdb_discover_params = self._map_llm_discover_params(prepared_discover_filters)
        suggested_titles = interpretation.get("suggested_titles", [])
        suggestion_rationale_map = self._build_suggestion_rationale_map(suggested_titles)

        logger.info("Discover filters: %s", prepared_discover_filters)
        logger.info("TMDb params: %s", tmdb_discover_params)

        # 4. Build TMDb client from config
        tmdb_client = self._make_tmdb_client()
        tmdb_discover = self._make_tmdb_discover(tmdb_client.omdb_client)

        from contextlib import AsyncExitStack
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(tmdb_client)
            await stack.enter_async_context(tmdb_discover)
            if tmdb_client.omdb_client:
                await stack.enter_async_context(tmdb_client.omdb_client)

            # 5. Resolve each suggested title on TMDB in parallel
            title_tasks = [
                self._resolve_suggested_title(t, media_type, tmdb_client)
                for t in suggested_titles
            ]
            title_results: List[Optional[Dict]] = list(await asyncio.gather(*title_tasks))

            discover_results: List[Dict[str, Any]] = []
            if tmdb_discover_params:
                logger.info("Calling TMDb discover for %s with params: %s", media_type, tmdb_discover_params)
                if media_type == "movie":
                    discover_results = await tmdb_discover.discover_movies(prepared_discover_filters, max_results=max_results)
                else:
                    discover_results = await tmdb_discover.discover_tv(prepared_discover_filters, max_results=max_results)
                logger.info("TMDb discover returned %d %s results", len(discover_results), media_type)

        # 6. Build result list: AI suggestions only, filtered & deduped
        seen_ids: set = set()
        final: List[Dict] = []

        for tmdb_item, suggestion in zip(title_results, suggested_titles):
            self._append_candidate_result(
                final=final,
                seen_ids=seen_ids,
                item=tmdb_item,
                media_type=media_type,
                tmdb_client=tmdb_client,
                already_requested=already_requested,
                watched_titles=watched_titles,
                exclude_watched=exclude_watched,
                source="ai_suggestion",
                rationale=suggestion.get("rationale", ""),
                tmdb_discover_params=tmdb_discover_params,
                apply_discover_filters=True,
            )

        for tmdb_item in discover_results:
            if len(final) >= max_results:
                break
            self._append_candidate_result(
                final=final,
                seen_ids=seen_ids,
                item=tmdb_item,
                media_type=media_type,
                tmdb_client=tmdb_client,
                already_requested=already_requested,
                watched_titles=watched_titles,
                exclude_watched=exclude_watched,
                source="tmdb_discover",
                rationale="",
                tmdb_discover_params=tmdb_discover_params,
                apply_discover_filters=False,
            )

        self._apply_suggestion_rationales(final, suggestion_rationale_map)

        return {
            "results": final[:max_results],
            "ai_reasoning": ai_reasoning,
            "total": len(final[:max_results]),
        }

    @staticmethod
    def _build_ai_reasoning(interpretation: Dict[str, Any]) -> Dict[str, Any]:
        """Build a frontend-friendly reasoning payload from the full LLM interpretation."""
        discover_params = interpretation.get("discover_params", {}) or {}
        suggested_titles = interpretation.get("suggested_titles", []) or []

        return {
            "genres": discover_params.get("genres") or [],
            "year_from": discover_params.get("year_from"),
            "year_to": discover_params.get("year_to"),
            "original_language": discover_params.get("original_language"),
            "min_rating": discover_params.get("min_rating"),
            "title_suggestions": suggested_titles,
            "explanation": interpretation.get("explanation") or AiSearchService._generate_reasoning_explanation(
                discover_params,
                suggested_titles,
            ),
        }

    @staticmethod
    def _generate_reasoning_explanation(
        discover_params: Dict[str, Any],
        suggested_titles: List[Dict[str, Any]],
    ) -> str:
        """Generate a concise explanation when the LLM payload does not include one."""
        parts: List[str] = []

        genres = discover_params.get("genres") or []
        if genres:
            parts.append(f"Focused on {', '.join(genres)} titles")

        year_from = discover_params.get("year_from")
        year_to = discover_params.get("year_to")
        if year_from and year_to:
            parts.append(f"released between {year_from} and {year_to}")
        elif year_from:
            parts.append(f"released from {year_from} onward")
        elif year_to:
            parts.append(f"released up to {year_to}")

        language = discover_params.get("original_language")
        if language:
            parts.append(f"with original language '{language}'")

        min_rating = discover_params.get("min_rating")
        if min_rating is not None:
            parts.append(f"targeting titles rated at least {min_rating:.1f} on TMDb")

        if suggested_titles:
            preview_titles = [item.get("title") for item in suggested_titles if item.get("title")][:3]
            if preview_titles:
                parts.append(f"and highlighted examples like {', '.join(preview_titles)}")

        if not parts:
            return "The AI interpreted your request and selected titles that best match the query."

        return "The AI interpreted your request by " + ", ".join(parts) + "."

    @staticmethod
    def _normalize_date_string(value: Any) -> Optional[str]:
        """Return a YYYY-MM-DD string for date-like values, or None when invalid."""
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if len(text) == 4 and text.isdigit():
            return f"{text}-01-01"
        try:
            # Accept date/datetime-like values while preserving date-only comparison.
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return None

    @staticmethod
    def _map_llm_discover_params(discover_params: Dict[str, Any]) -> Dict[str, Any]:
        """Map LLM discover filters to TMDb discover-style parameter names."""
        normalized = normalize_filters(discover_params)
        params = build_tmdb_params(normalized)

        vote_count_gte = discover_params.get("vote_count_gte")
        if vote_count_gte is not None:
            params["vote_count_gte"] = int(vote_count_gte)

        sort_by = discover_params.get("sort_by")
        if sort_by:
            params["sort_by"] = str(sort_by)

        return params

    @staticmethod
    def _prepare_tmdb_discover_filters(discover_params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply AI-search quality defaults before invoking TMDb discover."""
        prepared = dict(discover_params or {})
        prepared["sort_by"] = _DISCOVER_SORT_BY
        prepared["vote_count_gte"] = max(int(prepared.get("vote_count_gte") or 0), _DISCOVER_MIN_VOTES)
        prepared["min_rating"] = _DISCOVER_MIN_RATING
        return prepared

    def _passes_tmdb_discover_params(
        self,
        item: Dict[str, Any],
        media_type: str,
        tmdb_discover_params: Dict[str, Any],
    ) -> bool:
        """Apply mapped TMDb discover-style params to resolved search items."""
        if not tmdb_discover_params:
            return True

        genres_csv = tmdb_discover_params.get("with_genres")
        if genres_csv:
            allowed_genres = {
                int(g.strip()) for g in str(genres_csv).replace("|", ",").split(",")
                if g.strip().isdigit()
            }
            if allowed_genres:
                item_genres = set(item.get("genre_ids") or [])
                if not (item_genres & allowed_genres):
                    return False

        expected_language = tmdb_discover_params.get("with_original_language")
        if expected_language:
            item_language = str(item.get("original_language") or "").strip().lower()
            if item_language != str(expected_language).strip().lower():
                return False

        vote_average_gte = tmdb_discover_params.get("vote_average_gte")
        if vote_average_gte is not None:
            try:
                if float(item.get("vote_average") or 0) < float(vote_average_gte):
                    return False
            except (TypeError, ValueError):
                return False

        vote_count_gte = tmdb_discover_params.get("vote_count_gte")
        if vote_count_gte is not None:
            try:
                if int(item.get("vote_count") or 0) < int(vote_count_gte):
                    return False
            except (TypeError, ValueError):
                return False

        item_date = item.get("release_date") if media_type == "movie" else item.get("first_air_date")
        normalized_item_date = self._normalize_date_string(item_date)

        gte_date = self._normalize_date_string(tmdb_discover_params.get("primary_release_date_gte"))
        if gte_date and normalized_item_date and normalized_item_date < gte_date:
            return False

        lte_date = self._normalize_date_string(tmdb_discover_params.get("primary_release_date_lte"))
        if lte_date and normalized_item_date and normalized_item_date > lte_date:
            return False

        return True

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
        logger.debug("Jellyfin URL: %s, Token: %s", api_url, "SET" if token else "EMPTY")
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

        async with client:
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

        async with client:
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
        logger.debug("TMDb API key: %s", "SET" if c.get("TMDB_API_KEY") else "EMPTY")
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

    def _make_tmdb_discover(self, omdb_client=None) -> TMDbDiscover:
        """Instantiate TMDbDiscover from the current configuration."""
        return TMDbDiscover(
            api_key=self.config.get("TMDB_API_KEY", ""),
            omdb_client=omdb_client,
        )

    def _append_candidate_result(
        self,
        final: List[Dict[str, Any]],
        seen_ids: set,
        item: Optional[Dict[str, Any]],
        media_type: str,
        tmdb_client: TMDbClient,
        already_requested: set,
        watched_titles: set,
        exclude_watched: bool,
        source: str,
        rationale: str,
        tmdb_discover_params: Dict[str, Any],
        apply_discover_filters: bool,
    ) -> None:
        """Append a candidate result when it survives local filtering."""
        if item is None:
            logger.debug("Skipping %s result: TMDb returned no item", source)
            return

        item_id = item.get("id")
        title = item.get("title") or item.get("name") or "Unknown"

        if not item_id:
            logger.debug("Skipping %s result without TMDb id: %s", source, title)
            return
        if item_id in seen_ids:
            logger.debug("Skipping duplicate %s result: %s (%s)", source, title, item_id)
            return
        if str(item_id) in already_requested:
            logger.debug("Skipping already requested %s result: %s (%s)", source, title, item_id)
            return
        if exclude_watched and self._is_watched(item, watched_titles):
            logger.debug("Skipping watched %s result: %s (%s)", source, title, item_id)
            return
        if apply_discover_filters and not self._passes_tmdb_discover_params(item, media_type, tmdb_discover_params):
            logger.debug("Skipping %s result failing discover filters: %s (%s)", source, title, item_id)
            return

        filter_result = tmdb_client._apply_filters(item, media_type)
        if not filter_result['passed']:
            logger.debug("Skipping %s result failing TMDbClient filters: %s (%s) -> %s", source, title, item_id, filter_result)
            return

        seen_ids.add(item_id)
        item["rationale"] = rationale
        item["source"] = source
        item["media_type"] = media_type
        final.append(item)

    @staticmethod
    def _build_suggestion_rationale_map(suggested_titles: List[Dict[str, Any]]) -> Dict[str, str]:
        """Build a normalized title-to-rationale lookup from LLM title suggestions."""
        rationale_map: Dict[str, str] = {}

        for suggestion in suggested_titles:
            title = str(suggestion.get("title") or "").strip().lower()
            rationale = str(suggestion.get("rationale") or "")
            if title and rationale and title not in rationale_map:
                rationale_map[title] = rationale

        return rationale_map

    @staticmethod
    def _apply_suggestion_rationales(results: List[Dict[str, Any]], suggestion_rationale_map: Dict[str, str]) -> None:
        """Copy LLM suggestion rationales onto matching final results by normalized title."""
        if not suggestion_rationale_map:
            return

        for result in results:
            title = str(result.get("title") or result.get("name") or "").strip().lower()
            if not title:
                continue
            result["rationale"] = suggestion_rationale_map.get(title, result.get("rationale", ""))

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
