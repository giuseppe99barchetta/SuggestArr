"""
AI Search blueprint — semantic movie/TV search powered by LLM + TMDB.
"""

import asyncio
import re

import aiohttp
from flask import Blueprint, g, jsonify, request

from api_service.auth.limiter import limiter
from api_service.auth.middleware import require_tab
from api_service.config.config import ARR_INSTANCES, arr_default_profile, get_request_backend
from api_service.config.logger_manager import LoggerManager
from api_service.db.components.suggestion_feedback_mixin import FEEDBACK_REASONS, FEEDBACK_VALUES
from api_service.db.database_manager import DatabaseManager
from api_service.services.ai_search.ai_search_service import AiSearchService
from api_service.services.arr.arr_client import ArrClient
from api_service.services.config_service import ConfigService
from api_service.services.llm.llm_service import MAX_GROUP_PEOPLE, get_llm_client

MAX_QUERY_CHARS = 500
MAX_RESULTS_LIMIT = 24

ai_search_bp = Blueprint("ai_search", __name__)
logger = LoggerManager.get_logger("AiSearchRoute")
# Legacy global like/dislike rows, read as the equivalent personal rating.
_LEGACY_FEEDBACK = {"like": "interested", "dislike": "not_interested"}
_METADATA_FIELDS = ("title", "name", "overview", "release_date", "poster_path", "backdrop_path",
                    "logo_path", "rating", "votes", "genre_ids", "origin_country")


@ai_search_bp.before_request
def require_ai_search_page():
    """Searching and requesting belong to the AI Search page; personal history stays open."""
    if request.endpoint in ("ai_search.ai_search_query", "ai_search.ai_search_request", "ai_search.ai_search_people"):
        return require_tab("ai_search")
    return None


def _current_user_id():
    """SuggestArr account id of the caller, or None when the request has none."""
    user = getattr(g, "current_user", None)
    try:
        return int(user["id"]) if user and user.get("id") is not None else None
    except (TypeError, ValueError):
        return None


def _verified_media_profile(db, provider):
    """Resolve the caller's proven link for the configured media server."""
    user_id = _current_user_id()
    if user_id is None:
        return None
    return next((profile for profile in db.get_user_media_profiles(user_id)
                 if profile.get("provider") == provider and profile.get("verified")
                 and profile.get("external_user_id")), None)


def _configured_provider(config=None):
    """Lower-cased media server AI Search reads history from."""
    config = config if config is not None else ConfigService.get_runtime_config()
    return str(config.get("SELECTED_SERVICE") or "").lower()


@ai_search_bp.route("/people", methods=["GET"])
@limiter.limit("30 per minute")
def ai_search_people():
    """People a search can be for: the caller first, then others who allow it.

    Only display names are returned, never media-server ids. Others need a verified link to the
    configured media server (the proof AI Search already requires before reading anyone's
    history) and must not have opted out in their profile.
    """
    user_id = _current_user_id()
    if user_id is None:
        return jsonify({"status": "success", "people": []}), 200
    try:
        others = [person for person in DatabaseManager().list_ai_search_people(_configured_provider())
                  if person["id"] != user_id]
        me = {"id": user_id, "name": g.current_user.get("username") or "You", "self": True}
        return jsonify({"status": "success", "people": [me] + [
            {"id": person["id"], "name": person["username"], "self": False} for person in others]}), 200
    except Exception:
        logger.warning("Could not list people for AI Search", exc_info=True)
        return jsonify({"status": "error", "message": "Could not load people"}), 503


def _resolve_people(db, raw_ids, provider):
    """Turn requested account ids into the people a search is for, or an error.

    The caller is always allowed (ratings and, when linked, history); anyone else must be
    in the opted-in, verified-link list. Nothing here trusts a name or media id from the client.

    :return: ``(people, None)`` or ``(None, (message, status))``.
    """
    ids = []
    for value in raw_ids:
        if isinstance(value, bool) or not isinstance(value, int):
            return None, ("people must be a list of account ids", 400)
        if value not in ids:
            ids.append(value)
    if len(ids) > MAX_GROUP_PEOPLE:
        return None, (f"You can pick up to {MAX_GROUP_PEOPLE} people", 400)
    user_id = _current_user_id()
    if user_id is None:
        return None, ("Sign in to search for people", 403)
    available = {person["id"]: person for person in db.list_ai_search_people(provider)}
    people = []
    for account_id in ids:
        if account_id == user_id:
            profile = _verified_media_profile(db, provider)
            people.append({"user_id": user_id, "name": g.current_user.get("username") or "You",
                           "external_user_id": str(profile["external_user_id"]) if profile else None,
                           "requester": True})
        elif account_id in available:
            person = available[account_id]
            people.append({"user_id": account_id, "name": person["username"],
                           "external_user_id": person["external_user_id"], "requester": False})
        else:
            return None, ("A selected person is not available", 403)
    return people, None


@ai_search_bp.route("/inspiration", methods=["GET"])
@limiter.limit("20 per minute")
async def ai_search_inspiration():
    """Return viewing-history starters belonging only to the signed-in user."""
    user = getattr(g, "current_user", None)
    if not user or not user.get("id"):
        return jsonify({"status": "success", "items": []}), 200
    try:
        service = AiSearchService()
        provider = str(service.config.get("SELECTED_SERVICE") or "").lower()
        db = DatabaseManager()
        profile = _verified_media_profile(db, provider)
        if not profile:
            return jsonify({"status": "success", "items": []}), 200
        identity = db.upsert_media_user_identity(provider, str(profile["external_user_id"]), profile.get("external_username"))
        saved_history = [item for item in db.list_watched_media(identity["id"], limit=50)
                         if not item.get("excluded")][:6]
        items = await service.inspiration(profile, saved_history)
        return jsonify({"status": "success", "items": items}), 200
    except Exception:
        logger.warning("Could not load AI Search inspiration", exc_info=True)
        return jsonify({"status": "error", "message": "Could not load viewing history"}), 503


@ai_search_bp.route("/query", methods=["POST"])
@limiter.limit("10 per minute")
async def ai_search_query():
    """Execute an AI-powered semantic search.

    Request body:
        query (str): Natural language description of desired content.
        media_type (str): 'movie', 'tv', or 'both'. Defaults to 'movie'.
        user_ids (list): Admin-only explicit media-server IDs. Otherwise history
            uses the caller's verified link to the configured provider.
        people (list): SuggestArr account ids the search is for (the caller and/or others who
            allow it, at most 4). When given, each person's own history and ratings are used and
            ``user_ids`` is ignored; omitted keeps the single-user behaviour.
        max_results (int): Maximum results to return (default 12).
        original_language (str): 'auto' (from prompt), 'any', or an ISO 639-1 code.

    Returns:
        JSON response with 'results', 'ai_reasoning', and 'total'.
    """
    try:
        data = request.json or {}
        query = (data.get("query") or "").strip()
        if not query:
            return jsonify({"status": "error", "message": "query is required"}), 400
        if len(query) > MAX_QUERY_CHARS:
            return jsonify({"status": "error", "message": f"query must be at most {MAX_QUERY_CHARS} characters"}), 400

        media_type = data.get("media_type", "movie")
        if media_type not in ("movie", "tv", "both"):
            media_type = "movie"

        original_language = data.get("original_language", "auto")
        if not isinstance(original_language, str) or not (
            original_language in ("auto", "any") or re.fullmatch(r"[a-z]{2}", original_language)
        ):
            return jsonify({
                "status": "error",
                "message": "original_language must be 'auto', 'any', or a two-letter lowercase language code",
            }), 400

        user_ids = data.get("user_ids") or []
        if not isinstance(user_ids, list):
            return jsonify({"status": "error", "message": "user_ids must be a list"}), 400
        raw_people = data.get("people")
        if raw_people is not None and not isinstance(raw_people, list):
            return jsonify({"status": "error", "message": "people must be a list"}), 400
        raw_max = data.get("max_results")
        if raw_max is None:
            max_results = 12
        elif isinstance(raw_max, int) and not isinstance(raw_max, bool):
            max_results = raw_max
        elif isinstance(raw_max, str) and raw_max.strip().isdigit():
            max_results = int(raw_max)
        else:
            return jsonify({"status": "error", "message": "max_results must be a whole number"}), 400
        if max_results < 1:
            return jsonify({"status": "error", "message": "max_results must be at least 1"}), 400
        max_results = min(max_results, MAX_RESULTS_LIMIT)  # every result costs an LLM and a TMDb call
        use_history = data.get("use_history", True)
        if not isinstance(use_history, bool):
            use_history = True
        exclude_watched = data.get("exclude_watched", True)
        if not isinstance(exclude_watched, bool):
            exclude_watched = True
        exclude_seen = data.get("exclude_seen", False)
        if not isinstance(exclude_seen, bool):
            exclude_seen = False

        # Check LLM is configured (not strictly required — service degrades gracefully,
        # but we surface a clear error before attempting if completely unconfigured)
        if not get_llm_client(_current_user_id()):
            return jsonify({
                "status": "error",
                "message": (
                    "LLM is not configured. "
                    "Please set OPENAI_API_KEY (and optionally OPENAI_BASE_URL) "
                    "in the Advanced settings."
                ),
            }), 400

        service = AiSearchService(llm_user_id=_current_user_id())
        user = getattr(g, "current_user", None)
        people = None
        if raw_people:
            people, failure = _resolve_people(DatabaseManager(), raw_people, _configured_provider(service.config))
            if failure:
                return jsonify({"status": "error", "message": failure[0]}), failure[1]
        elif not (user and user.get("role") == "admin" and user_ids):
            provider = str(service.config.get("SELECTED_SERVICE") or "").lower()
            profile = _verified_media_profile(DatabaseManager(), provider) if _current_user_id() is not None else None
            user_ids = [str(profile["external_user_id"])] if profile else []
        if not people and not user_ids:
            use_history = False

        result = await service.search(
            query=query,
            media_type=media_type,
            user_ids=user_ids if user_ids else None,
            max_results=max_results,
            use_history=use_history,
            exclude_watched=exclude_watched,
            exclude_seen=exclude_seen,
            original_language=original_language,
            feedback_scope=_feedback_scope(DatabaseManager()),
            people=people,
        )

        user_id = _current_user_id()
        if user_id is not None:
            try:
                DatabaseManager().add_ai_search_history(user_id, query)
            except Exception as exc:
                # History is a convenience; a failure to store it must not lose the results.
                logger.warning("Could not save AI search history: %s", exc)

        return jsonify({
            "status": "success",
            "results": result.get("results", []),
            "ai_reasoning": result.get("ai_reasoning", {}),
            "total": result.get("total", 0),
        }), 200

    except Exception as exc:
        logger.error("Error during AI search query: %s", str(exc))
        return jsonify({"status": "error", "message": "Search failed. Check the logs for details."}), 500


@ai_search_bp.route("/request", methods=["POST"])
@limiter.limit("20 per minute")
async def ai_search_request():
    """Request a media item via Seer.

    Calls the Seer API directly so the local database entry is saved with
    ``tmdb_source_id = 'ai_search'`` (allowing proper separation from
    watched-content recommendations) and with full item metadata so the title
    is stored correctly.

    Request body:
        tmdb_id (int): TMDB ID of the item to request.
        media_type (str): 'movie' or 'tv'.
        rationale (str): Optional AI per-item rationale (why this title was suggested).
        search_query (str): The original natural-language query used for this search.
        metadata (dict): Full item metadata dict (title, poster_path, overview,
            release_date, rating, …) returned by the search endpoint.

    Returns:
        JSON response with 'status' and 'message'.
    """
    try:
        data = request.json or {}
        tmdb_id = data.get("tmdb_id")
        media_type = data.get("media_type", "movie")
        rationale = data.get("rationale") or None
        search_query = (data.get("search_query") or "").strip() or None
        metadata = data.get("metadata") or {}
        # Prefer the original search query as the stored rationale so the
        # "AI Requests" tab can show what the user was looking for.
        db_rationale = search_query or rationale

        if not tmdb_id:
            return jsonify({"status": "error", "message": "tmdb_id is required"}), 400
        if media_type not in ("movie", "tv"):
            return jsonify({"status": "error", "message": "media_type must be 'movie' or 'tv'"}), 400

        config = ConfigService.get_runtime_config()
        seer_url = (config.get("SEER_API_URL") or "").rstrip("/")
        seer_token = config.get("SEER_TOKEN", "")
        seer_session = config.get("SEER_SESSION_TOKEN", "")
        direct_arr = get_request_backend(config) == "arr"  # decided by the setting, never by leftover Seer credentials

        if not direct_arr and (not seer_url or not seer_token):
            return jsonify({
                "status": "error",
                "message": "Seer is not configured.",
            }), 400

        # Build the request payload (Seer-shaped; Radarr/Sonarr reuse the same fields)
        req_payload = {"mediaType": media_type, "mediaId": int(tmdb_id)}
        if media_type == "tv":
            num_seasons = config.get("FILTER_NUM_SEASONS", "all")
            first_season_only = config.get("REQUEST_FIRST_SEASON_ONLY", False)
            first_season_only = (
                first_season_only if isinstance(first_season_only, bool)
                else str(first_season_only).strip().lower() in {"1", "true", "yes", "on"}
            )
            if first_season_only:
                req_payload["seasons"] = [1]
            elif num_seasons in (None, "", "all", 0, "0"):
                req_payload["seasons"] = "all"
            else:
                req_payload["seasons"] = list(range(1, int(num_seasons) + 1))

        if direct_arr:
            # Parity with the Seer path: no anime classification here, default profiles only.
            service, url_key, token_key = next(
                ((name, u, t) for name, (u, t, served) in ARR_INSTANCES.items() if served == media_type), (None, None, None))
            profile = arr_default_profile(config, media_type)
            if not service or not config.get(url_key) or not config.get(token_key) or profile is None:
                return jsonify({
                    "status": "error",
                    "message": "Radarr/Sonarr is not configured for this media type.",
                }), 400
            req_payload.update(profileId=profile["profileId"], rootFolder=profile["rootFolder"],
                               tags=profile.get("tags") or [])
            try:
                async with ArrClient(service, config[url_key], config[token_key]) as arr:
                    await arr.add(req_payload)
            except Exception as exc:
                logger.error("%s request failed: %s", service.capitalize(), exc)
                return jsonify({"status": "error", "message": f"{service.capitalize()} could not add the title."}), 500
            db = DatabaseManager()
            media_dict = {key: metadata[key] for key in _METADATA_FIELDS if key in metadata}
            media_dict["id"] = str(tmdb_id)
            db.save_metadata(media_dict, media_type)
            db.save_request(media_type, str(tmdb_id), "ai_search", None, rationale=db_rationale)
            return jsonify({"status": "success", "message": "Request submitted successfully."}), 200

        # A stored Seer session can be valid but belong to a user without request
        # permission. Retry once with the configured technical API key in that case.
        auth_attempts = []
        if seer_session:
            auth_attempts.append(("session", {"connect.sid": seer_session}))
        auth_attempts.append(("API key", {}))

        url = f"{seer_url}/api/v1/request"
        for auth_name, cookies in auth_attempts:
            headers = {"Content-Type": "application/json", "accept": "application/json"}
            if auth_name == "API key":
                headers["X-Api-Key"] = seer_token

            async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
                async with session.post(url, json=req_payload, timeout=10) as response:
                    if response.status == 403 and auth_name == "session":
                        logger.warning("Seer session cannot submit requests; retrying with API key")
                        continue

                    if response.status in (200, 201, 202):
                        db = DatabaseManager()
                        # Persist metadata using data supplied by the frontend so the
                        # title and poster are stored correctly in the local DB.
                        # Only display fields, keyed to the requested id: the cache is shared by all users.
                        media_dict = {key: metadata[key] for key in _METADATA_FIELDS if key in metadata}
                        media_dict["id"] = str(tmdb_id)
                        db.save_metadata(media_dict, media_type)
                        # Tag with 'ai_search' source to keep these requests out of the
                        # "By Watched Content" view in the dashboard.
                        db.save_request(
                            media_type, str(tmdb_id), "ai_search", None, rationale=db_rationale
                        )
                        return jsonify({"status": "success", "message": "Request submitted successfully."}), 200

                    if response.status == 409:
                        return jsonify({
                            "status": "error",
                            "message": "Already requested or already available.",
                        }), 409

                    resp_text = await response.text()
                    logger.error(
                        "Seer request failed: status=%d, body=%s",
                        response.status, resp_text[:200],
                    )
                    return jsonify({
                        "status": "error",
                        "message": f"Seer returned status {response.status}.",
                    }), 500

    except Exception as exc:
        logger.error("Error during AI search request: %s", str(exc))
        return jsonify({"status": "error", "message": "Request failed. Check the logs for details."}), 500


@ai_search_bp.route("/status", methods=["GET"])
def ai_search_status():
    """Return whether the LLM is configured and AI search is available.

    Returns:
        JSON with 'available' bool and optional 'message'.
    """
    client = get_llm_client(_current_user_id())
    if client:
        return jsonify({"available": True}), 200
    return jsonify({
        "available": False,
        "message": (
            "LLM is not configured. "
            "Set OPENAI_API_KEY (and optionally OPENAI_BASE_URL) in Advanced settings."
        ),
    }), 200


def _feedback_scope(db):
    """``(user_id, media_user_id)`` that owns the caller's ratings, taken from the session.

    The media profile is never read from the request body: it comes from the caller's
    verified link, or is empty, so one user cannot rate on behalf of another profile.
    """
    user_id = _current_user_id()
    if user_id is None:
        return None
    provider = str(ConfigService.get_runtime_config().get("SELECTED_SERVICE") or "").lower()
    profile = _verified_media_profile(db, provider)
    return user_id, str(profile["external_user_id"]) if profile else ""


@ai_search_bp.route("/feedback", methods=["GET"])
def ai_search_feedback_list():
    """Return the caller's ratings (and legacy global likes/dislikes) so the page can show state."""
    try:
        db = DatabaseManager()
        scope = _feedback_scope(db)
        rows = {(r["media_type"], str(r["tmdb_id"])): {"feedback": _LEGACY_FEEDBACK[r["feedback"]]}
                for r in db.get_all_ai_feedback() if r["feedback"] in _LEGACY_FEEDBACK}
        for r in (db.list_media_feedback(*scope) if scope else []):
            rows[(r["media_type"], r["tmdb_id"])] = r
        return jsonify({"status": "success", "feedback": [
            {**row, "media_type": mt, "tmdb_id": tid} for (mt, tid), row in rows.items()]}), 200
    except Exception as exc:
        logger.error("Failed to list ai feedback: %s", exc)
        return jsonify({"status": "error", "message": "An internal error occurred"}), 500


@ai_search_bp.route("/feedback", methods=["POST"])
@limiter.limit("60 per minute")
def ai_search_feedback_set():
    """Record the caller's rating of an AI search result.

    Request body:
        tmdb_id (int|str): TMDB id.
        media_type (str): 'movie' or 'tv'.
        feedback (str): any value the Requests page offers (interested, not_interested,
            already_seen, seen_liked, seen_disliked, too_similar, save_for_later).
        reason_type (str, optional): genre, provider, content, title or other.
        title (str, optional)
        year (int, optional)
    """
    try:
        data = request.json or {}
        tmdb_id = data.get("tmdb_id")
        media_type = data.get("media_type")
        feedback = data.get("feedback")
        reason_type = data.get("reason_type")
        year = data.get("year")
        if year is not None:
            try:
                year = int(year)
            except (TypeError, ValueError):
                year = None
        if not tmdb_id:
            return jsonify({"status": "error", "message": "tmdb_id is required"}), 400
        if media_type not in ("movie", "tv"):
            return jsonify({"status": "error", "message": "media_type must be 'movie' or 'tv'"}), 400
        if feedback not in FEEDBACK_VALUES:
            return jsonify({"status": "error", "message": "Invalid feedback value"}), 400
        if reason_type is not None and reason_type not in FEEDBACK_REASONS:
            return jsonify({"status": "error", "message": "Invalid feedback reason"}), 400
        title = data.get("title")
        if title is not None and not isinstance(title, str):
            return jsonify({"status": "error", "message": "title must be a string"}), 400
        db = DatabaseManager()
        scope = _feedback_scope(db)
        if not scope:
            return jsonify({"status": "error", "message": "Sign in to rate results"}), 403
        saved = db.set_media_feedback(*scope, str(tmdb_id), media_type, feedback, reason_type, None, title, year)
        db.delete_ai_feedback(str(tmdb_id), media_type)  # the new rating replaces a legacy one
        return jsonify({"status": "success", "feedback": saved}), 200
    except Exception as exc:
        logger.error("Failed to set ai feedback: %s", exc)
        return jsonify({"status": "error", "message": "An internal error occurred"}), 500


@ai_search_bp.route("/feedback", methods=["DELETE"])
@limiter.limit("60 per minute")
def ai_search_feedback_delete():
    """Remove the caller's rating (and any legacy like/dislike) for a TMDB item."""
    try:
        data = request.json or {}
        tmdb_id = data.get("tmdb_id")
        media_type = data.get("media_type")
        if not tmdb_id or media_type not in ("movie", "tv"):
            return jsonify({"status": "error", "message": "tmdb_id and media_type required"}), 400
        db = DatabaseManager()
        scope = _feedback_scope(db)
        if scope:
            db.clear_media_feedback(*scope, str(tmdb_id), media_type)
        db.delete_ai_feedback(str(tmdb_id), media_type)
        return jsonify({"status": "success"}), 200
    except Exception as exc:
        logger.error("Failed to delete ai feedback: %s", exc)
        return jsonify({"status": "error", "message": "An internal error occurred"}), 500


@ai_search_bp.route("/seen", methods=["DELETE"])
@limiter.limit("30 per minute")
def ai_search_seen_clear():
    """Clear the already-recommended history (optionally per media_type)."""
    try:
        data = request.json or {}
        media_type = data.get("media_type")
        if media_type and media_type not in ("movie", "tv"):
            return jsonify({"status": "error", "message": "media_type must be 'movie' or 'tv'"}), 400
        deleted = DatabaseManager().clear_ai_seen(media_type)
        return jsonify({"status": "success", "deleted": deleted}), 200
    except Exception as exc:
        logger.error("Failed to clear ai seen: %s", exc)
        return jsonify({"status": "error", "message": "An internal error occurred"}), 500


@ai_search_bp.route("/history", methods=["GET"])
def ai_search_history_list():
    """Return the caller's recent AI searches, newest first."""
    user_id = _current_user_id()
    if user_id is None:
        return jsonify({"status": "success", "history": []}), 200
    try:
        return jsonify({"status": "success", "history": DatabaseManager().get_ai_search_history(user_id)}), 200
    except Exception as exc:
        logger.error("Failed to load AI search history: %s", exc)
        return jsonify({"status": "error", "message": "Could not load recent searches"}), 500


@ai_search_bp.route("/history", methods=["POST"])
@limiter.limit("10 per minute")
def ai_search_history_import():
    """Import searches kept in this browser before history moved to the server.

    Request body:
        queries (list[str]): Searches newest first; only the newest few are kept.
    """
    user_id = _current_user_id()
    queries = (request.get_json(silent=True) or {}).get("queries")
    if user_id is None:
        return jsonify({"status": "error", "message": "Sign in to save recent searches"}), 400
    if not isinstance(queries, list) or not all(isinstance(item, str) for item in queries):
        return jsonify({"status": "error", "message": "queries must be a list of strings"}), 400
    try:
        db = DatabaseManager()
        # Oldest first, so the newest ends on top.
        for query in reversed(queries[:db.AI_SEARCH_HISTORY_LIMIT]):
            db.add_ai_search_history(user_id, query)
        return jsonify({"status": "success", "history": db.get_ai_search_history(user_id)}), 200
    except Exception as exc:
        logger.error("Failed to import AI search history: %s", exc)
        return jsonify({"status": "error", "message": "Could not save recent searches"}), 500


@ai_search_bp.route("/history", methods=["DELETE"])
def ai_search_history_clear():
    """Forget the caller's recent AI searches."""
    user_id = _current_user_id()
    if user_id is None:
        return jsonify({"status": "success"}), 200
    try:
        DatabaseManager().clear_ai_search_history(user_id)
        return jsonify({"status": "success"}), 200
    except Exception as exc:
        logger.error("Failed to clear AI search history: %s", exc)
        return jsonify({"status": "error", "message": "Could not clear recent searches"}), 500
