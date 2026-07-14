import unittest
from unittest.mock import patch

from api_service.blueprints.tmdb import routes


class TestTmdbRouteCache(unittest.TestCase):
    def setUp(self):
        routes.clear_cache()

    def tearDown(self):
        routes.clear_cache()

    @patch.object(routes, 'load_env_vars', return_value={
        'ENABLE_API_CACHING': True,
        'CACHE_TTL': 1,
        'MAX_CACHE_SIZE': 1,
    })
    def test_cache_expires_and_evicts_oldest_entries(self, _config):
        with patch.object(routes.time, 'time', return_value=100):
            routes._cache_set('first', {'value': 'x' * 600_000})
            routes._cache_set('second', {'value': 'y' * 600_000})
            self.assertIsNone(routes._cache_get('first'))
            self.assertIsNotNone(routes._cache_get('second'))

        with patch.object(routes.time, 'time', return_value=3701):
            self.assertIsNone(routes._cache_get('second'))

    @patch.object(routes, 'load_env_vars', return_value={
        'ENABLE_API_CACHING': False,
        'CACHE_TTL': 24,
        'MAX_CACHE_SIZE': 100,
    })
    def test_disabled_cache_does_not_store_entries(self, _config):
        routes._cache_set('key', {'value': 1})
        self.assertIsNone(routes._cache_get('key'))
        self.assertEqual(len(routes._cache), 0)


if __name__ == '__main__':
    unittest.main()
