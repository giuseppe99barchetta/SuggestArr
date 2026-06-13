import os
import json
import tempfile
import unittest
import yaml
from unittest.mock import patch, MagicMock

from test import _verbose_dict_compare
from api_service.config.config import (
    load_env_vars, save_env_vars, get_default_values,
    get_config_values, get_config_sections, get_config_section,
    save_config_section, clear_env_vars, save_session_token, is_setup_complete,
    invalidate_config_cache, INTEGRATION_TO_FLAT,
)
from api_service.db.database_manager import DatabaseManager
from api_service.services import config_service


class TestConfig(unittest.TestCase):

    # This should be kept in sync with mock data for save/load config structure.
    config_data = {
        "CRON_TIMES": "0 4 * * *",
        "FILTER_LANGUAGE": [{"id": "en", "english_name": "English"}],
        "FILTER_GENRES_EXCLUDE": [{"id": 27, "name": "Horror"}, {"id": 10752, "name": "War"}],
        "FILTER_INCLUDE_NO_RATING": "false",
        "FILTER_RELEASE_YEAR": "2000",
        "FILTER_TMDB_MIN_VOTES": "50",
        "FILTER_TMDB_THRESHOLD": "75",
        "FILTER_NUM_SEASONS": 0,
        "REQUEST_FIRST_SEASON_ONLY": False,
        "HONOR_JELLYSEER_DISCOVERY": "false",
        "JELLYFIN_API_URL": "",
        "JELLYFIN_LIBRARIES": [],
        "JELLYFIN_TOKEN": "",
        "MAX_CONTENT_CHECKS": 10,
        "MAX_SIMILAR_MOVIE": 5,
        "MAX_SIMILAR_TV": 2,
        "PLEX_API_URL": "https://totally.legit.url.tld",
        "PLEX_CLIENT_ID": "mock-uuid-1234",
        "PLEX_LIBRARIES": ["1", "2"],
        "PLEX_TOKEN": "7h349fh349fj3",
        "SEARCH_SIZE": 20,
        "SEER_API_URL": "https://overseerr.totally.legit.url.tld",
        "SEER_SESSION_TOKEN": "s%3A1Db_7DWVJ7nU1R_KsGRQWFLxbisV2m4q.RTKKKBwhMWdMJ4VJNrAIngNFmztqnywP5TkctRYB%2B6M",
        "SEER_TOKEN": "",
        "SEER_USER_NAME": "someemail123@somedomain.com",
        "SEER_USER_PSW": "Y.M8d*HUkpds8PXCeMZM",
        "SELECTED_SERVICE": "plex",
        "TMDB_API_KEY": "123abc",
        "SELECTED_USERS": ["1", "2"],
        "FILTER_STREAMING_SERVICES": [{"provider_id": "8", "provider_name": "Netflix"}],
        "FILTER_REGION_PROVIDER": "US",
        "SUBPATH": "/suggestarr",
        "DB_TYPE": "sqlite",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_USER": "postgres",
        "DB_PASSWORD": "password",
        "DB_NAME": "suggestarr",
        "EXCLUDE_DOWNLOADED": "true",
        "EXCLUDE_REQUESTED": "true",
        "SETUP_COMPLETED": "false",
        # Database pool settings
        "DB_MIN_CONNECTIONS": "2",
        "DB_MAX_CONNECTIONS": "10",
        "DB_MAX_IDLE_TIME": "300",
        "DB_MAX_LIFETIME": "3600",
        "DB_CONNECTION_TIMEOUT": "30",
        "DB_RETRY_ATTEMPTS": "3",
        "DB_RETRY_DELAY": "1.0",
        "LOG_LEVEL": "INFO",
        "SEER_ANIME_PROFILE_CONFIG": {},
        "ENABLE_BETA_FEATURES": False,
        "ENABLE_ADVANCED_ALGORITHM": False,
        "ENABLE_SOCIAL_FEATURES": False,
        "ENABLE_DEBUG_MODE": False,
        "ENABLE_PERFORMANCE_MONITORING": False,
        "CACHE_TTL": 24,
        "MAX_CACHE_SIZE": 100,
        "API_TIMEOUT": 30,
        "API_RETRIES": 3,
        "ENABLE_API_CACHING": True,
        "FILTER_MIN_RUNTIME": 0,
        "ENABLE_VISUAL_EFFECTS": False,
        "ENABLE_STATIC_BACKGROUND": False,
        "STATIC_BACKGROUND_COLOR": "#000000",
        "OMDB_API_KEY": "omdb123abc",
        "FILTER_RATING_SOURCE": "TMDB",
        "FILTER_IMDB_THRESHOLD": "7.0",
        "FILTER_IMDB_MIN_VOTES": "1000",
        "OPENAI_API_KEY": "openai123abc",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
        "LLM_MODEL": "gpt-4-0613",
        "TRAKT_CLIENT_ID": "trakt-client-id",
        "TRAKT_CLIENT_SECRET": "trakt-client-secret",
        "TRAKT_ACCESS_TOKEN": "trakt-access-token",
        "TRAKT_REFRESH_TOKEN": "trakt-refresh-token",
        "TRAKT_EXPIRES_AT": 1234567890,
        "SEER_REQUEST_DELAY": 0.5,
        "FILTER_INCLUDE_TVOD": "false",
        "ALLOW_REGISTRATION": False,
        "AUTH_MODE": "enabled",
        "AUTH_TRUSTED_CIDRS": "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,::1/128,fc00::/7",
        "AUTH_BYPASS_USERNAME": "local_admin",
    }

    def setUp(self):
        """Redirect all config I/O to a temporary file so the real config is never touched."""
        self._tmp = tempfile.NamedTemporaryFile(suffix='.yaml', delete=False)
        self._tmp.close()
        self._patch = patch('api_service.config.config.CONFIG_PATH', self._tmp.name)
        self._patch.start()
        self._db_patch = patch('api_service.db.database_manager.DatabaseManager')
        self._db_manager_cls = self._db_patch.start()
        self._config_service_db_patch = patch(
            'api_service.services.config_service.DatabaseManager',
            self._db_manager_cls,
        )
        self._config_service_db_patch.start()
        self._db_manager_cls.return_value.get_all_integrations.return_value = {}
        # _sanitize_integration_config is a pure static helper (no DB I/O); keep
        # the real implementation on the mocked class so config import/export
        # still strips Trakt account tokens as in production.
        self._db_manager_cls._sanitize_integration_config = staticmethod(
            DatabaseManager._sanitize_integration_config
        )
        invalidate_config_cache()

    def tearDown(self):
        invalidate_config_cache()
        self._config_service_db_patch.stop()
        self._db_patch.stop()
        self._patch.stop()
        os.unlink(self._tmp.name)

    def test_save_default_env_vars(self):
        """The default values should be able to be saved/loaded."""
        default_config = {key: default_value() for key, default_value in get_default_values().items()}
        save_env_vars(default_config)
        loaded_config = load_env_vars()
        _verbose_dict_compare(default_config, loaded_config, self.assertEqual)

    def test_save_env_vars(self):
        """Confirms that the backend save and load functions retain the correct types, values, and
        structure."""
        save_env_vars(self.config_data)
        loaded_config = load_env_vars()
        _verbose_dict_compare(self.config_data, loaded_config, self.assertEqual)

    # ------------------------------------------------------------------
    # load_env_vars / _parse_json_fields
    # ------------------------------------------------------------------

    def test_load_env_vars_file_not_exists_returns_defaults(self):
        # lines 56-58: missing file → get_config_values() returned
        os.unlink(self._tmp.name)
        try:
            config = load_env_vars()
            self.assertIsInstance(config, dict)
            self.assertIn('TMDB_API_KEY', config)
        finally:
            open(self._tmp.name, 'w').close()  # recreate for tearDown

    def test_parse_json_fields_parses_valid_json_string(self):
        # lines 37-42: JSON string field is parsed into a Python list
        yaml.safe_dump({'SELECTED_USERS': '["user1", "user2"]'}, open(self._tmp.name, 'w'))
        config = load_env_vars()
        self.assertEqual(config['SELECTED_USERS'], ['user1', 'user2'])

    def test_parse_json_fields_invalid_json_falls_back_to_empty_list(self):
        # lines 43-47: invalid JSON string for a list field → []
        yaml.safe_dump({'SELECTED_USERS': 'not-valid-json{'}, open(self._tmp.name, 'w'))
        config = load_env_vars()
        self.assertEqual(config['SELECTED_USERS'], [])

    def test_load_env_vars_merges_db_integrations_into_flat_config(self):
        yaml.safe_dump({'TMDB_API_KEY': 'file_tmdb'}, open(self._tmp.name, 'w'))
        self._db_manager_cls.return_value.get_all_integrations.return_value = {
            'tmdb': {'api_key': 'db_tmdb'},
            'jellyfin': {'api_url': 'http://jf', 'api_key': 'jf_token'},
            'trakt': {
                'client_id': 'trakt_id',
                'client_secret': 'trakt_secret',
                'access_token': 'trakt_access',
                'refresh_token': 'trakt_refresh',
                'expires_at': 12345,
            },
        }
        config = load_env_vars(force_reload=True)
        self.assertEqual(config['TMDB_API_KEY'], 'db_tmdb')
        self.assertEqual(config['JELLYFIN_API_URL'], 'http://jf')
        self.assertEqual(config['JELLYFIN_TOKEN'], 'jf_token')
        self.assertEqual(config['TRAKT_CLIENT_ID'], 'trakt_id')
        self.assertEqual(config['TRAKT_CLIENT_SECRET'], 'trakt_secret')
        self.assertEqual(config['TRAKT_ACCESS_TOKEN'], '')
        self.assertEqual(config['TRAKT_REFRESH_TOKEN'], '')
        self.assertIsNone(config['TRAKT_EXPIRES_AT'])

    def test_trakt_defaults_and_integration_mapping_are_present(self):
        defaults = get_config_values()
        self.assertEqual(defaults['TRAKT_CLIENT_ID'], '')
        self.assertEqual(defaults['TRAKT_CLIENT_SECRET'], '')
        self.assertEqual(defaults['TRAKT_ACCESS_TOKEN'], '')
        self.assertEqual(defaults['TRAKT_REFRESH_TOKEN'], '')
        self.assertIsNone(defaults['TRAKT_EXPIRES_AT'])
        self.assertEqual(INTEGRATION_TO_FLAT['trakt'], {
            'client_id': 'TRAKT_CLIENT_ID',
            'client_secret': 'TRAKT_CLIENT_SECRET',
        })

    def test_trakt_is_valid_when_client_credentials_are_present(self):
        self.assertTrue(DatabaseManager._is_integration_valid(
            'trakt',
            {'client_id': 'cid', 'client_secret': 'secret'},
        ))
        self.assertFalse(DatabaseManager._is_integration_valid(
            'trakt',
            {'client_id': 'cid', 'client_secret': ''},
        ))

    def test_migrate_integrations_from_config_includes_only_trakt_app_credentials(self):
        manager = object.__new__(DatabaseManager)
        manager.logger = unittest.mock.MagicMock()
        manager.get_integration = unittest.mock.MagicMock(return_value=None)
        manager.set_integration = unittest.mock.MagicMock()

        with patch('api_service.db.database_manager.load_env_vars', return_value={
            'TRAKT_CLIENT_ID': 'cid',
            'TRAKT_CLIENT_SECRET': 'secret',
            'TRAKT_ACCESS_TOKEN': 'access',
            'TRAKT_REFRESH_TOKEN': 'refresh',
            'TRAKT_EXPIRES_AT': 12345,
        }):
            manager.migrate_integrations_from_config()

        manager.set_integration.assert_called_once_with('trakt', {
            'client_id': 'cid',
            'client_secret': 'secret',
        })

    def test_migrate_integrations_from_config_purges_stored_legacy_trakt_tokens(self):
        import api_service.db.database_manager as dm_mod

        real_db_cls = DatabaseManager
        real_db_cls._instance = None
        fd, db_file = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        path_patch = patch.object(dm_mod, 'DB_PATH', db_file)
        env_patch = patch(
            'api_service.db.database_manager.load_env_vars',
            return_value={'DB_TYPE': 'sqlite'},
        )
        path_patch.start()
        env_patch.start()

        try:
            manager = real_db_cls()
            with manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO integrations (service, config_json) VALUES (?, ?)",
                    (
                        'trakt',
                        json.dumps({
                            'client_id': 'cid',
                            'client_secret': 'secret',
                            'access_token': 'legacy-access',
                            'refresh_token': 'legacy-refresh',
                            'expires_at': 12345,
                        }),
                    ),
                )
                conn.commit()

            env_patch.stop()
            env_patch = patch(
                'api_service.db.database_manager.load_env_vars',
                return_value={
                    'TRAKT_CLIENT_ID': 'cid',
                    'TRAKT_CLIENT_SECRET': 'secret',
                    'TRAKT_ACCESS_TOKEN': 'new-access',
                    'TRAKT_REFRESH_TOKEN': 'new-refresh',
                    'TRAKT_EXPIRES_AT': 67890,
                },
            )
            env_patch.start()
            manager.migrate_integrations_from_config()

            with manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT config_json FROM integrations WHERE service = ?", ('trakt',))
                stored = json.loads(cursor.fetchone()[0])

            self.assertEqual(stored, {
                'client_id': 'cid',
                'client_secret': 'secret',
            })
        finally:
            real_db_cls._instance = None
            env_patch.stop()
            path_patch.stop()
            try:
                os.unlink(db_file)
            except FileNotFoundError:
                pass

    def test_config_service_classifies_trakt_keys_as_db_integration_keys(self):
        for key in (
            'TRAKT_CLIENT_ID',
            'TRAKT_CLIENT_SECRET',
        ):
            self.assertIn(key, config_service._DB_INTEGRATION_KEYS)
            self.assertNotIn(key, config_service._VALID_SETTING_KEYS)
        for key in (
            'TRAKT_ACCESS_TOKEN',
            'TRAKT_REFRESH_TOKEN',
            'TRAKT_EXPIRES_AT',
        ):
            self.assertNotIn(key, config_service._DB_INTEGRATION_KEYS)
            self.assertNotIn(key, config_service._VALID_SETTING_KEYS)

    def test_config_export_strips_legacy_trakt_account_tokens_from_integrations(self):
        self._db_manager_cls.return_value.get_all_integrations.return_value = {
            'trakt': {
                'client_id': 'cid',
                'client_secret': 'secret',
                'access_token': 'legacy-access',
                'refresh_token': 'legacy-refresh',
                'expires_at': 12345,
            },
        }

        exported = config_service.ConfigService.export_config()

        self.assertEqual(exported['integrations']['trakt'], {
            'client_id': 'cid',
            'client_secret': 'secret',
        })
        self.assertNotIn('TRAKT_ACCESS_TOKEN', exported['settings'])
        self.assertNotIn('TRAKT_REFRESH_TOKEN', exported['settings'])
        self.assertNotIn('TRAKT_EXPIRES_AT', exported['settings'])

    def test_config_import_strips_trakt_account_tokens_before_writing_integration(self):
        self._db_manager_cls.return_value.get_all_integrations.return_value = {}
        self._db_manager_cls.return_value.refresh_config.return_value = None

        config_service.ConfigService.import_config({
            'version': config_service.CURRENT_VERSION,
            'integrations': {
                'trakt': {
                    'client_id': 'cid',
                    'client_secret': 'secret',
                    'access_token': 'legacy-access',
                    'refresh_token': 'legacy-refresh',
                    'expires_at': 12345,
                },
            },
            'settings': {},
        })

        self._db_manager_cls.return_value.set_integration.assert_called_once_with('trakt', {
            'client_id': 'cid',
            'client_secret': 'secret',
        })

    def test_config_import_log_redacts_secret_like_keys(self):
        self._db_manager_cls.return_value.get_all_integrations.return_value = {}
        self._db_manager_cls.return_value.refresh_config.return_value = None

        with patch.object(config_service, 'logger') as logger:
            config_service.ConfigService.import_config({
                'version': config_service.CURRENT_VERSION,
                'integrations': {
                    'trakt': {
                        'client_id': 'cid',
                        'client_secret': 'secret',
                    },
                },
                'settings': {},
            })

        info_calls = [
            call for call in logger.info.call_args_list
            if call.args and call.args[0] == "Importing integration '%s' %s"
        ]
        self.assertEqual(len(info_calls), 1)
        safe_payload = info_calls[0].args[2]
        self.assertEqual(safe_payload['client_id'], 'cid')
        self.assertEqual(safe_payload['client_secret'], '***')

    def test_config_export_import_media_users_roundtrip(self):
        import api_service.db.database_manager as dm_mod

        real_db_cls = DatabaseManager
        real_db_cls._instance = None
        fd, db_file = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        path_patch = patch.object(dm_mod, 'DB_PATH', db_file)
        env_patch = patch(
            'api_service.db.database_manager.load_env_vars',
            return_value={'DB_TYPE': 'sqlite'},
        )
        config_db_patch = patch(
            'api_service.services.config_service.DatabaseManager',
            real_db_cls,
        )
        path_patch.start()
        env_patch.start()
        config_db_patch.start()

        try:
            manager = real_db_cls()
            identity = manager.upsert_media_user_identity('jellyfin', 'jf-1', 'alice')
            link_id = manager.upsert_trakt_account_link(
                media_user_identity_id=identity['id'],
                trakt_user_id='t-1',
                trakt_username='trakt_alice',
                token_source='manual_oauth',
                status='connected',
            )
            manager.upsert_trakt_oauth_tokens(
                link_id, 'access-token', 'refresh-token', 1234567890,
            )
            manager.upsert_trakt_source(
                media_user_identity_id=identity['id'],
                source_type='watched_history',
                source_key='watched_history',
                enabled=True,
                use_as_seed=True,
                use_as_exclusion=False,
            )

            exported = config_service.ConfigService.export_config()
            self.assertEqual(len(exported['media_users']), 1)

            real_db_cls._instance = None
            manager = real_db_cls()
            config_service.ConfigService.import_config(exported)

            restored = manager.get_media_user_identity('jellyfin', 'jf-1')
            self.assertEqual(restored['external_username'], 'alice')
            link = manager.get_trakt_account_link(restored['id'])
            self.assertEqual(link['trakt_username'], 'trakt_alice')
            tokens = manager.get_trakt_oauth_tokens(link['id'])
            self.assertEqual(tokens['access_token'], 'access-token')
            sources = manager.get_trakt_sources(restored['id'])
            self.assertEqual(len(sources), 1)
            self.assertFalse(sources[0]['use_as_exclusion'])
        finally:
            real_db_cls._instance = None
            config_db_patch.stop()
            env_patch.stop()
            path_patch.stop()
            try:
                os.unlink(db_file)
            except FileNotFoundError:
                pass

    def test_config_status_exposes_trakt_app_configured_without_secret_values(self):
        from api_service.blueprints.config.routes import config_bp
        from flask import Flask

        app = Flask(__name__)
        app.register_blueprint(config_bp, url_prefix='/api/config')
        db = MagicMock()
        db.get_all_integrations.return_value = {
            'trakt': {'client_id': 'cid', 'client_secret': 'secret'},
        }

        with patch('api_service.blueprints.config.routes.load_env_vars', return_value={
            'TMDB_API_KEY': 'tmdb',
            'SELECTED_SERVICE': 'trakt',
            'DB_TYPE': 'sqlite',
        }), patch('api_service.blueprints.config.routes.DatabaseManager', return_value=db):
            response = app.test_client().get('/api/config/status')

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body['trakt_app_configured'])
        self.assertNotIn('TRAKT_CLIENT_ID', body)
        self.assertNotIn('TRAKT_CLIENT_SECRET', body)

    def test_load_env_vars_cache_is_used_until_invalidated(self):
        self._db_manager_cls.return_value.get_all_integrations.return_value = {
            'tmdb': {'api_key': 'first_key'},
        }
        first = load_env_vars(force_reload=True)
        self.assertEqual(first['TMDB_API_KEY'], 'first_key')

        self._db_manager_cls.return_value.get_all_integrations.return_value = {
            'tmdb': {'api_key': 'second_key'},
        }
        cached = load_env_vars()
        self.assertEqual(cached['TMDB_API_KEY'], 'first_key')

        invalidate_config_cache()
        refreshed = load_env_vars()
        self.assertEqual(refreshed['TMDB_API_KEY'], 'second_key')

    # ------------------------------------------------------------------
    # get_config_values
    # ------------------------------------------------------------------

    def test_get_config_values_resolves_all_defaults(self):
        # lines 156-160: lambdas are called and result is a plain dict
        values = get_config_values()
        self.assertIsInstance(values, dict)
        self.assertIn('TMDB_API_KEY', values)
        self.assertIsInstance(values['TMDB_API_KEY'], str)

    # ------------------------------------------------------------------
    # save_env_vars edge cases
    # ------------------------------------------------------------------

    def test_save_env_vars_invalid_cron_raises_value_error(self):
        # lines 171-173: non-preset, non-valid cron string → ValueError
        config = {key: val() for key, val in get_default_values().items()}
        config['CRON_TIMES'] = 'not_a_cron_expr'
        with self.assertRaises(ValueError):
            save_env_vars(config)

    def test_save_env_vars_creates_config_file_when_missing(self):
        # lines 183-187: file doesn't exist → created before writing
        os.unlink(self._tmp.name)
        config = {key: val() for key, val in get_default_values().items()}
        save_env_vars(config)
        self.assertTrue(os.path.exists(self._tmp.name))

    # ------------------------------------------------------------------
    # clear_env_vars
    # ------------------------------------------------------------------

    def test_clear_env_vars_removes_existing_file(self):
        # lines 203-210: file exists → os.remove() is called
        config = {key: val() for key, val in get_default_values().items()}
        save_env_vars(config)
        self.assertTrue(os.path.exists(self._tmp.name))
        clear_env_vars()
        self.assertFalse(os.path.exists(self._tmp.name))
        open(self._tmp.name, 'w').close()  # recreate for tearDown

    def test_clear_env_vars_is_noop_when_file_missing(self):
        # lines 203-206: file doesn't exist → no error raised
        os.unlink(self._tmp.name)
        try:
            clear_env_vars()  # must not raise
        finally:
            open(self._tmp.name, 'w').close()  # recreate for tearDown

    # ------------------------------------------------------------------
    # save_session_token
    # ------------------------------------------------------------------

    def test_save_session_token_writes_token_to_config(self):
        # lines 213-221: token is persisted and original keys are preserved
        yaml.safe_dump({'TMDB_API_KEY': 'mykey'}, open(self._tmp.name, 'w'))
        save_session_token('my_session_token')
        with open(self._tmp.name, 'r') as f:
            loaded = yaml.safe_load(f)
        self.assertEqual(loaded['SEER_SESSION_TOKEN'], 'my_session_token')
        self.assertEqual(loaded.get('TMDB_API_KEY'), 'mykey')

    # ------------------------------------------------------------------
    # get_config_sections / get_config_section / save_config_section
    # ------------------------------------------------------------------

    def test_get_config_sections_returns_expected_top_level_keys(self):
        # line 227: function body is executed
        sections = get_config_sections()
        self.assertIn('services', sections)
        self.assertIn('database', sections)
        self.assertIn('content_filters', sections)
        self.assertIn('advanced', sections)

    def test_get_config_section_returns_section_keys(self):
        # lines 261-268: valid section name → dict with section keys
        config = {key: val() for key, val in get_default_values().items()}
        save_env_vars(config)
        section = get_config_section('database')
        self.assertIn('DB_TYPE', section)

    def test_get_config_section_invalid_raises_value_error(self):
        # lines 261-263: unknown section → ValueError
        with self.assertRaises(ValueError):
            get_config_section('nonexistent_section')

    def test_save_config_section_updates_only_section_keys(self):
        # lines 278-298: only section keys are updated, rest preserved
        config = {key: val() for key, val in get_default_values().items()}
        config['TMDB_API_KEY'] = 'original_key'
        save_env_vars(config)
        save_config_section('services', {'TMDB_API_KEY': 'updated_key'})
        updated = load_env_vars()
        self.assertEqual(updated['TMDB_API_KEY'], 'updated_key')

    def test_save_config_section_invalid_raises_value_error(self):
        # lines 278-280: unknown section → ValueError
        with self.assertRaises(ValueError):
            save_config_section('nonexistent_section', {})

    # ------------------------------------------------------------------
    # is_setup_complete
    # ------------------------------------------------------------------

    def test_is_setup_complete_plex_all_fields_present(self):
        # lines 320-326: plex branch checks PLEX_TOKEN and PLEX_API_URL
        config = {
            'TMDB_API_KEY': 'key', 'SELECTED_SERVICE': 'plex',
            'PLEX_TOKEN': 'tok', 'PLEX_API_URL': 'http://plex',
            'DB_TYPE': 'sqlite',
        }
        self.assertTrue(is_setup_complete(config))

    def test_is_setup_complete_plex_missing_token_returns_false(self):
        config = {
            'TMDB_API_KEY': 'key', 'SELECTED_SERVICE': 'plex',
            'PLEX_TOKEN': '', 'PLEX_API_URL': 'http://plex',
            'DB_TYPE': 'sqlite',
        }
        self.assertFalse(is_setup_complete(config))

    def test_is_setup_complete_jellyfin_all_fields_present(self):
        # lines 326-330: jellyfin/emby branch
        config = {
            'TMDB_API_KEY': 'key', 'SELECTED_SERVICE': 'jellyfin',
            'JELLYFIN_API_URL': 'http://jf', 'JELLYFIN_TOKEN': 'tok',
            'DB_TYPE': 'sqlite',
        }
        self.assertTrue(is_setup_complete(config))

    def test_is_setup_complete_non_sqlite_db_incomplete_returns_false(self):
        # lines 333-342: non-sqlite DB requires DB_HOST, DB_PORT, etc.
        config = {
            'TMDB_API_KEY': 'key', 'SELECTED_SERVICE': 'jellyfin',
            'JELLYFIN_API_URL': 'http://jf', 'JELLYFIN_TOKEN': 'tok',
            'DB_TYPE': 'postgres',
            # missing DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
        }
        self.assertFalse(is_setup_complete(config))

    def test_is_setup_complete_loads_from_file_when_config_data_is_none(self):
        # lines 310-311: config_data=None → load_env_vars() is called
        config = {key: val() for key, val in get_default_values().items()}
        config.update({
            'TMDB_API_KEY': 'key', 'SELECTED_SERVICE': 'plex',
            'PLEX_TOKEN': 'tok', 'PLEX_API_URL': 'http://x',
        })
        save_env_vars(config)
        result = is_setup_complete(None)
        self.assertTrue(result)
