import unittest

from test import _verbose_dict_compare
from api_service.config.config import load_env_vars, save_env_vars, get_default_values


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
    }

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
