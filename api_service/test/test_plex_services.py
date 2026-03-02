"""
Tests for PlexBaseClient, PlexLibraryService, PlexUserService, and PlexAuth.

Covers:
- PlexBaseClient._make_request(): success, HTTP error (raises PlexConnectionError), network errors
- PlexLibraryService.get_libraries(): success, empty Directory, error propagation
- PlexLibraryService.get_library_items(): success, empty Metadata
- PlexLibraryService.filter_libraries_by_type(): known types, unknown type, no filter
- PlexUserService.get_all_users(): success, filters no-username, deduplicates
- PlexUserService.filter_users_by_role(): admins, regular, no filter
- PlexAuth.get_authentication_pin(): returns (id, url)
- PlexAuth.check_authentication(): token found, not found
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from api_service.exceptions.api_exceptions import PlexConnectionError
from api_service.services.plex.base_client import PlexBaseClient
from api_service.services.plex.library_service import PlexLibraryService
from api_service.services.plex.user_service import PlexUserService
from api_service.services.plex.plex_auth import PlexAuth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_json_response(status=200, data=None):
    resp = AsyncMock()
    resp.status = status
    resp.reason = 'OK' if status == 200 else 'Error'
    resp.json = AsyncMock(return_value=data or {})
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _mock_session(response=None):
    session = MagicMock()
    session.get = MagicMock(return_value=response or _mock_json_response())
    return session


# ---------------------------------------------------------------------------
# PlexBaseClient._make_request
# ---------------------------------------------------------------------------

class TestPlexBaseClientMakeRequest(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = PlexBaseClient(token='tok', api_url='http://plex.local')

    async def test_returns_json_on_200(self):
        data = {'key': 'value'}
        resp = _mock_json_response(200, data)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client._make_request('http://plex.local/library/sections')
        self.assertEqual(result, data)

    async def test_raises_plex_connection_error_on_non_200(self):
        resp = _mock_json_response(403)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            with self.assertRaises(PlexConnectionError):
                await self.client._make_request('http://plex.local/library/sections')

    async def test_raises_plex_connection_error_on_client_error(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('refused'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            with self.assertRaises(PlexConnectionError):
                await self.client._make_request('http://plex.local/library/sections')

    async def test_raises_plex_connection_error_on_generic_exception(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=RuntimeError('oops'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            with self.assertRaises(PlexConnectionError):
                await self.client._make_request('http://plex.local/library/sections')


# ---------------------------------------------------------------------------
# PlexLibraryService.get_libraries
# ---------------------------------------------------------------------------

class TestPlexLibraryServiceGetLibraries(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.service = PlexLibraryService(token='tok', api_url='http://plex.local')

    async def test_returns_directory_list_on_success(self):
        dirs = [{'key': '1', 'title': 'Movies', 'type': 'movie'}]
        with patch.object(self.service, '_make_request', AsyncMock(return_value={'Directory': dirs})):
            result = await self.service.get_libraries()
        self.assertEqual(result, dirs)

    async def test_returns_empty_when_no_directory_key(self):
        with patch.object(self.service, '_make_request', AsyncMock(return_value={})):
            result = await self.service.get_libraries()
        self.assertEqual(result, [])

    async def test_propagates_plex_connection_error(self):
        with patch.object(self.service, '_make_request', AsyncMock(side_effect=PlexConnectionError('fail'))):
            with self.assertRaises(PlexConnectionError):
                await self.service.get_libraries()


# ---------------------------------------------------------------------------
# PlexLibraryService.get_library_items
# ---------------------------------------------------------------------------

class TestPlexLibraryServiceGetLibraryItems(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.service = PlexLibraryService(token='tok', api_url='http://plex.local')

    async def test_returns_metadata_items_on_success(self):
        items = [{'title': 'Inception', 'type': 'movie'}]
        with patch.object(self.service, '_make_request', AsyncMock(return_value={'Metadata': items})):
            result = await self.service.get_library_items('1')
        self.assertEqual(result, items)

    async def test_returns_empty_when_no_metadata_key(self):
        with patch.object(self.service, '_make_request', AsyncMock(return_value={})):
            result = await self.service.get_library_items('1')
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# PlexLibraryService.filter_libraries_by_type
# ---------------------------------------------------------------------------

class TestPlexLibraryServiceFilterByType(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.service = PlexLibraryService(token='tok', api_url='http://plex.local')
        self.all_libraries = [
            {'key': '1', 'title': 'Movies',  'type': 'movie'},
            {'key': '2', 'title': 'TV',      'type': 'show'},
            {'key': '3', 'title': 'Music',   'type': 'artist'},
        ]

    async def _setup(self):
        with patch.object(self.service, 'get_libraries', AsyncMock(return_value=self.all_libraries)):
            return self.service

    async def test_returns_all_when_no_filter(self):
        with patch.object(self.service, 'get_libraries', AsyncMock(return_value=self.all_libraries)):
            result = await self.service.filter_libraries_by_type(None)
        self.assertEqual(len(result), 3)

    async def test_filters_by_movie(self):
        with patch.object(self.service, 'get_libraries', AsyncMock(return_value=self.all_libraries)):
            result = await self.service.filter_libraries_by_type('movie')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], 'movie')

    async def test_filters_series_as_show(self):
        with patch.object(self.service, 'get_libraries', AsyncMock(return_value=self.all_libraries)):
            result = await self.service.filter_libraries_by_type('series')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], 'show')

    async def test_returns_empty_for_unknown_type(self):
        with patch.object(self.service, 'get_libraries', AsyncMock(return_value=self.all_libraries)):
            result = await self.service.filter_libraries_by_type('podcast')
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# PlexUserService.get_all_users
# ---------------------------------------------------------------------------

class TestPlexUserServiceGetAllUsers(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.service = PlexUserService(token='tok', api_url='http://plex.local')

    async def test_returns_formatted_users(self):
        data = {
            '_embedded': {
                'Account': [
                    {'id': 1, 'title': 'Alice', 'username': 'alice', 'email': 'a@a.com',
                     'thumb': None, 'realm': 'myplex', 'key': '/users/1'},
                ]
            }
        }
        with patch.object(self.service, '_make_request', AsyncMock(return_value=data)):
            result = await self.service.get_all_users()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 1)
        self.assertEqual(result[0]['username'], 'alice')

    async def test_excludes_users_without_username(self):
        data = {
            '_embedded': {
                'Account': [
                    {'id': 1, 'title': 'Alice', 'username': 'alice', 'email': 'a@a.com',
                     'thumb': None, 'realm': 'myplex', 'key': '/users/1'},
                    {'id': 2, 'title': 'NoUser'},  # no username
                ]
            }
        }
        with patch.object(self.service, '_make_request', AsyncMock(return_value=data)):
            result = await self.service.get_all_users()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 1)

    async def test_deduplicates_by_id(self):
        user = {'id': 1, 'title': 'Alice', 'username': 'alice', 'email': 'a@a.com',
                'thumb': None, 'realm': 'myplex', 'key': '/users/1'}
        data = {'_embedded': {'Account': [user, user]}}
        with patch.object(self.service, '_make_request', AsyncMock(return_value=data)):
            result = await self.service.get_all_users()
        self.assertEqual(len(result), 1)

    async def test_returns_empty_when_no_embedded_key(self):
        with patch.object(self.service, '_make_request', AsyncMock(return_value={})):
            result = await self.service.get_all_users()
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# PlexUserService.filter_users_by_role
# ---------------------------------------------------------------------------

class TestPlexUserServiceFilterByRole(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.service = PlexUserService(token='tok', api_url='http://plex.local')
        self.users = [
            {'id': 1, 'username': 'admin_user', 'realm': 'com.plexapp.plugins.myplex'},
            {'id': 2, 'username': 'reg_user',   'realm': 'other'},
        ]

    async def test_returns_all_when_no_role(self):
        with patch.object(self.service, 'get_all_users', AsyncMock(return_value=self.users)):
            result = await self.service.filter_users_by_role(None)
        self.assertEqual(len(result), 2)

    async def test_returns_admins_only(self):
        with patch.object(self.service, 'get_all_users', AsyncMock(return_value=self.users)):
            result = await self.service.filter_users_by_role('admins')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 1)

    async def test_returns_regular_only(self):
        with patch.object(self.service, 'get_all_users', AsyncMock(return_value=self.users)):
            result = await self.service.filter_users_by_role('regular')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 2)


# ---------------------------------------------------------------------------
# PlexAuth
# ---------------------------------------------------------------------------

class TestPlexAuth(unittest.TestCase):

    def setUp(self):
        self.auth = PlexAuth(client_id='test_client_id')

    def test_get_authentication_pin_returns_id_and_url(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'id': 123, 'code': 'ABCDEF'}

        with patch('requests.post', return_value=mock_resp):
            pin_id, auth_url = self.auth.get_authentication_pin()

        self.assertEqual(pin_id, 123)
        self.assertIn('ABCDEF', auth_url)
        self.assertIn('test_client_id', auth_url)

    def test_check_authentication_returns_token_when_present(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'authToken': 'my_token_xyz'}

        with patch('requests.get', return_value=mock_resp):
            token = self.auth.check_authentication(123)

        self.assertEqual(token, 'my_token_xyz')

    def test_check_authentication_returns_none_when_no_token(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'id': 123, 'code': 'ABCDEF'}

        with patch('requests.get', return_value=mock_resp):
            token = self.auth.check_authentication(123)

        self.assertIsNone(token)


if __name__ == '__main__':
    unittest.main()
