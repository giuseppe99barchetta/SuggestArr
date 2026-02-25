"""
Tests for ContentAutomation (automate_process.py).

Covers:
- __new__(): logger attached to instance
- create(): Jellyfin/emby/Plex initialization paths, unknown service → ValueError
- create(): SELECTED_USERS normalization (valid dict, dict without id, string, invalid type, non-list)
- create(): OmdbClient init conditions (rating_source vs OMDB_API_KEY)
- create(): list field normalization (JELLYFIN_LIBRARIES, PLEX_LIBRARIES, FILTER_LANGUAGE, etc.)
- create(): numeric caps (MAX_SIMILAR_MOVIE ≤ 20, MAX_SIMILAR_TV ≤ 20, SEARCH_SIZE ≤ 100)
- run(): calls media_handler.process_recent_items()
- run(): enters correct async context managers (seer, tmdb, media client, omdb)
- run(): prefers jellyseer_client attribute over seer_client
- run(): re-raises exceptions
"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from api_service.automate_process import ContentAutomation


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

BASE_ENV = {
    'SELECTED_SERVICE': 'jellyfin',
    'SELECTED_USERS': [{'id': 'u1', 'name': 'Alice'}],
    'MAX_CONTENT_CHECKS': 10,
    'MAX_SIMILAR_MOVIE': '3',
    'MAX_SIMILAR_TV': '2',
    'SEARCH_SIZE': '20',
    'FILTER_NUM_SEASONS': None,
    'FILTER_TMDB_THRESHOLD': '60',
    'FILTER_TMDB_MIN_VOTES': '20',
    'FILTER_INCLUDE_NO_RATING': True,
    'FILTER_RELEASE_YEAR': '0',
    'FILTER_LANGUAGE': [],
    'FILTER_GENRES_EXCLUDE': [],
    'FILTER_REGION_PROVIDER': None,
    'FILTER_STREAMING_SERVICES': [],
    'FILTER_MIN_RUNTIME': None,
    'FILTER_RATING_SOURCE': 'tmdb',
    'FILTER_IMDB_THRESHOLD': None,
    'FILTER_IMDB_MIN_VOTES': None,
    'OMDB_API_KEY': '',
    'EXCLUDE_DOWNLOADED': True,
    'EXCLUDE_REQUESTED': True,
    'SEER_REQUEST_DELAY': '0',
    'SEER_ANIME_PROFILE_CONFIG': {},
    'SEER_API_URL': 'http://seer.local',
    'SEER_TOKEN': 'seer_tok',
    'SEER_USER_NAME': 'admin',
    'SEER_USER_PSW': 'pass',
    'SEER_SESSION_TOKEN': '',
    'TMDB_API_KEY': 'tmdb_key',
    'JELLYFIN_API_URL': 'http://jellyfin.local',
    'JELLYFIN_TOKEN': 'jf_tok',
    'JELLYFIN_LIBRARIES': [],
    'PLEX_API_URL': 'http://plex.local',
    'PLEX_TOKEN': 'plex_tok',
    'PLEX_LIBRARIES': [],
}


def _env(**overrides):
    """Return a copy of BASE_ENV with any overrides applied."""
    env = dict(BASE_ENV)
    env.update(overrides)
    return env


def _make_async_cm():
    """Return a MagicMock that works as an async context manager."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=cm)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _mock_seer():
    seer = _make_async_cm()
    seer.init = AsyncMock()
    return seer


def _mock_tmdb(omdb_client=None):
    tmdb = _make_async_cm()
    tmdb.omdb_client = omdb_client
    return tmdb


def _mock_jf_client():
    jf = _make_async_cm()
    jf.init_existing_content = AsyncMock()
    return jf


def _mock_plex_client():
    pc = _make_async_cm()
    pc.init_existing_content = AsyncMock()
    return pc


class _BaseCreateTest(unittest.IsolatedAsyncioTestCase):
    """
    Base for create() tests — starts all service patches before each test
    and stops them afterwards.
    """

    def setUp(self):
        self.mock_env = _env()
        self.seer = _mock_seer()
        self.tmdb = _mock_tmdb()
        self.jf_client = _mock_jf_client()
        self.jf_handler = MagicMock()
        self.plex_client = _mock_plex_client()
        self.plex_handler = MagicMock()
        self.omdb_instance = _make_async_cm()

        self.MockEnv = patch(
            'api_service.automate_process.load_env_vars',
            return_value=self.mock_env,
        ).start()
        self.MockSeer = patch(
            'api_service.automate_process.SeerClient',
            return_value=self.seer,
        ).start()
        self.MockTmdb = patch(
            'api_service.automate_process.TMDbClient',
            return_value=self.tmdb,
        ).start()
        self.MockJfClient = patch(
            'api_service.automate_process.JellyfinClient',
            return_value=self.jf_client,
        ).start()
        self.MockJfHandler = patch(
            'api_service.automate_process.JellyfinHandler',
            return_value=self.jf_handler,
        ).start()
        self.MockPlexClient = patch(
            'api_service.automate_process.PlexClient',
            return_value=self.plex_client,
        ).start()
        self.MockPlexHandler = patch(
            'api_service.automate_process.PlexHandler',
            return_value=self.plex_handler,
        ).start()
        self.MockOmdb = patch(
            'api_service.automate_process.OmdbClient',
            return_value=self.omdb_instance,
        ).start()

    def tearDown(self):
        patch.stopall()


# ---------------------------------------------------------------------------
# __new__
# ---------------------------------------------------------------------------

class TestContentAutomationNew(unittest.TestCase):
    """__new__ must attach a properly-named logger to the instance."""

    def test_logger_is_attached(self):
        with patch('api_service.automate_process.LoggerManager.get_logger') as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger
            instance = ContentAutomation.__new__(ContentAutomation)
        self.assertIs(instance.logger, mock_logger)
        mock_get.assert_called_once_with('ContentAutomation')


# ---------------------------------------------------------------------------
# create() — service initialization paths
# ---------------------------------------------------------------------------

class TestContentAutomationCreateServicePaths(_BaseCreateTest):

    async def test_jellyfin_initializes_jellyfin_client_and_handler(self):
        await ContentAutomation.create()
        self.MockJfClient.assert_called_once()
        self.jf_client.init_existing_content.assert_awaited_once()
        self.MockJfHandler.assert_called_once()
        self.MockPlexClient.assert_not_called()
        self.MockPlexHandler.assert_not_called()

    async def test_emby_uses_jellyfin_code_path(self):
        self.mock_env['SELECTED_SERVICE'] = 'emby'
        await ContentAutomation.create()
        self.MockJfClient.assert_called_once()
        self.MockJfHandler.assert_called_once()
        self.MockPlexClient.assert_not_called()

    async def test_plex_initializes_plex_client_and_handler(self):
        self.mock_env['SELECTED_SERVICE'] = 'plex'
        await ContentAutomation.create()
        self.MockPlexClient.assert_called_once()
        self.plex_client.init_existing_content.assert_awaited_once()
        self.MockPlexHandler.assert_called_once()
        self.MockJfClient.assert_not_called()
        self.MockJfHandler.assert_not_called()

    async def test_unknown_service_raises_value_error(self):
        self.mock_env['SELECTED_SERVICE'] = 'unsupported'
        with self.assertRaises(ValueError):
            await ContentAutomation.create()

    async def test_selected_service_stored_on_instance(self):
        instance = await ContentAutomation.create()
        self.assertEqual(instance.selected_service, 'jellyfin')

    async def test_seer_init_is_awaited(self):
        await ContentAutomation.create()
        self.seer.init.assert_awaited_once()

    async def test_media_handler_assigned_on_instance(self):
        instance = await ContentAutomation.create()
        self.assertIs(instance.media_handler, self.jf_handler)


# ---------------------------------------------------------------------------
# create() — numeric limits
# ---------------------------------------------------------------------------

class TestContentAutomationCreateNumericLimits(_BaseCreateTest):

    async def test_max_similar_movie_stored(self):
        instance = await ContentAutomation.create()
        self.assertEqual(instance.max_similar_movie, 3)

    async def test_max_similar_movie_capped_at_20(self):
        self.mock_env['MAX_SIMILAR_MOVIE'] = '50'
        instance = await ContentAutomation.create()
        self.assertEqual(instance.max_similar_movie, 20)

    async def test_max_similar_tv_stored(self):
        instance = await ContentAutomation.create()
        self.assertEqual(instance.max_similar_tv, 2)

    async def test_max_similar_tv_capped_at_20(self):
        self.mock_env['MAX_SIMILAR_TV'] = '99'
        instance = await ContentAutomation.create()
        self.assertEqual(instance.max_similar_tv, 20)

    async def test_search_size_stored(self):
        instance = await ContentAutomation.create()
        self.assertEqual(instance.search_size, 20)

    async def test_search_size_capped_at_100(self):
        self.mock_env['SEARCH_SIZE'] = '500'
        instance = await ContentAutomation.create()
        self.assertEqual(instance.search_size, 100)

    async def test_values_below_cap_are_not_altered(self):
        self.mock_env['MAX_SIMILAR_MOVIE'] = '20'
        self.mock_env['MAX_SIMILAR_TV'] = '20'
        self.mock_env['SEARCH_SIZE'] = '100'
        instance = await ContentAutomation.create()
        self.assertEqual(instance.max_similar_movie, 20)
        self.assertEqual(instance.max_similar_tv, 20)
        self.assertEqual(instance.search_size, 100)


# ---------------------------------------------------------------------------
# create() — SELECTED_USERS normalization
# ---------------------------------------------------------------------------

class TestContentAutomationCreateUserNormalization(_BaseCreateTest):

    async def test_valid_dict_user_is_kept(self):
        self.mock_env['SELECTED_USERS'] = [{'id': 'u1', 'name': 'Alice'}]
        instance = await ContentAutomation.create()
        self.assertEqual(instance.selected_users, [{'id': 'u1', 'name': 'Alice'}])

    async def test_dict_user_without_id_is_skipped(self):
        self.mock_env['SELECTED_USERS'] = [{'name': 'NoId'}]
        instance = await ContentAutomation.create()
        self.assertEqual(instance.selected_users, [])

    async def test_string_user_is_converted_to_dict(self):
        self.mock_env['SELECTED_USERS'] = ['user123']
        instance = await ContentAutomation.create()
        self.assertEqual(instance.selected_users, [{'id': 'user123', 'name': 'user123'}])

    async def test_invalid_type_users_are_skipped(self):
        self.mock_env['SELECTED_USERS'] = [42, 3.14]
        instance = await ContentAutomation.create()
        self.assertEqual(instance.selected_users, [])

    async def test_mixed_user_types_normalized_correctly(self):
        self.mock_env['SELECTED_USERS'] = [
            {'id': 'u1', 'name': 'Alice'},  # kept
            {'name': 'NoId'},               # skipped (no 'id' key)
            'str_user',                     # converted to dict
            99,                             # skipped (invalid type)
        ]
        instance = await ContentAutomation.create()
        self.assertEqual(instance.selected_users, [
            {'id': 'u1', 'name': 'Alice'},
            {'id': 'str_user', 'name': 'str_user'},
        ])

    async def test_non_list_selected_users_yields_empty_list(self):
        self.mock_env['SELECTED_USERS'] = 'not-a-list'
        instance = await ContentAutomation.create()
        self.assertEqual(instance.selected_users, [])

    async def test_none_selected_users_yields_empty_list(self):
        self.mock_env['SELECTED_USERS'] = None
        instance = await ContentAutomation.create()
        self.assertEqual(instance.selected_users, [])

    async def test_empty_list_yields_empty_list(self):
        self.mock_env['SELECTED_USERS'] = []
        instance = await ContentAutomation.create()
        self.assertEqual(instance.selected_users, [])


# ---------------------------------------------------------------------------
# create() — OmdbClient conditions
# ---------------------------------------------------------------------------

class TestContentAutomationCreateOmdbClient(_BaseCreateTest):

    async def test_omdb_not_created_for_tmdb_rating_source(self):
        self.mock_env['FILTER_RATING_SOURCE'] = 'tmdb'
        self.mock_env['OMDB_API_KEY'] = 'key123'
        await ContentAutomation.create()
        self.MockOmdb.assert_not_called()

    async def test_omdb_created_for_imdb_source_with_key(self):
        self.mock_env['FILTER_RATING_SOURCE'] = 'imdb'
        self.mock_env['OMDB_API_KEY'] = 'key123'
        await ContentAutomation.create()
        self.MockOmdb.assert_called_once_with('key123')

    async def test_omdb_created_for_both_source_with_key(self):
        self.mock_env['FILTER_RATING_SOURCE'] = 'both'
        self.mock_env['OMDB_API_KEY'] = 'key123'
        await ContentAutomation.create()
        self.MockOmdb.assert_called_once_with('key123')

    async def test_omdb_not_created_when_api_key_missing(self):
        self.mock_env['FILTER_RATING_SOURCE'] = 'imdb'
        self.mock_env['OMDB_API_KEY'] = ''
        await ContentAutomation.create()
        self.MockOmdb.assert_not_called()

    async def test_omdb_not_created_when_api_key_none(self):
        self.mock_env['FILTER_RATING_SOURCE'] = 'both'
        self.mock_env['OMDB_API_KEY'] = None
        await ContentAutomation.create()
        self.MockOmdb.assert_not_called()


# ---------------------------------------------------------------------------
# create() — list field normalization
# ---------------------------------------------------------------------------

class TestContentAutomationCreateListNormalization(_BaseCreateTest):
    """Non-list values for list config fields must be coerced to []."""

    async def test_jellyfin_libraries_non_list_coerced_to_empty(self):
        self.mock_env['JELLYFIN_LIBRARIES'] = 'not-a-list'
        await ContentAutomation.create()
        args, _ = self.MockJfClient.call_args
        # JellyfinClient(api_url, token, max_content, library_ids)
        self.assertEqual(args[3], [])

    async def test_filter_language_non_list_coerced_to_empty(self):
        self.mock_env['FILTER_LANGUAGE'] = 'en'
        await ContentAutomation.create()
        args, _ = self.MockTmdb.call_args
        # TMDbClient(key, search_size, tmdb_threshold, tmdb_min_votes,
        #            include_no_ratings, filter_release_year, filter_language, ...)
        self.assertEqual(args[6], [])

    async def test_filter_genres_exclude_non_list_coerced_to_empty(self):
        self.mock_env['FILTER_GENRES_EXCLUDE'] = 'drama'
        await ContentAutomation.create()
        args, _ = self.MockTmdb.call_args
        self.assertEqual(args[7], [])

    async def test_filter_streaming_services_non_list_coerced_to_empty(self):
        self.mock_env['FILTER_STREAMING_SERVICES'] = 'netflix'
        await ContentAutomation.create()
        args, _ = self.MockTmdb.call_args
        self.assertEqual(args[9], [])

    async def test_plex_libraries_non_list_coerced_to_empty(self):
        self.mock_env['SELECTED_SERVICE'] = 'plex'
        self.mock_env['PLEX_LIBRARIES'] = 'not-a-list'
        await ContentAutomation.create()
        _, kwargs = self.MockPlexClient.call_args
        self.assertEqual(kwargs['library_ids'], [])

    async def test_seer_anime_profile_config_non_dict_coerced_to_empty(self):
        self.mock_env['SEER_ANIME_PROFILE_CONFIG'] = ['list', 'not', 'dict']
        # Should not raise; SeerClient receives an empty dict instead
        await ContentAutomation.create()
        _, kwargs = self.MockSeer.call_args
        # anime_profile_config is the 9th positional arg
        args, _ = self.MockSeer.call_args
        self.assertEqual(args[8], {})


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------

def _make_handler(**attrs):
    """
    Build a SimpleNamespace media handler.
    process_recent_items defaults to an AsyncMock if not provided.
    """
    ns = SimpleNamespace(**attrs)
    if not hasattr(ns, 'process_recent_items'):
        ns.process_recent_items = AsyncMock()
    return ns


class TestContentAutomationRun(unittest.IsolatedAsyncioTestCase):

    def _make_instance(self, handler):
        """Create a ContentAutomation with a pre-set media_handler, bypassing create()."""
        instance = ContentAutomation.__new__(ContentAutomation)
        instance.media_handler = handler
        return instance

    # -- happy-path ----------------------------------------------------------

    async def test_process_recent_items_is_called(self):
        seer = _make_async_cm()
        tmdb = _mock_tmdb()
        jf_client = _make_async_cm()
        handler = _make_handler(seer_client=seer, tmdb_client=tmdb, jellyfin_client=jf_client)

        await self._make_instance(handler).run()

        handler.process_recent_items.assert_awaited_once()

    # -- context managers ----------------------------------------------------

    async def test_seer_client_context_manager_is_entered(self):
        seer = _make_async_cm()
        tmdb = _mock_tmdb()
        jf_client = _make_async_cm()
        handler = _make_handler(seer_client=seer, tmdb_client=tmdb, jellyfin_client=jf_client)

        await self._make_instance(handler).run()

        seer.__aenter__.assert_awaited_once()
        seer.__aexit__.assert_awaited_once()

    async def test_jellyseer_client_preferred_over_seer_client(self):
        jellyseer = _make_async_cm()
        seer = _make_async_cm()
        tmdb = _mock_tmdb()
        jf_client = _make_async_cm()
        handler = _make_handler(
            jellyseer_client=jellyseer,
            seer_client=seer,
            tmdb_client=tmdb,
            jellyfin_client=jf_client,
        )

        await self._make_instance(handler).run()

        jellyseer.__aenter__.assert_awaited_once()
        seer.__aenter__.assert_not_called()

    async def test_tmdb_client_context_manager_is_entered(self):
        seer = _make_async_cm()
        tmdb = _mock_tmdb()
        jf_client = _make_async_cm()
        handler = _make_handler(seer_client=seer, tmdb_client=tmdb, jellyfin_client=jf_client)

        await self._make_instance(handler).run()

        tmdb.__aenter__.assert_awaited_once()
        tmdb.__aexit__.assert_awaited_once()

    async def test_jellyfin_client_context_manager_is_entered(self):
        seer = _make_async_cm()
        tmdb = _mock_tmdb()
        jf_client = _make_async_cm()
        handler = _make_handler(seer_client=seer, tmdb_client=tmdb, jellyfin_client=jf_client)

        await self._make_instance(handler).run()

        jf_client.__aenter__.assert_awaited_once()
        jf_client.__aexit__.assert_awaited_once()

    async def test_plex_client_context_entered_when_no_jellyfin_client(self):
        seer = _make_async_cm()
        tmdb = _mock_tmdb()
        plex_client = _make_async_cm()
        handler = _make_handler(seer_client=seer, tmdb_client=tmdb, plex_client=plex_client)

        await self._make_instance(handler).run()

        plex_client.__aenter__.assert_awaited_once()

    async def test_omdb_client_context_entered_when_present(self):
        seer = _make_async_cm()
        omdb = _make_async_cm()
        tmdb = _mock_tmdb(omdb_client=omdb)
        jf_client = _make_async_cm()
        handler = _make_handler(seer_client=seer, tmdb_client=tmdb, jellyfin_client=jf_client)

        await self._make_instance(handler).run()

        omdb.__aenter__.assert_awaited_once()

    async def test_omdb_client_not_entered_when_none(self):
        seer = _make_async_cm()
        tmdb = _mock_tmdb(omdb_client=None)
        jf_client = _make_async_cm()
        handler = _make_handler(seer_client=seer, tmdb_client=tmdb, jellyfin_client=jf_client)

        # Should complete without error and still call process_recent_items
        await self._make_instance(handler).run()
        handler.process_recent_items.assert_awaited_once()

    # -- error handling ------------------------------------------------------

    async def test_exception_from_process_recent_items_is_reraised(self):
        seer = _make_async_cm()
        tmdb = _mock_tmdb()
        jf_client = _make_async_cm()
        handler = _make_handler(seer_client=seer, tmdb_client=tmdb, jellyfin_client=jf_client)
        handler.process_recent_items = AsyncMock(side_effect=RuntimeError('boom'))

        instance = self._make_instance(handler)
        with self.assertRaises(RuntimeError, msg='boom'):
            await instance.run()
