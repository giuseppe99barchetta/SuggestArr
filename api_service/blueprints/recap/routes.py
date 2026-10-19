"""Authenticated recap data and administrator support reminders."""
from flask import Blueprint, g, jsonify, request

from api_service.auth.middleware import require_role
from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.db.recap_repository import RecapRepository

recap_bp = Blueprint('recap', __name__)
logger = LoggerManager.get_logger('RecapRoute')


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
