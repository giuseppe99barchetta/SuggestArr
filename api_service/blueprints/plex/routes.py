import os
import uuid
from flask import Blueprint, request, jsonify
from services.plex.plex_auth import PlexAuth
from services.plex.plex_client import PlexClient
from config.logger_manager import LoggerManager

logger = LoggerManager().get_logger(__name__)
plex_bp = Blueprint('plex', __name__)
client_id = os.getenv('PLEX_CLIENT_ID', str(uuid.uuid4()))
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
        # Verifica se il token è valido
        # Salva il token e autentica l'utente nella tua app
        return jsonify({'message': 'Login success', 'auth_token': auth_token})
    else:
        return jsonify({'error': 'Invalid token'}), 401
    
@plex_bp.route('/check-auth/<int:pin_id>', methods=['GET'])
def check_plex_auth(pin_id):
    """Verifica se il login su Plex è stato completato e ottieni il token."""
    plex_auth = PlexAuth(client_id=client_id)
    auth_token = plex_auth.check_authentication(pin_id)
    
    if auth_token:
        return jsonify({'auth_token': auth_token})
    else:
        return jsonify({'auth_token': None}), 200
    
@plex_bp.route('/servers', methods=['POST'])
async def get_plex_servers_async_route():
    """
    Route asincrona per ottenere i server Plex disponibili usando un auth_token.
    """
    try:
        auth_token = request.json.get('auth_token')

        if not auth_token:
            return jsonify({'message': 'Auth token is required', 'type': 'error'}), 400

        plex_client = PlexClient(token=auth_token, client_id=os.getenv('PLEX_CLIENT_ID', str(uuid.uuid4())))
        servers = await plex_client.get_servers()

        if servers:
            return jsonify({'message': 'Plex servers fetched successfully', 'servers': servers}), 200
        else:
            return jsonify({'message': 'Failed to fetch Plex servers', 'type': 'error'}), 404

    except Exception as e:
        print(f"Errore durante il recupero dei server Plex: {str(e)}")
        return jsonify({'message': f'Error fetching Plex servers: {str(e)}', 'type': 'error'}), 500