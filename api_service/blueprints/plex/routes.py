import os
from flask import Blueprint, request, jsonify, g
from api_service.services.plex.plex_auth import PlexAuth
from api_service.services.plex.plex_client import PlexClient
from api_service.config.logger_manager import LoggerManager
from api_service.utils.error_handling import handle_api_errors, validate_request_data, success_response
from api_service.utils.ssrf_guard import validate_url
from api_service.services.config_service import ConfigService
from api_service.services.config_secrets import REDACTED

logger = LoggerManager.get_logger("PlexRoute")
plex_bp = Blueprint('plex', __name__)


def _same_plex_url(left, right):
    """Compare two Plex base URLs, ignoring case of scheme/host and a trailing slash."""
    def norm(url):
        return str(url or '').strip().rstrip('/').lower()
    return bool(norm(left)) and norm(left) == norm(right)


def _resolve_plex_token(token, api_url):
    """
    Swap the redacted-secret sentinel for the stored Plex token, but only safely.

    The settings UI sends '***' for a secret it did not change, and that value can
    reach these routes from a form loaded before the save. Sent to Plex as-is it is
    simply an invalid token (HTTP 401). The stored token is used instead only for an
    admin, and only towards the configured Plex server: these routes take the URL
    from the caller, so resolving the sentinel for anyone, or for any URL, would let
    a caller send the saved token to a host of their choosing.

    :param token: Token from the request body.
    :param api_url: Plex URL from the request body.
    :return: The token to use with Plex, or None when the sentinel cannot be resolved.
    """
    if token != REDACTED:
        return token
    if (getattr(g, 'current_user', None) or {}).get('role') != 'admin':
        return None
    config = ConfigService.get_runtime_config()
    if not _same_plex_url(api_url, config.get('PLEX_API_URL')):
        return None
    return config.get('PLEX_TOKEN') or None


@plex_bp.route('/libraries', methods=['POST'])
async def get_plex_libraries():
    """
    Fetch Plex libraries using the provided API key and server URL.
    """
    logger.info("Received request to fetch Plex libraries")
    try:
        config_data = request.json
        api_url = config_data.get('PLEX_API_URL')
        api_token = _resolve_plex_token(config_data.get('PLEX_TOKEN'), api_url)

        if not api_url or not api_token:
            logger.warning("Missing API URL or token in Plex libraries request")
            return jsonify({'message': 'API URL and token are required', 'type': 'error'}), 400

        try:
            validate_url(api_url, allow_private=True)
        except ValueError as exc:
            logger.warning("Invalid API URL provided for Plex libraries request", exc_info=True)
            return jsonify({'message': 'Invalid API URL', 'type': 'error'}), 400

        logger.debug(f"Connecting to Plex server at: {api_url}")
        async with PlexClient(api_url=api_url, token=api_token) as plex_client:
            libraries = await plex_client.get_libraries()

            if not libraries:
                logger.warning("No libraries found on Plex server")
                return jsonify({'message': 'No library found', 'type': 'error'}), 404

        logger.info(f"Successfully fetched {len(libraries)} libraries from Plex server")
        return jsonify({'message': 'Libraries fetched successfully', 'items': libraries}), 200
    except Exception as e:
        logger.error(f'Error fetching Plex libraries: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error fetching Plex libraries', 'type': 'error'}), 500
    
    

@plex_bp.route('/auth', methods=['POST'])
def plex_login():
    client_id = ConfigService.get_runtime_config().get('PLEX_CLIENT_ID')
    plex_auth = PlexAuth(client_id=client_id)
    pin_id, auth_url = plex_auth.get_authentication_pin()
    return jsonify({'pin_id': pin_id, 'auth_url': auth_url})

@plex_bp.route('/callback', methods=['POST'])
def check_plex_authentication():
    pin_id = request.json.get('pin_id')
    client_id = ConfigService.get_runtime_config().get('PLEX_CLIENT_ID')
    plex_auth = PlexAuth(client_id=client_id)
    
    auth_token = plex_auth.check_authentication(pin_id)
    
    if auth_token:
        return jsonify({'auth_token': auth_token})
    else:
        return jsonify({'error': 'Authentication failed'}), 401
    
@plex_bp.route('/api/v1/auth/plex', methods=['POST'])
def login_with_plex():
    auth_token = request.json.get('authToken')
    
    if auth_token:
        return jsonify({'message': 'Login success', 'auth_token': auth_token})
    else:
        return jsonify({'error': 'Invalid token'}), 401
    
@plex_bp.route('/check-auth/<int:pin_id>', methods=['GET'])
def check_plex_auth(pin_id):
    """Check if Plex login has been completed and get the token."""
    client_id = ConfigService.get_runtime_config().get('PLEX_CLIENT_ID')
    plex_auth = PlexAuth(client_id=client_id)
    auth_token = plex_auth.check_authentication(pin_id)
    
    if auth_token:
        return jsonify({'auth_token': auth_token})
    else:
        return jsonify({'auth_token': None}), 200
    
@plex_bp.route('/servers', methods=['POST'])
async def get_plex_servers_async_route():
    """
    Find all available Plex servers.
    """
    try:
        auth_token = request.json.get('auth_token')

        if not auth_token:
            return jsonify({'message': 'Auth token is required', 'type': 'error'}), 400

        client_id = ConfigService.get_runtime_config().get('PLEX_CLIENT_ID')
        async with PlexClient(token=auth_token, client_id=client_id) as plex_client:
            servers = await plex_client.get_servers()

            if servers:
                return jsonify({'message': 'Plex servers fetched successfully', 'servers': servers}), 200
            else:
                return jsonify({'message': 'Failed to fetch Plex servers', 'type': 'error'}), 404

    except Exception as e:
        logger.error(f"Error fetching Plex servers: {str(e)}", exc_info=True)
        return jsonify({'message': 'Error fetching Plex servers', 'type': 'error'}), 500
    
@plex_bp.route('/test', methods=['POST'])
async def test_plex_connection():
    """
    Test Plex server connection using the provided API token and URL.
    """
    logger.info("Received request to test Plex connection")
    try:
        config_data = request.json
        api_url = config_data.get('api_url')
        api_token = _resolve_plex_token(config_data.get('token'), api_url)

        if not api_token or not api_url:
            logger.warning("Missing API token or URL in Plex connection test request")
            return jsonify({
                'message': 'API token and URL are required',
                'status': 'error'
            }), 400

        try:
            validate_url(api_url, allow_private=True)
        except ValueError as exc:
            return jsonify({'message': str(exc), 'status': 'error'}), 400

        logger.debug(f"Testing connection to Plex server at: {api_url}")
        
        try:
            client_id = ConfigService.get_runtime_config().get('PLEX_CLIENT_ID')
            async with PlexClient(token=api_token, client_id=client_id, api_url=api_url) as plex_client:
                # Try to get server information or libraries as a connection test
                libraries = await plex_client.get_libraries()
                logger.debug(f"Connection test response: {type(libraries)} - {len(libraries) if libraries else 0} libraries")

                # Check if we got a valid response with actual libraries data
                if libraries and isinstance(libraries, list):
                    logger.info(f"Plex connection test successful - found {len(libraries)} libraries")
                    return jsonify({
                        'message': 'Plex connection successful!',
                        'status': 'success',
                        'data': {
                            'libraries_count': len(libraries),
                            'server_url': api_url
                        }
                    }), 200
                else:
                    # None or invalid response means connection failed
                    logger.warning(f"Plex connection test failed - invalid response from server")
                    return jsonify({
                        'message': 'Failed to connect to Plex server - invalid token or server unreachable',
                        'status': 'error'
                    }), 400

        except Exception as conn_error:
            logger.error(f'Plex connection test failed: {str(conn_error)}', exc_info=True)
            return jsonify({
                'message': 'Plex connection failed',
                'status': 'error'
            }), 400

    except Exception as e:
        logger.error(f'Error testing Plex connection: {str(e)}', exc_info=True)
        return jsonify({
            'message': 'Error testing Plex connection',
            'status': 'error'
        }), 500

@plex_bp.route('/users', methods=['POST'])
async def get_plex_users():
    """
    Fetch Plex users using the provided API token.
    """
    try:
        config_data = request.get_json(silent=True) or {}
        api_url = config_data.get('PLEX_API_URL')
        api_token = _resolve_plex_token(config_data.get('PLEX_TOKEN'), api_url)

        if not api_token:
            return jsonify({'message': 'API token is required', 'type': 'error'}), 400

        if api_url:
            try:
                validate_url(api_url, allow_private=True)
            except ValueError as exc:
                return jsonify({'message': str(exc), 'type': 'error'}), 400

        client_id = ConfigService.get_runtime_config().get('PLEX_CLIENT_ID')
        async with PlexClient(token=api_token, client_id=client_id, api_url=api_url) as plex_client:
            users = await plex_client.get_all_users()

            if not users:
                return jsonify({'message': 'No users found', 'type': 'error'}), 404

            return jsonify({'message': 'Users fetched successfully', 'users': users}), 200
    except Exception as e:
        logger.error(f'Error fetching Plex users: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error fetching Plex users', 'type': 'error'}), 500
