import os
import tempfile
import unittest
import yaml
from unittest.mock import patch

from test import _verbose_dict_compare
from api_service.config.config import (
    load_env_vars, save_env_vars, get_default_values,
    get_config_values, get_config_sections, get_config_section,
    save_config_section, clear_env_vars, save_session_token, is_setup_complete,
)


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
        "HONOR_JELLYSEER_DISCOVERY": "false",
        "JELLYFIN_API_URL": "",
        "JELLYFIN_LIBRARIES": [],
        "JELLYFIN_TOKEN": "",
        "MAX_CONTENT_CHECKS": 10,
        "MAX_SIMILAR_MOVIE": 5,
        "MAX_SIMILAR_TV": 2,
        "PLEX_API_URL": "https://totally.legit.url.tld",
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
        "SEER_REQUEST_DELAY": 0.5,
        "FILTER_INCLUDE_TVOD": "false",
        "ALLOW_REGISTRATION": False,
    }

    def setUp(self):
        """Redirect all config I/O to a temporary file so the real config is never touched."""
        self._tmp = tempfile.NamedTemporaryFile(suffix='.yaml', delete=False)
        self._tmp.close()
        self._patch = patch('api_service.config.config.CONFIG_PATH', self._tmp.name)
        self._patch.start()

    def tearDown(self):
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
