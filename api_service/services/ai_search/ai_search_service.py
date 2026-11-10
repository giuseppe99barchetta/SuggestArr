"""
AI Search Service — orchestrates LLM query interpretation, TMDB search/discover,
rating filtering, and history-based deduplication to power the AI Search tab.
"""

import asyncio
import inspect
from datetime import datetime
from typing import Any, Awaitable, Dict, List, Optional, Union


from api_service.config.logger_manager import LoggerManager
from api_service.services.config_service import ConfigService
from api_service.services.filter_normalization import build_tmdb_params, normalize_filters
from api_service.config.config import get_request_backend
from api_service.services.library_content import load_library_content
from api_service.services.llm.llm_service import (
    MAX_EXCLUSION_ITEMS,
    MAX_HISTORY_ITEMS,
    _deduplicate_history,
    _unique_person_labels,
    clean_excluded_title,
    generate_search_result_rationales,
    group_history_slices,
    interpret_search_query,
)
from api_service.services.tmdb.tmdb_client import TMDbClient

logger = LoggerManager.get_logger("AiSearchService")

# How long the prompt waits for the library before searching without its titles.
_OWNED_PROMPT_TIMEOUT = 5.0
# Candidates asked from the LLM: 1.5x headroom for post-filtering (capped), never below max_results.
_CANDIDATE_HEADROOM_CAP = 36

# Maximum total results returned to the caller
_RESULTS_MAX = 12


class AiSearchService:
    """Provides semantic AI-powered movie and TV show search.

    Flow:
    1. Fetch viewing history from the configured media server (Jellyfin / Plex).
    2. Send query + history to the LLM to obtain a ranked list of specific title
       suggestions (plus discover_params used for the interpretation bar).
    3. Resolve each suggested title on TMDB in parallel.
    4. Apply rating filters, exclude already-watched/requested/owned titles, deduplicate.
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

    async def inspiration(self, profile: Dict, saved_history: List[Dict]) -> List[Dict]:
        """Build a small poster shelf from an explicitly linked media profile.

        Never fall back to all server users. Loading this shelf neither calls
        the LLM nor records titles as recommendations already shown.
        """
        external_id = profile.get("external_user_id")
        if not external_id or profile.get("provider") != str(self.config.get("SELECTED_SERVICE") or "").lower():
            return []
        try:
            history = await asyncio.wait_for(self._get_history([external_id]), timeout=8)
        except Exception:
            logger.warning("Could not load AI Search inspiration history")
            history = []

        items, seen = [], set()
        for item in history + saved_history:
            title = str(item.get("title") or "").strip()
            media_type = item.get("media_type") or item.get("type")
            key = (title.casefold(), media_type)
            if not title or media_type not in {"movie", "tv"} or key in seen:
                continue
            seen.add(key)
            items.append({"title": title, "year": item.get("year"), "media_type": media_type, "poster_path": None})
            if len(items) == 6:
                break
        if not items or not self.config.get("TMDB_API_KEY"):
            return items

        async def enrich(item, client):
            try:
                match = await asyncio.wait_for(
                    self._resolve_suggested_title(item, item["media_type"], client), timeout=5,
                )
                if match:
                    item["poster_path"] = match.get("poster_path")
            except Exception:
                logger.warning("Could not load an AI Search inspiration poster")

        try:
            async with self._make_tmdb_client() as client:
                await asyncio.gather(*(enrich(item, client) for item in items))
        except Exception:
            logger.warning("Could not initialise AI Search inspiration posters")
        return items

    async def search(
        self,
        query: str,
        media_type: str = "movie",
        user_ids: Optional[List] = None,
        max_results: int = _RESULTS_MAX,
        use_history: bool = True,
        exclude_watched: bool = True,
        exclude_seen: bool = False,
        original_language: str = "auto",
        feedback_scope: Optional[tuple] = None,
        people: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Execute an AI-powered search.

        :param query: Natural language description of desired content.
        :param media_type: 'movie', 'tv', or 'both'.
        :param user_ids: Explicit media-server user IDs; empty means no history.
        :param max_results: Maximum number of results to return.
        :param use_history: Whether to fetch and pass viewing history to the LLM.
        :param exclude_watched: Whether to exclude already-watched titles from results.
        :param original_language: 'auto' uses the prompt, 'any' removes language restrictions,
            otherwise an ISO 639-1 code overrides the prompt's language filter.
        :param feedback_scope: ``(user_id, media_user_id)`` whose personal feedback hides
            rated titles and steers the prompt; None applies only the legacy global feedback.
        :param people: People the search is for, each ``{'user_id', 'name', 'external_user_id'}``
            (already authorised by the caller). Non-empty means per-person history and ratings
            replace ``user_ids``/``feedback_scope``; two or more make it a group search.
        :return: Dict with 'results', 'ai_reasoning', and 'total'.
        """
        # Load the library in the background while the LLM interprets the query;
        # each media type awaits it only when filtering results.
        owned_ids = asyncio.ensure_future(self._get_owned_tmdb_ids())
        try:
            if media_type == "both":
                movie_task = self._search_single(
                    query, "movie", user_ids, max_results, use_history, exclude_watched, exclude_seen,
                    record_seen=False, owned_ids=owned_ids,
                    original_language=original_language, feedback_scope=feedback_scope, people=people,
                )
                tv_task = self._search_single(
                    query, "tv", user_ids, max_results, use_history, exclude_watched, exclude_seen,
                    record_seen=False, owned_ids=owned_ids,
                    original_language=original_language, feedback_scope=feedback_scope, people=people,
                )
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
                final_results = merged[:max_results]
                self._record_seen_items(final_results, media_type)

                return {
                    "results": final_results,
                    "ai_reasoning": ai_reasoning,
                    "total": len(final_results),
                }

            return await self._search_single(
                query, media_type, user_ids, max_results, use_history, exclude_watched, exclude_seen,
                owned_ids=owned_ids,
                original_language=original_language, feedback_scope=feedback_scope, people=people,
            )
        finally:
            owned_ids.cancel()  # no-op once the library has loaded

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_owned_tmdb_ids(self) -> Dict[str, set]:
        """Return the TMDB IDs already in the library, keyed by media type.

        Uses the shared owned-content policy (media server plus Seer availability,
        see :func:`load_library_content`), so AI Search and the jobs agree on what
        counts as owned. Without Seer configured only the media server is used.
        Best-effort: a failure never breaks a search.

        :return: Dict mapping 'movie' / 'tv' to sets of TMDB ID strings (may be empty).
        """
        if not self.config.get("EXCLUDE_DOWNLOADED", True):
            return {}
        try:
            # Direct Radarr/Sonarr delivery never contacts Seer, even if its credentials are still saved.
            if not self.config.get("SEER_API_URL") or get_request_backend(self.config) == "arr":
                return await load_library_content(self.config)
            from api_service.services.seer.seer_client import SeerClient  # local import avoids circular deps
            async with SeerClient(self.config["SEER_API_URL"], self.config.get("SEER_TOKEN")) as seer_client:
                return await load_library_content(self.config, seer_client)
        except Exception as exc:
            logger.warning("Could not load the library for AI Search: %s", exc)
            return {}

    async def _search_single(
        self,
        query: str,
        media_type: str,
        user_ids: Optional[List],
        max_results: int,
        use_history: bool = True,
        exclude_watched: bool = True,
        exclude_seen: bool = False,
        record_seen: bool = True,
        owned_ids: Optional[Union[Dict[str, set], Awaitable[Dict[str, set]]]] = None,
        original_language: str = "auto",
        feedback_scope: Optional[tuple] = None,
        people: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Run the full search pipeline for a single media type.

        :param owned_ids: TMDB IDs already in the library, keyed by media type, or
            a task resolving to them; matching results are excluded like
            already-requested ones.
        """
        # 1. Fetch history (best-effort — never crash the search if unavailable)
        history: List[Dict] = []
        people_data: Optional[Dict[str, Any]] = None
        if people:
            people_data = await self._load_people(people, media_type, use_history, exclude_watched)
            history = people_data["watched_history"]
        elif use_history:
            try:
                history = await self._get_history(user_ids)
            except Exception as exc:
                logger.warning("Could not fetch viewing history: %s", exc)

        watched_titles = {
            (item.get("title") or item.get("name") or "").strip().lower()
            for item in history
        } | ({title.lower() for title in people_data["stored_titles"]} if people_data else set())
        watched_ids = people_data["watched_ids"] if people_data else set()

        # 2. Fetch already-requested TMDB IDs to exclude from results (best-effort)
        already_requested: set = set()
        try:
            from api_service.db.database_manager import DatabaseManager  # local import avoids circular deps
            already_requested = DatabaseManager().get_requested_tmdb_ids()
        except Exception as exc:
            logger.warning("Could not fetch already-requested IDs: %s", exc)

        # 2b. Fetch user feedback (likes positively bias the prompt; dislikes are excluded from results).
        liked_titles: list = []
        try:
            from api_service.db.database_manager import DatabaseManager
            db = DatabaseManager()
            disliked_ids = db.get_ai_dislike_ids(media_type)
            already_requested = already_requested | {str(i) for i in disliked_ids}
            liked_titles = [] if people_data else db.get_ai_likes(media_type)
            if people_data:
                # Everyone selected: what any of them dismissed or marked seen stays out.
                already_requested = already_requested | people_data["negative_ids"]
            elif feedback_scope:
                # Personal ratings: anything the user dismissed or has watched stays out,
                # and what they liked or saved steers the prompt like the legacy likes do.
                signals = db.get_suggestion_feedback_signals(*feedback_scope, media_type)
                already_requested = already_requested | {
                    tmdb_id for tmdb_id, value in signals.items() if value in db.NEGATIVE_FEEDBACK}
                taste = db.get_taste_profile(*feedback_scope, media_type)
                liked_titles = liked_titles + [
                    {**entry, 'media_type': media_type}
                    for bucket in ('loved', 'interested', 'saved') for entry in taste[bucket]]
            if exclude_seen:
                seen_ids = db.get_ai_seen_ids(media_type)
                already_requested = already_requested | seen_ids
        except Exception as exc:
            logger.warning("Could not fetch AI feedback: %s", exc)

        # 3. LLM interpretation — request enough suggestions to fill max_results after
        # filtering; ask for slightly more than needed to absorb TMDB lookup misses.
        llm_suggestions_count = max(
            max_results, 12, min((3 * max_results + 1) // 2, _CANDIDATE_HEADROOM_CAP))
        excluded_titles = await self._excluded_titles_for_prompt(
            media_type, history, exclude_watched, exclude_seen, feedback_scope, owned_ids, people_data)
        interpretation_query = query
        if original_language == "any":
            interpretation_query += "\nSearch option: recommend titles in any original language; do not apply an original-language restriction."
        elif original_language != "auto":
            interpretation_query += (
                f"\nSearch option: ONLY recommend titles whose original language is '{original_language}' "
                "(ISO 639-1). This selection overrides any language restriction in the prompt."
            )
        interpretation = await interpret_search_query(
            interpretation_query, [] if people_data else history, media_type,
            max_suggestions=llm_suggestions_count, liked_titles=liked_titles, excluded_titles=excluded_titles,
            people_profiles=people_data["profiles"] if people_data else None,
        )
        # Enforce the UI selection even if the LLM returns a conflicting language.
        if original_language != "auto":
            interpretation = {
                **interpretation,
                "discover_params": {
                    **(interpretation.get("discover_params") or {}),
                    "original_language": None if original_language == "any" else original_language,
                },
                "explanation": "",
            }
        ai_reasoning = self._build_ai_reasoning(interpretation)
        discover_params = interpretation.get("discover_params", {})
        tmdb_discover_params = self._map_llm_discover_params(discover_params)
        suggested_titles = interpretation.get("suggested_titles", [])
        reference_titles = interpretation.get("reference_titles", [])
        suggestion_rationale_map = self._build_suggestion_rationale_map(suggested_titles)

        logger.debug("AI search filters: %s", tmdb_discover_params)

        # 4. Build TMDb client from config
        tmdb_client = self._make_tmdb_client()

        from contextlib import AsyncExitStack
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(tmdb_client)
            if tmdb_client.omdb_client:
                await stack.enter_async_context(tmdb_client.omdb_client)

            # 5. Resolve each suggested title on TMDB in parallel
            title_tasks = [
                self._resolve_suggested_title(t, media_type, tmdb_client)
                for t in suggested_titles
            ]
            title_results: List[Optional[Dict]] = list(await asyncio.gather(*title_tasks))
            # A group search does not use TMDb "similar" titles, so it never asks for them.
            skip_similar = bool(people_data) and len(people_data["profiles"]) >= 2
            reference_tasks = [
                self._resolve_suggested_title(t, media_type, tmdb_client)
                for t in ([] if skip_similar else reference_titles)
            ]
            reference_results: List[Optional[Dict]] = list(await asyncio.gather(*reference_tasks))

            resolved_references = [
                (reference, result)
                for reference, result in zip(reference_titles, reference_results)
                if result and result.get("id")
            ]
            similar_tasks = [
                tmdb_client.find_similar_movies(result["id"])
                if media_type == "movie"
                else tmdb_client.find_similar_tvshows(result["id"])
                for _, result in resolved_references
            ]
            similar_result_groups: List[List[Dict]] = list(await asyncio.gather(*similar_tasks))

        # 6. Build result list: AI suggestions only, filtered & deduped.
        # Titles already in the library are excluded like already-requested ones.
        if inspect.isawaitable(owned_ids):
            try:
                owned_ids = await owned_ids
            except Exception as exc:  # a failed library load never breaks a search
                logger.warning("Could not load the library for AI Search: %s", exc)
                owned_ids = {}
        already_requested = already_requested | (owned_ids or {}).get(media_type, set())

        seen_ids: set = set()
        final: List[Dict] = []

        def add_similar() -> None:
            for similar_results in similar_result_groups:
                for tmdb_item in similar_results:
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
                        source="tmdb_similar",
                        rationale="",
                        tmdb_discover_params=tmdb_discover_params,
                        apply_discover_filters=True,
                        watched_ids=watched_ids,
                    )

        def add_suggestions() -> None:
            for tmdb_item, suggestion in zip(title_results, suggested_titles):
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
                    source="ai_suggestion",
                    rationale=suggestion.get("rationale", ""),
                    tmdb_discover_params=tmdb_discover_params,
                    apply_discover_filters=True,
                    watched_ids=watched_ids,
                )

        # TMDb "similar" titles are chosen by similarity to the reference alone, so a group
        # search leaves them out: only titles the group-aware LLM picked are returned, even if
        # that means fewer results. shortcut: upgrade to an LLM fit check on similar titles
        # if groups with a named reference title come back too short.
        if skip_similar:
            add_suggestions()
        else:
            add_similar()
            add_suggestions()

        await self._apply_suggestion_rationales(
            final,
            suggestion_rationale_map,
            query,
            discover_params,
            media_type,
            reference_titles=reference_titles,
            people_context=[{"name": person["name"], "taste": person["taste"], "requester": person["requester"]}
                            for person in people_data["profiles"]]
            if people_data else None,
        )

        final_slice = final[:max_results]
        if record_seen:
            self._record_seen_items(final_slice, media_type)

        return {
            "results": final_slice,
            "ai_reasoning": ai_reasoning,
            "total": len(final_slice),
        }

    async def _excluded_titles_for_prompt(
        self,
        media_type: str,
        history: List[Dict],
        exclude_watched: bool,
        exclude_seen: bool,
        feedback_scope: Optional[tuple],
        owned_ids: Optional[Union[Dict[str, set], Awaitable[Dict[str, set]]]],
        people_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """Titles the post-filter would drop, named so the LLM can avoid them up front.

        Best-effort and read-only: the post-filter stays the source of truth, so any
        failure here just means a prompt without the list. The library is awaited for at
        most ``_OWNED_PROMPT_TIMEOUT`` seconds; it is still awaited later for the filter.
        """
        try:
            owned: Dict[str, set] = {}
            if inspect.isawaitable(owned_ids):
                try:
                    owned = await asyncio.wait_for(asyncio.shield(owned_ids), _OWNED_PROMPT_TIMEOUT) or {}
                except Exception:  # timeout or failed load: search without library titles
                    owned = {}
            elif owned_ids:
                owned = owned_ids
            from api_service.db.database_manager import DatabaseManager  # local import avoids circular deps
            return self._build_excluded_titles(
                DatabaseManager(), media_type, history, exclude_watched, exclude_seen,
                feedback_scope, (owned or {}).get(media_type, set()), people_data)
        except Exception as exc:
            logger.warning("Could not build the already-handled list for the prompt: %s", exc)
            return []

    @staticmethod
    def _build_excluded_titles(
        db, media_type: str, history: List[Dict], exclude_watched: bool, exclude_seen: bool,
        feedback_scope: Optional[tuple], owned_ids: set, people: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """Assemble the ordered, deduplicated, capped list of already-handled titles.

        Priority: personal dismissed/seen feedback, legacy dislikes, watched history past
        the 20 titles the prompt already lists (only when watched titles are excluded),
        requested, owned, then titles shown in earlier searches (only when that toggle is on).
        shortcut: arbitrary order inside a group; upgrade to recency ordering if big
        libraries still waste results.

        :param people: Per-person data from :meth:`_load_people` for a people search: every
            person's dismissed titles are listed, the "already in the prompt" set comes from the
            exact per-person slices the prompt renders, and their stored watched titles join the list.
        """
        result: List[Dict] = []
        keys: set = set()
        # The prompt already lists these (even when watched titles are not excluded), so
        # repeating them would waste slots. Same dedupe + cut-off as interpret_search_query.
        if people:
            rendered_items = [item for part in group_history_slices(people["prompt_histories"]) for item in part]
        else:
            rendered_items = _deduplicate_history(history)[:MAX_HISTORY_ITEMS]
        rendered = {(item.get("title") or item.get("name") or "").strip().lower() for item in rendered_items}

        def add(title, year) -> None:
            clean = clean_excluded_title(title)
            key = (clean.lower(), year or None)
            # 'Unknown Title' is the placeholder save_metadata stores when a title is missing.
            if clean and clean != "Unknown Title" and clean.lower() not in rendered                     and key not in keys and len(result) < MAX_EXCLUSION_ITEMS:
                keys.add(key)
                result.append({"title": clean, "year": year or None})

        def add_ids(ids) -> None:
            # Fetch every known title: entries already listed by an earlier group are
            # dropped by add(), so a limit of the remaining room could starve the list.
            if len(result) < MAX_EXCLUSION_ITEMS and ids:
                for entry in db.get_titles_for_tmdb_ids(media_type, ids, len(ids)):
                    add(entry["title"], entry["year"])

        scopes = people["scopes"] if people else ([feedback_scope] if feedback_scope else [])
        unnamed = set()
        for scope in scopes:
            for row in db.list_negative_feedback_titles(*scope, media_type):
                if row["title"]:
                    add(row["title"], row["year"])
                else:
                    unnamed.add(row["tmdb_id"])
        add_ids(unnamed)
        for row in db.get_ai_dislikes(media_type):
            add(row["title"], row["year"])
        if exclude_watched:
            # Titles the prompt already renders are skipped by add(); the rest are listed here.
            for item in _deduplicate_history(history):
                add(item.get("title") or item.get("name"), item.get("year"))
            for title in people["stored_titles"] if people else []:
                add(title, None)
        add_ids(db.get_requested_tmdb_ids_by_type(media_type))
        add_ids(owned_ids)
        if exclude_seen:
            add_ids(db.get_ai_seen_ids(media_type))
        return result

    async def _load_people(
        self, people: List[Dict], media_type: str, use_history: bool, exclude_watched: bool,
    ) -> Dict[str, Any]:
        """Gather what each selected person has watched and rated, best-effort.

        Recent provider history is fetched when it personalises the prompt or filters watched
        titles; stored watched records (all of them, via a read-only identity lookup) are
        added for filtering because the provider only returns the latest 20 titles. A failure
        for one person leaves that part empty rather than failing the search.

        :return: ``profiles`` (name/history/taste per person for the prompt, history empty when
            personalisation is off), ``prompt_histories``, ``watched_history`` (everyone's recent
            history), ``stored_titles`` (sorted, as stored), ``watched_ids`` (TMDB ids of stored titles),
            ``negative_ids`` (dismissed or seen by anyone) and ``scopes``.
        """
        from api_service.db.database_manager import DatabaseManager  # local import avoids circular deps
        db = DatabaseManager()
        provider = str(self.config.get("SELECTED_SERVICE") or "").lower()

        async def load(person: Dict) -> Dict[str, Any]:
            external_id = person.get("external_user_id")
            history: List[Dict] = []
            if external_id and (use_history or exclude_watched):
                try:
                    # A TV series and a film can share a title: only the searched type counts,
                    # for the prompt as much as for filtering (ratings are per type already).
                    history = [entry for entry in await self._get_history([external_id])
                               if entry.get("type") in (media_type, None)]
                except Exception as exc:
                    logger.warning("Could not fetch viewing history for a selected person: %s", exc)
            stored: List[Dict] = []
            if external_id and exclude_watched:
                try:
                    identity = db.get_media_user_identity(provider, str(external_id))
                    stored = [row for row in db.list_watched_media_ids(identity["id"])
                              if row["media_type"] == media_type]
                except ValueError:
                    pass  # no identity yet: nothing stored for this person
                except Exception as exc:
                    logger.warning("Could not load stored watched titles for a selected person: %s", exc)
            scope = (person["user_id"], str(external_id) if external_id else "")
            signals: Dict[str, str] = {}
            taste: Dict[str, List] = {}
            try:
                signals = db.get_suggestion_feedback_signals(*scope, media_type)
                taste = db.get_taste_profile(*scope, media_type)
            except Exception as exc:
                logger.warning("Could not load ratings for a selected person: %s", exc)
            return {"scope": scope, "history": history, "stored": stored, "signals": signals, "taste": taste}

        loaded = await asyncio.gather(*(load(person) for person in people))
        return {
            "profiles": [
                {"name": person["name"], "history": item["history"] if use_history else [], "taste": item["taste"],
                 "requester": bool(person.get("requester"))}
                for person, item in zip(people, loaded)
            ],
            "prompt_histories": [item["history"] if use_history else [] for item in loaded],
            "watched_history": [entry for item in loaded for entry in item["history"]] if exclude_watched else [],
            "stored_titles": sorted({str(row["title"] or "").strip() for item in loaded for row in item["stored"]} - {""}),
            "watched_ids": {row["tmdb_id"] for item in loaded for row in item["stored"]},
            "negative_ids": {tmdb_id for item in loaded for tmdb_id, value in item["signals"].items()
                             if value in db.NEGATIVE_FEEDBACK},
            "scopes": [item["scope"] for item in loaded],
        }

    def _record_seen_items(self, items: List[Dict], media_type: str) -> None:
        try:
            from api_service.db.database_manager import DatabaseManager
            DatabaseManager().record_ai_seen(
                [(item.get("id"), item.get("media_type") or media_type) for item in items]
            )
        except Exception as exc:
            logger.warning("Could not record AI seen items: %s", exc)

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
            "reference_titles": interpretation.get("reference_titles", []) or [],
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
                rating = item.get("vote_average")
                if rating is None:
                    rating = item.get("rating")
                if float(rating or 0) < float(vote_average_gte):
                    return False
            except (TypeError, ValueError):
                return False

        vote_count_gte = tmdb_discover_params.get("vote_count_gte")
        if vote_count_gte is not None:
            try:
                votes = item.get("vote_count")
                if votes is None:
                    votes = item.get("votes")
                if int(votes or 0) < int(vote_count_gte):
                    return False
            except (TypeError, ValueError):
                return False

        # TMDbClient formats both movies and TV results with ``release_date``.
        # Keep the raw TV key as a fallback for callers that pass TMDb payloads.
        item_date = item.get("release_date") or (
            item.get("first_air_date") if media_type == "tv" else None
        )
        normalized_item_date = self._normalize_date_string(item_date)

        gte_date = self._normalize_date_string(tmdb_discover_params.get("primary_release_date_gte"))
        if gte_date and (not normalized_item_date or normalized_item_date < gte_date):
            return False

        lte_date = self._normalize_date_string(tmdb_discover_params.get("primary_release_date_lte"))
        if lte_date and (not normalized_item_date or normalized_item_date > lte_date):
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
            search_year = None if str(title).strip() == str(year).strip() else year
            if media_type == "movie":
                results = await tmdb_client.search_movie(title, search_year)
            else:
                results = await tmdb_client.search_tv(title, search_year)
            if not results and search_year is not None:
                if media_type == "movie":
                    results = await tmdb_client.search_movie(title)
                else:
                    results = await tmdb_client.search_tv(title)
            return results[0] if results else None
        except Exception as exc:
            logger.warning("TMDB search failed for '%s': %s", title, exc)
            return None

    async def _get_history(self, user_ids: Optional[List]) -> List[Dict]:
        """Fetch and normalise the user's viewing history from Jellyfin or Plex.

        :param user_ids: Explicit user dicts or IDs; empty means no history.
        :return: Flat list of dicts with 'title', 'year', and 'type'.
        """
        if not user_ids:
            return []
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
        if not user_ids:
            return []
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
            users = [
                u if isinstance(u, dict) else {"id": u, "name": str(u)}
                for u in user_ids
            ]

            history: List[Dict] = []
            for user in users:
                try:
                    items_by_library = await client.get_recent_items(user) or {}
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
        if not user_ids:
            return []
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
            # AI Search uses its own prompt/selector filter, never the legacy job setting.
            filter_language=[],
            filter_genre=filter_genre,
            filter_region_provider=None,
            filter_streaming_services=None,
            filter_min_runtime=filter_min_runtime,
            rating_source=rating_source,
            imdb_threshold=imdb_threshold,
            imdb_min_votes=imdb_min_votes,
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
        watched_ids: Optional[set] = None,
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
        if exclude_watched and str(item_id) in (watched_ids or ()):
            logger.debug("Skipping stored-watched %s result: %s (%s)", source, title, item_id)
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
    async def _apply_suggestion_rationales(
        results: List[Dict[str, Any]],
        suggestion_rationale_map: Dict[str, str],
        query: str,
        discover_params: Dict[str, Any],
        media_type: str,
        reference_titles: Optional[List[Dict[str, Any]]] = None,
        people_context: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Set per-item rationale from exact matches, then LLM-generated one-liners, then contextual fallback."""
        llm_rationale_map: Dict[str, str] = {}
        unresolved_results: List[Dict[str, Any]] = []

        for result in results:
            title = str(result.get("title") or result.get("name") or "").strip().lower()
            if title and title in suggestion_rationale_map:
                result["rationale"] = suggestion_rationale_map[title]
            else:
                unresolved_results.append(result)

        if unresolved_results:
            llm_rationale_map = await generate_search_result_rationales(
                query=query,
                media_type=media_type,
                discover_params=discover_params,
                results=unresolved_results,
                **({"people_context": people_context} if people_context else {}),
            )

        seen_rationales: set = set()

        for result in results:
            existing = str(result.get("rationale") or "").strip()
            if existing:
                rationale = existing
            else:
                key = AiSearchService._result_lookup_key(result, media_type)
                rationale = llm_rationale_map.get(key, "") if key else ""
                if not rationale:
                    rationale = AiSearchService._generate_contextual_result_rationale(
                        result=result,
                        discover_params=discover_params,
                        media_type=media_type,
                        reference_titles=reference_titles,
                        people_names=_unique_person_labels([p["name"] for p in people_context])
                        if people_context and (len(people_context) >= 2 or not people_context[0].get("requester"))
                        else None,
                    )

            # Keep rationale strings distinct even if two items resolve to identical text.
            if rationale in seen_rationales:
                item_id = result.get("id")
                if item_id is not None:
                    rationale = f"{rationale} (TMDb {item_id})"

            seen_rationales.add(rationale)
            result["rationale"] = rationale

    @staticmethod
    def _result_lookup_key(result: Dict[str, Any], media_type: str) -> str:
        """Build a normalized title/year lookup key matching LLM rationale map keys."""
        title = str(result.get("title") or result.get("name") or "").strip().lower()
        if not title:
            return ""

        year = result.get("year")
        if year is None:
            date_value = result.get("release_date") if media_type == "movie" else result.get("first_air_date")
            year_text = str(date_value).split("-")[0] if date_value else ""
            year = int(year_text) if year_text.isdigit() else None

        year_key = str(year) if year is not None else ""
        return f"{title}|{year_key}"

    @staticmethod
    def _generate_contextual_result_rationale(
        result: Dict[str, Any],
        discover_params: Dict[str, Any],
        media_type: str,
        reference_titles: Optional[List[Dict[str, Any]]] = None,
        people_names: Optional[List[str]] = None,
    ) -> str:
        """Generate a per-result rationale aligned to interpreted discover filters.

        With ``people_names`` (a group search) the generic sentence is neutral: it must not
        claim a fit for people it has no evidence about.
        """
        title = str(result.get("title") or result.get("name") or "This title").strip() or "This title"
        reference_title = next(
            (str(item.get("title") or "").strip() for item in reference_titles or [] if item.get("title")),
            "",
        )
        who = (people_names[0] if len(people_names) == 1
               else f"{', '.join(people_names[:-1])} and {people_names[-1]}") if people_names else ""
        # In a people search only TMDb "similar" results may claim a TMDb recommendation.
        if reference_title and (not who or result.get("source") == "tmdb_similar"):
            suffix = f", picked for {who}" if who else ""
            return f"TMDb recommends {title} as similar to {reference_title}{suffix}."

        if who:
            return f"Picked for {who} based on your search."

        genres = discover_params.get("genres") or []
        if isinstance(genres, list) and genres:
            genres_text = ", ".join(str(genre) for genre in genres)
            genre_part = f"the {genres_text} genre focus"
        else:
            genre_part = "the genre and tone from your query"

        year_from = discover_params.get("year_from")
        year_to = discover_params.get("year_to")
        if year_from and year_to:
            year_part = f"the requested {year_from}-{year_to} time range"
        elif year_from:
            year_part = f"the requested period from {year_from} onward"
        elif year_to:
            year_part = f"the requested period up to {year_to}"
        else:
            year_part = "the requested release window"

        min_rating = discover_params.get("min_rating")
        if min_rating is not None:
            rating_part = f"the minimum rating target of {float(min_rating):.1f}+"
        else:
            rating_part = "the quality threshold inferred by the AI"

        date_value = result.get("release_date") if media_type == "movie" else result.get("first_air_date")
        release_year = str(date_value).split("-")[0] if date_value else None
        if release_year and release_year.isdigit():
            release_part = f" Released in {release_year}, it remains consistent with those constraints."
        else:
            release_part = ""

        return (
            f"{title} matches the AI search because it fits {genre_part}, aligns with {year_part}, "
            f"and meets {rating_part}.{release_part}"
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
