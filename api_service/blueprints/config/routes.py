import os
from flask import Blueprint, request, jsonify
import yaml
import requests
from api_service.auth.middleware import require_role
from api_service.config.config import (
    load_env_vars, save_env_vars, clear_env_vars,
    get_config_sections, get_config_section, save_config_section,
    is_setup_complete
)
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.config_service import ConfigService

logger = LoggerManager.get_logger("ConfigRoute")
config_bp = Blueprint('config', __name__)

# Keys whose plaintext values must never appear in API responses.
_SECRET_KEYS = frozenset({
    'TMDB_API_KEY', 'OMDB_API_KEY',
    'PLEX_TOKEN', 'JELLYFIN_TOKEN',
    'SEER_TOKEN', 'SEER_USER_PSW', 'SEER_SESSION_TOKEN',
    'DB_PASSWORD',
    'OPENAI_API_KEY',
    'TRAKT_CLIENT_SECRET', 'TRAKT_ACCESS_TOKEN', 'TRAKT_REFRESH_TOKEN',
})

_REDACTED = "***"


def _redact_config(config: dict) -> dict:
    """Return a copy of config with non-empty secret values replaced by '***'."""
    return {k: (_REDACTED if k in _SECRET_KEYS and v else v) for k, v in config.items()}


def _merge_secrets(incoming: dict, existing: dict) -> dict:
    """Replace '***' sentinel values in incoming with the real value from existing config."""
    merged = dict(incoming)
    for key in _SECRET_KEYS:
        if merged.get(key) == _REDACTED:
            merged[key] = existing.get(key)
    return merged

@config_bp.route('/fetch', methods=['GET'])
@require_role('admin')
def fetch_config():
    """
    Load current configuration in JSON format.
    """
    try:
        config = load_env_vars()
        return jsonify(_redact_config(config)), 200
    except Exception as e:
        logger.error(f'Error loading configuration: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error loading configuration', 'status': 'error'}), 500

@config_bp.route('/save', methods=['POST'])
@require_role('admin')
def save_config():
    """
    Save environment variables.
    """
    try:
        config_data = _merge_secrets(request.json or {}, load_env_vars())
        save_env_vars(config_data)
        DatabaseManager().refresh_config()
        return jsonify({'message': 'Configuration saved successfully!', 'status': 'success'}), 200
    except Exception as e:
        logger.error(f'Error saving configuration: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error saving configuration', 'status': 'error'}), 500

@config_bp.route('/reset', methods=['POST'])
@require_role('admin')
def reset_config():
    """
    Reset environment variables.
    """
    try:
        clear_env_vars()
        return jsonify({'message': 'Configuration cleared successfully!', 'status': 'success'}), 200
    except Exception as e:
        logger.error(f'Error clearing configuration: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error clearing configuration', 'status': 'error'}), 500

@config_bp.route('/test-db-connection', methods=['POST'])
@require_role('admin')
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
        logger.error(f'Error testing database connection: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error testing database connection', 'status': 'error'}), 500

@config_bp.route('/sections', methods=['GET'])
@require_role('admin')
def get_config_sections_endpoint():
    """
    Get available configuration sections.
    """
    try:
        from api_service.config.config import get_config_sections as _get_sections
        sections = _get_sections()
        return jsonify({
            'sections': sections,
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f'Error getting configuration sections: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error getting configuration sections', 'status': 'error'}), 500

@config_bp.route('/section/<section_name>', methods=['GET'])
@require_role('admin')
def get_config_section_endpoint(section_name):
    """
    Get a specific configuration section.
    """
    try:
        section_data = get_config_section(section_name)
        return jsonify({
            'section': section_name,
            'data': _redact_config(section_data),
            'status': 'success'
        }), 200
    except ValueError as e:
        logger.error(f'Invalid configuration section: {str(e)}')
        return jsonify({'message': f'Invalid configuration section: {str(e)}', 'status': 'error'}), 400
    except Exception as e:
        logger.error(f'Error getting configuration section {section_name}: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error getting configuration section', 'status': 'error'}), 500

@config_bp.route('/section/<section_name>', methods=['POST'])
@require_role('admin')
def save_config_section_endpoint(section_name):
    """
    Save a specific configuration section.
    """
    try:
        section_data = request.json
        if not section_data:
            return jsonify({'message': 'No configuration data provided', 'status': 'error'}), 400

        section_data = _merge_secrets(section_data, load_env_vars())
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
        logger.error(f'Error saving configuration section {section_name}: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error saving configuration section', 'status': 'error'}), 500

@config_bp.route('/status', methods=['GET'])
def get_setup_status():
    """
    Get setup completion status.
    """
    try:
        config = load_env_vars()
        setup_completed = config.get('SETUP_COMPLETED', False)
        is_complete = is_setup_complete(config)

        return jsonify({
            'setup_completed': setup_completed,
            'is_complete': is_complete,
            'selected_service': config.get('SELECTED_SERVICE'),
            'has_tmdb_key': bool(config.get('TMDB_API_KEY')),
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f'Error getting setup status: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error getting setup status', 'status': 'error'}), 500

@config_bp.route('/complete-setup', methods=['POST'])
@require_role('admin')
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
        logger.error(f'Error completing setup: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error completing setup', 'status': 'error'}), 500

@config_bp.route('/log-level', methods=['GET'])
@require_role('admin')
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
        logger.error(f'Error getting log level: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error getting log level', 'status': 'error'}), 500

@config_bp.route('/log-level', methods=['POST'])
@require_role('admin')
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
        logger.error(f'Error setting log level: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error setting log level', 'status': 'error'}), 500

@config_bp.route('/pool-stats', methods=['GET'])
@require_role('admin')
def get_pool_statistics():
    """
    Get database connection pool statistics.
    """
    try:
        db_manager = DatabaseManager()
        pool_stats = db_manager.get_pool_stats()
        all_stats = {'status': 'direct_connection', 'message': 'Connection pooling has been removed for better performance'}
        
        return jsonify({
            'message': 'Connection pool statistics retrieved successfully',
            'current_pool': pool_stats,
            'all_pools': all_stats,
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f'Error getting pool statistics: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error getting pool statistics', 'status': 'error'}), 500

@config_bp.route('/force_run', methods=['POST'])
@require_role('admin')
def force_run_automation():
    """
    Force run the automation script immediately.
    """
    try:
        from api_service.utils.utils import execute_automation
        logger.info("Force run automation script requested")
        
        # Execute automation in background
        execute_automation(force_run=True)
        
        return jsonify({
            'message': 'Automation script forced successfully!',
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f'Error forcing automation run: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error forcing automation run', 'status': 'error'}), 500

@config_bp.route('/test-db', methods=['POST'])
@require_role('admin')
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
        logger.error(f'Error testing database connection: {str(e)}', exc_info=True)
        return jsonify({
            'message': 'Error testing database connection',
            'status': 'error'
        }), 500

@config_bp.route('/docker-info', methods=['GET'])
def get_docker_info():
    """
    Get Docker container information using multiple reliable methods.
    Prioritizes build args passed as ENV/LABELs.
    """
    try:
        import os
        import json
        
        docker_tag = os.environ.get('DOCKER_TAG') or os.environ.get('DOCKER_IMAGE_TAG')
        build_date = os.environ.get('BUILD_DATE')
        
        if docker_tag:
            logger.info(f'Docker info from ENV: tag={docker_tag}, source=environment')
            return jsonify({
                'tag': docker_tag,
                'build_date': build_date,
                'source': 'environment',
                'status': 'success'
            }), 200
        
        metadata_file = '/app/.docker_metadata'
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    logger.info(f'Docker info from metadata file: {metadata.get("tag")}')
                    return jsonify({
                        'tag': metadata.get('tag', 'latest'),
                        'build_date': metadata.get('build_date'),
                        'source': 'metadata_file',
                        'status': 'success'
                    }), 200
            except Exception as e:
                logger.warning(f'Metadata file read error: {e}')
        
        try:
            import requests
            container_id = os.environ.get('HOSTNAME', '').split('.')[0]
            
            if container_id:
                sock_url = f"http://unix:///var/run/docker.sock:2375/containers/{container_id}/json"
                response = requests.get(
                    sock_url,
                    timeout=5,
                    headers={'Accept': 'application/json'}
                )
                
                if response.status_code == 200:
                    container_info = response.json()
                    
                    labels = container_info.get('Config', {}).get('Labels', {})
                    docker_tag = labels.get('DOCKER_TAG') or labels.get('org.opencontainers.image.version')
                    
                    if not docker_tag:
                        image_name = container_info.get('Config', {}).get('Image', '')
                        if ':' in image_name:
                            docker_tag = image_name.split(':')[-1]
                        else:
                            docker_tag = 'latest'
                    
                    logger.info(f'Docker info from socket: tag={docker_tag}')
                    return jsonify({
                        'tag': docker_tag or 'latest',
                        'build_date': labels.get('BUILD_DATE'),
                        'source': 'docker_socket',
                        'status': 'success'
                    }), 200
                    
        except Exception as e:
            logger.debug(f'Docker socket failed: {e}')
        
        logger.debug('Docker info fallback: latest')
        return jsonify({
            'tag': 'latest',
            'build_date': None,
            'source': 'fallback',
            'status': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f'get_docker_info error: {e}', exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@config_bp.route('/docker-digest/<tag>', methods=['GET'])
def get_docker_digest(tag):
    """
    Docker Hub API proxy per digest (per nightly/stable checks).
    """
    try:
        import requests
        
        url = f'https://registry.hub.docker.com/v2/repositories/ciuse99/suggestarr/tags/{tag}'
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = data.get('results', [])
        if results:
            digest = results[0].get('digest')
            if digest:
                logger.info(f'Digest for {tag}: {digest[:16]}...')
                return jsonify({
                    'tag': tag,
                    'digest': digest,
                    'status': 'success'
                }), 200
        
        return jsonify({
            'tag': tag,
            'message': 'No digest found',
            'status': 'error'
        }), 404
        
    except requests.exceptions.RequestException as e:
        logger.error(f'Docker digest API error for {tag}: {e}', exc_info=True)
        return jsonify({'status': 'error', 'message': 'Failed to retrieve Docker digest'}), 500


@config_bp.route('/export', methods=['GET'])
@require_role('admin')
def export_config():
    """
    Export the full application configuration as a portable JSON snapshot.

    Requires admin role.  The response includes API keys in plain text so that
    a configuration backup can be fully restored; callers must treat the
    response as sensitive.

    Returns:
        200 JSON with keys: version, integrations, settings.
        500 on unexpected server error.
    """
    try:
        snapshot = ConfigService.export_config()
        logger.info("Admin config export requested by user '%s'", _current_username())
        return jsonify(snapshot), 200
    except Exception as e:
        logger.error('Error exporting configuration: %s', e, exc_info=True)
        return jsonify({'message': 'Error exporting configuration', 'status': 'error'}), 500


@config_bp.route('/import', methods=['POST'])
@require_role('admin')
def import_config():
    """
    Import a configuration snapshot produced by the export endpoint.

    Requires admin role.  Accepts a JSON body matching the export format
    (version, integrations, settings).  Integrations are upserted into the DB;
    settings are merged into config.yaml.

    Returns:
        200 on success.
        400 if the body is missing, not JSON, or the version is unsupported.
        500 on unexpected server error.
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'message': 'Request body must be valid JSON', 'status': 'error'}), 400

        ConfigService.import_config(data)
        logger.info("Admin config import completed by user '%s'", _current_username())
        return jsonify({'message': 'Configuration imported successfully', 'status': 'success'}), 200
    except ValueError as e:
        logger.warning('Config import rejected: %s', e)
        return jsonify({'message': str(e), 'status': 'error'}), 400
    except Exception as e:
        logger.error('Error importing configuration: %s', e, exc_info=True)
        return jsonify({'message': 'Error importing configuration', 'status': 'error'}), 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_username() -> str:
    """Return the username of the authenticated user, or '<unknown>'."""
    try:
        from flask import g
        user = getattr(g, 'current_user', None)
        return user.get('username', '<unknown>') if user else '<unknown>'
    except Exception:
        return '<unknown>'
