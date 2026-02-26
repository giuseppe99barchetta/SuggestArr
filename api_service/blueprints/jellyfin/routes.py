from flask import Blueprint, request, jsonify
from api_service.services.jellyfin.jellyfin_client import JellyfinClient
from api_service.config.logger_manager import LoggerManager
from api_service.config.config import load_env_vars
from api_service.utils.ssrf_guard import validate_url

logger = LoggerManager.get_logger("JellyfinRoute")
jellyfin_bp = Blueprint('jellyfin', __name__)

@jellyfin_bp.route('/libraries', methods=['POST'])
async def get_jellyfin_library():
    """
    Fetch Jellyfin libraries using the provided API key and server URL.
    """
    logger.info("Received request to fetch Jellyfin libraries")
    try:
        config_data = request.json
        api_url = config_data.get('JELLYFIN_API_URL')
        api_key = config_data.get('JELLYFIN_TOKEN')

        if not api_url or not api_key:
            logger.warning("Missing API URL or token in Jellyfin libraries request")
            return jsonify({'message': 'API URL and token are required', 'type': 'error'}), 400

        try:
            validate_url(api_url)
        except ValueError as exc:
            return jsonify({'message': str(exc), 'type': 'error'}), 400

        logger.debug(f"Connecting to Jellyfin server at: {api_url}")
        async with JellyfinClient(api_url=api_url, token=api_key) as jellyfin_client:
            libraries = await jellyfin_client.get_libraries()
            logger.debug(f"Retrieved {len(libraries) if libraries else 0} libraries from Jellyfin")

            if libraries:
                logger.info(f"Successfully fetched {len(libraries)} libraries from Jellyfin server")
                return jsonify({'message': 'Libraries fetched successfully', 'items': libraries}), 200
            else:
                logger.warning("No libraries found on Jellyfin server")
                return jsonify({'message': 'No library found', 'type': 'error'}), 404
    except Exception as e:
        logger.error(f'Error fetching Jellyfin libraries: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error fetching Jellyfin libraries', 'type': 'error'}), 500

@jellyfin_bp.route('/test', methods=['POST'])
async def test_jellyfin_connection():
    """
    Test Jellyfin server connection using the provided API key and URL.
    """
    logger.info("Received request to test Jellyfin connection")
    try:
        config_data = request.json
        api_url = config_data.get('api_url')
        api_key = config_data.get('token')

        if not api_key or not api_url:
            logger.warning("Missing API key or URL in Jellyfin connection test request")
            return jsonify({
                'message': 'API key and URL are required',
                'status': 'error'
            }), 400

        try:
            validate_url(api_url)
        except ValueError as exc:
            return jsonify({'message': str(exc), 'status': 'error'}), 400

        logger.debug(f"Testing connection to Jellyfin server at: {api_url}")
        
        try:
            async with JellyfinClient(api_url=api_url, token=api_key) as jellyfin_client:
                # Try to get libraries as a connection test
                libraries = await jellyfin_client.get_libraries()
                logger.debug(f"Connection test response: {type(libraries)} - {len(libraries) if libraries else 0} libraries")

                # Check if we got a valid response with actual libraries data
                if libraries and isinstance(libraries, list):
                    logger.info(f"Jellyfin connection test successful - found {len(libraries)} libraries")
                    return jsonify({
                        'message': 'Jellyfin connection successful!',
                        'status': 'success',
                        'data': {
                            'libraries_count': len(libraries),
                            'server_url': api_url
                        }
                    }), 200
                else:
                    # None or invalid response means connection failed
                    logger.warning(f"Jellyfin connection test failed - invalid response from server")
                    return jsonify({
                        'message': 'Failed to connect to Jellyfin server - invalid token or server unreachable',
                        'status': 'error'
                    }), 400

        except Exception as conn_error:
            logger.error(f'Jellyfin connection test failed: {str(conn_error)}', exc_info=True)
            return jsonify({
                'message': 'Jellyfin connection failed',
                'status': 'error'
            }), 400

    except Exception as e:
        logger.error(f'Error testing Jellyfin connection: {str(e)}', exc_info=True)
        return jsonify({
            'message': 'Error testing Jellyfin connection',
            'status': 'error'
        }), 500

@jellyfin_bp.route('/users', methods=['POST', 'GET'])
async def get_jellyfin_users():
    """
    Fetch Jellyfin users using the provided API key and server URL.
    """
    try:
        if request.method == 'POST':
            config_data = request.json
            api_url = config_data.get('JELLYFIN_API_URL')
            api_key = config_data.get('JELLYFIN_TOKEN')
        else:
            # For GET requests, use saved configuration
            env_vars = load_env_vars()
            api_url = env_vars.get('JELLYFIN_API_URL')
            api_key = env_vars.get('JELLYFIN_TOKEN')

        if not api_url or not api_key:
            logger.warning("Missing API URL or token in Jellyfin users request")
            return jsonify({'message': 'API URL and token are required', 'type': 'error'}), 400

        try:
            validate_url(api_url)
        except ValueError as exc:
            return jsonify({'message': str(exc), 'type': 'error'}), 400

        async with JellyfinClient(api_url=api_url, token=api_key) as jellyfin_client:
            users = await jellyfin_client.get_all_users()
            if users:
                return jsonify({'message': 'Users fetched successfully', 'users': users}), 200
            return jsonify({'message': 'No users found', 'type': 'error'}), 404
    except Exception as e:
        logger.error(f'Error fetching Jellyfin users: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error fetching Jellyfin users', 'type': 'error'}), 500