"""
AI Search blueprint — semantic movie/TV search powered by LLM + TMDB.
"""

import asyncio

import aiohttp
from flask import Blueprint, jsonify, request

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.ai_search.ai_search_service import AiSearchService
from api_service.services.llm.llm_service import get_llm_client

ai_search_bp = Blueprint("ai_search", __name__)
logger = LoggerManager.get_logger("AiSearchRoute")


@ai_search_bp.route("/query", methods=["POST"])
async def ai_search_query():
    """Execute an AI-powered semantic search.

    Request body:
        query (str): Natural language description of desired content.
        media_type (str): 'movie', 'tv', or 'both'. Defaults to 'movie'.
        user_ids (list): Optional list of media-server user IDs to scope history.
        max_results (int): Maximum results to return (default 12).

    Returns:
        JSON response with 'results', 'query_interpretation', and 'total'.
    """
    try:
        data = request.json or {}
        query = (data.get("query") or "").strip()
        if not query:
            return jsonify({"status": "error", "message": "query is required"}), 400

        media_type = data.get("media_type", "movie")
        if media_type not in ("movie", "tv", "both"):
            media_type = "movie"

        user_ids = data.get("user_ids") or []
        max_results = int(data.get("max_results") or 12)
        use_history = data.get("use_history", True)
        if not isinstance(use_history, bool):
            use_history = True
        exclude_watched = data.get("exclude_watched", True)
        if not isinstance(exclude_watched, bool):
            exclude_watched = True

        # Check LLM is configured (not strictly required — service degrades gracefully,
        # but we surface a clear error before attempting if completely unconfigured)
        if not get_llm_client():
            return jsonify({
                "status": "error",
                "message": (
                    "LLM is not configured. "
                    "Please set OPENAI_API_KEY (and optionally OPENAI_BASE_URL) "
                    "in the Advanced settings."
                ),
            }), 400

        service = AiSearchService()
        result = await service.search(
            query=query,
            media_type=media_type,
            user_ids=user_ids if user_ids else None,
            max_results=max_results,
            use_history=use_history,
            exclude_watched=exclude_watched,
        )

        return jsonify({
            "status": "success",
            "results": result.get("results", []),
            "query_interpretation": result.get("query_interpretation", {}),
            "total": result.get("total", 0),
        }), 200

    except Exception as exc:
        logger.error("Error during AI search query: %s", str(exc))
        return jsonify({"status": "error", "message": f"Search failed: {str(exc)}"}), 500


@ai_search_bp.route("/request", methods=["POST"])
async def ai_search_request():
    """Request a media item via Jellyseer/Overseer.

    Calls the Jellyseer API directly so the local database entry is saved with
    ``tmdb_source_id = 'ai_search'`` (allowing proper separation from
    watched-content recommendations) and with full item metadata so the title
    is stored correctly.

    Request body:
        tmdb_id (int): TMDB ID of the item to request.
        media_type (str): 'movie' or 'tv'.
        rationale (str): Optional AI rationale to attach to the request record.
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
        metadata = data.get("metadata") or {}

        if not tmdb_id:
            return jsonify({"status": "error", "message": "tmdb_id is required"}), 400
        if media_type not in ("movie", "tv"):
            return jsonify({"status": "error", "message": "media_type must be 'movie' or 'tv'"}), 400

        config = load_env_vars()
        seer_url = (config.get("SEER_API_URL") or "").rstrip("/")
        seer_token = config.get("SEER_TOKEN", "")
        seer_session = config.get("SEER_SESSION_TOKEN", "")

        if not seer_url or not seer_token:
            return jsonify({
                "status": "error",
                "message": "Jellyseer/Overseer is not configured.",
            }), 400

        # Build Jellyseer request payload
        req_payload = {"mediaType": media_type, "mediaId": int(tmdb_id)}
        if media_type == "tv":
            num_seasons = config.get("FILTER_NUM_SEASONS", "all")
            req_payload["tvdbId"] = int(tmdb_id)
            req_payload["seasons"] = (
                "all" if str(num_seasons) == "all"
                else list(range(1, int(num_seasons) + 1))
            )

        # Auth: prefer session cookie, fall back to API key (mirrors SeerClient behaviour)
        headers = {"Content-Type": "application/json", "accept": "application/json"}
        cookies = {}
        if seer_session:
            cookies["connect.sid"] = seer_session
        else:
            headers["X-Api-Key"] = seer_token

        async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
            url = f"{seer_url}/api/v1/request"
            async with session.post(url, json=req_payload, timeout=10) as response:
                if response.status in (200, 201, 202):
                    db = DatabaseManager()
                    # Persist metadata using data supplied by the frontend so the
                    # title and poster are stored correctly in the local DB.
                    media_dict = {"id": str(tmdb_id)}
                    media_dict.update(metadata)
                    db.save_metadata(media_dict, media_type)
                    # Tag with 'ai_search' source to keep these requests out of the
                    # "By Watched Content" view in the dashboard.
                    db.save_request(
                        media_type, str(tmdb_id), "ai_search", None, rationale=rationale
                    )
                    return jsonify({"status": "success", "message": "Request submitted successfully."}), 200

                if response.status == 409:
                    return jsonify({
                        "status": "error",
                        "message": "Already requested or already available.",
                    }), 409

                resp_text = await response.text()
                logger.error(
                    "Jellyseer request failed: status=%d, body=%s",
                    response.status, resp_text[:200],
                )
                return jsonify({
                    "status": "error",
                    "message": f"Jellyseer returned status {response.status}.",
                }), 500

    except Exception as exc:
        logger.error("Error during AI search request: %s", str(exc))
        return jsonify({"status": "error", "message": f"Request failed: {str(exc)}"}), 500


@ai_search_bp.route("/status", methods=["GET"])
def ai_search_status():
    """Return whether the LLM is configured and AI search is available.

    Returns:
        JSON with 'available' bool and optional 'message'.
    """
    client = get_llm_client()
    if client:
        return jsonify({"available": True}), 200
    return jsonify({
        "available": False,
        "message": (
            "LLM is not configured. "
            "Set OPENAI_API_KEY (and optionally OPENAI_BASE_URL) in Advanced settings."
        ),
    }), 200
