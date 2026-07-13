import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from api_service.services.integration_sanitizer import sanitize_integration_config

_INTEGRATION_REQUIRED_FIELDS = {
    'jellyfin': ['api_url', 'api_key'],
    'seer': ['api_url', 'api_key'],
    'tmdb': ['api_key'],
    'omdb': ['api_key'],
    'trakt': ['client_id', 'client_secret'],
    'openai': [],
}
class IntegrationMixin:
    def get_integration(self, service: str) -> Optional[dict]:
        """
        Retrieve the stored config for a named service integration.

        Args:
            service: Integration service name (e.g. 'jellyfin', 'seer').

        Returns:
            dict with stored config, or None if no row exists.
        """
        query = "SELECT config_json FROM integrations WHERE service = ?"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if self.db_type in ['mysql', 'mariadb', 'postgres']:
                query = query.replace("?", "%s")
            cursor.execute(query, (service,))
            row = cursor.fetchone()
        if row is None:
            return None
        return self._sanitize_integration_config(service, json.loads(row[0]))

    def get_all_integrations(self) -> dict:
        """
        Retrieve all service integrations from the database.

        Returns:
            dict mapping service name to its config dict.
        """
        query = "SELECT service, config_json FROM integrations"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
        return {
            row[0]: self._sanitize_integration_config(row[0], json.loads(row[1]))
            for row in rows
        }

    def set_integration(self, service: str, config: dict) -> None:
        """
        Insert or replace the config for a named service integration.

        Args:
            service: Integration service name.
            config: Configuration dict to persist as JSON.
        """
        config = self._sanitize_integration_config(service, config)
        config_json = json.dumps(config)
        now = datetime.now(timezone.utc)

        if self.db_type == 'sqlite':
            query = (
                "INSERT OR REPLACE INTO integrations (service, config_json, updated_at) "
                "VALUES (?, ?, ?)"
            )
            params = (service, config_json, now)
        elif self.db_type == 'postgres':
            query = (
                "INSERT INTO integrations (service, config_json, updated_at) VALUES (%s, %s, %s) "
                "ON CONFLICT (service) DO UPDATE SET config_json = EXCLUDED.config_json, "
                "updated_at = EXCLUDED.updated_at"
            )
            params = (service, config_json, now)
        else:  # mysql / mariadb
            query = (
                "INSERT INTO integrations (service, config_json, updated_at) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE config_json = VALUES(config_json), updated_at = VALUES(updated_at)"
            )
            params = (service, config_json, now)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
        # Keep runtime config cache coherent with DB-backed secret updates.
        from api_service.config.config import invalidate_config_cache
        invalidate_config_cache()

    @staticmethod
    def _is_integration_valid(service: str, config: dict) -> bool:
        """
        Return True if *config* contains all required non-empty fields for *service*.

        Args:
            service: Integration service name (e.g. 'jellyfin', 'tmdb').
            config:  Stored config dict retrieved from the integrations table.

        Returns:
            True when every required field is present and non-empty.
        """
        required = _INTEGRATION_REQUIRED_FIELDS.get(service, [])
        return all(config.get(field) for field in required)

    @staticmethod
    def _sanitize_integration_config(service: str, config: dict) -> dict:
        """Return an integration config safe for generic integrations storage.

        Thin delegator to the shared public helper
        :func:`api_service.services.integration_sanitizer.sanitize_integration_config`
        so the allow-listing logic lives in a single place. Retained as a
        backward-compatible alias for existing call sites/tests.
        """
        return sanitize_integration_config(service, config)

    def migrate_integrations_from_config(self) -> None:
        """
        Startup migration: seed or repair the integrations table from config.yaml.

        Rules applied per service:
        - Row does not exist -> insert from config (if config has required fields).
        - Row exists but invalid/empty -> update from config (if config has required fields).
        - Row exists and valid -> leave untouched.

        This is safe to call on every startup.
        """
        env_vars = self._load_env_vars()
        candidates = {
            'jellyfin': {
                'api_url': env_vars.get('JELLYFIN_API_URL', ''),
                'api_key': env_vars.get('JELLYFIN_TOKEN', ''),
            },
            'seer': {
                'api_url': env_vars.get('SEER_API_URL', ''),
                'api_key': env_vars.get('SEER_TOKEN', ''),
                'session_token': env_vars.get('SEER_SESSION_TOKEN'),
            },
            'tmdb': {
                'api_key': env_vars.get('TMDB_API_KEY', ''),
            },
            'omdb': {
                'api_key': env_vars.get('OMDB_API_KEY', ''),
            },
            'trakt': {
                'client_id': env_vars.get('TRAKT_CLIENT_ID', ''),
                'client_secret': env_vars.get('TRAKT_CLIENT_SECRET', ''),
            },
        }

        # AI provider: only seed the DB when YAML already has a key or base_url configured.
        # No required fields are enforced (either api_key for cloud or base_url for local providers).
        _openai_key = env_vars.get('OPENAI_API_KEY', '')
        _openai_base = env_vars.get('OPENAI_BASE_URL', '')
        if _openai_key or _openai_base:
            candidates['openai'] = {
                'api_key': _openai_key,
                'base_url': _openai_base,
                'model': env_vars.get('LLM_MODEL', ''),
            }

        for service, config in candidates.items():
            existing = self.get_integration(service)

            if service == 'trakt' and existing is not None:
                self.set_integration(service, existing)

            if existing is not None and self._is_integration_valid(service, existing):
                self.logger.debug(
                    "Integration '%s' already in DB with valid credentials - skipping migration", service
                )
                continue

            # Check whether config.yaml provides the required fields.
            required = _INTEGRATION_REQUIRED_FIELDS.get(service, [])
            if not all(config.get(field) for field in required):
                self.logger.debug(
                    "Integration '%s': config.yaml missing required fields %s - skipping",
                    service, required,
                )
                continue

            action = "Updating" if existing is not None else "Migrating"
            safe_log = {k: v for k, v in config.items() if k not in (
                'api_key', 'session_token', 'client_secret', 'access_token', 'refresh_token'
            )}
            self.logger.info(
                "%s '%s' credentials from config.yaml -> integrations table %s",
                action, service, safe_log,
            )
            self.set_integration(service, config)

