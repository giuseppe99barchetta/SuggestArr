"""Integration tests for watched-media editing against a real SQLite database."""
import os
import tempfile
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


if __name__ == '__main__':
    unittest.main()
