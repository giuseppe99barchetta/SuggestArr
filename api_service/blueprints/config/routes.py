import os
from flask import Blueprint, request, jsonify
import yaml
from api_service.config.config import load_env_vars, save_env_vars, clear_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager

logger = LoggerManager().get_logger(__name__)
config_bp = Blueprint('config', __name__)

@config_bp.route('/fetch', methods=['GET'])
def fetch_config():
    """
    Load current configuration in JSON format.
    """
    try:
        config = load_env_vars()
        return jsonify(config), 200
    except Exception as e:
        logger.error(f'Error loading configuration: {str(e)}')
        return jsonify({'message': f'Error loading configuration: {str(e)}', 'status': 'error'}), 500

@config_bp.route('/save', methods=['POST'])
def save_config():
    """
    Save environment variables.
    """
    try:
        config_data = request.json
        save_env_vars(config_data)
        DatabaseManager().initialize_db()
        return jsonify({'message': 'Configuration saved successfully!', 'status': 'success'}), 200
    except Exception as e:
        logger.error(f'Error saving configuration: {str(e)}')
        return jsonify({'message': f'Error saving configuration: {str(e)}', 'status': 'error'}), 500

@config_bp.route('/reset', methods=['POST'])
def reset_config():
    """
    Reset environment variables.
    """
    try:
        clear_env_vars()
        return jsonify({'message': 'Configuration cleared successfully!', 'status': 'success'}), 200
    except Exception as e:
        logger.error(f'Error clearing configuration: {str(e)}')
        return jsonify({'message': f'Error clearing configuration: {str(e)}', 'status': 'error'}), 500

@config_bp.route('/test-db-connection', methods=['POST'])
def test_db_connection():
    """
    Test database connection.
    """
    try:
        # Extract DB configuration data from the request
        db_config = request.json

        # Check if the necessary data has been provided
        required_keys = ['DB_TYPE', 'DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']
        if any(key not in db_config for key in required_keys):
            return jsonify({'message': 'Missing required database configuration parameters.', 'status': 'error'}), 400

        # Create an instance of the DatabaseManager
        db_manager = DatabaseManager()

        # Call the connection test method
        result = db_manager.test_connection(db_config)

        # Respond with the test result
        return jsonify(result), 200 if result['status'] == 'success' else 500

    except Exception as e:
        logger.error(f'Error testing database connection: {str(e)}')
        return jsonify({'message': f'Error testing database connection: {str(e)}', 'status': 'error'}), 500