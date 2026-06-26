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
from api_service.services.config_secrets import (
    EXPORT_SENSITIVE_DATA_WARNING,
    REDACTED,
    is_redacted,
    merge_integration_config,
    redact_settings,
    strip_integration_secrets,
)
from api_service.services.integration_sanitizer import sanitize_integration_config

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
    'TRAKT_CLIENT_ID',
    'TRAKT_CLIENT_SECRET',
})

_TRAKT_ACCOUNT_TOKEN_SETTING_KEYS: frozenset = frozenset({
    'TRAKT_ACCESS_TOKEN',
    'TRAKT_REFRESH_TOKEN',
    'TRAKT_EXPIRES_AT',
})

# All valid top-level setting keys (resolved once at module load).
_VALID_SETTING_KEYS: frozenset = (
    frozenset(get_default_values().keys())
    - _DB_INTEGRATION_KEYS
    - _TRAKT_ACCOUNT_TOKEN_SETTING_KEYS
)

_LOG_SECRET_KEY_FRAGMENTS: tuple = ("token", "api_key", "password", "secret")

_TRAKT_MISSING_TOKENS_ERROR = (
    "Trakt OAuth tokens were not included in this config export. "
    "Re-link the Trakt account."
)


def _sanitize_integration_config(service: str, config: dict) -> dict:
    """Return a copy of an integration config safe for global storage/export.

    Thin wrapper delegating to the canonical public helper
    :func:`api_service.services.integration_sanitizer.sanitize_integration_config`
    so the Trakt-allowlist logic lives in a single place.
    """
    return sanitize_integration_config(service, config)


def _export_media_users(db: DatabaseManager, *, include_secrets: bool = False) -> list:
    """Serialize media-user identities and per-user Trakt data for export.

    Account metadata and source settings are always included.  When OAuth tokens
    exist, ``oauth_tokens`` is always emitted; secret fields are redacted unless
    ``include_secrets`` is True.
    """
    media_users = []
    for identity in db.get_all_media_user_identities():
        entry = {
            "provider": identity["provider"],
            "external_user_id": identity["external_user_id"],
            "external_username": identity.get("external_username"),
        }
        link = db.get_trakt_account_link(identity["id"])
        if not link:
            media_users.append(entry)
            continue

        trakt_entry = {
            "trakt_user_id": link.get("trakt_user_id"),
            "trakt_username": link.get("trakt_username"),
            "token_source": link.get("token_source"),
            "status": link.get("status"),
        }
        tokens = db.get_trakt_oauth_tokens(link["id"])
        if tokens:
            if include_secrets:
                trakt_entry["oauth_tokens"] = {
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    "expires_at": tokens.get("expires_at"),
                }
            else:
                trakt_entry["oauth_tokens"] = {
                    "access_token": REDACTED,
                    "refresh_token": REDACTED,
                    "expires_at": None,
                }
        trakt_entry["sources"] = [
            {
                "source_type": source["source_type"],
                "source_key": source["source_key"],
                "list_id": source.get("list_id"),
                "list_slug": source.get("list_slug"),
                "username": source.get("username"),
                "enabled": source.get("enabled", True),
                "use_as_seed": source.get("use_as_seed", True),
                "use_as_exclusion": source.get("use_as_exclusion", True),
            }
            for source in db.get_trakt_sources(identity["id"])
        ]
        entry["trakt"] = trakt_entry
        media_users.append(entry)
    return media_users


def _import_media_users(db: DatabaseManager, media_users: list) -> None:
    """Restore media-user identities and per-user Trakt data from a snapshot."""
    if not isinstance(media_users, list):
        raise ValueError('"media_users" must be a list')

    for entry in media_users:
        if not isinstance(entry, dict):
            raise ValueError('Each media user entry must be an object')
        provider = entry.get("provider")
        external_user_id = entry.get("external_user_id")
        if not provider or external_user_id is None:
            raise ValueError('Media user entries require provider and external_user_id')

        identity = db.upsert_media_user_identity(
            str(provider), str(external_user_id), entry.get("external_username"),
        )
        trakt = entry.get("trakt")
        if not isinstance(trakt, dict):
            continue

        token_source = trakt.get("token_source") or "manual_oauth"
        requested_status = trakt.get("status") or "connected"
        oauth = trakt.get("oauth_tokens")
        imported_tokens_available = False
        if isinstance(oauth, dict):
            access_token = oauth.get("access_token")
            refresh_token = oauth.get("refresh_token")
            imported_tokens_available = bool(
                access_token and refresh_token
                and not is_redacted(access_token)
                and not is_redacted(refresh_token)
            )

        existing_tokens_available = False
        existing_link = db.get_trakt_account_link(identity["id"])
        if existing_link:
            existing_tokens_available = bool(db.get_trakt_oauth_tokens(existing_link["id"]))

        status = requested_status
        missing_manual_oauth_tokens = (
            token_source == "manual_oauth"
            and requested_status == "connected"
            and not imported_tokens_available
            and not existing_tokens_available
        )
        if missing_manual_oauth_tokens:
            status = "error"

        link_id = db.upsert_trakt_account_link(
            media_user_identity_id=identity["id"],
            trakt_user_id=trakt.get("trakt_user_id"),
            trakt_username=trakt.get("trakt_username"),
            token_source=token_source,
            status=status,
        )

        if imported_tokens_available:
            db.upsert_trakt_oauth_tokens(
                link_id=link_id,
                access_token=oauth.get("access_token"),
                refresh_token=oauth.get("refresh_token"),
                expires_at=oauth.get("expires_at"),
            )
        elif missing_manual_oauth_tokens:
            db.mark_trakt_account_link_error(
                identity["id"], "error", _TRAKT_MISSING_TOKENS_ERROR,
            )

        sources = trakt.get("sources") or []
        if not isinstance(sources, list):
            raise ValueError('Trakt sources must be a list')
        for source in sources:
            if not isinstance(source, dict):
                raise ValueError('Each Trakt source entry must be an object')
            source_type = source.get("source_type")
            source_key = source.get("source_key")
            if not source_type or not source_key:
                raise ValueError('Trakt source entries require source_type and source_key')
            db.upsert_trakt_source(
                media_user_identity_id=identity["id"],
                source_type=source_type,
                source_key=source_key,
                enabled=bool(source.get("enabled", True)),
                use_as_seed=bool(source.get("use_as_seed", True)),
                use_as_exclusion=bool(source.get("use_as_exclusion", True)),
                list_id=source.get("list_id"),
                list_slug=source.get("list_slug"),
                username=source.get("username"),
            )


def _redact_for_log(config: dict) -> dict:
    """Return a copy with secret-like keys redacted for logging."""
    safe = {}
    for key, value in config.items():
        key_lower = str(key).lower()
        if any(fragment in key_lower for fragment in _LOG_SECRET_KEY_FRAGMENTS):
            safe[key] = "***"
        else:
            safe[key] = value
    return safe


class ConfigService:
    """Static service for exporting and importing the full application config.

    No instances needed – all methods are static/class-level.
    """

    @staticmethod
    def get_runtime_config() -> dict:
        """Return the full runtime configuration (YAML + DB integrations merged)."""
        return load_env_vars()

    @staticmethod
    def export_config(*, include_secrets: bool = False) -> dict:
        """Build a configuration snapshot.

        By default, secret values are redacted so the export is safer to share
        for troubleshooting.  Pass ``include_secrets=True`` for a fully
        restorable backup.

        The snapshot has three sections:
        - ``integrations``: per-service credentials from the DB integrations
          table.  Secret fields are redacted unless ``include_secrets`` is True.
        - ``settings``: configuration values from config.yaml, with known
          secret keys redacted by default.
        - ``media_users``: media-user identities with Trakt account metadata
          and source settings.  Per-user OAuth tokens follow ``include_secrets``.

        Args:
            include_secrets: When True, include raw secret values and Trakt
                OAuth tokens.  Defaults to False.

        Returns:
            dict with keys ``version``, ``integrations``, ``settings``,
            ``media_users``, and optionally ``warnings``.
        """
        db = DatabaseManager()
        integrations = {
            service: _sanitize_integration_config(service, cfg)
            for service, cfg in db.get_all_integrations().items()
        }
        if not include_secrets:
            integrations = {
                service: strip_integration_secrets(cfg)
                for service, cfg in integrations.items()
            }
        logger.info(
            "Config export: collected %d integration(s): %s",
            len(integrations),
            list(integrations.keys()),
        )

        config = load_env_vars()
        settings = {
            k: v
            for k, v in config.items()
            if k in _VALID_SETTING_KEYS
        }
        if not include_secrets:
            settings = redact_settings(settings)

        snapshot = {
            "version": CURRENT_VERSION,
            "integrations": integrations,
            "settings": settings,
            "media_users": _export_media_users(db, include_secrets=include_secrets),
        }
        if include_secrets:
            snapshot["warnings"] = [EXPORT_SENSITIVE_DATA_WARNING]
        return snapshot

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

        integrations = data.get("integrations") or {}
        settings = data.get("settings") or {}
        media_users = data.get("media_users") or []
        if not isinstance(integrations, dict):
            raise ValueError('"integrations" must be an object')
        if not isinstance(settings, dict):
            raise ValueError('"settings" must be an object')
        if media_users and not isinstance(media_users, list):
            raise ValueError('"media_users" must be a list')

        db = DatabaseManager()

        # --- 1. Restore settings ----------------------------------------------
        if settings:
            current_config = load_env_vars()
            updated_keys = []
            for key in _VALID_SETTING_KEYS:
                if key in settings and not is_redacted(settings[key]):
                    current_config[key] = settings[key]
                    updated_keys.append(key)
            logger.info("Restoring %d setting key(s) from import", len(updated_keys))
            save_env_vars(current_config)

        # Refresh DB config before DB-backed restores. Imported database
        # settings must take effect before integrations/media users are written.
        db.refresh_config()

        # --- 2. Upsert integrations -------------------------------------------
        for service, service_cfg in integrations.items():
            if not isinstance(service_cfg, dict):
                logger.warning(
                    "Skipping integration '%s': value is not a dict", service
                )
                continue
            service_cfg = _sanitize_integration_config(service, service_cfg)
            existing = db.get_integration(service) or {}
            service_cfg = merge_integration_config(service, service_cfg, existing)
            # Log non-sensitive fields only.
            safe = _redact_for_log(service_cfg)
            logger.info("Importing integration '%s' %s", service, safe)
            db.set_integration(service, service_cfg)

        # --- 3. Restore media users (optional) --------------------------------
        if media_users:
            _import_media_users(db, media_users)

        logger.info("Config import completed successfully")
