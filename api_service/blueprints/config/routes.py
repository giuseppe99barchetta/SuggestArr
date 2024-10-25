from flask import Blueprint, request, jsonify
from config.config import load_env_vars, save_env_vars, clear_env_vars
from config.logger_manager import LoggerManager

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
