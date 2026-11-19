"""
Tests for DiscoverAutomation's already-in-library handling.

Covers:
- filter_and_request(): titles in the library are skipped, others are requested
- run(): library content is loaded before filtering
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from api_service.jobs.discover_automation import DiscoverAutomation
from api_service.services.seer.seer_client import SeerClient


def _automation(local_content=None):
    automation = DiscoverAutomation()
    automation.job_id = 1
    automation.job_data = {'id': 1, 'name': 'Discover', 'media_type': 'movie'}
    automation.db_manager = MagicMock()
    automation.db_manager.check_request_exists.return_value = False
    automation.repository = MagicMock()
    automation.seer_client = SeerClient('http://seer', 'key', exclude_downloaded=True, exclude_watched=False)
    automation.seer_client.request_media = AsyncMock(return_value=True)
    automation.local_content = local_content or {}
    return automation


class TestDiscoverLibraryExclusion(unittest.IsolatedAsyncioTestCase):

    async def test_titles_in_library_are_not_requested(self):
        automation = _automation(local_content={'movie': {'603'}})
        results = [{'id': 603, 'title': 'The Matrix'}, {'id': 155, 'title': 'The Dark Knight'}]

        requested_count, _ = await automation.filter_and_request(results)

        self.assertEqual(requested_count, 1)
        automation.seer_client.request_media.assert_awaited_once()
        self.assertEqual(automation.seer_client.request_media.await_args.args[1]['id'], 155)

    async def test_dry_run_reports_only_titles_missing_from_library(self):
        automation = _automation(local_content={'movie': {'603'}})
        results = [{'id': 603, 'title': 'The Matrix'}, {'id': 155, 'title': 'The Dark Knight'}]

        requested_count, dry_run_items = await automation.filter_and_request(results, dry_run=True)

        self.assertEqual(requested_count, 1)
        self.assertEqual([item['tmdb_id'] for item in dry_run_items], [155])

    async def test_already_requested_titles_do_not_use_up_max_results(self):
        """Day 2 of a job must not stop at the titles day 1 already requested."""
        automation = _automation()
        automation.job_data['max_results'] = 2
        automation.db_manager.check_request_exists.side_effect = lambda media_type, tmdb_id: tmdb_id in {'1', '2'}
        results = [{'id': i, 'title': str(i)} for i in range(1, 7)]

        requested_count, _ = await automation.filter_and_request(results)

        self.assertEqual(requested_count, 2)
        self.assertEqual([c.args[1]['id'] for c in automation.seer_client.request_media.await_args_list], [3, 4])

    async def test_fetch_scans_the_whole_budget(self):
        automation = _automation()
        automation.job_data.update(max_results=5, filters={})
        automation.tmdb_discover = MagicMock()
        automation.tmdb_discover._normalize_language_code.return_value = None
        automation.tmdb_discover.discover_movies = AsyncMock(return_value=[])

        await automation.fetch_discover_results()

        self.assertEqual(automation.tmdb_discover.discover_movies.await_args.args[1], 100)

    async def test_run_loads_library_content_before_filtering(self):
        automation = _automation()
        automation.env_vars = {'SELECTED_SERVICE': 'jellyfin'}
        automation.tmdb_discover = None
        automation.fetch_discover_results = AsyncMock(return_value=[{'id': 603, 'title': 'The Matrix'}])

        with patch('api_service.jobs.discover_automation.load_library_content',
                   AsyncMock(return_value={'movie': {'603'}})) as load:
            result = await automation.run(dry_run=True)

        load.assert_awaited_once_with(automation.env_vars, automation.seer_client)
        self.assertTrue(result.success)
        self.assertEqual(result.requested_count, 0)
        self.assertEqual(result.dry_run_items, [])


if __name__ == '__main__':
    unittest.main()
