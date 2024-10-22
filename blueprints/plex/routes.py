from flask import Blueprint, request, jsonify
from plex.plex_client import PlexClient
from config.logger_manager import LoggerManager

logger = LoggerManager().get_logger(__name__)
plex_bp = Blueprint('plex', __name__)

@plex_bp.route('/libraries', methods=['POST'])
async def get_plex_libraries():
    """
    Fetch Plex libraries using the provided API key and server URL.
    """
    try:
        config_data = request.json
        api_url = config_data.get('PLEX_API_URL')
        api_token = config_data.get('PLEX_TOKEN')

        if not api_url or not api_token:
            return jsonify({'message': 'API URL and token are required', 'type': 'error'}), 400

        plex_client = PlexClient(api_url=api_url, token=api_token)
        libraries = await plex_client.get_libraries()

        if not libraries:
            return jsonify({'message': 'No library found', 'type': 'error'}), 404

        return jsonify({'message': 'Libraries fetched successfully', 'items': libraries}), 200
    except Exception as e:
        logger.error(f'Error fetching Plex libraries: {str(e)}')
        return jsonify({'message': f'Error fetching Plex libraries: {str(e)}', 'type': 'error'}), 500
