"""Validate Radarr/Sonarr credentials and list their options without exposing keys."""
from flask import Blueprint, jsonify, request

from api_service.auth.limiter import limiter
from api_service.auth.middleware import require_role
from api_service.config.logger_manager import LoggerManager
from api_service.services.arr.arr_client import SERVICES, ArrClient
from api_service.services.config_service import ConfigService
from api_service.services.integration_security import select_credentials
from api_service.utils.asyncio_loop import run_coroutine_sync

arr_bp = Blueprint('arr', __name__)
logger = LoggerManager.get_logger('ArrRoute')


def _credentials():
    """Return ``(service, url, key)`` from the request, or ``(error response, None, None)``.

    The body is ``{service}`` (use the saved credentials) or a complete explicit
    ``{<S>_API_URL, <S>_TOKEN}`` tuple, never a mixture.
    """
    data = request.get_json(silent=True)
    service = data.get('service') if isinstance(data, dict) else None
    if service not in SERVICES:
        return (jsonify({'status': 'error', 'message': 'Unknown service.'}), 400), None, None
    name = service.capitalize()
    keys = (f'{service.upper()}_API_URL', f'{service.upper()}_TOKEN')

    def load_saved():
        config = ConfigService.get_runtime_config()
        return tuple(config.get(key) or '' for key in keys)

    try:
        api_url, api_key = select_credentials(data, keys, load_saved)
        if not api_url or not api_key:
            raise ValueError('missing')
    except ValueError:
        return (jsonify({'status': 'error', 'message': f'{name} URL and API key are required.'}), 400), None, None
    return service, api_url, api_key


def _call(action, success_payload):
    """Run ``action(client)`` against the requested instance and shape the JSON answer."""
    service, api_url, api_key = _credentials()
    if api_url is None:
        return service  # the error response
    name = service.capitalize()
    result = {}

    async def run():
        async with ArrClient(service, api_url, api_key) as client:
            result['value'] = await action(client)

    try:
        run_coroutine_sync(run(), logger)
    except Exception:
        logger.error('%s request failed.', name)
        return jsonify({'status': 'error', 'message': f'Could not connect to {name}. Check the URL and API key.'}), 400
    return jsonify(success_payload(name, result.get('value'))), 200


@arr_bp.route('/test', methods=['POST'])
@require_role('admin')
@limiter.limit('10 per minute')
def test_arr_connection():
    return _call(lambda client: client.test_connection(),
                 lambda name, _: {'status': 'success', 'message': f'{name} connection verified.'})


@arr_bp.route('/options', methods=['POST'])
@require_role('admin')
@limiter.limit('20 per minute')
def arr_options():
    """Quality profiles, root folders and tags of an instance (ids and names only)."""
    return _call(lambda client: client.get_options(),
                 lambda name, options: {'status': 'success', **options})
