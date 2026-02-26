"""
Tests for SeerClient.

Covers:
- _get_auth_headers(): api-key vs cookie mode
- _make_request(): success, 403 quota, 403 login-retry, 404 retry, client error
- login(): success with cookie, non-200 failure
- get_all_users(): success, None data
- get_total_request(): success, None data
- check_already_requested(): exclude_requested=True/False, found/not-found, exception
- check_already_downloaded(): found, not found, None local_content, exclude=False
- _apply_profile_config(): applies all keys, tv languageProfileId, empty profile
- _build_seer_payload(): movie / tv (all/numbered seasons), anime key, private meta-keys present
- request_media(): duplicate pending, already in DB, new enqueue
- submit_queued_request(): success (strips private keys), failure
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from api_service.services.jellyseer.seer_client import SeerClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(**kwargs):
    defaults = dict(
        api_url='http://seer.local',
        api_key='fake_key',
        seer_user_name='admin',
        seer_password='secret',
    )
    defaults.update(kwargs)
    return SeerClient(**defaults)


def _mock_response(status=200, json_data=None, cookies=None):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data if json_data is not None else {})
    resp.cookies = cookies or {}
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _mock_session(response=None):
    session = MagicMock()
    session.request = MagicMock(return_value=response or _mock_response())
    session.post = MagicMock(return_value=response or _mock_response())
    return session


# ---------------------------------------------------------------------------
# _get_auth_headers
# ---------------------------------------------------------------------------

class TestGetAuthHeaders(unittest.TestCase):

    def test_returns_api_key_header_when_not_using_cookie(self):
        client = _make_client()
        headers, cookies = client._get_auth_headers(use_cookie=False)
        self.assertIn('X-Api-Key', headers)
        self.assertEqual(headers['X-Api-Key'], 'fake_key')
        self.assertEqual(cookies, {})

    def test_returns_cookie_when_session_token_present(self):
        client = _make_client(session_token='tok123')
        headers, cookies = client._get_auth_headers(use_cookie=True)
        self.assertNotIn('X-Api-Key', headers)
        self.assertEqual(cookies.get('connect.sid'), 'tok123')

    def test_no_cookie_header_when_no_session_token(self):
        client = _make_client()
        headers, cookies = client._get_auth_headers(use_cookie=True)
        self.assertEqual(cookies, {})
        self.assertNotIn('X-Api-Key', headers)


# ---------------------------------------------------------------------------
# _make_request
# ---------------------------------------------------------------------------

class TestMakeRequest(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_returns_json_on_success_200(self):
        payload = {'results': []}
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)), \
             patch('asyncio.sleep', AsyncMock()):
            result = await self.client._make_request('GET', 'api/v1/user')
        self.assertEqual(result, payload)

    async def test_returns_json_on_success_201(self):
        payload = {'id': 42}
        resp = _mock_response(201, payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)), \
             patch('asyncio.sleep', AsyncMock()):
            result = await self.client._make_request('POST', 'api/v1/request', data={'mediaType': 'movie'})
        self.assertEqual(result, payload)

    async def test_returns_none_on_403_quota_exceeded(self):
        resp = _mock_response(403, {'message': 'Request quota exceeded'})
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)), \
             patch('asyncio.sleep', AsyncMock()):
            result = await self.client._make_request('POST', 'api/v1/request')
        self.assertIsNone(result)

    async def test_returns_none_after_all_retries_exhausted_on_403(self):
        resp = _mock_response(403, {'message': 'Forbidden'})
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)), \
             patch.object(self.client, 'login', AsyncMock()), \
             patch('asyncio.sleep', AsyncMock()):
            result = await self.client._make_request('POST', 'api/v1/request', retries=2)
        self.assertIsNone(result)

    async def test_returns_none_on_client_error(self):
        session = MagicMock()
        session.request = MagicMock(side_effect=aiohttp.ClientError('refused'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)), \
             patch('asyncio.sleep', AsyncMock()):
            result = await self.client._make_request('GET', 'api/v1/request/count', retries=1)
        self.assertIsNone(result)

    async def test_returns_none_when_all_retries_fail_on_500(self):
        resp = _mock_response(500, {'message': 'Internal Server Error'})
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)), \
             patch('asyncio.sleep', AsyncMock()):
            result = await self.client._make_request('GET', 'api/v1/request', retries=1)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------

class TestLogin(unittest.IsolatedAsyncioTestCase):

    async def test_sets_session_token_on_success(self):
        cookie_mock = MagicMock()
        cookie_mock.value = 'session_xyz'

        resp = AsyncMock()
        resp.status = 200
        resp.cookies = {'connect.sid': cookie_mock}
        resp.__aenter__ = AsyncMock(return_value=resp)
        resp.__aexit__ = AsyncMock(return_value=False)

        session = MagicMock()
        session.post = MagicMock(return_value=resp)
        client = _make_client()

        with patch.object(client, '_get_session', AsyncMock(return_value=session)):
            await client.login()

        self.assertEqual(client.session_token, 'session_xyz')
        self.assertTrue(client.is_logged_in)

    async def test_does_not_set_token_on_non_200(self):
        resp = AsyncMock()
        resp.status = 401
        resp.cookies = {}
        resp.__aenter__ = AsyncMock(return_value=resp)
        resp.__aexit__ = AsyncMock(return_value=False)

        session = MagicMock()
        session.post = MagicMock(return_value=resp)
        client = _make_client()

        with patch.object(client, '_get_session', AsyncMock(return_value=session)):
            await client.login()

        self.assertFalse(client.is_logged_in)
        self.assertIsNone(client.session_token)


# ---------------------------------------------------------------------------
# get_all_users
# ---------------------------------------------------------------------------

class TestGetAllUsers(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_returns_formatted_user_list(self):
        api_payload = {
            'results': [
                {'id': 1, 'displayName': 'Alice', 'email': 'a@example.com', 'plexUsername': None, 'jellyfinUsername': None},
                {'id': 2, 'jellyfinUsername': 'bob',  'email': 'b@example.com', 'plexUsername': None},
            ]
        }
        with patch.object(self.client, '_make_request', AsyncMock(return_value=api_payload)):
            result = await self.client.get_all_users()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['id'], 1)
        self.assertEqual(result[0]['name'], 'Alice')

    async def test_returns_empty_list_when_no_data(self):
        with patch.object(self.client, '_make_request', AsyncMock(return_value=None)):
            result = await self.client.get_all_users()
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# get_total_request
# ---------------------------------------------------------------------------

class TestGetTotalRequest(unittest.IsolatedAsyncioTestCase):

    async def test_returns_total_count(self):
        client = _make_client()
        with patch.object(client, '_make_request', AsyncMock(return_value={'total': 42})):
            total = await client.get_total_request()
        self.assertEqual(total, 42)

    async def test_returns_zero_when_none_response(self):
        client = _make_client()
        with patch.object(client, '_make_request', AsyncMock(return_value=None)):
            total = await client.get_total_request()
        self.assertEqual(total, 0)


# ---------------------------------------------------------------------------
# check_already_requested
# ---------------------------------------------------------------------------

class TestCheckAlreadyRequested(unittest.IsolatedAsyncioTestCase):

    async def test_returns_true_when_found_in_db(self):
        client = _make_client()
        with patch('api_service.services.jellyseer.seer_client.DatabaseManager') as MockDB:
            MockDB.return_value.check_request_exists.return_value = True
            result = await client.check_already_requested('12345', 'movie')
        self.assertTrue(result)

    async def test_returns_false_when_not_in_db(self):
        client = _make_client()
        with patch('api_service.services.jellyseer.seer_client.DatabaseManager') as MockDB:
            MockDB.return_value.check_request_exists.return_value = False
            result = await client.check_already_requested('12345', 'movie')
        self.assertFalse(result)

    async def test_returns_false_on_exception(self):
        client = _make_client()
        with patch('api_service.services.jellyseer.seer_client.DatabaseManager') as MockDB:
            MockDB.return_value.check_request_exists.side_effect = Exception('db error')
            result = await client.check_already_requested('12345', 'movie')
        self.assertFalse(result)

    async def test_returns_false_when_exclude_requested_is_false(self):
        client = _make_client(exclude_watched=False)
        # DB should not be called
        with patch('api_service.services.jellyseer.seer_client.DatabaseManager') as MockDB:
            result = await client.check_already_requested('12345', 'movie')
        MockDB.return_value.check_request_exists.assert_not_called()
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# check_already_downloaded
# ---------------------------------------------------------------------------

class TestCheckAlreadyDownloaded(unittest.IsolatedAsyncioTestCase):

    async def test_returns_true_when_tmdb_id_matches(self):
        client = _make_client(exclude_downloaded=True)
        local_content = {'movie': [{'tmdb_id': '999'}]}
        result = await client.check_already_downloaded('999', 'movie', local_content)
        self.assertTrue(result)

    async def test_returns_false_when_no_match(self):
        client = _make_client(exclude_downloaded=True)
        local_content = {'movie': [{'tmdb_id': '111'}]}
        result = await client.check_already_downloaded('999', 'movie', local_content)
        self.assertFalse(result)

    async def test_returns_false_when_local_content_is_none(self):
        client = _make_client(exclude_downloaded=True)
        result = await client.check_already_downloaded('999', 'movie', None)
        self.assertFalse(result)

    async def test_returns_false_when_exclude_downloaded_is_false(self):
        client = _make_client(exclude_downloaded=False)
        local_content = {'movie': [{'tmdb_id': '999'}]}
        result = await client.check_already_downloaded('999', 'movie', local_content)
        self.assertFalse(result)

    async def test_skips_items_without_tmdb_id_key(self):
        client = _make_client(exclude_downloaded=True)
        local_content = {'movie': [{'name': 'no id'}]}
        result = await client.check_already_downloaded('999', 'movie', local_content)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# _apply_profile_config
# ---------------------------------------------------------------------------

class TestApplyProfileConfig(unittest.TestCase):

    def test_applies_all_supported_keys(self):
        client = _make_client(anime_profile_config={
            'anime_movie': {'serverId': 1, 'profileId': 5, 'rootFolder': '/movies', 'tags': [10]}
        })
        data = {}
        client._apply_profile_config(data, 'anime_movie', 'movie')
        self.assertEqual(data['serverId'], 1)
        self.assertEqual(data['profileId'], 5)
        self.assertEqual(data['rootFolder'], '/movies')
        self.assertEqual(data['tags'], [10])

    def test_applies_language_profile_id_for_tv(self):
        client = _make_client(anime_profile_config={
            'anime_tv': {'languageProfileId': 3}
        })
        data = {}
        client._apply_profile_config(data, 'anime_tv', 'tv')
        self.assertEqual(data['languageProfileId'], 3)

    def test_does_not_apply_language_profile_id_for_movie(self):
        client = _make_client(anime_profile_config={
            'anime_movie': {'languageProfileId': 3}
        })
        data = {}
        client._apply_profile_config(data, 'anime_movie', 'movie')
        self.assertNotIn('languageProfileId', data)

    def test_does_nothing_on_empty_profile(self):
        client = _make_client(anime_profile_config={})
        data = {'mediaType': 'movie'}
        client._apply_profile_config(data, 'anime_movie', 'movie')
        self.assertEqual(data, {'mediaType': 'movie'})


# ---------------------------------------------------------------------------
# _build_seer_payload
# ---------------------------------------------------------------------------

class TestBuildSeerPayload(unittest.TestCase):

    def _movie(self, **kw):
        return {'id': 101, **kw}

    def test_movie_payload_has_no_seasons_key(self):
        client = _make_client()
        payload = client._build_seer_payload('movie', self._movie())
        self.assertNotIn('seasons', payload)
        self.assertEqual(payload['mediaType'], 'movie')
        self.assertEqual(payload['mediaId'], 101)

    def test_tv_payload_seasons_all(self):
        client = _make_client(number_of_seasons='all')
        payload = client._build_seer_payload('tv', {'id': 200})
        self.assertEqual(payload['seasons'], 'all')

    def test_tv_payload_numbered_seasons(self):
        client = _make_client(number_of_seasons='3')
        payload = client._build_seer_payload('tv', {'id': 200})
        self.assertEqual(payload['seasons'], [1, 2, 3])

    def test_private_meta_keys_are_present(self):
        client = _make_client()
        source = {'id': 42}
        user = {'id': 7}
        payload = client._build_seer_payload('movie', self._movie(), source=source, user=user, rationale='test')
        self.assertEqual(payload['_source_id'], 42)
        self.assertEqual(payload['_user_id'], 7)
        self.assertEqual(payload['_rationale'], 'test')

    def test_anime_profile_key_applied(self):
        client = _make_client(anime_profile_config={
            'anime_movie': {'serverId': 9}
        })
        payload = client._build_seer_payload('movie', self._movie(), is_anime=True)
        self.assertEqual(payload['serverId'], 9)

    def test_default_profile_key_applied(self):
        client = _make_client(anime_profile_config={
            'default_movie': {'serverId': 1}
        })
        payload = client._build_seer_payload('movie', self._movie(), is_anime=False)
        self.assertEqual(payload['serverId'], 1)


# ---------------------------------------------------------------------------
# request_media
# ---------------------------------------------------------------------------

class TestRequestMedia(unittest.IsolatedAsyncioTestCase):

    async def test_returns_false_when_already_in_pending(self):
        client = _make_client()
        client.pending_requests.add(('movie', '123'))
        result = await client.request_media('movie', {'id': 123})
        self.assertFalse(result)

    async def test_returns_false_when_already_in_db(self):
        client = _make_client(exclude_watched=True)
        with patch('api_service.services.jellyseer.seer_client.DatabaseManager') as MockDB:
            MockDB.return_value.check_request_exists.return_value = True
            result = await client.request_media('movie', {'id': 456})
        self.assertFalse(result)

    async def test_enqueues_and_returns_true_for_new_request(self):
        client = _make_client(exclude_watched=True)
        user = {'id': 9, 'name': 'Alice'}
        with patch('api_service.services.jellyseer.seer_client.DatabaseManager') as MockDB:
            MockDB.return_value.check_request_exists.return_value = False
            MockDB.return_value.enqueue_request.return_value = True
            result = await client.request_media('movie', {'id': 789}, user=user)
        self.assertTrue(result)
        self.assertIn(('movie', '789'), client.pending_requests)


# ---------------------------------------------------------------------------
# submit_queued_request
# ---------------------------------------------------------------------------

class TestSubmitQueuedRequest(unittest.IsolatedAsyncioTestCase):

    async def test_strips_private_keys_and_returns_true_on_success(self):
        client = _make_client()
        payload = {
            'mediaType': 'movie',
            'mediaId': 101,
            '_source_id': 1,
            '_user_id': 2,
            '_rationale': 'test',
            '_is_anime': False,
            '_media_obj': {},
            '_source_obj': {},
        }
        with patch.object(client, '_make_request', AsyncMock(return_value={'id': 55})) as mock_req:
            result = await client.submit_queued_request(payload)

        self.assertTrue(result)
        sent_data = mock_req.call_args[1]['data']
        for key in sent_data:
            self.assertFalse(key.startswith('_'), f"Private key {key!r} was not stripped")

    async def test_returns_false_on_failure_response(self):
        client = _make_client()
        with patch.object(client, '_make_request', AsyncMock(return_value=None)):
            result = await client.submit_queued_request({'mediaType': 'movie', 'mediaId': 1})
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
