from flask import Blueprint, request, jsonify
from api_service.services.jellyseer.seer_client import SeerClient
from api_service.config.logger_manager import LoggerManager

logger = LoggerManager().get_logger(__name__)
seer_bp = Blueprint('seer', __name__)

@seer_bp.route('/get_users', methods=['POST'])
async def get_users():
    """
    Fetch Jellyseer/Overseer users using the provided API key.
    """
    try:
        config_data = request.json
        api_url = config_data.get('SEER_API_URL')
        api_key = config_data.get('SEER_TOKEN')

        if not api_key:
            return jsonify({'message': 'API key is required', 'type': 'error'}), 400

        # Initialize JellyseerClient with the provided API key
        jellyseer_client = SeerClient(api_url=api_url, api_key=api_key)
        users = await jellyseer_client.get_all_users()

        if not users:
            return jsonify({'message': 'Failed to fetch users', 'type': 'error'}), 404

        return jsonify({'message': 'Users fetched successfully', 'users': users}), 200
    except Exception as e:
        logger.error(f'Error fetching Jellyseer/Overseer users: {str(e)}')
        return jsonify({'message': f'Error fetching users: {str(e)}', 'type': 'error'}), 500

@seer_bp.route('/login', methods=['POST'])
async def login_seer():
    """
    Endpoint to log in to Jellyseer/Overseer using the provided credentials.
    """
    try:
        config_data = request.json
        api_url = config_data.get('SEER_API_URL')
        api_key = config_data.get('SEER_TOKEN')
        username = config_data.get('SEER_USER_NAME')
        password = config_data.get('SEER_PASSWORD')

        if not username or not password:
            return jsonify({'message': 'Username and password are required', 'type': 'error'}), 400

        # Initialize the Jellyseer/Overseer client with the credentials provided
        jellyseer_client = SeerClient(
            api_url=api_url, api_key=api_key, seer_user_name=username, seer_password=password
        )

        # Perform the login
        await jellyseer_client.login()

        # Check if the login was successful by verifying the session token
        if jellyseer_client.session_token:
            return jsonify({'message': 'Login successful', 'type': 'success'}), 200
        else:
            return jsonify({'message': 'Login failed', 'type': 'error'}), 401

    except Exception as e:
        logger.error(f'An error occurred during login: {str(e)}')
        return jsonify({'message': 'An internal error has occurred', 'type': 'error'}), 500