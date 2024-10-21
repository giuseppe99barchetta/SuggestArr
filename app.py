"""
Main Flask application for managing environment variables and running processes.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from asgiref.wsgi import WsgiToAsgi

from jellyfin.jellyfin_client import JellyfinClient
from jellyseer.jellyseer_client import JellyseerClient
from utils.utils import AppUtils
from config.config import load_env_vars, save_env_vars
from config.logger_manager import LoggerManager
from tasks.tasks import run_content_automation_task

executor = ThreadPoolExecutor(max_workers=3)
logger = LoggerManager().get_logger(__name__)

# App Factory Pattern for modularity and testability
def create_app():
    """
    Create and configure the Flask application.
    """

    if AppUtils.is_last_worker():
        AppUtils.print_welcome_message() # Print only for last worker

    application = Flask(__name__, static_folder='static', static_url_path='/')
    CORS(application)

    # Register routes
    register_routes(application)

    # Load environment variables at startup
    AppUtils.load_environment()

    return application

def register_routes(app): # pylint: disable=redefined-outer-name
    """
    Register the application routes.
    """

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        """
        Serve the built frontend's index.html or any other static file.
        """
        fullpath = os.path.normpath(os.path.join(app.static_folder, path))
        if fullpath.startswith(app.static_folder) and os.path.exists(fullpath):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

    @app.route('/api/config', methods=['GET'])
    def fetch_config():
        """
        Load current config in json
        """
        try:
            config = load_env_vars()
            return jsonify(config), 200
        except Exception as e: # pylint: disable=broad-except
            return jsonify(
                {'message': f'Error loading configuration: {str(e)}', 'status': 'error'}), 500

    @app.route('/api/save', methods=['POST'])
    def save_config():
        """
        Save env variables
        """
        try:
            config_data = request.json
            save_env_vars(config_data)
            return jsonify(
                {'message': 'Configuration saved successfully!', 'status': 'success'}), 200
        except Exception as e: # pylint: disable=broad-except
            return jsonify(
                {'message': f'Error saving configuration: {str(e)}', 'status': 'error'}), 500


    @app.route('/api/force_run', methods=['POST'])
    async def run_now():
        """
        Endpoint to execute the process in the background.
        """
        try:
            await run_content_automation_task()
            return jsonify({'status': 'success', 'message': 'Task is running in the background!'}), 202

        except ValueError as ve:
            return jsonify({'status': 'error', 'message': 'Value error: ' + str(ve)}), 400
        except FileNotFoundError as fnfe:
            return jsonify({'status': 'error', 'message': 'File not found: ' + str(fnfe)}), 404
        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Unexpected error: ' + str(e)}), 500


    @app.route('/api/jellyseer/get_users', methods=['POST'])
    async def get_users():
        """
        Fetch Jellyseer users using the provided API key.
        """
        try:
            config_data = request.json
            api_url = config_data.get('JELLYSEER_API_URL')
            api_key = config_data.get('JELLYSEER_TOKEN')

            if not api_key:
                return jsonify({'message': 'API key is required', 'type': 'error'}), 400

            # Initialize JellyseerClient with the provided API key
            jellyseer_client = JellyseerClient(api_url=api_url, api_key=api_key)

            # Fetch users from Jellyseer
            users = await jellyseer_client.get_all_users()

            if users is None or len(users) == 0:
                return jsonify({'message': 'Failed to fetch users', 'type': 'error'}), 500

            return jsonify(
                {'message': 'Users fetched successfully', 'users': users, 'type': 'success'}), 200

        except Exception as e: # pylint: disable=broad-except
            return jsonify({'message': f'Error fetching users: {str(e)}', 'type': 'error'}), 500

    @app.route('/api/jellyseer/login', methods=['POST'])
    async def login_jellyseer():
        """
        Endpoint to login to Jellyseer using the provided credentials.
        """
        try:
            # Estrai i parametri dalla richiesta POST
            config_data = request.json
            api_url = config_data.get('JELLYSEER_API_URL')
            api_key = config_data.get('JELLYSEER_TOKEN')
            username = config_data.get('JELLYSEER_USER_NAME')
            password = config_data.get('JELLYSEER_PASSWORD')

            if not username or not password:
                return jsonify({'message': 'Username and password are required', 'type': 'error'}), 400

            # Crea una nuova istanza del client Jellyseer con le credenziali fornite
            jellyseer_client = JellyseerClient(api_url=api_url, api_key=api_key, jellyseer_user_name=username, jellyseer_password=password)

            # Effettua il login
            await jellyseer_client.login()

            # Verifica se il login ha avuto successo controllando la session_token
            if jellyseer_client.session_token:
                return jsonify({'message': 'Login successful', 'type': 'success'}), 200
            else:
                return jsonify({'message': 'Login failed', 'type': 'error'}), 401

        except Exception as e:
            logger.error(f'An error occurred: {str(e)}')
            return jsonify({'message': 'An internal error has occurred', 'type': 'error'}), 500

    @app.route('/api/jellyfin/libraries', methods=['POST'])
    async def get_jellyfin_library():
        try:
            config_data = request.json
            api_url = config_data.get('JELLYFIN_API_URL')
            api_key = config_data.get('JELLYFIN_TOKEN')

            jellyfin_client = JellyfinClient(api_url=api_url, token=api_key)

            libraries = await jellyfin_client.get_libraries()

            if libraries:
                return libraries, 200
            else:
                return jsonify({'message': 'No library found in Jellyfin', 'type': 'error'}), 401
        except Exception as e:
            logger.error(f'An error occurred: {str(e)}')
            return jsonify({'message': 'An internal error has occurred', 'type': 'error'}), 500


app = create_app()
asgi_app = WsgiToAsgi(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
