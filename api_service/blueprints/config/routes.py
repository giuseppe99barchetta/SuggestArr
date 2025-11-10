import os
from flask import Blueprint, request, jsonify
import yaml
from api_service.config.config import (
    load_env_vars, save_env_vars, clear_env_vars,
    get_config_sections, get_config_section, save_config_section,
    is_setup_complete
)
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager

logger = LoggerManager.get_logger("ConfigRoute")
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

@config_bp.route('/sections', methods=['GET'])
def get_config_sections():
    """
    Get available configuration sections.
    """
    try:
        sections = get_config_sections()
        return jsonify({
            'sections': sections,
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f'Error getting configuration sections: {str(e)}')
        return jsonify({'message': f'Error getting configuration sections: {str(e)}', 'status': 'error'}), 500

@config_bp.route('/section/<section_name>', methods=['GET'])
def get_config_section_endpoint(section_name):
    """
    Get a specific configuration section.
    """
    try:
        section_data = get_config_section(section_name)
        return jsonify({
            'section': section_name,
            'data': section_data,
            'status': 'success'
        }), 200
    except ValueError as e:
        logger.error(f'Invalid configuration section: {str(e)}')
        return jsonify({'message': f'Invalid configuration section: {str(e)}', 'status': 'error'}), 400
    except Exception as e:
        logger.error(f'Error getting configuration section {section_name}: {str(e)}')
        return jsonify({'message': f'Error getting configuration section: {str(e)}', 'status': 'error'}), 500

@config_bp.route('/section/<section_name>', methods=['POST'])
def save_config_section_endpoint(section_name):
    """
    Save a specific configuration section.
    """
    try:
        section_data = request.json
        if not section_data:
            return jsonify({'message': 'No configuration data provided', 'status': 'error'}), 400

        save_config_section(section_name, section_data)
        return jsonify({
            'message': f'Configuration section {section_name} saved successfully!',
            'section': section_name,
            'status': 'success'
        }), 200
    except ValueError as e:
        logger.error(f'Invalid configuration section: {str(e)}')
        return jsonify({'message': f'Invalid configuration section: {str(e)}', 'status': 'error'}), 400
    except Exception as e:
        logger.error(f'Error saving configuration section {section_name}: {str(e)}')
        return jsonify({'message': f'Error saving configuration section: {str(e)}', 'status': 'error'}), 500

@config_bp.route('/status', methods=['GET'])
def get_setup_status():
    """
    Get setup completion status.
    """
    try:
        config = load_env_vars()
        setup_completed = config.get('SETUP_COMPLETED', False)
        is_complete = is_setup_complete(config)

        # Auto-update setup completion if it's actually complete but not marked
        if not setup_completed and is_complete:
            config['SETUP_COMPLETED'] = True
            save_env_vars(config)
            setup_completed = True

        return jsonify({
            'setup_completed': setup_completed,
            'is_complete': is_complete,
            'selected_service': config.get('SELECTED_SERVICE'),
            'has_tmdb_key': bool(config.get('TMDB_API_KEY')),
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f'Error getting setup status: {str(e)}')
        return jsonify({'message': f'Error getting setup status: {str(e)}', 'status': 'error'}), 500

@config_bp.route('/complete-setup', methods=['POST'])
def complete_setup():
    """
    Mark setup as completed.
    """
    try:
        config = load_env_vars()

        # Verify setup is actually complete before marking
        if not is_setup_complete(config):
            return jsonify({
                'message': 'Cannot complete setup: Essential configuration is missing',
                'status': 'error'
            }), 400

        config['SETUP_COMPLETED'] = True
        save_env_vars(config)

        return jsonify({
            'message': 'Setup marked as completed successfully!',
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f'Error completing setup: {str(e)}')
        return jsonify({'message': f'Error completing setup: {str(e)}', 'status': 'error'}), 500

@config_bp.route('/log-level', methods=['GET'])
def get_log_level():
    """
    Get current log level.
    """
    try:
        current_level = LoggerManager.get_current_log_level()
        return jsonify({
            'log_level': current_level,
            'available_levels': ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f'Error getting log level: {str(e)}')
        return jsonify({'message': f'Error getting log level: {str(e)}', 'status': 'error'}), 500

@config_bp.route('/log-level', methods=['POST'])
def set_log_level():
    """
    Set log level.
    """
    try:
        data = request.json
        if not data or 'level' not in data:
            return jsonify({'message': 'Log level is required', 'status': 'error'}), 400

        level = data['level'].upper()
        old_level = LoggerManager.get_current_log_level()
        LoggerManager.set_log_level(level)
        logger.info(f'Log level changed from {old_level} to {level}')

        return jsonify({
            'message': f'Log level set to {level} successfully!',
            'log_level': level,
            'previous_level': old_level,
            'status': 'success'
        }), 200
    except ValueError as e:
        logger.error(f'Invalid log level: {str(e)}')
        return jsonify({'message': str(e), 'status': 'error'}), 400
    except Exception as e:
        logger.error(f'Error setting log level: {str(e)}')
        return jsonify({'message': f'Error setting log level: {str(e)}', 'status': 'error'}), 500