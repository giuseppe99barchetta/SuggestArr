import os
from flask import Blueprint, request, jsonify
import requests
from api_service.auth.middleware import require_role
from api_service.config.config import (
    load_env_vars, save_env_vars, clear_env_vars,
    get_config_section, save_config_section, INTEGRATION_TO_FLAT,
    is_setup_complete
)
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.config_service import ConfigService
from api_service.services.integration_security import bind_flat_credentials
from api_service.utils.ssrf_guard import validate_url
from api_service.services.config_secrets import merge_integration_config

logger = LoggerManager.get_logger("ConfigRoute")
config_bp = Blueprint('config', __name__)

# Keys whose plaintext values must never appear in API responses.
_SECRET_KEYS = frozenset({
    'TMDB_API_KEY', 'OMDB_API_KEY', 'MDBLIST_API_KEY',
    'PLEX_TOKEN', 'JELLYFIN_TOKEN', 'RADARR_TOKEN', 'SONARR_TOKEN',
    'SEER_TOKEN', 'SEER_USER_PSW', 'SEER_SESSION_TOKEN',
    'DB_PASSWORD',
    'OPENAI_API_KEY',
    'TRAKT_CLIENT_SECRET', 'TRAKT_ACCESS_TOKEN', 'TRAKT_REFRESH_TOKEN',
})

_REDACTED = "***"

# Bidirectional mapping between flat config keys (YAML / API format) and the
# DB integrations table (service / field format).
_FLAT_TO_INTEGRATION: dict = {
    flat_key: (service, db_field)
    for service, field_map in INTEGRATION_TO_FLAT.items()
    for db_field, flat_key in field_map.items()
}


def _expand_integrations_into_flat(flat: dict, integrations: dict) -> None:
    """Inject non-empty DB integration values into a flat config dict (in-place).

    The integrations table is authoritative for the keys in ``_INTEGRATION_TO_FLAT``.
    Only non-empty values from the DB override the flat dict, so YAML-only keys
    (e.g. PLEX_TOKEN) are left untouched.

    Args:
        flat: Flat config dict to update (e.g. from ``load_env_vars``).
        integrations: Nested dict returned by ``get_all_integrations``.
    """
    for service, field_map in INTEGRATION_TO_FLAT.items():
        svc_cfg = integrations.get(service) or {}
        for db_field, flat_key in field_map.items():
            val = svc_cfg.get(db_field)
            if val:
                flat[flat_key] = val


def _sync_integrations_from_flat(db, flat: dict) -> None:
    """Upsert DB integration rows from a flat config dict.

    Missing/redacted keys leave stored values untouched. Explicit empty media
    integration values clear destinations, tokens and sessions; an empty Trakt
    client secret also clears the old secret for an ID-only app.

    Args:
        db: ``DatabaseManager`` instance.
        flat: Flat config dict (e.g. from ``request.json`` or ``load_env_vars``).
    """
    service_updates: dict = {}
    for flat_key, (service, db_field) in _FLAT_TO_INTEGRATION.items():
        if flat_key not in flat:
            continue
        val = flat.get(flat_key)
        if val == _REDACTED:
            continue
        if val or (service == 'trakt' and db_field == 'client_secret') or service in ('jellyfin', 'seer'):
            service_updates.setdefault(service, {})[db_field] = val

    for service, changes in service_updates.items():
        existing = db.get_integration(service) or {}
        db.set_integration(service, merge_integration_config(service, changes, existing))


def _merge_secrets(incoming: dict, existing: dict) -> dict:
    """Replace '***' sentinel values in incoming with the real value from existing config.

    Falls back to the DB integrations table for keys that are only stored there
    (not in config.yaml / ``existing``).
    """
    merged = dict(incoming)
    # Build a flat view of DB-backed values as a fallback for redacted secrets.
    db_flat: dict = {}
    try:
        _expand_integrations_into_flat(db_flat, DatabaseManager().get_all_integrations())
    except Exception:
        pass
    effective_existing = {**existing, **db_flat}
    merged = bind_flat_credentials(merged, effective_existing)
    for key in _SECRET_KEYS:
        if merged.get(key) == _REDACTED:
            merged[key] = effective_existing.get(key)
    return merged

@config_bp.route('/fetch', methods=['GET'])
@require_role('admin')
def fetch_config():
    """
    Load current configuration in JSON format (admin sees real keys).

    DB-backed integration values (TMDB_API_KEY, JELLYFIN_TOKEN, etc.) are
    injected into the flat response so the frontend can read them directly,
    even when config.yaml does not contain them.

    Secrets are returned as-is for admin users; the UI is responsible for
    masking them (reveal-on-demand pattern).  Non-admin access is blocked
    upstream by the require_role('admin') decorator.
    """
    try:
        config = load_env_vars()
        db = DatabaseManager()
        db_integrations = db.get_all_integrations()
        # Surface DB-backed keys in the flat format the frontend expects.
        _expand_integrations_into_flat(config, db_integrations)
        config['integrations'] = db_integrations
        return jsonify(config), 200
    except Exception as e:
        logger.error(f'Error loading configuration: {str(e)}', exc_info=True)
        return jsonify({'message': 'Error loading configuration', 'status': 'error'}), 500
    
@config_bp.route('/save', methods=['POST'])
@require_role('admin')
def save_config():
    """
    Save environment variables and sync the DB integrations table.
    """
    try:
        config_data = _merge_secrets(request.json or {}, load_env_vars())
        save_env_vars(config_data)
        db = DatabaseManager()
        _sync_integrations_from_flat(db, config_data)
        db.refresh_config()
        return jsonify({'message': 'Configuration saved successfully!', 'status': 'success'}), 200
    except ValueError as e:
        return jsonify({'message': str(e), 'status': 'error'}), 400
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
    Get a specific configuration section (admin only – real keys, no redaction).

    DB-backed integration values are injected so the response is always
    up-to-date even when config.yaml is stale or missing those keys.
    """
    try:
        section_data = get_config_section(section_name)
        _expand_integrations_into_flat(section_data, DatabaseManager().get_all_integrations())
        return jsonify({
            'section': section_name,
            'data': section_data,
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
    Save a specific configuration section and sync the DB integrations table.
    """
    try:
        section_data = request.json
        if not section_data:
            return jsonify({'message': 'No configuration data provided', 'status': 'error'}), 400

        section_data = _merge_secrets(section_data, load_env_vars())
        save_config_section(section_name, section_data)
        # Keep the integrations table in sync whenever service credentials are saved.
        db = DatabaseManager()
        _sync_integrations_from_flat(db, section_data)
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

from api_service.auth.limiter import limiter

@config_bp.route('/status', methods=['GET'])
@limiter.exempt
def get_setup_status():
    """
    Get setup completion status.

    The integrations table is checked as a fallback so that ``has_tmdb_key``
    and ``is_complete`` remain accurate even when config.yaml is missing
    DB-backed keys (e.g. after an import or a clean migration).
    """
    try:
        config = load_env_vars()
        # Inject DB-backed values so is_setup_complete sees the real state.
        try:
            _expand_integrations_into_flat(config, DatabaseManager().get_all_integrations())
        except Exception:
            pass
        setup_completed = config.get('SETUP_COMPLETED', False)
        is_complete = is_setup_complete(config)

        return jsonify({
            'setup_completed': setup_completed,
            'is_complete': is_complete,
            'selected_service': config.get('SELECTED_SERVICE'),
            'has_tmdb_key': bool(config.get('TMDB_API_KEY')),
            'trakt_app_configured': bool(config.get('TRAKT_CLIENT_ID')),
            # Simkl's device flow needs no client secret, so the client id alone
            # is the whole configuration requirement.
            'simkl_app_configured': bool(config.get('SIMKL_CLIENT_ID')),
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

    Requires admin role.  Secret values are redacted by default; pass
    ``include_secrets=true`` for a fully restorable backup.

    Query parameters:
        include_secrets (str): 'true' to include raw secret values (API keys,
            tokens, passwords) and Trakt OAuth tokens.  Defaults to 'false'.

    Returns:
        200 JSON with keys: version, integrations, settings, media_users.
        500 on unexpected server error.
    """
    try:
        include_secrets = request.args.get('include_secrets', 'false').lower() == 'true'
        snapshot = ConfigService.export_config(include_secrets=include_secrets)
        logger.info(
            "Admin config export requested by user '%s' (include_secrets=%s)",
            _current_username(),
            include_secrets,
        )
        return jsonify(snapshot), 200
    except Exception as e:
        logger.error('Error exporting configuration: %s', e, exc_info=True)
        return jsonify({'message': 'Error exporting configuration', 'status': 'error'}), 500


def _ai_manager_id():
    """Return ``(account id, None)`` for a caller allowed to manage their own AI provider, else ``(None, error response)``."""
    from flask import g
    current_user = getattr(g, 'current_user', None)
    if not current_user:
        return None, (jsonify({'error': 'Authentication required'}), 401)
    if current_user.get('role') != 'admin' and not current_user.get('can_manage_ai'):
        return None, (jsonify({'error': 'Insufficient permissions to manage AI settings'}), 403)
    try:
        return int(current_user['id']), None
    except (TypeError, ValueError):
        return None, (jsonify({'error': 'This account cannot hold personal settings'}), 403)


def _mask_secret(secret: str) -> str:
    """Show only the end of a key, enough to recognise it."""
    return '****' + secret[-4:] if len(secret) > 8 else '****'


@config_bp.route('/openai/user', methods=['GET'])
def get_user_openai_config():
    """
    Return the caller's own AI provider (key masked), if they set one.

    Administrators and accounts with ``can_manage_ai`` may have one; everyone else uses the shared provider
    set up by the administrator.

    Returns:
        200 JSON with openai_api_key (masked), openai_base_url and llm_model
        401/403 when the caller may not manage AI settings
        404 when no personal provider exists (the shared one is used)
    """
    user_id, error = _ai_manager_id()
    if error:
        return error
    from api_service.services.llm.llm_service import personal_llm_settings
    stored = personal_llm_settings(user_id)
    if not stored:
        return jsonify({'status': 'not_configured', 'message': 'No personal AI provider: the shared one is used'}), 404
    return jsonify({
        'status': 'success',
        'openai_api_key': _mask_secret(stored['api_key']) if stored['api_key'] else '',
        'openai_base_url': stored['base_url'],
        'llm_model': stored['model'],
    }), 200


@config_bp.route('/openai/user', methods=['POST'])
def save_user_openai_config():
    """
    Save the caller's own AI provider.

    A new provider replaces the previous one as a whole. When ``openai_api_key`` is left out and the address
    is unchanged, the saved key is kept, so the model or address can be edited without retyping the key.

    Request JSON:
      openai_api_key (str, optional) - API key (not needed for a local provider)
      openai_base_url (str, optional) - address of an OpenAI-compatible provider
      llm_model (str, optional) - model name; the shared model setting is used when empty
    At least a key or an address is required.

    Returns:
        200 on success, 400 on invalid input, 401/403 when the caller may not manage AI settings
    """
    user_id, error = _ai_manager_id()
    if error:
        return error
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Request body must be a JSON object'}), 400
    fields = {}
    for name, limit in (('openai_api_key', 512), ('openai_base_url', 512), ('llm_model', 128)):
        value = data.get(name, '')
        if value is None:
            value = ''
        if not isinstance(value, str) or len(value.strip()) > limit:
            return jsonify({'error': f'{name} must be a string of at most {limit} characters'}), 400
        fields[name] = value.strip()
    base_url = fields['openai_base_url']
    if base_url:
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            return jsonify({'error': 'openai_base_url must be an http(s) address'}), 400
        try:
            # Only an administrator may point the server at a private address (a local model on the LAN).
            from flask import g
            validate_url(base_url, allow_private=g.current_user.get('role') == 'admin')
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400

    from api_service.services.llm.llm_service import personal_llm_settings
    saved = personal_llm_settings(user_id)
    api_key = fields['openai_api_key']
    if not api_key and saved and saved['base_url'] == base_url:
        api_key = saved['api_key']  # editing the model only: keep the key
    if not api_key and not base_url:
        return jsonify({'error': 'At least one of openai_api_key or openai_base_url must be provided'}), 400
    try:
        import json
        from flask import g
        DatabaseManager().create_user_media_profile(
            user_id=user_id,
            provider='openai',
            external_user_id=str(user_id),
            external_username=g.current_user.get('username', 'user'),
            access_token=json.dumps({'api_key': api_key, 'base_url': base_url, 'model': fields['llm_model']}),
        )
    except Exception as e:
        logger.error(f'Error saving user OpenAI config: {e}', exc_info=True)
        return jsonify({'error': 'Failed to save AI provider'}), 500
    logger.info("User %s saved a personal AI provider", user_id)
    return jsonify({'status': 'success', 'message': 'AI provider saved'}), 200


@config_bp.route('/openai/user', methods=['DELETE'])
def delete_user_openai_config():
    """
    Delete the caller's own AI provider, so the shared one is used again.

    Returns:
        200 on success, 401/403 when the caller may not manage AI settings
    """
    user_id, error = _ai_manager_id()
    if error:
        return error
    try:
        DatabaseManager().delete_user_media_profile(user_id, 'openai')
    except Exception as e:
        logger.error(f'Error deleting user OpenAI config: {e}', exc_info=True)
        return jsonify({'error': 'Failed to delete AI provider'}), 500
    logger.info("User %s deleted their personal AI provider", user_id)
    return jsonify({'status': 'success', 'message': 'AI provider removed. The shared one is used.'}), 200


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
        return jsonify({'message': 'Invalid configuration payload', 'status': 'error'}), 400
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
