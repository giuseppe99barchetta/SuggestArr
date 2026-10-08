"""
Tests for the library-content helpers.

Covers:
- existing_content_to_sets(): item dicts, raw IDs, empty input
- merge_content_sets(): adds IDs per media type, ignores empty input
- load_media_server_content(): Jellyfin/Emby and Plex clients, unknown service
- load_library_content(): media server + Seer merge, each source fails open, snapshot reuse,
  no Seer client, skipped when exclude_downloaded is off
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from api_service.services.library_content import (
    existing_content_to_sets,
    load_library_content,
    load_media_server_content,
    merge_content_sets,
)


def _seer_client(exclude_downloaded=True, available=None):
    seer_client = MagicMock()
    seer_client.exclude_downloaded = exclude_downloaded
    seer_client.get_available_tmdb_ids = AsyncMock(
        return_value=available if available is not None else {'movie': set(), 'tv': set()}
    )
    return seer_client


def _media_client(existing_content):
    client = MagicMock()
    client.existing_content = existing_content
    client.init_existing_content = AsyncMock()
    client.close = AsyncMock()
    return client


class TestExistingContentToSets(unittest.TestCase):

    def test_collects_ids_from_item_dicts_and_raw_values(self):
        result = existing_content_to_sets({
            'movie': [{'tmdb_id': 603}, '155'],
            'tv': [],
        })
        self.assertEqual(result, {'movie': {'603', '155'}})

    def test_returns_empty_dict_for_missing_content(self):
        self.assertEqual(existing_content_to_sets(None), {})


class TestMergeContentSets(unittest.TestCase):

    def test_adds_ids_per_media_type(self):
        target = {'movie': {'1'}}
        result = merge_content_sets(target, {'movie': {2}, 'tv': {'3'}})
        self.assertIs(result, target)
        self.assertEqual(target, {'movie': {'1', '2'}, 'tv': {'3'}})

    def test_ignores_empty_input(self):
        target = {'movie': {'1'}}
        merge_content_sets(target, None)
        merge_content_sets(target, {'tv': set()})
        self.assertEqual(target, {'movie': {'1'}})


class TestLoadMediaServerContent(unittest.IsolatedAsyncioTestCase):

    async def test_jellyfin_library_ids_are_loaded_and_client_closed(self):
        client = _media_client({'movie': [{'tmdb_id': '603'}], 'tv': [{'tmdb_id': '1399'}]})
        with patch('api_service.services.jellyfin.jellyfin_client.JellyfinClient', return_value=client) as cls:
            result = await load_media_server_content({
                'SELECTED_SERVICE': 'jellyfin',
                'JELLYFIN_API_URL': 'http://jf',
                'JELLYFIN_TOKEN': 'token',
                'JELLYFIN_LIBRARIES': [{'id': 'lib1', 'name': 'Movies'}],
            })

        self.assertEqual(result, {'movie': {'603'}, 'tv': {'1399'}})
        cls.assert_called_once_with('http://jf', 'token', 10, [{'id': 'lib1', 'name': 'Movies'}])
        client.close.assert_awaited_once()

    async def test_uses_the_max_content_checks_setting(self):
        client = _media_client({'movie': []})
        with patch('api_service.services.jellyfin.jellyfin_client.JellyfinClient', return_value=client) as cls:
            await load_media_server_content({
                'SELECTED_SERVICE': 'jellyfin',
                'JELLYFIN_API_URL': 'http://jf',
                'JELLYFIN_TOKEN': 'token',
                'MAX_CONTENT_CHECKS': '25',
            })

        cls.assert_called_once_with('http://jf', 'token', 25, [])

    async def test_emby_uses_the_jellyfin_client(self):
        client = _media_client({'movie': [{'tmdb_id': '603'}]})
        with patch('api_service.services.jellyfin.jellyfin_client.JellyfinClient', return_value=client):
            result = await load_media_server_content({'SELECTED_SERVICE': 'emby'})
        self.assertEqual(result, {'movie': {'603'}})

    async def test_plex_library_ids_are_loaded_and_client_closed(self):
        client = _media_client({'movie': [{'tmdb_id': '603'}]})
        with patch('api_service.services.plex.plex_client.PlexClient', return_value=client):
            result = await load_media_server_content({'SELECTED_SERVICE': 'plex'})
        self.assertEqual(result, {'movie': {'603'}})
        client.close.assert_awaited_once()

    async def test_unknown_service_returns_empty(self):
        self.assertEqual(await load_media_server_content({'SELECTED_SERVICE': ''}), {})


class TestLoadLibraryContent(unittest.IsolatedAsyncioTestCase):

    async def test_merges_media_server_and_seer_availability(self):
        seer_client = _seer_client(available={'movie': {'155'}, 'tv': {'1399'}})
        with patch('api_service.services.library_content.load_media_server_content',
                   AsyncMock(return_value={'movie': {'603'}})):
            result = await load_library_content({'SELECTED_SERVICE': 'jellyfin'}, seer_client)

        self.assertEqual(result, {'movie': {'603', '155'}, 'tv': {'1399'}})

    async def test_media_server_failure_falls_back_to_seer(self):
        seer_client = _seer_client(available={'movie': {'155'}, 'tv': set()})
        with patch('api_service.services.library_content.load_media_server_content',
                   AsyncMock(side_effect=TimeoutError())):
            result = await load_library_content({'SELECTED_SERVICE': 'jellyfin'}, seer_client)

        self.assertEqual(result, {'movie': {'155'}})

    async def test_seer_failure_falls_back_to_media_server(self):
        seer_client = _seer_client()
        seer_client.get_available_tmdb_ids = AsyncMock(side_effect=RuntimeError('unexpected'))
        with patch('api_service.services.library_content.load_media_server_content',
                   AsyncMock(return_value={'movie': {'603'}})):
            result = await load_library_content({'SELECTED_SERVICE': 'jellyfin'}, seer_client)

        self.assertEqual(result, {'movie': {'603'}})

    async def test_existing_snapshot_is_used_instead_of_scanning(self):
        seer_client = _seer_client(available={'movie': {'155'}, 'tv': set()})
        snapshot = {'movie': {'603'}}
        with patch('api_service.services.library_content.load_media_server_content', AsyncMock()) as media_load:
            result = await load_library_content({}, seer_client, media_server_content=snapshot)

        media_load.assert_not_awaited()
        self.assertEqual(result, {'movie': {'603', '155'}})
        self.assertEqual(snapshot, {'movie': {'603'}})  # the caller's snapshot is not modified

    async def test_without_seer_client_uses_media_server_only(self):
        with patch('api_service.services.library_content.load_media_server_content',
                   AsyncMock(return_value={'movie': {'603'}})):
            result = await load_library_content({'SELECTED_SERVICE': 'jellyfin'})

        self.assertEqual(result, {'movie': {'603'}})

    async def test_without_seer_client_honours_exclude_downloaded_setting(self):
        with patch('api_service.services.library_content.load_media_server_content', AsyncMock()) as media_load:
            result = await load_library_content({'SELECTED_SERVICE': 'jellyfin', 'EXCLUDE_DOWNLOADED': False})

        self.assertEqual(result, {})
        media_load.assert_not_awaited()

    async def test_skipped_when_exclude_downloaded_is_off(self):
        seer_client = _seer_client(exclude_downloaded=False)
        with patch('api_service.services.library_content.load_media_server_content', AsyncMock()) as media_load:
            result = await load_library_content({'SELECTED_SERVICE': 'jellyfin'}, seer_client)

        self.assertEqual(result, {})
        media_load.assert_not_awaited()
        seer_client.get_available_tmdb_ids.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
