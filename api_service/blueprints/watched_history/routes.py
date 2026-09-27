import asyncio
import csv
import io

from flask import Blueprint, g, jsonify, request

from api_service.auth.limiter import limiter
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.config_service import ConfigService
from api_service.services.tmdb.tmdb_client import TMDbClient
from api_service.utils.asyncio_loop import run_coroutine_sync


watched_history_bp = Blueprint('watched_history', __name__)
logger = LoggerManager.get_logger('WatchedHistoryRoute')
CSV_COLUMNS = ('tmdb_id', 'media_type', 'title', 'year', 'rating')
MAX_IMPORT_ROWS = 1000
MAX_IMPORT_BYTES = 2 * 1024 * 1024


def _provider() -> str:
    return str(ConfigService.get_runtime_config().get('SELECTED_SERVICE') or '').lower()


def _identity_for_current_user(db: DatabaseManager):
    provider = _provider()
    if provider not in {'jellyfin', 'emby', 'plex'}:
        return None
    user_id = int(g.current_user['id'])
    for profile in db.get_user_media_profiles(user_id):
        if profile.get('provider') == provider:
            return db.upsert_media_user_identity(
                provider, str(profile['external_user_id']), profile.get('external_username'),
            )
    return None


def _missing_profile():
    return jsonify({'status': 'error', 'message': 'Link your media server account first'}), 404


def _validate_csv_row(row: dict) -> dict:
    if not isinstance(row, dict):
        raise ValueError('Invalid CSV row')
    normalized = {str(key or '').strip(): (value or '').strip() for key, value in row.items()}
    if not any(normalized.values()):
        return {}
    missing = [column for column in ('tmdb_id', 'media_type', 'title') if not normalized.get(column)]
    if missing:
        raise ValueError(f"Missing required value: {', '.join(missing)}")
    return normalized


@watched_history_bp.route('/me', methods=['GET'])
def list_my_watched_media():
    db = DatabaseManager()
    identity = _identity_for_current_user(db)
    if not identity:
        return _missing_profile()
    return jsonify({'status': 'success', 'items': db.list_watched_media(identity['id'])}), 200


@watched_history_bp.route('/me', methods=['POST'])
@limiter.limit('30 per minute')
def add_my_watched_media():
    db = DatabaseManager()
    identity = _identity_for_current_user(db)
    if not identity:
        return _missing_profile()
    payload = request.get_json(silent=True) or {}
    try:
        item = db.upsert_watched_media(
            identity['id'], payload.get('tmdb_id'), payload.get('media_type'), payload.get('title'),
            payload.get('year'), payload.get('rating'), source='manual',
        )
    except ValueError as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 400
    return jsonify({'status': 'success', 'item': item}), 201


@watched_history_bp.route('/me/<int:item_id>', methods=['DELETE'])
def delete_my_watched_media(item_id: int):
    db = DatabaseManager()
    identity = _identity_for_current_user(db)
    if not identity:
        return _missing_profile()
    if not db.delete_watched_media(identity['id'], item_id):
        return jsonify({'status': 'error', 'message': 'Watched title not found'}), 404
    return jsonify({'status': 'success'}), 200


@watched_history_bp.route('/me/import', methods=['POST'])
@limiter.limit('5 per minute')
def import_my_watched_media():
    db = DatabaseManager()
    identity = _identity_for_current_user(db)
    if not identity:
        return _missing_profile()
    upload = request.files.get('file')
    if not upload or not upload.filename:
        return jsonify({'status': 'error', 'message': 'A CSV file is required'}), 400
    raw = upload.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        return jsonify({'status': 'error', 'message': 'CSV file exceeds the 2 MB limit'}), 400
    try:
        rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    except (UnicodeDecodeError, csv.Error):
        return jsonify({'status': 'error', 'message': 'CSV must be valid UTF-8 text'}), 400
    if not rows:
        return jsonify({'status': 'error', 'message': 'CSV contains no rows'}), 400
    if len(rows) > MAX_IMPORT_ROWS:
        return jsonify({'status': 'error', 'message': f'CSV can contain at most {MAX_IMPORT_ROWS} rows'}), 400
    headers = tuple(rows[0].keys()) if rows[0] else ()
    if set(CSV_COLUMNS) - set(headers):
        return jsonify({
            'status': 'error',
            'message': 'CSV headers must be: tmdb_id, media_type, title, year, rating',
        }), 400

    imported, errors = 0, []
    for number, row in enumerate(rows, start=2):
        try:
            item = _validate_csv_row(row)
            if not item:
                continue
            db.upsert_watched_media(
                identity['id'], item['tmdb_id'], item['media_type'], item['title'],
                item.get('year'), item.get('rating'), source='csv_import',
            )
            imported += 1
        except ValueError as exc:
            errors.append({'row': number, 'message': str(exc)})
    return jsonify({
        'status': 'success', 'imported': imported, 'errors': errors,
        'message': f'Imported {imported} watched title(s)',
    }), 200


async def _search_tmdb(query: str, media_type: str):
    config = ConfigService.get_runtime_config()
    integrations = config.get('integrations') if isinstance(config.get('integrations'), dict) else {}
    tmdb_config = integrations.get('tmdb') if isinstance(integrations.get('tmdb'), dict) else {}
    api_key = config.get('TMDB_API_KEY') or tmdb_config.get('api_key')
    if not api_key:
        return None
    client = TMDbClient(api_key, 10, 0, 0, True, 0, [], [], None, [])
    async with client:
        functions = []
        if media_type in {'movie', 'both'}:
            functions.append(client.search_movie(query))
        if media_type in {'tv', 'both'}:
            functions.append(client.search_tv(query))
        results = []
        for group in await asyncio.gather(*functions):
            results.extend(group or [])
        return [{
            'tmdb_id': str(item.get('id')), 'media_type': item.get('media_type'),
            'title': item.get('title') or item.get('name'),
            'year': str(item.get('release_date') or item.get('first_air_date') or '')[:4] or None,
        } for item in results if item.get('id') and (item.get('title') or item.get('name'))]


@watched_history_bp.route('/me/search', methods=['GET'])
@limiter.limit('20 per minute')
def search_watched_media():
    query = str(request.args.get('query') or '').strip()
    media_type = str(request.args.get('media_type') or 'both').lower()
    if len(query) < 2:
        return jsonify({'status': 'error', 'message': 'Search term must be at least 2 characters'}), 400
    if media_type not in {'movie', 'tv', 'both'}:
        return jsonify({'status': 'error', 'message': "media_type must be 'movie', 'tv', or 'both'"}), 400
    try:
        results = run_coroutine_sync(_search_tmdb(query, media_type), logger)
    except Exception as exc:
        logger.warning('Watch-history TMDb search failed: %s', exc)
        return jsonify({'status': 'error', 'message': 'TMDb search failed'}), 502
    if results is None:
        return jsonify({'status': 'error', 'message': 'TMDb is not configured'}), 400
    return jsonify({'status': 'success', 'results': results[:20]}), 200
