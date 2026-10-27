import unittest
from datetime import datetime
from unittest.mock import patch

from api_service.jobs import cleanup_automation


class TestCleanupAutomationCutoff(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_cutoff_uses_current_timestamp_format(self):
        class FakeDB:
            cutoff = None
            updates = []

            def get_cleanup_settings(self):
                return {"enabled": True, "dry_run": True, "grace_days": 1}

            def get_suggestarr_requests_older_than(self, cutoff):
                FakeDB.cutoff = cutoff
                return []

            def update_cleanup_settings(self, **kwargs):
                FakeDB.updates.append(kwargs)

        fixed_now = datetime(2026, 5, 25, 12, 34, 56)

        class FixedDatetime:
            @staticmethod
            def utcnow():
                return fixed_now

        with patch.object(cleanup_automation, "DatabaseManager", return_value=FakeDB()), \
             patch.object(cleanup_automation.ConfigService, "get_runtime_config", return_value={
                 "SELECTED_SERVICE": "plex",
                 "PLEX_API_URL": "http://plex.local",
                 "PLEX_TOKEN": "token",
             }), \
             patch.object(cleanup_automation, "datetime", FixedDatetime):
            result = await cleanup_automation.execute_cleanup_job()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(FakeDB.cutoff, "2026-05-24 12:34:56")
        self.assertNotIn("T", FakeDB.cutoff)
        self.assertEqual(FakeDB.updates[-1]["last_run_at"], "2026-05-25 12:34:56")


class TestCleanupAbortsWhenFavoritesUnreadable(unittest.IsolatedAsyncioTestCase):
    async def test_favorites_error_deletes_nothing(self):
        deleted = []

        class FakeDB:
            updates = []

            def get_cleanup_settings(self):
                return {"enabled": True, "dry_run": False, "grace_days": 1}

            def get_suggestarr_requests_older_than(self, cutoff):
                return [{"tmdb_id": "603", "media_type": "movie", "title": "The Matrix"}]

            def update_cleanup_settings(self, **kwargs):
                FakeDB.updates.append(kwargs)

            def add_cleanup_log(self, **kwargs):
                deleted.append(kwargs)

        class FakeResponse:
            status = 500

            async def text(self):
                return "boom"

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        class FakeSession:
            def get(self, *args, **kwargs):
                return FakeResponse()

        class FakeJellyfin:
            api_url, headers, REQUEST_TIMEOUT, libraries = "http://jf", {}, 5, []

            def __init__(self, *args, **kwargs):
                import logging
                self.logger = logging.getLogger("test")

            async def get_all_library_items(self):
                return {"movie": [{"tmdb_id": "603"}]}

            async def _get_session(self):
                return FakeSession()

            async def close(self):
                pass

        with patch.object(cleanup_automation, "DatabaseManager", return_value=FakeDB()),              patch.object(cleanup_automation, "JellyfinClient", FakeJellyfin),              patch.object(cleanup_automation, "SeerClient") as seer,              patch.object(cleanup_automation.ConfigService, "get_runtime_config", return_value={
                 "SELECTED_SERVICE": "jellyfin", "JELLYFIN_API_URL": "http://jf", "JELLYFIN_TOKEN": "t",
                 "SELECTED_USERS": [{"id": "u1", "name": "Ann"}],
             }):
            result = await cleanup_automation.execute_cleanup_job()

        self.assertEqual(result["status"], "error")
        self.assertEqual(deleted, [])
        seer.assert_not_called()
        self.assertEqual(FakeDB.updates[-1]["last_run_status"], "error")


if __name__ == "__main__":
    unittest.main()
