import time
from urllib.parse import urlsplit

from flask import Blueprint, request, jsonify, g
import aiohttp
from api_service.services.seer.seer_client import SeerClient
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.utils.ssrf_guard import validate_base_url as validate_url
from api_service.auth.middleware import require_role
from api_service.services.integration_security import select_credentials, public_arr_servers
from api_service.services.http.guarded_session import GuardedSession

logger = LoggerManager().get_logger("SeerRoute")
seer_bp = Blueprint('seer', __name__)

# Seer's browser address rarely changes; asked again at most once an hour.
_WEB_URL_TTL = 3600
_web_url_cache = {'url': None, 'at': 0.0}


@seer_bp.before_request
def check_integration_access():
    if request.method == 'GET' and request.endpoint in ('seer.get_radarr_servers', 'seer.get_sonarr_servers',
                                                      'seer.get_seer_web_url'):
        if not getattr(g, 'current_user', None):
            return jsonify({'error': 'Authentication required'}), 401
        if request.args or request.get_data():
            return jsonify({'message': 'GET consultations do not accept overrides', 'type': 'error'}), 400
        return None
    return require_role('admin')(lambda: None)()


def _request_credentials(data):
    return select_credentials(data, ('SEER_API_URL', 'SEER_TOKEN'), _load_seer_config,
                              optional=('SEER_SESSION_TOKEN',))


def _load_seer_config():
    """
    Load Seer credentials from the integrations table.

    Returns:
        tuple: (api_url, api_key, session_token) — strings, may be empty/None.
    """
    config = DatabaseManager().get_integration('seer')
    if config is None:
        return '', '', None
    return (
        config.get('api_url', ''),
        config.get('api_key', ''),
        config.get('session_token'),
    )


@seer_bp.route('/get_users', methods=['GET', 'POST'])
async def get_users():
    """
    Fetch Seer users using the globally configured API key and URL,
    or credentials provided in the request body (e.g. during initial setup).
    """
    try:
        config_data = request.get_json(silent=True) or {}
        try:
            api_url, api_key, session_token = _request_credentials(config_data)
        except ValueError:
            return jsonify({'message': 'A complete explicit URL and token are required', 'type': 'error'}), 400

        if not api_key or not api_url:
            return jsonify({'message': 'Seer API URL and token are not configured', 'type': 'error'}), 400

        try:
            validate_url(api_url, allow_private=True)
        except ValueError as exc:
            return jsonify({'message': str(exc), 'type': 'error'}), 400

        async with SeerClient(api_url=api_url, api_key=api_key, session_token=session_token) as seer_client:
            users = await seer_client.get_all_users()

            if not users:
                return jsonify({'message': 'Failed to fetch users', 'type': 'error'}), 404

            return jsonify({'message': 'Users fetched successfully', 'users': users}), 200
    except Exception as e:
        logger.error(f'Error fetching Seer service users: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error fetching users', 'type': 'error'}), 500


async def _simple_seer_http_test(api_url, api_key):
    """
    Simple HTTP test to verify Seer API accessibility.
    Returns (success: bool, message: str, data: dict)
    """
    try:
        test_url = f"{api_url.rstrip('/')}/api/v1/status"
        headers = {
            'Content-Type': 'application/json',
            'accept': 'application/json',
            'X-Api-Key': api_key
        }

        timeout = aiohttp.ClientTimeout(total=10)
        async with GuardedSession(timeout=timeout, private_urls=(api_url,), allowed_urls=(api_url,)) as session:
            async with session.get(test_url, headers=headers) as response:
                if response.status == 200:
                    return True, "HTTP connection successful", {"http_status": 200}
                elif response.status == 401:
                    return False, "Invalid API key", {"http_status": 401}
                elif response.status == 404:
                    test_url2 = f"{api_url.rstrip('/')}/api/v1/settings"
                    async with session.get(test_url2, headers=headers) as response2:
                        if response2.status == 200:
                            return True, "HTTP connection successful", {"http_status": 200}
                        elif response2.status == 401:
                            return False, "Invalid API key", {"http_status": 401}
                        else:
                            return False, f"API endpoint not found (HTTP {response2.status})", {"http_status": response2.status}
                else:
                    return False, f"HTTP error {response.status}", {"http_status": response.status}

    except TimeoutError:
        return False, "Connection timeout", {}
    except aiohttp.ClientError as e:
        logger.error("Seer HTTP connection error: %s", e)
        return False, "Connection error", {}
    except Exception as e:
        logger.error("Seer HTTP unexpected error: %s", e, exc_info=True)
        return False, "Unexpected error occurred", {}


@seer_bp.route('/test', methods=['GET', 'POST'])
async def test_seer_connection():
    """
    Test Seer API connection using the globally configured API key and URL.
    """
    try:
        config_data = request.get_json(silent=True) or {}
        try:
            api_url, api_key, session_token = _request_credentials(config_data)
        except ValueError:
            return jsonify({'message': 'A complete explicit URL and token are required', 'type': 'error'}), 400

        if not api_key or not api_url:
            return jsonify({
                'message': 'Seer API URL and token are not configured',
                'status': 'error'
            }), 400

        try:
            validate_url(api_url, allow_private=True)
        except ValueError as exc:
            return jsonify({'message': str(exc), 'status': 'error'}), 400

        http_success, http_message, http_data = await _simple_seer_http_test(api_url, api_key)

        if not http_success:
            return jsonify({
                'message': f'HTTP test failed: {http_message}',
                'status': 'error'
            }), 400

        try:
            async with SeerClient(api_url=api_url, api_key=api_key, session_token=session_token) as seer_client:
                users = await seer_client.get_all_users()

                if users and isinstance(users, list) and len(users) > 0:
                    return jsonify({
                        'message': 'Seer connection successful!',
                        'status': 'success',
                        'data': {
                            'users_count': len(users),
                            'server_url': api_url,
                            **http_data
                        }
                    }), 200
                elif users and isinstance(users, list):
                    return jsonify({
                        'message': 'Seer connection successful but no users found',
                        'status': 'success',
                        'data': {
                            'users_count': 0,
                            'server_url': api_url,
                            **http_data
                        }
                    }), 200
                else:
                    return jsonify({
                        'message': 'HTTP connection successful but API authentication failed',
                        'status': 'error',
                        'data': http_data
                    }), 400

        except Exception as client_error:
            logger.error(f'Seer service client test failed: {str(client_error)}', exc_info=True)
            return jsonify({
                'message': 'HTTP connection successful but client test failed',
                'status': 'error',
                'data': http_data
            }), 400

    except Exception as e:
        logger.error(f'Error testing Seer service connection: {str(e)}', exc_info=True)
        return jsonify({
            'message': 'Error testing Seer connection',
            'status': 'error'
        }), 500


@seer_bp.route('/login', methods=['POST'])
async def login_seer():
    """
    Endpoint to log in to Seer using the provided credentials.
    Credentials are supplied in the request body (this is the Seer login flow, not SuggestArr auth).
    """
    try:
        config_data = request.json
        api_url = config_data.get('SEER_API_URL')
        api_key = config_data.get('SEER_TOKEN')
        username = config_data.get('SEER_USER_NAME')
        password = config_data.get('SEER_PASSWORD')

        if not username or not password or not api_url:
            return jsonify({'message': 'Username, password and URL are required', 'type': 'error'}), 400

        try:
            validate_url(api_url, allow_private=True)
        except ValueError as exc:
            return jsonify({'message': str(exc), 'type': 'error'}), 400

        async with SeerClient(
            api_url=api_url, api_key=api_key, seer_user_name=username, seer_password=password
        ) as seer_client:

            await seer_client.login()

            if seer_client.session_token:
                return jsonify({
                    'message': 'Login successful',
                    'type': 'success',
                    'session_token': seer_client.session_token
                }), 200
            else:
                return jsonify({'message': 'Login failed', 'type': 'error'}), 401

    except Exception as e:
        logger.error(f'An error occurred during login: {str(e)}')
        return jsonify({'message': 'An internal error has occurred', 'type': 'error'}), 500


@seer_bp.route('/radarr-servers', methods=['GET', 'POST'])
async def get_radarr_servers():
    """
    Fetch available Radarr servers from Seer using the globally configured credentials.
    Returns servers with their quality profiles, root folders, and tags.
    """
    try:
        config_data = request.get_json(silent=True) or {}
        try:
            api_url, api_key, session_token = _request_credentials(config_data)
        except ValueError:
            return jsonify({'message': 'A complete explicit URL and token are required', 'type': 'error'}), 400

        if not api_key or not api_url:
            return jsonify({'message': 'Seer API URL and token are not configured', 'type': 'error'}), 400

        try:
            validate_url(api_url, allow_private=True)
        except ValueError as exc:
            return jsonify({'message': str(exc), 'type': 'error'}), 400

        async with SeerClient(api_url=api_url, api_key=api_key, session_token=session_token) as seer_client:
            servers = await seer_client.get_radarr_servers()
            return jsonify({'servers': public_arr_servers(servers)}), 200
    except Exception as e:
        logger.error(f'Error fetching Radarr servers: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error fetching Radarr servers', 'type': 'error'}), 500


@seer_bp.route('/sonarr-servers', methods=['GET', 'POST'])
async def get_sonarr_servers():
    """
    Fetch available Sonarr servers from Seer using the globally configured credentials.
    Returns servers with their quality profiles, root folders, and tags.
    """
    try:
        config_data = request.get_json(silent=True) or {}
        try:
            api_url, api_key, session_token = _request_credentials(config_data)
        except ValueError:
            return jsonify({'message': 'A complete explicit URL and token are required', 'type': 'error'}), 400

        if not api_key or not api_url:
            return jsonify({'message': 'Seer API URL and token are not configured', 'type': 'error'}), 400

        try:
            validate_url(api_url, allow_private=True)
        except ValueError as exc:
            logger.warning(f'Invalid Seer API URL configuration: {exc}', exc_info=True)
            return jsonify({'message': 'Seer API URL is invalid or not allowed', 'type': 'error'}), 400

        async with SeerClient(api_url=api_url, api_key=api_key, session_token=session_token) as seer_client:
            servers = await seer_client.get_sonarr_servers()
            return jsonify({'servers': public_arr_servers(servers)}), 200
    except Exception as e:
        logger.error(f'Error fetching Sonarr servers: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error fetching Sonarr servers', 'type': 'error'}), 500


@seer_bp.route('/web-url', methods=['GET'])
async def get_seer_web_url():
    """
    Address to open Seer in the browser, for "Open in Seer" links.

    Prefers the Application URL set in Seer, since the configured API URL is often an
    internal Docker address the browser cannot reach; falls back to that API URL.

    Returns:
        200 with { url } — url is None when Seer is not configured.
    """
    if _web_url_cache['url'] and time.time() - _web_url_cache['at'] < _WEB_URL_TTL:
        return jsonify({'url': _web_url_cache['url']}), 200
    api_url, api_key, session_token = _load_seer_config()
    if not api_url or urlsplit(api_url).scheme.lower() not in ('http', 'https'):
        return jsonify({'url': None}), 200
    url = None
    try:
        async with SeerClient(api_url=api_url, api_key=api_key, session_token=session_token) as seer_client:
            url = await seer_client.get_application_url()
    except Exception as exc:
        logger.warning("Could not read Seer's application URL: %s", exc)
    url = url or api_url.rstrip('/')
    _web_url_cache.update(url=url, at=time.time())
    return jsonify({'url': url}), 200
