from flask import Blueprint, request, jsonify
from api_service.services.jellyfin.jellyfin_client import JellyfinClient
from api_service.config.logger_manager import LoggerManager

logger = LoggerManager().get_logger("JellyfinRoute")
jellyfin_bp = Blueprint('jellyfin', __name__)

@jellyfin_bp.route('/libraries', methods=['POST'])
async def get_jellyfin_library():
    """
    Fetch Jellyfin libraries using the provided API key and server URL.
    """
    try:
        config_data = request.json
        api_url = config_data.get('JELLYFIN_API_URL')
        api_key = config_data.get('JELLYFIN_TOKEN')

        jellyfin_client = JellyfinClient(api_url=api_url, token=api_key)

        libraries = await jellyfin_client.get_libraries()

        if libraries:
            return jsonify({'message': 'Libraries fetched successfully', 'items': libraries}), 200
        return jsonify({'message': 'No library found', 'type': 'error'}), 404
    except Exception as e:
        logger.error(f'Error fetching Jellyfin libraries: {str(e)}')
        return jsonify({'message': f'Error fetching Jellyfin libraries: {str(e)}', 'type': 'error'}), 500

@jellyfin_bp.route('/users', methods=['POST'])
async def get_jellyfin_users():
    """
    Fetch Jellyfin users using the provided API key and server URL.
    """
    try:
        config_data = request.json
        api_url = config_data.get('JELLYFIN_API_URL')
        api_key = config_data.get('JELLYFIN_TOKEN')
        
        jellyfin_client = JellyfinClient(api_url=api_url, token=api_key)
        
        users = await jellyfin_client.get_all_users()
        if users:
            return jsonify({'message': 'Users fetched successfully', 'users': users}), 200
        return jsonify({'message': 'No users found', 'type': 'error'}), 404
    except Exception as e:
        logger.error(f'Error fetching Jellyfin users: {str(e)}')  