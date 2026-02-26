import os
import uuid
from flask import Blueprint, request, jsonify
from api_service.services.plex.plex_auth import PlexAuth
from api_service.services.plex.plex_client import PlexClient
from api_service.config.logger_manager import LoggerManager
from api_service.utils.error_handling import handle_api_errors, validate_request_data, success_response
from api_service.utils.ssrf_guard import validate_url

logger = LoggerManager.get_logger("PlexRoute")
plex_bp = Blueprint('plex', __name__)
client_id = os.getenv('PLEX_CLIENT_ID', str(uuid.uuid4()))

@plex_bp.route('/libraries', methods=['POST'])
async def get_plex_libraries():
    """
    Fetch Plex libraries using the provided API key and server URL.
    """
    logger.info("Received request to fetch Plex libraries")
    try:
        config_data = request.json
        api_url = config_data.get('PLEX_API_URL')
        api_token = config_data.get('PLEX_TOKEN')

        if not api_url or not api_token:
            logger.warning("Missing API URL or token in Plex libraries request")
            return jsonify({'message': 'API URL and token are required', 'type': 'error'}), 400

        try:
            validate_url(api_url)
        except ValueError as exc:
            return jsonify({'message': str(exc), 'type': 'error'}), 400

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
    plex_auth = PlexAuth(client_id=client_id)
    pin_id, auth_url = plex_auth.get_authentication_pin()
    return jsonify({'pin_id': pin_id, 'auth_url': auth_url})

@plex_bp.route('/callback', methods=['POST'])
def check_plex_authentication():
    pin_id = request.json.get('pin_id')
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

        async with PlexClient(token=auth_token, client_id=os.getenv('PLEX_CLIENT_ID', str(uuid.uuid4()))) as plex_client:
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
        api_token = config_data.get('token')
        api_url = config_data.get('api_url')

        if not api_token or not api_url:
            logger.warning("Missing API token or URL in Plex connection test request")
            return jsonify({
                'message': 'API token and URL are required',
                'status': 'error'
            }), 400

        try:
            validate_url(api_url)
        except ValueError as exc:
            return jsonify({'message': str(exc), 'status': 'error'}), 400

        logger.debug(f"Testing connection to Plex server at: {api_url}")
        
        try:
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

@plex_bp.route('/users', methods=['GET', 'POST'])
async def get_plex_users():
    """
    Fetch Plex users using the provided API token.
    Accepts both GET and POST methods for flexibility.
    """
    try:
        # Handle both GET and POST request data
        if request.method == 'POST':
            config_data = request.json
            api_token = config_data.get('PLEX_TOKEN')
            api_url = config_data.get('PLEX_API_URL')
        else:  # GET method
            api_token = request.args.get('PLEX_TOKEN')
            api_url = request.args.get('PLEX_API_URL')

        if not api_token:
            return jsonify({'message': 'API token is required', 'type': 'error'}), 400

        if api_url:
            try:
                validate_url(api_url)
            except ValueError as exc:
                return jsonify({'message': str(exc), 'type': 'error'}), 400

        async with PlexClient(token=api_token, client_id=client_id, api_url=api_url) as plex_client:
            users = await plex_client.get_all_users()

            if not users:
                return jsonify({'message': 'No users found', 'type': 'error'}), 404

            return jsonify({'message': 'Users fetched successfully', 'users': users}), 200
    except Exception as e:
        logger.error(f'Error fetching Plex users: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error fetching Plex users', 'type': 'error'}), 500