"""
Main Flask application for managing environment variables and running processes.
"""
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from jellyseer.jellyseer_client import JellyseerClient
from utils.utils import AppUtils
from automate_process import ContentAutomation
from config.config import load_env_vars, save_env_vars

# App Factory Pattern for modularity and testability
def create_app():
    """
    Create and configure the Flask application.
    """

    if AppUtils.is_last_worker():
        AppUtils.print_welcome_message() # Print only for last worker

    application = Flask(__name__)
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

    @app.route('/', methods=['GET'])
    def configure():
        """
        Load configuration page
        """
        return render_template('index.html')

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


    @app.route('/run_now', methods=['POST'])
    async def run_now():
        """
        Endpoint to execute the process in the background.
        """
        try:
            automation = ContentAutomation()
            await automation.run()

            return jsonify({'status': 'success', 'message': 'Force Run correctly completed!'}), 202
        except ValueError as ve:
            return jsonify({'status': 'error', 'message': 'Value error: ' + str(ve)}), 400
        except FileNotFoundError as fnfe:
            return jsonify({'status': 'error', 'message': 'File not found: ' + str(fnfe)}), 404
        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Unexpected error: ' + str(e)}), 500


    @app.route('/api/get_users', methods=['POST'])
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

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000)
