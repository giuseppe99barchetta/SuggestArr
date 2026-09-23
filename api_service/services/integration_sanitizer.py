"""Shared helpers for sanitizing integration configuration payloads.

This module hosts the canonical implementation used both by the database layer
(:class:`api_service.db.database_manager.DatabaseManager`) and the config
export/import service (:mod:`api_service.services.config_service`) so the
per-service allow-listing logic lives in a single, public place.
"""

from typing import Any, Dict

# Simkl's entry omits client_secret deliberately: the PIN flow never uses one,
# so a secret arriving in a config payload is either a mistake or an attempt to
# get an unused credential persisted, and either way it should be dropped.
_APP_CREDENTIAL_KEYS = {
    'trakt': {'client_id', 'client_secret'},
    'simkl': {'client_id'},
}


def sanitize_integration_config(service: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Return an integration config safe for generic integrations storage/export.

    For most services the config is passed through verbatim (a shallow copy).
    The ``trakt`` and ``simkl`` services are allow-listed to only their
    app-level credential keys so per-user OAuth tokens never leak into the
    shared integrations store or exported snapshots.

    :param service: Integration service name (e.g. ``'trakt'``, ``'jellyfin'``).
    :param config: Raw integration config dict.
    :return: A new dict containing only the keys that are safe to persist/export.
    """
    allowed = _APP_CREDENTIAL_KEYS.get(service)
    if allowed is None:
        return dict(config)
    return {key: value for key, value in config.items() if key in allowed}
