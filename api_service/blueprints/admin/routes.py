"""
Admin blueprint: configuration export / import.

Export: GET  /api/admin/export-config?include_secrets=true|false
Import: POST /api/admin/import-config  (admin only)

The database is the single source of truth for integrations.
Config-file writes are intentionally absent from this module.
"""
from flask import Blueprint, g, jsonify, request

from api_service.auth.middleware import require_role
from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager

logger = LoggerManager.get_logger("AdminRoute")
admin_bp = Blueprint('admin', __name__)

# ---------------------------------------------------------------------------
# Secret-field detection
# ---------------------------------------------------------------------------

# Substring patterns used to identify secret fields inside integration configs.
# Any integration config key whose name contains one of these strings is treated
# as sensitive and stripped when include_secrets=false.
_INTEGRATION_SECRET_PATTERNS = ('token', 'api_key', 'password')

# Top-level keys in the settings dict (config.yaml) that hold secrets.
_SETTINGS_SECRET_KEYS = frozenset({
    'TMDB_API_KEY', 'OMDB_API_KEY',
    'PLEX_TOKEN', 'JELLYFIN_TOKEN',
    'SEER_TOKEN', 'SEER_USER_PSW', 'SEER_SESSION_TOKEN',
    'DB_PASSWORD',
    'OPENAI_API_KEY',
    'TRAKT_CLIENT_SECRET', 'TRAKT_ACCESS_TOKEN', 'TRAKT_REFRESH_TOKEN',
})

# ---------------------------------------------------------------------------
# Legacy v1 format: flat env-var dict → v2 integrations dict
# ---------------------------------------------------------------------------

_V1_INTEGRATION_MAP = {
    'jellyfin': {
        'api_url': 'JELLYFIN_API_URL',
        'api_key': 'JELLYFIN_TOKEN',
    },
    'seer': {
        'api_url': 'SEER_API_URL',
        'api_key': 'SEER_TOKEN',
        'session_token': 'SEER_SESSION_TOKEN',
    },
    'plex': {
        'api_url': 'PLEX_API_URL',
        'api_key': 'PLEX_TOKEN',
    },
    'tmdb': {
        'api_key': 'TMDB_API_KEY',
    },
    'omdb': {
        'api_key': 'OMDB_API_KEY',
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_integration_secrets(cfg: dict) -> dict:
    """
    Return a copy of an integration config with secret fields replaced by '***'.

    A field is considered secret if its name contains any string from
    _INTEGRATION_SECRET_PATTERNS.

    Args:
        cfg: Raw integration config dict.

    Returns:
        dict with secret values replaced by '***'.
    """
    return {
        k: '***' if any(p in k for p in _INTEGRATION_SECRET_PATTERNS) else v
        for k, v in cfg.items()
    }


def _redact_settings(settings: dict) -> dict:
    """
    Return a copy of the settings dict with known secret keys replaced by '***'.

    Args:
        settings: Flat settings dict from load_env_vars().

    Returns:
        dict with secret values replaced by '***'.
    """
    return {
        k: ('***' if k in _SETTINGS_SECRET_KEYS and v else v)
        for k, v in settings.items()
    }


def _integrations_from_v1(payload: dict) -> dict:
    """
    Convert a legacy v1 flat env-var dict to a v2 integrations dict.

    Only services that have at least one non-empty value are included.

    Args:
        payload: Flat dict of environment variable names → values.

    Returns:
        dict mapping service name to its config dict.
    """
    integrations = {}
    for service, field_map in _V1_INTEGRATION_MAP.items():
        cfg = {
            field: payload[env_key]
            for field, env_key in field_map.items()
            if env_key in payload
        }
        if any(v for v in cfg.values() if v):
            integrations[service] = cfg
    return integrations


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@admin_bp.route('/export-config', methods=['GET'])
def export_config():
    """
    Export the current DB-backed configuration as a portable backup.

    Query parameters:
        include_secrets (str): 'true' to include raw secret values in the
            response.  Requires admin role.  Defaults to 'false'.

    Returns:
        JSON: {schema_version, integrations, settings}
    """
    include_secrets = request.args.get('include_secrets', 'false').lower() == 'true'

    if include_secrets:
        user = getattr(g, 'current_user', None)
        if user is None or user.get('role') != 'admin':
            return jsonify({'error': 'Admin role required to export secrets'}), 403

    db = DatabaseManager()
    integrations = db.get_all_integrations()
    settings = load_env_vars()

    if not include_secrets:
        integrations = {
            svc: _strip_integration_secrets(cfg)
            for svc, cfg in integrations.items()
        }
        settings = _redact_settings(settings)

    return jsonify({
        'schema_version': 2,
        'integrations': integrations,
        'settings': settings,
    }), 200


@admin_bp.route('/import-config', methods=['POST'])
@require_role('admin')
def import_config():
    """
    Import a configuration backup into the database.

    Accepts schema_version 2 (explicit) or a legacy v1 flat env-var dict
    (schema_version absent).  Only integrations are written; auth users are
    never modified; config-file writes are not performed.

    Body (JSON):
        schema_version (int, optional): 2 for current format; omit for v1.
        integrations (dict): service-name → config dict  [v2 only]
        settings (dict, optional): ignored on import.

    Returns:
        JSON: {status, services_written, count}
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'error': 'Request body must be a JSON object'}), 400

    schema_version = payload.get('schema_version')

    if schema_version is None:
        # Legacy v1: treat the entire payload as a flat env-var dict.
        logger.info("import-config: no schema_version — treating as v1 legacy format")
        integrations = _integrations_from_v1(payload)

    elif schema_version == 2:
        integrations = payload.get('integrations', {})
        if not isinstance(integrations, dict):
            return jsonify({'error': '"integrations" must be an object'}), 400
        for svc, cfg in integrations.items():
            if not isinstance(cfg, dict):
                return jsonify({'error': f'Integration config for "{svc}" must be an object'}), 400

    else:
        return jsonify({'error': f'Unsupported schema_version: {schema_version}'}), 400

    db = DatabaseManager()
    written = []
    for service, cfg in integrations.items():
        if not isinstance(service, str) or not service:
            continue
        db.set_integration(service, cfg)
        written.append(service)
        logger.info("import-config: wrote integration '%s'", service)

    logger.info("import-config: import complete — %d service(s) written", len(written))
    return jsonify({
        'status': 'success',
        'services_written': written,
        'count': len(written),
    }), 200
