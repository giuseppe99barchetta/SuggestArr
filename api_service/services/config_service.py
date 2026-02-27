"""Service layer for configuration export and import.

Handles serialising the full application configuration (DB integrations +
YAML settings) into a portable snapshot and restoring it on import.  All DB
logic lives here; the route layer only calls these two static methods.
"""

from api_service.config.config import (
    get_default_values,
    load_env_vars,
    save_env_vars,
)
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager

logger = LoggerManager.get_logger(__name__)

# Schema version emitted in every export and validated on import.
CURRENT_VERSION = 2

# Config-YAML keys that are mirrored into the DB integrations table.
# They are exported under "integrations" (from DB) and must NOT appear in
# "settings" as well, to avoid ambiguity on re-import.
_DB_INTEGRATION_KEYS: frozenset = frozenset({
    'TMDB_API_KEY',
    'JELLYFIN_API_URL',
    'JELLYFIN_TOKEN',
    'SEER_API_URL',
    'SEER_TOKEN',
    'SEER_SESSION_TOKEN',
    'OMDB_API_KEY',
    'OPENAI_API_KEY',
    'OPENAI_BASE_URL',
    'LLM_MODEL',
})

# Mapping from DB service/field to flat config key.  Used by
# get_runtime_config() to overlay DB-backed credentials on top of the
# YAML-sourced config so that service clients always see real keys even
# when config.yaml does not contain them (e.g. after a config import).
# Must be kept in sync with _INTEGRATION_TO_FLAT in blueprints/config/routes.py.
_INTEGRATION_TO_FLAT: dict = {
    'tmdb':     {'api_key': 'TMDB_API_KEY'},
    'jellyfin': {'api_url': 'JELLYFIN_API_URL', 'api_key': 'JELLYFIN_TOKEN'},
    'seer':     {'api_url': 'SEER_API_URL', 'api_key': 'SEER_TOKEN',
                 'session_token': 'SEER_SESSION_TOKEN'},
    'omdb':     {'api_key': 'OMDB_API_KEY'},
    'openai':   {'api_key': 'OPENAI_API_KEY', 'base_url': 'OPENAI_BASE_URL', 'model': 'LLM_MODEL'},
}

# All valid top-level setting keys (resolved once at module load).
_VALID_SETTING_KEYS: frozenset = frozenset(get_default_values().keys()) - _DB_INTEGRATION_KEYS


class ConfigService:
    """Static service for exporting and importing the full application config.

    No instances needed – all methods are static/class-level.
    """

    @staticmethod
    def get_runtime_config() -> dict:
        """Return the full runtime configuration merged from YAML and the DB integrations table.

        ``load_env_vars()`` reads config.yaml, which does not contain integration
        API keys (those are stored exclusively in the DB integrations table after
        a config import or initial setup).  This method overlays the DB values on
        top of the YAML config so that service clients (TMDb, Jellyfin, Seer,
        OMDb) always receive real credentials regardless of whether the YAML has
        been updated.

        Only non-empty DB values override the flat dict; YAML-only keys (e.g.
        PLEX_TOKEN) are left untouched.

        Returns:
            dict: Flat configuration dict ready for service client initialisation.
        """
        config = load_env_vars()
        try:
            integrations = DatabaseManager().get_all_integrations()
            for service, field_map in _INTEGRATION_TO_FLAT.items():
                svc_cfg = integrations.get(service) or {}
                for db_field, flat_key in field_map.items():
                    val = svc_cfg.get(db_field)
                    if val:
                        config[flat_key] = val
        except Exception as exc:
            logger.warning("Could not load DB integrations for runtime config: %s", exc)
        return config

    @staticmethod
    def export_config() -> dict:
        """Build a fully-restorable configuration snapshot.

        The snapshot has two sections:
        - ``integrations``: per-service credentials read directly from the DB
          integrations table (api_url, api_key, etc.).  API keys are included
          verbatim – the caller must ensure only admin users receive this.
        - ``settings``: every other configuration value stored in config.yaml
          (filters, scheduling, feature flags, Plex/Trakt credentials, …).

        Returns:
            dict with keys ``version``, ``integrations``, ``settings``.
        """
        db = DatabaseManager()
        integrations = db.get_all_integrations()
        logger.info(
            "Config export: collected %d integration(s): %s",
            len(integrations),
            list(integrations.keys()),
        )

        config = load_env_vars()
        settings = {
            k: v
            for k, v in config.items()
            if k not in _DB_INTEGRATION_KEYS
        }

        return {
            "version": CURRENT_VERSION,
            "integrations": integrations,
            "settings": settings,
        }

    @staticmethod
    def import_config(data: dict) -> None:
        """Restore a configuration snapshot produced by :meth:`export_config`.

        Steps performed:
        1. Validate the ``version`` field.
        2. Upsert each entry in ``integrations`` into the DB integrations table
           (existing rows are updated; new rows are inserted – no table wipe).
        3. Merge ``settings`` into the current config.yaml, restricting to
           known keys and excluding DB-managed integration keys.
        4. Refresh the DB manager so any changed DB connection params take
           effect without a process restart.

        Args:
            data: Parsed JSON body of the import request.

        Raises:
            ValueError: If the version field is missing or unsupported.
        """
        version = data.get("version")
        if version != CURRENT_VERSION:
            raise ValueError(
                f"Unsupported config version: {version!r}. "
                f"Expected {CURRENT_VERSION}."
            )

        db = DatabaseManager()

        # --- 1. Upsert integrations -------------------------------------------
        integrations: dict = data.get("integrations") or {}
        for service, service_cfg in integrations.items():
            if not isinstance(service_cfg, dict):
                logger.warning(
                    "Skipping integration '%s': value is not a dict", service
                )
                continue
            # Log non-sensitive fields only.
            safe = {k: v for k, v in service_cfg.items() if k not in ("api_key", "session_token")}
            logger.info("Importing integration '%s' %s", service, safe)
            db.set_integration(service, service_cfg)

        # --- 2. Restore settings ----------------------------------------------
        settings: dict = data.get("settings") or {}
        if settings:
            current_config = load_env_vars()
            updated_keys = []
            for key in _VALID_SETTING_KEYS:
                if key in settings:
                    current_config[key] = settings[key]
                    updated_keys.append(key)
            logger.info("Restoring %d setting key(s) from import", len(updated_keys))
            save_env_vars(current_config)

        # --- 3. Refresh DB config in case DB connection settings changed ------
        db.refresh_config()
        logger.info("Config import completed successfully")
