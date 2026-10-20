"""Authenticated recap data and administrator support reminders."""
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from api_service.auth.middleware import require_role
from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.db.recap_repository import RecapRepository
from api_service.db.year_recap_repository import YearRecapRepository
from api_service.services.year_recap import RecapWatchSync, YearWatchActivity
from api_service.utils.asyncio_loop import run_coroutine_sync
from api_service.auth.limiter import limiter

recap_bp = Blueprint('recap', __name__)
logger = LoggerManager.get_logger('RecapRoute')


@recap_bp.route('/year', methods=['GET'])
@require_role('admin', 'user')
@limiter.limit('10 per minute')
def get_year_recap():
    year = request.args.get('year', str(datetime.now(timezone.utc).year))
    scope = request.args.get('scope', 'personal')
    if (set(request.args) - {'year', 'scope', 'include_playback'} or len(year) != 4
            or not year.isascii() or not year.isdecimal()
            or not 2000 <= int(year) <= datetime.now(timezone.utc).year
            or scope not in ('personal', 'server')
            or request.args.get('include_playback', 'false') not in ('true', 'false')
            or any(len(request.args.getlist(key)) != 1 for key in request.args)):
        return jsonify({'status': 'error', 'message': 'Provide a valid year and recap scope'}), 400
    try:
        db, env = DatabaseManager(), load_env_vars()
        repo = YearRecapRepository(db)
        if request.args.get('include_playback') == 'true':
            # The hit rate reads the ledger, so refresh it first; a failed sync leaves it as it was.
            try:
                run_coroutine_sync(RecapWatchSync().sync(repo, g.current_user, env), logger)
            except Exception:
                logger.warning('Recap watch sync skipped before the annual recap', exc_info=True)
        data = repo.summary(g.current_user, env, int(year), scope)
        if request.args.get('include_playback') == 'true':
            profiles = db.get_user_media_profiles(int(g.current_user['id'])) if scope == 'personal' else []
            data.update(run_coroutine_sync(YearWatchActivity().load(data, profiles, env), logger))
        return jsonify({'status': 'success', 'data': data})
    except PermissionError:
        return jsonify({'status': 'error', 'message': 'Server recap is unavailable for this account'}), 403
    except Exception:
        logger.error('Unable to load annual recap', exc_info=True)
        return jsonify({'status': 'error', 'message': 'Unable to load your annual recap'}), 500


@recap_bp.route('', methods=['GET'])
@require_role('admin', 'user')
def get_recap():
    try:
        data = RecapRepository(DatabaseManager()).summary(
            g.current_user, load_env_vars(), include_posters=request.args.get('include_posters') == 'true')
        return jsonify({'status': 'success', 'data': data})
    except Exception:
        logger.error('Unable to load recap', exc_info=True)
        return jsonify({'status': 'error', 'message': 'Unable to load your recap'}), 500


@recap_bp.route('/watch-sync', methods=['POST'])
@require_role('admin', 'user')
@limiter.limit('20 per hour')
def sync_watch_activity():
    """Link recorded requests to plays on the media server, for the hit rate and watch badges."""
    try:
        result = run_coroutine_sync(RecapWatchSync().sync(RecapRepository(DatabaseManager()), g.current_user,
                                                          load_env_vars()), logger)
        return jsonify({'status': 'success', 'data': result})
    except Exception:
        logger.error('Unable to sync recap watch activity', exc_info=True)
        return jsonify({'status': 'error', 'message': 'Unable to check watch activity'}), 500


@recap_bp.route('/prompt', methods=['POST'])
@require_role('admin')
def claim_prompt():
    try:
        prompt = RecapRepository(DatabaseManager()).claim_prompt(g.current_user, load_env_vars())
        return jsonify({'status': 'success', 'data': {'prompt': prompt}})
    except Exception:
        logger.error('Unable to check recap reminder', exc_info=True)
        return jsonify({'status': 'error', 'message': 'Unable to check support reminder'}), 500


@recap_bp.route('/preferences', methods=['PATCH'])
@require_role('admin')
def update_preferences():
    body = request.get_json(silent=True)
    if (not isinstance(body, dict) or set(body) != {'action'}
            or body['action'] not in ('enable', 'disable', 'supported', 'dismiss', 'remind_later')):
        return jsonify({'status': 'error', 'message': 'Provide a valid reminder action'}), 400
    try:
        preferences = RecapRepository(DatabaseManager()).update_preferences(
            g.current_user, load_env_vars(), body['action'])
        return jsonify({'status': 'success', 'data': preferences})
    except Exception:
        logger.error('Unable to save recap preferences', exc_info=True)
        return jsonify({'status': 'error', 'message': 'Unable to save reminder preferences'}), 500
