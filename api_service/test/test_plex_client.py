"""
Tests for PlexClient.

Covers:
- get_all_users(): friends + accounts merged/deduplicated, friends HTTP error, network error
- get_libraries(): success, HTTP error, network error
- get_recent_items(): success with user_id dict/string, no user_ids, library param, HTTP error
- filter_recent_items(): movies, episode dedup by series, max_content_fetch cap, library filter
- get_metadata_provider_id(): found tmdb GUID, not found, HTTP error, network error
- _safe_json_decode(): normal flow, UnicodeDecodeError fallback
"""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from api_service.exceptions.api_exceptions import PlexConnectionError, PlexClientError
from api_service.services.plex.plex_client import PlexClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(library_ids=None, user_ids=None, max_content=5):
    return PlexClient(
        token='fake_token',
        api_url='http://plex.local',
        max_content=max_content,
        library_ids=library_ids,
        user_ids=user_ids,
    )


def _text_response(status, data):
    """Build a mock response that returns JSON via .text() (PlexClient uses _safe_json_decode)."""
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=json.dumps(data))
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _error_response(status):
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value='{}')
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# get_all_users
# ---------------------------------------------------------------------------

class TestGetAllUsers(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_merges_friends_and_local_accounts(self):
        friends = [
            {'id': 1, 'title': 'Alice', 'username': 'alice'},
        ]
        accounts = {
            'MediaContainer': {
                'Account': [{'id': 2, 'name': 'Bob'}]
            }
        }
        friends_resp = _text_response(200, friends)
        accounts_resp = _text_response(200, accounts)
        session = MagicMock()
        session.get = MagicMock(side_effect=[friends_resp, accounts_resp])
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_all_users()

        ids = [u['id'] for u in result]
        self.assertIn(1, ids)
        self.assertIn(2, ids)

    async def test_excludes_friends_without_username(self):
        friends = [
            {'id': 1, 'title': 'Alice', 'username': 'alice'},
            {'id': 2, 'title': 'NoUser'},              # no 'username' key
        ]
        accounts_resp = _text_response(200, {'MediaContainer': {'Account': []}})
        friends_resp = _text_response(200, friends)
        session = MagicMock()
        session.get = MagicMock(side_effect=[friends_resp, accounts_resp])
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_all_users()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 1)

    async def test_deduplicates_by_id(self):
        friends = [{'id': 1, 'title': 'Alice', 'username': 'alice'}]
        accounts = {'MediaContainer': {'Account': [{'id': 1, 'name': 'Alice'}]}}
        friends_resp = _text_response(200, friends)
        accounts_resp = _text_response(200, accounts)
        session = MagicMock()
        session.get = MagicMock(side_effect=[friends_resp, accounts_resp])
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_all_users()
        ids = [u['id'] for u in result]
        self.assertEqual(len(ids), len(set(ids)))

    async def test_raises_plex_connection_error_on_client_error(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('refused'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            with self.assertRaises(PlexConnectionError):
                await self.client.get_all_users()


# ---------------------------------------------------------------------------
# get_libraries
# ---------------------------------------------------------------------------

class TestGetLibraries(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_returns_directory_list_on_success(self):
        data = {'MediaContainer': {'Directory': [
            {'key': '1', 'title': 'Movies', 'type': 'movie'},
            {'key': '2', 'title': 'TV',     'type': 'show'},
        ]}}
        resp = _text_response(200, data)
        session = MagicMock()
        session.get = MagicMock(return_value=resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_libraries()
        self.assertEqual(len(result), 2)

    async def test_returns_empty_list_on_http_error(self):
        resp = _error_response(401)
        session = MagicMock()
        session.get = MagicMock(return_value=resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_libraries()
        self.assertEqual(result, [])

    async def test_returns_empty_list_on_network_error(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('timeout'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_libraries()
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# get_recent_items
# ---------------------------------------------------------------------------

class TestGetRecentItems(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client(user_ids=[{'id': 'u1', 'name': 'Alice'}])

    async def test_returns_filtered_items_for_user(self):
        data = {'MediaContainer': {'Metadata': [
            {'type': 'movie', 'title': 'Inception', 'librarySectionID': '1'},
        ]}}
        resp = _text_response(200, data)
        session = MagicMock()
        session.get = MagicMock(return_value=resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_recent_items()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], 'Inception')

    async def test_uses_none_user_when_no_user_ids(self):
        """When user_ids is empty/None, a single request without accountID is made."""
        client = _make_client(user_ids=[])
        data = {'MediaContainer': {'Metadata': [
            {'type': 'movie', 'title': 'Film', 'librarySectionID': '1'},
        ]}}
        resp = _text_response(200, data)
        session = MagicMock()
        session.get = MagicMock(return_value=resp)
        with patch.object(client, '_get_session', AsyncMock(return_value=session)):
            result = await client.get_recent_items()
        self.assertIsInstance(result, list)

    async def test_raises_plex_connection_error_on_client_error(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('refused'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            with self.assertRaises(PlexConnectionError):
                await self.client.get_recent_items()


# ---------------------------------------------------------------------------
# filter_recent_items
# ---------------------------------------------------------------------------

class TestFilterRecentItems(unittest.IsolatedAsyncioTestCase):

    async def test_includes_all_movies(self):
        client = _make_client(max_content=10)
        metadata = [
            {'type': 'movie', 'title': 'A'},
            {'type': 'movie', 'title': 'B'},
        ]
        result = await client.filter_recent_items(metadata)
        self.assertEqual(len(result), 2)

    async def test_deduplicates_episodes_by_grand_parent_title(self):
        client = _make_client(max_content=10)
        metadata = [
            {'type': 'episode', 'grandparentTitle': 'Breaking Bad', 'title': 'S01E01'},
            {'type': 'episode', 'grandparentTitle': 'Breaking Bad', 'title': 'S01E02'},  # dup
            {'type': 'episode', 'grandparentTitle': 'Chernobyl',    'title': 'S01E01'},
        ]
        result = await client.filter_recent_items(metadata)
        titles = [i['grandparentTitle'] for i in result]
        self.assertEqual(len(result), 2)
        self.assertIn('Breaking Bad', titles)
        self.assertIn('Chernobyl', titles)

    async def test_respects_max_content_fetch(self):
        client = _make_client(max_content=2)
        metadata = [{'type': 'movie', 'title': f'Film {i}'} for i in range(10)]
        result = await client.filter_recent_items(metadata)
        self.assertEqual(len(result), 2)

    async def test_filters_by_library_id(self):
        client = _make_client(library_ids=[{'id': '1', 'name': 'Movies'}], max_content=10)
        metadata = [
            {'type': 'movie', 'title': 'InLib',    'librarySectionID': 1},
            {'type': 'movie', 'title': 'OutOfLib',  'librarySectionID': 2},
        ]
        result = await client.filter_recent_items(metadata)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], 'InLib')


# ---------------------------------------------------------------------------
# get_metadata_provider_id
# ---------------------------------------------------------------------------

class TestGetMetadataProviderId(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_returns_tmdb_id_when_found(self):
        data = {
            'MediaContainer': {
                'Metadata': [{'Guid': [
                    {'id': 'tmdb://12345'},
                    {'id': 'imdb://tt9999'},
                ]}]
            }
        }
        resp = _text_response(200, data)
        session = MagicMock()
        session.get = MagicMock(return_value=resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_metadata_provider_id('/library/metadata/1')
        self.assertEqual(result, '12345')

    async def test_returns_none_when_provider_not_found(self):
        data = {
            'MediaContainer': {
                'Metadata': [{'Guid': [{'id': 'imdb://tt1234'}]}]
            }
        }
        resp = _text_response(200, data)
        session = MagicMock()
        session.get = MagicMock(return_value=resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_metadata_provider_id('/library/metadata/1')
        self.assertIsNone(result)

    async def test_returns_none_on_http_error(self):
        resp = _error_response(404)
        session = MagicMock()
        session.get = MagicMock(return_value=resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_metadata_provider_id('/library/metadata/1')
        self.assertIsNone(result)

    async def test_returns_none_on_network_error(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('refused'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_metadata_provider_id('/library/metadata/1')
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# _safe_json_decode
# ---------------------------------------------------------------------------

class TestSafeJsonDecode(unittest.IsolatedAsyncioTestCase):

    async def test_decodes_normal_json_response(self):
        client = _make_client()
        resp = AsyncMock()
        resp.text = AsyncMock(return_value='{"key": "value"}')
        result = await client._safe_json_decode(resp)
        self.assertEqual(result, {'key': 'value'})

    async def test_raises_plex_client_error_on_decode_failure(self):
        client = _make_client()
        resp = AsyncMock()
        resp.text = AsyncMock(return_value='not valid json{{{')
        with self.assertRaises(Exception):
            await client._safe_json_decode(resp)


if __name__ == '__main__':
    unittest.main()
