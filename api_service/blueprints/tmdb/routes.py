import time
from flask import Blueprint, request, jsonify
import aiohttp
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager

tmdb_bp = Blueprint('tmdb', __name__)
logger = LoggerManager.get_logger("TMDBRoute")

TMDB_BASE_URL = "https://api.themoviedb.org/3"

# ── In-memory cache ───────────────────────────────────────────────────────────
_cache: dict = {}
_POPULAR_TTL = 300   # 5 minutes — popular results change often
_STATIC_TTL  = 600   # 10 minutes — genres / languages / regions / providers


def _cache_get(key: str, ttl: int):
    """Return cached value if it exists and has not expired, else None."""
    entry = _cache.get(key)
    if entry and time.time() - entry[1] < ttl:
        return entry[0]
    return None


def _cache_set(key: str, data) -> None:
    """Store data in the cache together with the current timestamp."""
    _cache[key] = (data, time.time())


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_api_key() -> str | None:
    """
    Load the TMDB API key from the integrations table.

    Returns:
        The api_key string, or None if TMDB is not configured.
    """
    integration = DatabaseManager().get_integration('tmdb')
    if not integration:
        return None
    return integration.get('api_key') or None


def _not_configured():
    """Standard 400 response when TMDB is not yet configured."""
    return jsonify({'message': 'TMDB is not configured', 'status': 'error'}), 400


async def _fetch_tmdb(path: str, api_key: str, params: dict | None = None):
    """
    Perform a GET request against the TMDB API.

    Args:
        path:    TMDB API path (e.g. '/movie/popular').
        api_key: TMDB API key to include as a query parameter.
        params:  Additional query parameters (without api_key).

    Returns:
        Tuple (data, http_status). data is None on non-200 responses.
    """
    qs = {'api_key': api_key}
    if params:
        qs.update(params)

    url = f"{TMDB_BASE_URL}{path}"
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, params=qs) as resp:
            if resp.status == 200:
                return await resp.json(), 200
            return None, resp.status


def _run(coro):
    """Run an async coroutine synchronously via the shared event-loop helper."""
    from api_service.blueprints.jobs.routes import run_async
    return run_async(coro)


# ── Routes ────────────────────────────────────────────────────────────────────

@tmdb_bp.route('/test', methods=['POST'])
def test_tmdb_connection():
    """
    Test a TMDB API key provided in the request body (key not yet saved to DB).

    The key is sent in the POST body, never in the URL, and is not logged.
    The backend calls TMDB on behalf of the client — the key is not exposed
    to the browser.

    Request body:
        { "api_key": "<key>" }

    Returns:
        200 with { status: 'success', message, data } on success.
        400 with { status: 'error', message } on failure.
    """
    try:
        data = request.json
        if not data or 'api_key' not in data:
            return jsonify({'message': 'TMDB API key is required', 'status': 'error'}), 400

        api_key = data['api_key']

        async def _test():
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(
                        f"{TMDB_BASE_URL}/movie/popular",
                        params={'api_key': api_key, 'page': 1},
                    ) as resp:
                        if resp.status == 200:
                            body = await resp.json()
                            return {
                                'status': 'success',
                                'message': 'TMDB API connection successful!',
                                'data': {
                                    'total_results': body.get('total_results', 0),
                                    'total_pages':   body.get('total_pages', 0),
                                },
                            }
                        if resp.status == 401:
                            return {'status': 'error', 'message': 'Invalid TMDB API key'}
                        return {'status': 'error', 'message': f'TMDB API returned status {resp.status}'}
            except aiohttp.ClientTimeout:
                return {'status': 'error', 'message': 'Connection to TMDB API timed out'}
            except aiohttp.ClientError as exc:
                logger.error("TMDB connection error: %s", exc)
                return {'status': 'error', 'message': 'Failed to connect to TMDB API'}
            except Exception as exc:
                logger.error("TMDB unexpected error: %s", exc, exc_info=True)
                return {'status': 'error', 'message': 'An unexpected error occurred'}

        result = _run(_test())
        return (jsonify(result), 200) if result['status'] == 'success' else (jsonify(result), 400)

    except Exception as exc:
        logger.error("Error testing TMDB connection: %s", exc, exc_info=True)
        return jsonify({'message': 'Error testing TMDB connection', 'status': 'error'}), 500


@tmdb_bp.route('/popular', methods=['GET'])
def get_popular_movies():
    """
    Proxy GET /movie/popular from TMDB.

    Loads the API key from the database — it is never sent to the client.
    Results are cached for 5 minutes per (page, include_adult) combination.

    Query params:
        page          (int, default 1)
        include_adult (str, default 'false')

    Returns:
        200 with { status, results: [{id, title, backdrop_path}], page, total_pages }
        400 if TMDB is not configured.
        502 if TMDB upstream returns an error.
    """
    page          = request.args.get('page', 1, type=int)
    include_adult = request.args.get('include_adult', 'false')
    cache_key     = f'popular:{page}:{include_adult}'

    cached = _cache_get(cache_key, _POPULAR_TTL)
    if cached is not None:
        return jsonify(cached), 200

    api_key = _get_api_key()
    if not api_key:
        return _not_configured()

    try:
        data, status = _run(
            _fetch_tmdb('/movie/popular', api_key, {'page': page, 'include_adult': include_adult})
        )
        if status != 200:
            return jsonify({'message': f'TMDB returned {status}', 'status': 'error'}), 502

        # Only pass fields the frontend needs; never include the api_key.
        safe_results = [
            {
                'id':            m.get('id'),
                'title':         m.get('title'),
                'backdrop_path': m.get('backdrop_path'),
            }
            for m in data.get('results', [])
            if m.get('backdrop_path')
        ]
        payload = {
            'status':      'success',
            'results':     safe_results,
            'page':        data.get('page', page),
            'total_pages': data.get('total_pages', 1),
        }
        _cache_set(cache_key, payload)
        return jsonify(payload), 200

    except Exception as exc:
        logger.error("Error fetching popular movies: %s", exc, exc_info=True)
        return jsonify({'message': 'Error fetching popular movies', 'status': 'error'}), 500


@tmdb_bp.route('/genres/movie', methods=['GET'])
def get_movie_genres():
    """
    Proxy GET /genre/movie/list from TMDB.

    API key is loaded from the database. Cached for 10 minutes.

    Returns:
        200 with { status, genres: [...] }
        400 if TMDB is not configured.
        502 if TMDB upstream returns an error.
    """
    cache_key = 'genres:movie'
    cached = _cache_get(cache_key, _STATIC_TTL)
    if cached is not None:
        return jsonify(cached), 200

    api_key = _get_api_key()
    if not api_key:
        return _not_configured()

    try:
        data, status = _run(_fetch_tmdb('/genre/movie/list', api_key, {'language': 'en-US'}))
        if status != 200:
            return jsonify({'message': f'TMDB returned {status}', 'status': 'error'}), 502

        payload = {'status': 'success', 'genres': data.get('genres', [])}
        _cache_set(cache_key, payload)
        return jsonify(payload), 200

    except Exception as exc:
        logger.error("Error fetching movie genres: %s", exc, exc_info=True)
        return jsonify({'message': 'Error fetching movie genres', 'status': 'error'}), 500


@tmdb_bp.route('/genres/tv', methods=['GET'])
def get_tv_genres():
    """
    Proxy GET /genre/tv/list from TMDB.

    API key is loaded from the database. Cached for 10 minutes.

    Returns:
        200 with { status, genres: [...] }
        400 if TMDB is not configured.
        502 if TMDB upstream returns an error.
    """
    cache_key = 'genres:tv'
    cached = _cache_get(cache_key, _STATIC_TTL)
    if cached is not None:
        return jsonify(cached), 200

    api_key = _get_api_key()
    if not api_key:
        return _not_configured()

    try:
        data, status = _run(_fetch_tmdb('/genre/tv/list', api_key, {'language': 'en-US'}))
        if status != 200:
            return jsonify({'message': f'TMDB returned {status}', 'status': 'error'}), 502

        payload = {'status': 'success', 'genres': data.get('genres', [])}
        _cache_set(cache_key, payload)
        return jsonify(payload), 200

    except Exception as exc:
        logger.error("Error fetching TV genres: %s", exc, exc_info=True)
        return jsonify({'message': 'Error fetching TV genres', 'status': 'error'}), 500


@tmdb_bp.route('/languages', methods=['GET'])
def get_languages():
    """
    Proxy GET /configuration/languages from TMDB.

    API key is loaded from the database. Cached for 10 minutes.

    Returns:
        200 with { status, languages: [...] }
        400 if TMDB is not configured.
        502 if TMDB upstream returns an error.
    """
    cache_key = 'languages'
    cached = _cache_get(cache_key, _STATIC_TTL)
    if cached is not None:
        return jsonify(cached), 200

    api_key = _get_api_key()
    if not api_key:
        return _not_configured()

    try:
        data, status = _run(_fetch_tmdb('/configuration/languages', api_key))
        if status != 200:
            return jsonify({'message': f'TMDB returned {status}', 'status': 'error'}), 502

        # TMDB returns a raw array for this endpoint
        payload = {'status': 'success', 'languages': data if isinstance(data, list) else []}
        _cache_set(cache_key, payload)
        return jsonify(payload), 200

    except Exception as exc:
        logger.error("Error fetching languages: %s", exc, exc_info=True)
        return jsonify({'message': 'Error fetching languages', 'status': 'error'}), 500


@tmdb_bp.route('/providers/regions', methods=['GET'])
def get_provider_regions():
    """
    Proxy GET /watch/providers/regions from TMDB.

    API key is loaded from the database. Cached for 10 minutes.

    Returns:
        200 with { status, results: [...] }
        400 if TMDB is not configured.
        502 if TMDB upstream returns an error.
    """
    cache_key = 'providers:regions'
    cached = _cache_get(cache_key, _STATIC_TTL)
    if cached is not None:
        return jsonify(cached), 200

    api_key = _get_api_key()
    if not api_key:
        return _not_configured()

    try:
        data, status = _run(_fetch_tmdb('/watch/providers/regions', api_key))
        if status != 200:
            return jsonify({'message': f'TMDB returned {status}', 'status': 'error'}), 502

        payload = {'status': 'success', 'results': data.get('results', [])}
        _cache_set(cache_key, payload)
        return jsonify(payload), 200

    except Exception as exc:
        logger.error("Error fetching provider regions: %s", exc, exc_info=True)
        return jsonify({'message': 'Error fetching provider regions', 'status': 'error'}), 500


@tmdb_bp.route('/providers/movie', methods=['GET'])
def get_movie_providers():
    """
    Proxy GET /watch/providers/movie from TMDB filtered by region.

    API key is loaded from the database. Cached for 10 minutes per region.

    Query params:
        watch_region (str, required) — ISO 3166-1 region code (e.g. 'US').

    Returns:
        200 with { status, results: [...] }
        400 if watch_region is missing or TMDB is not configured.
        502 if TMDB upstream returns an error.
    """
    watch_region = request.args.get('watch_region')
    if not watch_region:
        return jsonify({'message': 'watch_region is required', 'status': 'error'}), 400

    cache_key = f'providers:movie:{watch_region}'
    cached = _cache_get(cache_key, _STATIC_TTL)
    if cached is not None:
        return jsonify(cached), 200

    api_key = _get_api_key()
    if not api_key:
        return _not_configured()

    try:
        data, status = _run(
            _fetch_tmdb('/watch/providers/movie', api_key, {'watch_region': watch_region})
        )
        if status != 200:
            return jsonify({'message': f'TMDB returned {status}', 'status': 'error'}), 502

        payload = {'status': 'success', 'results': data.get('results', [])}
        _cache_set(cache_key, payload)
        return jsonify(payload), 200

    except Exception as exc:
        logger.error("Error fetching movie providers: %s", exc, exc_info=True)
        return jsonify({'message': 'Error fetching movie providers', 'status': 'error'}), 500
