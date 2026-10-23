"""Integration tests for watched-media editing against a real SQLite database."""
import os
import tempfile
from datetime import datetime
import unittest
from unittest.mock import patch

import logging
logging.disable(logging.CRITICAL)


class TestWatchedMediaUpdate(unittest.TestCase):
    """Re-rating and excluding titles keeps their source and stays per identity."""

    def setUp(self):
        import api_service.db.database_manager as dm_mod
        dm_mod.DatabaseManager._instance = None
        fd, self._db_file = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self._path_patch = patch.object(dm_mod, 'DB_PATH', self._db_file)
        self._path_patch.start()
        self._env_patch = patch('api_service.db.database_manager.load_env_vars', return_value={'DB_TYPE': 'sqlite'})
        self._env_patch.start()
        from api_service.db.database_manager import DatabaseManager
        self.db = DatabaseManager()
        self.owner = self.db.upsert_media_user_identity('jellyfin', 'jf-1', 'alice')['id']
        self.other = self.db.upsert_media_user_identity('jellyfin', 'jf-2', 'bob')['id']
        self.item = self.db.upsert_watched_media(self.owner, '27205', 'movie', 'Inception', 2010, 9, source='csv_import')

    def tearDown(self):
        import api_service.db.database_manager as dm_mod
        dm_mod.DatabaseManager._instance = None
        self._path_patch.stop()
        self._env_patch.stop()
        try:
            os.unlink(self._db_file)
        except FileNotFoundError:
            pass

    def test_new_titles_are_not_excluded(self):
        self.assertFalse(self.item['excluded'])

    def test_rating_edit_keeps_csv_source(self):
        updated = self.db.update_watched_media(self.owner, self.item['id'], {'rating': 4})
        self.assertEqual(updated['rating'], 4.0)
        self.assertEqual(updated['source'], 'csv_import')

    def test_rating_can_be_cleared(self):
        updated = self.db.update_watched_media(self.owner, self.item['id'], {'rating': None})
        self.assertIsNone(updated['rating'])

    def test_excluded_title_is_flagged_in_seeds(self):
        self.db.update_watched_media(self.owner, self.item['id'], {'excluded': True})
        seeds = self.db.get_watched_media_seeds(self.owner)
        self.assertEqual(len(seeds), 1)
        self.assertTrue(seeds[0]['excluded'])

    def test_other_identity_cannot_update(self):
        self.assertIsNone(self.db.update_watched_media(self.other, self.item['id'], {'rating': 1}))
        self.assertEqual(self.db.get_watched_media_item(self.owner, '27205', 'movie')['rating'], 9.0)

    def test_invalid_values_are_rejected(self):
        with self.assertRaises(ValueError):
            self.db.update_watched_media(self.owner, self.item['id'], {'rating': 11})
        with self.assertRaises(ValueError):
            self.db.update_watched_media(self.owner, self.item['id'], {'excluded': 'yes'})
        with self.assertRaises(ValueError):
            self.db.update_watched_media(self.owner, self.item['id'], {})


    def test_server_plays_are_stored_once_and_keep_user_edits(self):
        plays = [
            {'tmdb_id': '27205', 'media_type': 'movie', 'title': 'Inception', 'year': 2010,
             'watched_at': datetime(2026, 3, 1, 20, 0)},
            {'tmdb_id': '82728', 'media_type': 'tv', 'title': 'Bluey', 'year': None,
             'watched_at': datetime(2026, 5, 1, 8, 0)},
        ]
        self.assertEqual(self.db.record_server_plays(self.owner, plays), 1)
        self.assertEqual(self.db.record_server_plays(self.owner, plays), 0)
        items = self.db.list_watched_media(self.owner)
        # Newest play first; the CSV row keeps its rating and source.
        self.assertEqual([item['title'] for item in items], ['Bluey', 'Inception'])
        self.assertEqual((items[1]['rating'], items[1]['source']), (9.0, 'csv_import'))
        self.assertEqual(self.db.latest_server_play(self.owner), datetime(2026, 5, 1, 8, 0))
        self.assertEqual(self.db.list_watched_media(self.other), [])

    def test_untouched_server_plays_are_not_seeds_until_rated_or_excluded(self):
        self.db.record_server_plays(self.owner, [{'tmdb_id': '82728', 'media_type': 'tv', 'title': 'Bluey',
                                                  'year': None, 'watched_at': datetime(2026, 5, 1)}])
        self.assertEqual([seed['tmdb_id'] for seed in self.db.get_watched_media_seeds(self.owner)], ['27205'])
        bluey = self.db.get_watched_media_item(self.owner, '82728', 'tv')
        self.db.update_watched_media(self.owner, bluey['id'], {'excluded': True})
        seeds = {seed['tmdb_id']: seed for seed in self.db.get_watched_media_seeds(self.owner)}
        self.assertTrue(seeds['82728']['excluded'])


if __name__ == '__main__':
    unittest.main()
