"""
Health check blueprint.

Exposes two probes:
  GET /api/health/live   — liveness: is the process alive?
  GET /api/health/ready  — readiness: are all dependencies reachable?
  GET /api/health        — alias for /ready
"""
import asyncio
import aiohttp
from flask import Blueprint, jsonify

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager

logger = LoggerManager.get_logger("HealthRoute")
health_bp = Blueprint('health', __name__)
health_bp.strict_slashes = False

_OK = "ok"
_ERROR = "error"
_NOT_CONFIGURED = "not_configured"


@health_bp.route('/live', methods=['GET'])
def liveness():
    """
    Liveness probe — confirms the process is running.

    Always returns HTTP 200 as long as the application is up.
    Does not check external dependencies.
    """
    return jsonify({"status": _OK}), 200


@health_bp.route('/ready', methods=['GET'])
@health_bp.route('', methods=['GET'])
def readiness():
    """
    Readiness probe — checks that all configured services are reachable.

    Critical services (DB, TMDB) drive the HTTP status code:
      - 200 if all critical checks pass
      - 503 if any critical service is unreachable

    Optional services (Seer, LLM) are always reported but never cause a 503.

    Returns:
        JSON with keys: status, db, tmdb, seer, llm.
        Each value is one of: "ok", "error", "not_configured".
    """
    config = load_env_vars()

    db_status = _check_db()
    tmdb_status, seer_status = _run_async_checks(config)
    llm_status = _check_llm()

    overall = _OK if db_status == _OK and tmdb_status == _OK else _ERROR

    return jsonify({
        "status": overall,
        "db": db_status,
        "tmdb": tmdb_status,
        "seer": seer_status,
        "llm": llm_status,
    }), 200 if overall == _OK else 503


# ---------------------------------------------------------------------------
# Synchronous helpers
# ---------------------------------------------------------------------------

def _check_db() -> str:
    """
    Check database connectivity with a minimal query.

    Returns:
        "ok" if the DB is reachable, "error" otherwise.
    """
    try:
        from api_service.db.database_manager import DatabaseManager
        db = DatabaseManager()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return _OK
    except Exception as e:
        logger.error("Health DB check failed: %s", e)
        return _ERROR


def _check_llm() -> str:
    """
    Report LLM availability by inspecting the configured client.

    Returns:
        "ok" if an LLM client is configured, "not_configured" if no key/URL
        is set, "error" on unexpected failures.
    """
    try:
        from api_service.services.llm.llm_service import get_llm_client
        client = get_llm_client()
        return _OK if client is not None else _NOT_CONFIGURED
    except Exception as e:
        logger.error("Health LLM check failed: %s", e)
        return _ERROR


def _run_async_checks(config: dict) -> tuple:
    """
    Run TMDB and Seer checks concurrently in a new event loop.

    Args:
        config: Application config dict from load_env_vars().

    Returns:
        Tuple of (tmdb_status, seer_status).
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_gather_async_checks(config))
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

async def _gather_async_checks(config: dict) -> tuple:
    """Run TMDB and Seer checks in parallel."""
    tmdb_key = config.get("TMDB_API_KEY") or ""
    seer_url = config.get("SEER_API_URL") or ""
    seer_key = config.get("SEER_TOKEN") or ""
    return await asyncio.gather(
        _check_tmdb(tmdb_key),
        _check_seer(seer_url, seer_key),
    )


async def _check_tmdb(api_key: str) -> str:
    """
    Ping the TMDB API with the configured key.

    Args:
        api_key: TMDB API key.

    Returns:
        "ok", "error", or "not_configured".
    """
    if not api_key:
        return _NOT_CONFIGURED
    try:
        url = f"https://api.themoviedb.org/3/movie/popular?api_key={api_key}&page=1"
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                return _OK if resp.status == 200 else _ERROR
    except Exception as e:
        logger.error("Health TMDB check failed: %s", e)
        return _ERROR


async def _check_seer(api_url: str, api_key: str) -> str:
    """
    Ping the Seer /api/v1/status endpoint.

    Args:
        api_url: Base URL for Jellyseer/Overseer.
        api_key: Seer API key.

    Returns:
        "ok", "error", or "not_configured".
    """
    if not api_url or not api_key:
        return _NOT_CONFIGURED
    try:
        url = f"{api_url.rstrip('/')}/api/v1/status"
        headers = {"X-Api-Key": api_key, "accept": "application/json"}
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                return _OK if resp.status == 200 else _ERROR
    except Exception as e:
        logger.error("Health Seer check failed: %s", e)
        return _ERROR
