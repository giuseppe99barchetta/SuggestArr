"""Shared helpers for redacting secrets in configuration export/import."""

from typing import Any, Dict

REDACTED = '***'

INTEGRATION_SECRET_PATTERNS = ('token', 'api_key', 'password', 'secret')

SETTINGS_SECRET_KEYS = frozenset({
    'TMDB_API_KEY', 'OMDB_API_KEY', 'MDBLIST_API_KEY',
    'PLEX_TOKEN', 'JELLYFIN_TOKEN',
    'SEER_TOKEN', 'SEER_USER_PSW', 'SEER_SESSION_TOKEN',
    'DB_PASSWORD',
    'OPENAI_API_KEY',
    'TRAKT_CLIENT_SECRET', 'TRAKT_ACCESS_TOKEN', 'TRAKT_REFRESH_TOKEN',
})

EXPORT_SENSITIVE_DATA_WARNING = (
    'This export contains live credentials (API keys, tokens, and passwords). '
    'Treat the file as sensitive and do not share it.'
)


def is_redacted(value: Any) -> bool:
    """Return True when a value is the export redaction placeholder."""
    return value == REDACTED


def strip_integration_secrets(cfg: dict) -> dict:
    """Return a copy of an integration config with secret fields redacted."""
    return {
        key: REDACTED if any(pattern in key for pattern in INTEGRATION_SECRET_PATTERNS) else value
        for key, value in cfg.items()
    }


def redact_settings(settings: dict) -> dict:
    """Return a copy of settings with known secret keys redacted."""
    return {
        key: (REDACTED if key in SETTINGS_SECRET_KEYS and value else value)
        for key, value in settings.items()
    }


def merge_integration_config(service: str, incoming: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
    """Merge an imported integration config, preserving secrets omitted as redacted."""
    from api_service.services.integration_sanitizer import sanitize_integration_config
    from api_service.services.integration_security import bind_flat_credentials

    if service in ('plex', 'jellyfin', 'seer'):
        prefix = service.upper()
        fields = {'api_url': f'{prefix}_API_URL', 'api_key': f'{prefix}_TOKEN'}
        if service == 'seer':
            fields['session_token'] = 'SEER_SESSION_TOKEN'
        bound = bind_flat_credentials(
            {fields[k]: v for k, v in incoming.items() if k in fields},
            {fields[k]: v for k, v in (existing or {}).items() if k in fields},
        )
        incoming = {**incoming, **{k: bound[v] for k, v in fields.items() if v in bound}}

    merged = dict(existing or {})
    for key, value in incoming.items():
        if not is_redacted(value):
            merged[key] = value
    return sanitize_integration_config(service, merged)
