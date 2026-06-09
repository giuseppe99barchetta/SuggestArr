"""Shared helpers for sanitizing integration configuration payloads.

This module hosts the canonical implementation used both by the database layer
(:class:`api_service.db.database_manager.DatabaseManager`) and the config
export/import service (:mod:`api_service.services.config_service`) so the
per-service allow-listing logic lives in a single, public place.
"""

from typing import Any, Dict


def sanitize_integration_config(service: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Return an integration config safe for generic integrations storage/export.

    For most services the config is passed through verbatim (a shallow copy).
    The ``trakt`` service is allow-listed to only the app-level OAuth credential
    keys so per-user OAuth tokens never leak into the shared integrations store
    or exported snapshots.

    :param service: Integration service name (e.g. ``'trakt'``, ``'jellyfin'``).
    :param config: Raw integration config dict.
    :return: A new dict containing only the keys that are safe to persist/export.
    """
    if service != 'trakt':
        return dict(config)
    return {
        key: value
        for key, value in config.items()
        if key in {'client_id', 'client_secret'}
    }
