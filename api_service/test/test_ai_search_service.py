"""
Tests for AiSearchService.

Covers:
- _is_watched(): exact match, substring (long title), short title no-match, not watched, empty title
- _resolve_suggested_title(): movie found, tv found, no title → None, TMDB error → None
- _search_single(): full pipeline with mocked LLM, TMDB, and history
- search(): 'both' media_type interleaves results, single type delegates correctly
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from api_service.services.ai_search.ai_search_service import AiSearchService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = {
    'SELECTED_SERVICE': 'jellyfin',
    'TMDB_API_KEY': 'fake',
    'FILTER_TMDB_THRESHOLD': 60,
    'FILTER_TMDB_MIN_VOTES': 10,
    'FILTER_INCLUDE_NO_RATING': True,
    'FILTER_RELEASE_YEAR': 0,
    'FILTER_LANGUAGE': [],
    'FILTER_GENRES_EXCLUDE': [],
    'FILTER_MIN_RUNTIME': None,
    'FILTER_RATING_SOURCE': 'tmdb',
    'FILTER_IMDB_THRESHOLD': None,
    'FILTER_IMDB_MIN_VOTES': None,
    'OMDB_API_KEY': None,
}


def _make_service():
    with patch('api_service.services.ai_search.ai_search_service.ConfigService.get_runtime_config',
               return_value=_DEFAULT_CONFIG):
        return AiSearchService()


def _tmdb_item(item_id=1, title='Test Movie', media_type='movie'):
    return {
        'id': item_id,
        'title': title,
        'vote_average': 8.0,
        'vote_count': 1000,
        'original_language': 'en',
        'release_date': '2020-01-01',
        'genre_ids': [],
    }


# ---------------------------------------------------------------------------
# _is_watched (static method)
# ---------------------------------------------------------------------------

class TestIsWatched(unittest.TestCase):

    def test_returns_true_on_exact_match(self):
        watched = {'inception', 'interstellar'}
        item = {'title': 'Inception'}
        self.assertTrue(AiSearchService._is_watched(item, watched))

    def test_returns_true_on_substring_match_with_long_title(self):
        # watched title len >= 5: substring check applies
        watched = {'breaking bad'}
        item = {'title': 'Breaking Bad: Season 2'}
        self.assertTrue(AiSearchService._is_watched(item, watched))

    def test_returns_false_for_short_watched_title_no_exact_match(self):
        # 'dark' (len 4 < 5) → substring logic NOT applied
        watched = {'dark'}
        item = {'title': 'Darkest Hour'}
        self.assertFalse(AiSearchService._is_watched(item, watched))

    def test_returns_false_when_not_in_watched(self):
        watched = {'dune', 'tenet'}
        item = {'title': 'Inception'}
        self.assertFalse(AiSearchService._is_watched(item, watched))

    def test_returns_false_for_empty_title(self):
        watched = {'inception'}
        item = {'title': ''}
        self.assertFalse(AiSearchService._is_watched(item, watched))

    def test_uses_name_key_as_fallback(self):
        watched = {'succession'}
        item = {'name': 'Succession'}
        self.assertTrue(AiSearchService._is_watched(item, watched))

    def test_returns_false_when_both_title_and_name_missing(self):
        watched = {'something'}
        item = {}
        self.assertFalse(AiSearchService._is_watched(item, watched))


# ---------------------------------------------------------------------------
# _resolve_suggested_title
# ---------------------------------------------------------------------------

class TestResolveSuggestedTitle(unittest.IsolatedAsyncioTestCase):

    def _service(self):
        return _make_service()

    async def test_returns_first_result_for_movie(self):
        service = self._service()
        mock_tmdb = MagicMock()
        mock_tmdb.search_movie = AsyncMock(return_value=[_tmdb_item(1, 'Se7en')])
        suggestion = {'title': 'Se7en', 'year': 1995}
        result = await service._resolve_suggested_title(suggestion, 'movie', mock_tmdb)
        self.assertEqual(result['id'], 1)

    async def test_returns_first_result_for_tv(self):
        service = self._service()
        mock_tmdb = MagicMock()
        mock_tmdb.search_tv = AsyncMock(return_value=[_tmdb_item(2, 'Succession')])
        suggestion = {'title': 'Succession', 'year': 2018}
        result = await service._resolve_suggested_title(suggestion, 'tv', mock_tmdb)
        self.assertEqual(result['id'], 2)

    async def test_returns_none_when_no_title_in_suggestion(self):
        service = self._service()
        mock_tmdb = MagicMock()
        result = await service._resolve_suggested_title({'year': 2020}, 'movie', mock_tmdb)
        self.assertIsNone(result)

    async def test_returns_none_when_tmdb_returns_empty_list(self):
        service = self._service()
        mock_tmdb = MagicMock()
        mock_tmdb.search_movie = AsyncMock(return_value=[])
        result = await service._resolve_suggested_title({'title': 'Unknown', 'year': 2000}, 'movie', mock_tmdb)
        self.assertIsNone(result)

    async def test_returns_none_on_tmdb_exception(self):
        service = self._service()
        mock_tmdb = MagicMock()
        mock_tmdb.search_movie = AsyncMock(side_effect=Exception('TMDB error'))
        result = await service._resolve_suggested_title({'title': 'Film', 'year': 2010}, 'movie', mock_tmdb)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# _search_single
# ---------------------------------------------------------------------------

class TestSearchSingle(unittest.IsolatedAsyncioTestCase):

    def _make_tmdb_client(self):
        """Return a TMDbClient-like mock that passes all filters."""
        mock_tmdb = MagicMock()
        mock_tmdb.search_movie = AsyncMock(return_value=[_tmdb_item(1, 'Se7en')])
        mock_tmdb.search_tv   = AsyncMock(return_value=[])
        mock_tmdb._apply_filters = MagicMock(return_value={'passed': True})
        mock_tmdb.omdb_client = None
        # Async context manager support
        mock_tmdb.__aenter__ = AsyncMock(return_value=mock_tmdb)
        mock_tmdb.__aexit__  = AsyncMock(return_value=False)
        return mock_tmdb

    async def test_returns_results_from_llm_suggestions(self):
        service = _make_service()
        interpretation = {
            'discover_params': {'genres': ['Thriller']},
            'suggested_titles': [{'title': 'Se7en', 'year': 1995, 'rationale': 'great film'}],
        }
        mock_tmdb = self._make_tmdb_client()

        with patch('api_service.services.ai_search.ai_search_service.interpret_search_query',
                   AsyncMock(return_value=interpretation)), \
             patch.object(service, '_get_history', AsyncMock(return_value=[])), \
             patch.object(service, '_make_tmdb_client', return_value=mock_tmdb), \
             patch('api_service.db.database_manager.DatabaseManager') as MockDB:
            MockDB.return_value.get_requested_tmdb_ids.return_value = set()
            result = await service._search_single('dark thriller', 'movie', None, 12)

        self.assertIn('results', result)
        self.assertGreaterEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['id'], 1)

    async def test_excludes_already_requested_ids(self):
        service = _make_service()
        interpretation = {
            'discover_params': {},
            'suggested_titles': [{'title': 'Se7en', 'year': 1995, 'rationale': 'ok'}],
        }
        mock_tmdb = self._make_tmdb_client()

        with patch('api_service.services.ai_search.ai_search_service.interpret_search_query',
                   AsyncMock(return_value=interpretation)), \
             patch.object(service, '_get_history', AsyncMock(return_value=[])), \
             patch.object(service, '_make_tmdb_client', return_value=mock_tmdb), \
             patch('api_service.db.database_manager.DatabaseManager') as MockDB:
            # Mark TMDB id '1' as already requested
            MockDB.return_value.get_requested_tmdb_ids.return_value = {'1'}
            result = await service._search_single('thriller', 'movie', None, 12)

        self.assertEqual(len(result['results']), 0)

    async def test_excludes_watched_titles_when_exclude_watched_true(self):
        service = _make_service()
        interpretation = {
            'discover_params': {},
            'suggested_titles': [{'title': 'Se7en', 'year': 1995, 'rationale': 'ok'}],
        }
        mock_tmdb = self._make_tmdb_client()
        history = [{'title': 'Se7en', 'year': 1995, 'type': 'movie'}]

        with patch('api_service.services.ai_search.ai_search_service.interpret_search_query',
                   AsyncMock(return_value=interpretation)), \
             patch.object(service, '_get_history', AsyncMock(return_value=history)), \
             patch.object(service, '_make_tmdb_client', return_value=mock_tmdb), \
             patch('api_service.db.database_manager.DatabaseManager') as MockDB:
            MockDB.return_value.get_requested_tmdb_ids.return_value = set()
            result = await service._search_single('thriller', 'movie', None, 12, exclude_watched=True)

        self.assertEqual(len(result['results']), 0)


# ---------------------------------------------------------------------------
# search() — 'both' media type
# ---------------------------------------------------------------------------

class TestSearch(unittest.IsolatedAsyncioTestCase):

    async def test_both_media_type_interleaves_movie_and_tv(self):
        service = _make_service()

        movie_result = {
            'results': [{'id': 1, 'title': 'Movie A', 'media_type': 'movie'}],
            'query_interpretation': {},
            'total': 1,
        }
        tv_result = {
            'results': [{'id': 2, 'title': 'Show B', 'media_type': 'tv'}],
            'query_interpretation': {},
            'total': 1,
        }

        with patch.object(service, '_search_single', AsyncMock(side_effect=[movie_result, tv_result])):
            result = await service.search('thriller', media_type='both', max_results=4)

        ids = [r['id'] for r in result['results']]
        self.assertIn(1, ids)
        self.assertIn(2, ids)

    async def test_single_media_type_delegates_to_search_single(self):
        service = _make_service()
        expected = {
            'results': [{'id': 1, 'title': 'Se7en'}],
            'query_interpretation': {},
            'total': 1,
        }
        with patch.object(service, '_search_single', AsyncMock(return_value=expected)) as mock_ss:
            result = await service.search('thriller', media_type='movie')

        mock_ss.assert_awaited_once()
        self.assertEqual(result, expected)


# ---------------------------------------------------------------------------
# Additional _is_watched edge cases (lines 362, 368)
# ---------------------------------------------------------------------------

class TestIsWatchedEdgeCases(unittest.TestCase):

    def test_empty_watched_entry_is_skipped(self):
        # '' in watched_titles set → triggers `continue` on line 362
        watched = {'', 'inception'}
        item = {'title': 'Inception'}
        self.assertTrue(AiSearchService._is_watched(item, watched))

    def test_item_title_contained_in_longer_watched_title(self):
        # `title in watched` (both ≥ 5 chars) → True on line 368
        watched = {'breaking bad season finale extended'}
        item = {'title': 'Breaking Bad'}
        self.assertTrue(AiSearchService._is_watched(item, watched))


# ---------------------------------------------------------------------------
# search() – 'both' mode leftover append (line 81)
# ---------------------------------------------------------------------------

class TestSearchBothLeftovers(unittest.IsolatedAsyncioTestCase):

    async def test_leftover_items_appended_when_lists_differ_in_length(self):
        service = _make_service()
        movie_result = {
            'results': [{'id': 1, 'title': 'Movie A'}, {'id': 2, 'title': 'Movie B'}],
            'query_interpretation': {},
            'total': 2,
        }
        tv_result = {
            'results': [{'id': 3, 'title': 'Show C'}],
            'query_interpretation': {},
            'total': 1,
        }
        with patch.object(service, '_search_single', AsyncMock(side_effect=[movie_result, tv_result])):
            result = await service.search('q', media_type='both', max_results=10)
        ids = [r['id'] for r in result['results']]
        self.assertIn(2, ids)   # leftover from longer movie list
        self.assertEqual(len(ids), 3)


# ---------------------------------------------------------------------------
# _search_single branch coverage (lines 113-114, 126-127, 145, 163, 169)
# ---------------------------------------------------------------------------

class TestSearchSingleBranchCoverage(unittest.IsolatedAsyncioTestCase):

    def _mock_tmdb(self, *, filter_pass=True, search_return=None, omdb_client=None):
        mock = MagicMock()
        mock.search_movie = AsyncMock(return_value=search_return if search_return is not None else [_tmdb_item(1)])
        mock.search_tv = AsyncMock(return_value=[])
        mock._apply_filters = MagicMock(return_value={'passed': filter_pass})
        mock.omdb_client = omdb_client
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=False)
        return mock

    async def test_history_exception_is_caught_and_search_continues(self):
        # lines 113-114: exception from _get_history is swallowed
        service = _make_service()
        interp = {'discover_params': {}, 'suggested_titles': [{'title': 'Film', 'year': 2020, 'rationale': 'ok'}]}
        with patch('api_service.services.ai_search.ai_search_service.interpret_search_query',
                   AsyncMock(return_value=interp)), \
             patch.object(service, '_get_history', AsyncMock(side_effect=Exception('history boom'))), \
             patch.object(service, '_make_tmdb_client', return_value=self._mock_tmdb()), \
             patch('api_service.db.database_manager.DatabaseManager') as MockDB:
            MockDB.return_value.get_requested_tmdb_ids.return_value = set()
            result = await service._search_single('q', 'movie', None, 12, use_history=True)
        self.assertIn('results', result)

    async def test_db_exception_is_caught_and_search_continues(self):
        # lines 126-127: exception from DatabaseManager is swallowed
        service = _make_service()
        interp = {'discover_params': {}, 'suggested_titles': [{'title': 'Film', 'year': 2020}]}
        with patch('api_service.services.ai_search.ai_search_service.interpret_search_query',
                   AsyncMock(return_value=interp)), \
             patch.object(service, '_get_history', AsyncMock(return_value=[])), \
             patch.object(service, '_make_tmdb_client', return_value=self._mock_tmdb()), \
             patch('api_service.db.database_manager.DatabaseManager',
                   side_effect=Exception('db boom')):
            result = await service._search_single('q', 'movie', None, 12)
        self.assertIn('results', result)

    async def test_item_without_id_is_skipped(self):
        # line 163: not item_id → continue
        service = _make_service()
        no_id_item = {'title': 'No ID Film', 'vote_average': 7.0}   # no 'id' key
        interp = {'discover_params': {}, 'suggested_titles': [{'title': 'Film', 'year': 2020}]}
        with patch('api_service.services.ai_search.ai_search_service.interpret_search_query',
                   AsyncMock(return_value=interp)), \
             patch.object(service, '_get_history', AsyncMock(return_value=[])), \
             patch.object(service, '_make_tmdb_client', return_value=self._mock_tmdb(search_return=[no_id_item])), \
             patch('api_service.db.database_manager.DatabaseManager') as MockDB:
            MockDB.return_value.get_requested_tmdb_ids.return_value = set()
            result = await service._search_single('q', 'movie', None, 12)
        self.assertEqual(len(result['results']), 0)

    async def test_filter_failure_excludes_item(self):
        # line 169: _apply_filters returns False → continue
        service = _make_service()
        interp = {'discover_params': {}, 'suggested_titles': [{'title': 'Film', 'year': 2020}]}
        with patch('api_service.services.ai_search.ai_search_service.interpret_search_query',
                   AsyncMock(return_value=interp)), \
             patch.object(service, '_get_history', AsyncMock(return_value=[])), \
             patch.object(service, '_make_tmdb_client', return_value=self._mock_tmdb(filter_pass=False)), \
             patch('api_service.db.database_manager.DatabaseManager') as MockDB:
            MockDB.return_value.get_requested_tmdb_ids.return_value = set()
            result = await service._search_single('q', 'movie', None, 12, exclude_watched=False)
        self.assertEqual(len(result['results']), 0)

    async def test_omdb_client_context_manager_entered_when_present(self):
        # line 145: omdb_client async context manager is entered
        service = _make_service()
        mock_omdb = MagicMock()
        mock_omdb.__aenter__ = AsyncMock(return_value=mock_omdb)
        mock_omdb.__aexit__ = AsyncMock(return_value=False)
        interp = {'discover_params': {}, 'suggested_titles': [{'title': 'Film', 'year': 2020, 'rationale': 'ok'}]}
        with patch('api_service.services.ai_search.ai_search_service.interpret_search_query',
                   AsyncMock(return_value=interp)), \
             patch.object(service, '_get_history', AsyncMock(return_value=[])), \
             patch.object(service, '_make_tmdb_client',
                          return_value=self._mock_tmdb(omdb_client=mock_omdb)), \
             patch('api_service.db.database_manager.DatabaseManager') as MockDB:
            MockDB.return_value.get_requested_tmdb_ids.return_value = set()
            await service._search_single('q', 'movie', None, 12)
        mock_omdb.__aenter__.assert_awaited_once()


# ---------------------------------------------------------------------------
# _get_history routing (lines 206-216)
# ---------------------------------------------------------------------------

class TestGetHistoryRouting(unittest.IsolatedAsyncioTestCase):

    def _service_with_service(self, selected_service):
        config = {**_DEFAULT_CONFIG, 'SELECTED_SERVICE': selected_service}
        with patch('api_service.services.ai_search.ai_search_service.ConfigService.get_runtime_config',
                   return_value=config):
            return AiSearchService()

    async def test_routes_to_plex(self):
        service = self._service_with_service('plex')
        with patch.object(service, '_get_plex_history', AsyncMock(return_value=[])) as mock:
            await service._get_history(None)
        mock.assert_awaited_once()

    async def test_emby_routes_to_jellyfin(self):
        service = self._service_with_service('emby')
        with patch.object(service, '_get_jellyfin_history', AsyncMock(return_value=[])) as mock:
            await service._get_history(None)
        mock.assert_awaited_once()

    async def test_no_service_returns_empty_list(self):
        service = self._service_with_service('')
        result = await service._get_history(None)
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# _get_jellyfin_history (lines 220-272)
# ---------------------------------------------------------------------------

class TestGetJellyfinHistory(unittest.IsolatedAsyncioTestCase):

    def _service(self, api_url='http://jf', token='tok'):
        config = {
            **_DEFAULT_CONFIG,
            'SELECTED_SERVICE': 'jellyfin',
            'JELLYFIN_API_URL': api_url,
            'JELLYFIN_TOKEN': token,
            'JELLYFIN_LIBRARIES': [],
        }
        with patch('api_service.services.ai_search.ai_search_service.ConfigService.get_runtime_config',
                   return_value=config):
            return AiSearchService()

    async def test_no_credentials_returns_empty(self):
        service = self._service(api_url='', token='')
        result = await service._get_jellyfin_history(None)
        self.assertEqual(result, [])

    async def test_movie_and_episode_items_with_user_ids(self):
        service = self._service()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get_recent_items = AsyncMock(return_value={
            'lib': [
                {'Type': 'Movie', 'Name': 'Se7en', 'ProductionYear': 1995},
                {'Type': 'Episode', 'SeriesName': 'Breaking Bad', 'Name': 'Ep1', 'ProductionYear': 2008},
            ]
        })
        with patch('api_service.services.jellyfin.jellyfin_client.JellyfinClient',
                   return_value=mock_client):
            result = await service._get_jellyfin_history([{'id': '1', 'name': 'User'}])
        titles = {r['title'] for r in result}
        types = {r['type'] for r in result}
        self.assertIn('Se7en', titles)
        self.assertIn('Breaking Bad', titles)
        self.assertIn('movie', types)
        self.assertIn('tv', types)

    async def test_get_all_users_exception_returns_empty(self):
        service = self._service()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get_all_users = AsyncMock(side_effect=Exception('users fail'))
        with patch('api_service.services.jellyfin.jellyfin_client.JellyfinClient',
                   return_value=mock_client):
            result = await service._get_jellyfin_history(None)
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# _get_plex_history (lines 276-314)
# ---------------------------------------------------------------------------

class TestGetPlexHistory(unittest.IsolatedAsyncioTestCase):

    def _service(self, token='tok'):
        config = {
            **_DEFAULT_CONFIG,
            'PLEX_TOKEN': token,
            'PLEX_API_URL': 'http://plex',
            'PLEX_LIBRARIES': [],
        }
        with patch('api_service.services.ai_search.ai_search_service.ConfigService.get_runtime_config',
                   return_value=config):
            return AiSearchService()

    async def test_no_token_returns_empty(self):
        service = self._service(token='')
        result = await service._get_plex_history(None)
        self.assertEqual(result, [])

    async def test_movie_and_episode_items(self):
        service = self._service()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get_recent_items = AsyncMock(return_value=[
            {'type': 'movie', 'title': 'Inception', 'year': 2010},
            {'type': 'episode', 'grandparentTitle': 'Breaking Bad', 'year': 2008},
        ])
        with patch('api_service.services.plex.plex_client.PlexClient',
                   return_value=mock_client):
            result = await service._get_plex_history(None)
        titles = {r['title'] for r in result}
        types = {r['type'] for r in result}
        self.assertIn('movie', types)
        self.assertIn('tv', types)
        self.assertIn('Inception', titles)
        self.assertIn('Breaking Bad', titles)

    async def test_get_recent_items_exception_returns_empty(self):
        service = self._service()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get_recent_items = AsyncMock(side_effect=Exception('plex fail'))
        with patch('api_service.services.plex.plex_client.PlexClient',
                   return_value=mock_client):
            result = await service._get_plex_history(None)
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# _make_tmdb_client (lines 318-336)
# ---------------------------------------------------------------------------

class TestMakeTmdbClient(unittest.TestCase):

    def test_returns_tmdb_client_instance(self):
        from api_service.services.tmdb.tmdb_client import TMDbClient
        service = _make_service()
        client = service._make_tmdb_client()
        self.assertIsInstance(client, TMDbClient)

    def test_imdb_rating_source_creates_omdb_client(self):
        config = {**_DEFAULT_CONFIG, 'FILTER_RATING_SOURCE': 'imdb', 'OMDB_API_KEY': 'omdb_key'}
        with patch('api_service.services.ai_search.ai_search_service.ConfigService.get_runtime_config',
                   return_value=config):
            service = AiSearchService()
        with patch('api_service.services.omdb.omdb_client.OmdbClient') as MockOmdb:
            service._make_tmdb_client()
        MockOmdb.assert_called_once_with('omdb_key')


if __name__ == '__main__':
    unittest.main()
