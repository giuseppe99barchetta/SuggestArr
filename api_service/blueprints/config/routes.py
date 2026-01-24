import os
from flask import Blueprint, request, jsonify
import yaml
import requests
from api_service.config.config import (
    load_env_vars, save_env_vars, clear_env_vars,
    get_config_sections, get_config_section, save_config_section,
    is_setup_complete
)
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.db.connection_pool import pool_manager

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

@config_bp.route('/pool-stats', methods=['GET'])
def get_pool_statistics():
    """
    Get database connection pool statistics.
    """
    try:
        db_manager = DatabaseManager()
        pool_stats = db_manager.get_pool_stats()
        all_stats = pool_manager.get_all_stats()
        
        return jsonify({
            'message': 'Connection pool statistics retrieved successfully',
            'current_pool': pool_stats,
            'all_pools': all_stats,
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f'Error getting pool statistics: {str(e)}')
        return jsonify({'message': f'Error getting pool statistics: {str(e)}', 'status': 'error'}), 500

@config_bp.route('/test-db', methods=['POST'])
def test_database_connection():
    """
    Test database connection with current configuration.
    """
    try:
        config = load_env_vars()
        db_config = {
            'DB_TYPE': config.get('DB_TYPE', 'sqlite'),
            'DB_HOST': config.get('DB_HOST'),
            'DB_PORT': config.get('DB_PORT'),
            'DB_USER': config.get('DB_USER'),
            'DB_PASSWORD': config.get('DB_PASSWORD'),
            'DB_NAME': config.get('DB_NAME'),
            'DB_PATH': os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'config_files', 'requests.db')
        }
        
        db_manager = DatabaseManager()
        result = db_manager.test_connection(db_config)
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f'Error testing database connection: {str(e)}')
        return jsonify({
            'message': f'Error testing database connection: {str(e)}', 
            'status': 'error'
        }), 500

@config_bp.route('/version', methods=['GET'])
def get_version():
    """
    Get current SuggestArr version.
    """
    try:
        # Read version from package.json in client directory
        client_package_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'client', 'package.json')
        
        if os.path.exists(client_package_path):
            with open(client_package_path, 'r') as f:
                import json
                package_data = json.load(f)
                version = package_data.get('version', 'unknown')
        else:
            # Fallback version if package.json not found
            version = 'v2.0.0'
        
        return jsonify({
            'version': version,
            'name': 'SuggestArr',
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f'Error getting version: {str(e)}')
        return jsonify({
            'version': 'unknown',
            'message': f'Error getting version: {str(e)}', 
            'status': 'error'
        }), 500

@config_bp.route('/docker-info', methods=['GET'])
def get_docker_info():
    """
    Get Docker container information including image tag from labels.
    """
    try:
        import json
        import os
        
        # Method 1: Try to read from environment variable first (most reliable)
        docker_tag = os.environ.get('DOCKER_IMAGE_TAG')
        docker_digest = os.environ.get('DOCKER_IMAGE_DIGEST')
        
        if docker_tag:
            logger.info(f'Docker tag from environment: {docker_tag}')
            return jsonify({
                'tag': docker_tag,
                'digest': docker_digest,
                'source': 'environment',
                'status': 'success'
            }), 200
        
        # Method 2: Try to read from mounted metadata file (fallback)
        metadata_file = '/app/.docker_metadata'
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    logger.info(f'Docker tag from metadata file: {metadata.get("tag")}')
                    return jsonify({
                        'tag': metadata.get('tag', 'latest'),
                        'digest': metadata.get('digest'),
                        'source': 'metadata_file',
                        'status': 'success'
                    }), 200
            except Exception as e:
                logger.warning(f'Failed to read metadata file: {e}')
        
        # Method 3: Try Docker socket if available (last resort)
        try:
            # Try to connect to Docker socket
            import requests
            container_id = os.environ.get('HOSTNAME', 'unknown')
            
            response = requests.get(
                f'unix:///var/run/docker.sock:/containers/{container_id}/json',
                timeout=5,
                headers={'Accept': 'application/json'}
            )
            
            if response.status_code == 200:
                container_info = response.json()
                image_name = container_info.get('Config', {}).get('Image', '')
                
                # Extract tag from image name (e.g., "ciuse99/suggestarr:nightly" -> "nightly")
                if ':' in image_name:
                    tag = image_name.split(':')[-1]
                else:
                    tag = 'latest'
                
                logger.info(f'Docker tag from Docker socket: {tag}')
                return jsonify({
                    'tag': tag,
                    'digest': None,
                    'source': 'docker_socket',
                    'status': 'success'
                }), 200
                
        except Exception as e:
            logger.debug(f'Docker socket method failed: {e}')
        
        # Fallback: Assume latest if no method worked
        logger.debug('Could not determine Docker tag, assuming latest')
        return jsonify({
            'tag': 'latest',
            'digest': None,
            'source': 'fallback',
            'status': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f'Error getting Docker info: {str(e)}')
        return jsonify({
            'message': f'Error getting Docker info: {str(e)}',
            'status': 'error'
        }), 500

@config_bp.route('/docker-digest/<tag>', methods=['GET'])
def get_docker_digest(tag):
    """
    Get Docker Hub image digest for specified tag.
    This endpoint acts as a proxy to avoid CORS issues.
    """
    try:
        # Make request to Docker Hub API from backend
        url = f'https://registry.hub.docker.com/v2/repositories/ciuse99/suggestarr/tags/{tag}'
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract digest from response
        digest = data.get('digest') or data.get('images', [{}])[0].get('digest')
        
        if not digest:
            return jsonify({
                'message': f'No digest found for tag {tag}',
                'status': 'error'
            }), 404
        
        return jsonify({
            'tag': tag,
            'digest': digest,
            'status': 'success'
        }), 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f'Error fetching Docker digest for {tag}: {str(e)}')
        return jsonify({
            'message': f'Error fetching Docker digest: {str(e)}',
            'status': 'error'
        }), 500
    except Exception as e:
        logger.error(f'Unexpected error getting Docker digest: {str(e)}')
        return jsonify({
            'message': f'Unexpected error: {str(e)}',
            'status': 'error'
        }), 500