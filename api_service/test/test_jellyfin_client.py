"""
Tests for JellyfinClient.

Covers:
- get_all_users(): success, HTTP error, network error
- get_libraries(): success, HTTP error, network error
- get_all_library_items(): movie/tv buckets, missing tmdb_id, non-Movie/Series items,
  auto-fetch libraries when unconfigured, no libraries, HTTP error, network error
- get_recent_items(): success, series deduplication, max_content_fetch cap,
  404 fallback trigger, empty result, network error
- _fallback_recent_items(): success, HTTP failure, exception
- init_existing_content(): delegates to get_all_library_items
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from api_service.services.jellyfin.jellyfin_client import JellyfinClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(libraries=None, max_content=5):
    """Return a JellyfinClient with minimal required args."""
    return JellyfinClient(
        api_url='http://jellyfin.local',
        token='fake_token',
        max_content=max_content,
        library_ids=libraries,
    )


def _mock_response(status=200, json_data=None, text_data=''):
    """Build a reusable aiohttp response context-manager mock."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.text = AsyncMock(return_value=text_data)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _mock_session(response):
    """Build a mock session whose .get() returns *response*."""
    session = MagicMock()
    session.get = MagicMock(return_value=response)
    return session


# ---------------------------------------------------------------------------
# get_all_users
# ---------------------------------------------------------------------------

class TestGetAllUsers(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_returns_user_list_on_success(self):
        payload = [
            {'Id': 'u1', 'Name': 'Alice', 'Policy': {'IsAdministrator': True}},
            {'Id': 'u2', 'Name': 'Bob',   'Policy': {'IsAdministrator': False}},
        ]
        session = _mock_session(_mock_response(200, payload))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_all_users()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {'id': 'u1', 'name': 'Alice', 'policy': {'IsAdministrator': True}})
        self.assertEqual(result[1], {'id': 'u2', 'name': 'Bob',   'policy': {'IsAdministrator': False}})

    async def test_returns_empty_list_on_http_error(self):
        session = _mock_session(_mock_response(401))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_all_users()
        self.assertEqual(result, [])

    async def test_returns_empty_list_on_client_error(self):
        import aiohttp
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('refused'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_all_users()
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# get_libraries
# ---------------------------------------------------------------------------

class TestGetLibraries(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_returns_libraries_on_success(self):
        payload = [
            {'ItemId': 'lib1', 'Name': 'Movies'},
            {'ItemId': 'lib2', 'Name': 'TV Shows'},
        ]
        session = _mock_session(_mock_response(200, payload))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_libraries()

        self.assertEqual(result, payload)

    async def test_returns_none_on_http_error(self):
        session = _mock_session(_mock_response(403))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_libraries()
        self.assertIsNone(result)

    async def test_returns_none_on_client_error(self):
        import aiohttp
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('timeout'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_libraries()
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# get_all_library_items
# ---------------------------------------------------------------------------

class TestGetAllLibraryItems(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.libraries = [
            {'id': 'lib1', 'name': 'Movies'},
            {'id': 'lib2', 'name': 'TV'},
        ]
        self.client = _make_client(libraries=self.libraries)

    async def test_buckets_movies_and_tv_series(self):
        items_payload = {
            'Items': [
                {'Type': 'Movie',  'ProviderIds': {'Tmdb': '101'}, 'Name': 'Film A'},
                {'Type': 'Series', 'ProviderIds': {'Tmdb': '202'}, 'Name': 'Show B'},
            ]
        }
        resp = _mock_response(200, items_payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_all_library_items()

        # Both libraries return same payload → 2 movies and 2 tv (one per lib)
        self.assertEqual(len(result['movie']), 2)
        self.assertEqual(len(result['tv']), 2)
        self.assertEqual(result['movie'][0]['tmdb_id'], '101')
        self.assertEqual(result['tv'][0]['tmdb_id'], '202')

    async def test_skips_items_without_tmdb_id(self):
        items_payload = {
            'Items': [
                {'Type': 'Movie', 'ProviderIds': {}, 'Name': 'No TMDB'},
                {'Type': 'Movie', 'ProviderIds': {'Tmdb': '999'}, 'Name': 'Has TMDB'},
            ]
        }
        self.client.libraries = [{'id': 'lib1', 'name': 'Movies'}]
        resp = _mock_response(200, items_payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_all_library_items()

        self.assertEqual(len(result['movie']), 1)
        self.assertEqual(result['movie'][0]['tmdb_id'], '999')

    async def test_skips_episode_type_items(self):
        """Episodes come through the Items API but must be excluded from the buckets."""
        items_payload = {
            'Items': [
                {'Type': 'Episode', 'ProviderIds': {'Tmdb': '111'}, 'Name': 'Ep 1'},
                {'Type': 'Movie',   'ProviderIds': {'Tmdb': '222'}, 'Name': 'Movie X'},
            ]
        }
        self.client.libraries = [{'id': 'lib1', 'name': 'Mixed'}]
        resp = _mock_response(200, items_payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_all_library_items()

        self.assertEqual(len(result['movie']), 1)
        self.assertEqual(len(result['tv']), 0)

    async def test_auto_fetches_libraries_when_not_configured(self):
        """When libraries=None the client should call get_libraries() first."""
        raw_libs = [
            {'ItemId': 'libA', 'Name': 'Films'},
        ]
        items_payload = {'Items': [
            {'Type': 'Movie', 'ProviderIds': {'Tmdb': '500'}, 'Name': 'Auto Movie'},
        ]}

        self.client.libraries = None

        # First call → get_libraries; subsequent call → library items
        responses = iter([
            _mock_response(200, raw_libs),     # get_libraries
            _mock_response(200, items_payload), # get_all_library_items for libA
        ])

        def get_side_effect(*args, **kwargs):
            return next(responses)

        session = MagicMock()
        session.get = MagicMock(side_effect=get_side_effect)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_all_library_items()

        self.assertEqual(len(result['movie']), 1)
        self.assertEqual(self.client.libraries, [{'id': 'libA', 'name': 'Films'}])

    async def test_returns_none_when_no_libraries(self):
        self.client.libraries = []
        # get_libraries is not called when libraries is explicitly []
        # but get_all_library_items should guard and return None
        # The method actually checks `if not libraries` after assignment
        result = await self.client.get_all_library_items()
        self.assertIsNone(result)

    async def test_continues_on_non_200_for_a_library(self):
        """A 4xx from one library should be skipped; others still processed."""
        responses = iter([
            _mock_response(500),                                          # lib1 fails
            _mock_response(200, {'Items': [
                {'Type': 'Movie', 'ProviderIds': {'Tmdb': '777'}, 'Name': 'OK Movie'},
            ]}),                                                          # lib2 succeeds
        ])

        def get_side_effect(*args, **kwargs):
            return next(responses)

        session = MagicMock()
        session.get = MagicMock(side_effect=get_side_effect)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_all_library_items()

        self.assertEqual(len(result['movie']), 1)

    async def test_continues_on_client_error_for_a_library(self):
        import aiohttp
        responses = iter([
            aiohttp.ClientError('network down'),                          # lib1 raises
            _mock_response(200, {'Items': [
                {'Type': 'Series', 'ProviderIds': {'Tmdb': '888'}, 'Name': 'Good Show'},
            ]}),                                                          # lib2 ok
        ])

        def get_side_effect(*args, **kwargs):
            r = next(responses)
            if isinstance(r, Exception):
                raise r
            return r

        session = MagicMock()
        session.get = MagicMock(side_effect=get_side_effect)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_all_library_items()

        self.assertEqual(len(result['tv']), 1)


# ---------------------------------------------------------------------------
# get_recent_items
# ---------------------------------------------------------------------------

class TestGetRecentItems(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.libraries = [{'id': 'lib1', 'name': 'Movies'}]
        self.client = _make_client(libraries=self.libraries, max_content=5)
        self.user = {'id': 'user1', 'name': 'Alice'}

    async def test_returns_movies_for_user(self):
        items_payload = {'Items': [
            {'Type': 'Movie', 'Name': 'Inception', 'ProviderIds': {'Imdb': 'tt1375666'}},
            {'Type': 'Movie', 'Name': 'Interstellar', 'ProviderIds': {'Imdb': 'tt0816692'}},
        ]}
        resp = _mock_response(200, items_payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_recent_items(self.user)

        self.assertIn('Movies', result)
        self.assertEqual(len(result['Movies']), 2)

    async def test_deduplicates_episodes_by_series_name(self):
        """Multiple episodes from the same series should count as one entry."""
        items_payload = {'Items': [
            {'Type': 'Episode', 'SeriesName': 'Breaking Bad', 'ProviderIds': {}},
            {'Type': 'Episode', 'SeriesName': 'Breaking Bad', 'ProviderIds': {}},  # duplicate
            {'Type': 'Episode', 'SeriesName': 'Chernobyl',    'ProviderIds': {}},
        ]}
        resp = _mock_response(200, items_payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_recent_items(self.user)

        self.assertEqual(len(result['Movies']), 2)  # Breaking Bad + Chernobyl

    async def test_respects_max_content_fetch(self):
        self.client.max_content_fetch = 2
        items_payload = {'Items': [
            {'Type': 'Movie', 'Name': f'Movie {i}', 'ProviderIds': {}} for i in range(10)
        ]}
        resp = _mock_response(200, items_payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_recent_items(self.user)

        self.assertEqual(len(result['Movies']), 2)

    async def test_triggers_fallback_on_404(self):
        fallback_items = [
            {'Type': 'Movie', 'Name': 'Fallback Movie', 'ProviderIds': {}}
        ]
        resp_404 = _mock_response(404, text_data='not found')
        session = _mock_session(resp_404)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)), \
             patch.object(self.client, '_fallback_recent_items',
                          AsyncMock(return_value=fallback_items)) as mock_fallback:
            result = await self.client.get_recent_items(self.user)

        mock_fallback.assert_awaited_once()
        self.assertEqual(result['Movies'], fallback_items)

    async def test_returns_none_when_all_libraries_fail(self):
        resp = _mock_response(500)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_recent_items(self.user)

        self.assertIsNone(result)

    async def test_handles_client_error_per_library(self):
        import aiohttp
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('timeout'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.get_recent_items(self.user)

        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# _fallback_recent_items
# ---------------------------------------------------------------------------

class TestFallbackRecentItems(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_returns_items_on_success(self):
        items = [{'Type': 'Movie', 'Name': 'Fallback Film', 'ProviderIds': {}}]
        resp = _mock_response(200, {'Items': items})
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client._fallback_recent_items('u1', 'Alice', 'lib1', 'Movies')

        self.assertEqual(result, items)

    async def test_returns_none_on_http_failure(self):
        resp = _mock_response(403, text_data='forbidden')
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client._fallback_recent_items('u1', 'Alice', 'lib1', 'Movies')

        self.assertIsNone(result)

    async def test_returns_none_on_exception(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=Exception('unexpected'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client._fallback_recent_items('u1', 'Alice', 'lib1', 'Movies')

        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# init_existing_content
# ---------------------------------------------------------------------------

class TestInitExistingContent(unittest.IsolatedAsyncioTestCase):

    async def test_populates_existing_content(self):
        client = _make_client()
        expected = {'movie': [{'tmdb_id': '1'}], 'tv': []}
        with patch.object(client, 'get_all_library_items', AsyncMock(return_value=expected)):
            await client.init_existing_content()

        self.assertEqual(client.existing_content, expected)

    async def test_existing_content_is_none_when_no_libraries(self):
        client = _make_client()
        with patch.object(client, 'get_all_library_items', AsyncMock(return_value=None)):
            await client.init_existing_content()

        self.assertIsNone(client.existing_content)


if __name__ == '__main__':
    unittest.main()
