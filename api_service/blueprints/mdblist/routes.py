"""Validate MDBList credentials without exposing provider responses or keys."""
from flask import Blueprint, jsonify, request

from api_service.auth.limiter import limiter
from api_service.auth.middleware import require_role
from api_service.config.logger_manager import LoggerManager
from api_service.services.config_service import ConfigService
from api_service.services.mdblist.mdblist_client import MDBListClient
from api_service.services.public_lists import PublicListError
from api_service.utils.asyncio_loop import run_coroutine_sync

mdblist_bp = Blueprint('mdblist', __name__)
logger = LoggerManager.get_logger('MDBListRoute')


@mdblist_bp.route('/test', methods=['POST'])
@require_role('admin')
@limiter.limit('10 per minute')
def test_mdblist_connection():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'status': 'error', 'message': 'MDBList API key is required.'}), 400
    key = data.get('api_key')
    if key == '***':
        key = ConfigService.get_runtime_config().get('MDBLIST_API_KEY')
    if not isinstance(key, str) or not key.strip() or key.strip() == '***':
        return jsonify({'status': 'error', 'message': 'MDBList API key is required.'}), 400
    try:
        async def check():
            async with MDBListClient(key.strip()) as client:
                await client.test_connection()
        run_coroutine_sync(check(), logger)
        return jsonify({'status': 'success', 'message': 'MDBList connection verified.'}), 200
    except PublicListError:
        return jsonify({'status': 'error', 'message': 'Could not connect to MDBList. Check your API key and try again.'}), 400
    except Exception:
        logger.error('MDBList connection test failed.')
        return jsonify({'status': 'error', 'message': 'Could not test the MDBList connection.'}), 502
