"""
Tests for TMDbClient (non-filter parts already covered in test_omdb_filters.py).

Covers:
- _apply_filters(): language, release year, genre, TMDB rating/votes, rating_source='imdb'
- _format_result(): movie and tv formatting
- _fetch_page_data(): success, HTTP error, network error
- _get_item_details(): movie (runtime + imdb_id), tv (episode_run_time + external_ids call)
- _get_tv_imdb_id(): found, not found, HTTP error
- find_tmdb_id_from_tvdb(): found, no results, HTTP error, network error
- get_watch_providers(): excluded, not excluded, no region/services configured
- search_movie() / search_tv(): success, empty, network error
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from api_service.services.tmdb.tmdb_client import TMDbClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(
    tmdb_threshold=60,
    tmdb_min_votes=10,
    include_no_ratings=True,
    filter_release_year=0,
    filter_language=None,
    filter_genre=None,
    filter_region_provider=None,
    filter_streaming_services=None,
    rating_source='tmdb',
):
    return TMDbClient(
        api_key='fake_tmdb_key',
        search_size=5,
        tmdb_threshold=tmdb_threshold,
        tmdb_min_votes=tmdb_min_votes,
        include_no_ratings=include_no_ratings,
        filter_release_year=filter_release_year,
        filter_language=filter_language,
        filter_genre=filter_genre,
        filter_region_provider=filter_region_provider,
        filter_streaming_services=filter_streaming_services,
        rating_source=rating_source,
    )


def _mock_response(status=200, data=None):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data or {})
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _mock_session(response):
    session = MagicMock()
    session.get = MagicMock(return_value=response)
    return session


_MOVIE_ITEM = {
    'id': 101,
    'title': 'Inception',
    'vote_average': 8.8,
    'vote_count': 30000,
    'original_language': 'en',
    'release_date': '2010-07-16',
    'genre_ids': [28, 878],
}

_TV_ITEM = {
    'id': 202,
    'name': 'Breaking Bad',
    'vote_average': 9.5,
    'vote_count': 20000,
    'original_language': 'en',
    'first_air_date': '2008-01-20',
    'genre_ids': [18],
}


# ---------------------------------------------------------------------------
# _apply_filters
# ---------------------------------------------------------------------------

class TestApplyFilters(unittest.TestCase):

    def test_passes_item_with_good_rating_and_votes(self):
        client = _make_client(tmdb_threshold=60, tmdb_min_votes=10)
        self.assertTrue(client._apply_filters(_MOVIE_ITEM, 'movie'))

    def test_excludes_when_missing_rating_and_include_no_ratings_false(self):
        client = _make_client(include_no_ratings=False)
        item = {**_MOVIE_ITEM, 'vote_average': None, 'vote_count': None}
        self.assertFalse(client._apply_filters(item, 'movie'))

    def test_passes_when_missing_rating_and_include_no_ratings_true(self):
        client = _make_client(include_no_ratings=True)
        item = {**_MOVIE_ITEM, 'vote_average': None, 'vote_count': None}
        self.assertTrue(client._apply_filters(item, 'movie'))

    def test_excludes_when_rating_below_threshold(self):
        client = _make_client(tmdb_threshold=90, include_no_ratings=False)
        item = {**_MOVIE_ITEM, 'vote_average': 5.0, 'vote_count': 1000}
        self.assertFalse(client._apply_filters(item, 'movie'))

    def test_excludes_when_votes_below_minimum(self):
        client = _make_client(tmdb_min_votes=50000, include_no_ratings=False)
        item = {**_MOVIE_ITEM, 'vote_average': 9.0, 'vote_count': 100}
        self.assertFalse(client._apply_filters(item, 'movie'))

    def test_excludes_when_language_not_in_filter(self):
        client = _make_client(filter_language=[{'id': 'it', 'english_name': 'Italian'}])
        item = {**_MOVIE_ITEM, 'original_language': 'en'}
        self.assertFalse(client._apply_filters(item, 'movie'))

    def test_passes_when_language_in_filter(self):
        client = _make_client(filter_language=[{'id': 'en', 'english_name': 'English'}])
        self.assertTrue(client._apply_filters(_MOVIE_ITEM, 'movie'))

    def test_excludes_when_release_year_before_filter(self):
        client = _make_client(filter_release_year=2020)
        item = {**_MOVIE_ITEM, 'release_date': '2010-01-01'}
        self.assertFalse(client._apply_filters(item, 'movie'))

    def test_excludes_when_genre_in_exclude_list(self):
        client = _make_client(filter_genre=[{'id': 28, 'name': 'Action'}])
        item = {**_MOVIE_ITEM, 'genre_ids': [28]}
        self.assertFalse(client._apply_filters(item, 'movie'))

    def test_passes_when_genre_not_in_exclude_list(self):
        client = _make_client(filter_genre=[{'id': 99, 'name': 'Comedy'}])
        item = {**_MOVIE_ITEM, 'genre_ids': [28]}
        self.assertTrue(client._apply_filters(item, 'movie'))

    def test_skips_tmdb_rating_check_when_rating_source_is_imdb(self):
        """When rating_source='imdb', TMDB rating/votes filters should be skipped."""
        client = _make_client(tmdb_threshold=90, tmdb_min_votes=100000, rating_source='imdb')
        item = {**_MOVIE_ITEM, 'vote_average': 1.0, 'vote_count': 1}
        # Should pass because TMDB rating check is skipped
        self.assertTrue(client._apply_filters(item, 'movie'))


# ---------------------------------------------------------------------------
# _format_result
# ---------------------------------------------------------------------------

class TestFormatResult(unittest.TestCase):

    def test_formats_movie_correctly(self):
        client = _make_client()
        item = {
            'id': 1, 'title': 'Dune', 'vote_average': 7.8, 'vote_count': 5000,
            'release_date': '2021-10-22', 'origin_country': ['US'],
            'original_language': 'en', 'poster_path': '/dune.jpg',
            'overview': 'A sci-fi epic.', 'genre_ids': [878],
            'backdrop_path': '/bg.jpg',
        }
        result = client._format_result(item, 'movie')
        self.assertEqual(result['id'], 1)
        self.assertEqual(result['title'], 'Dune')
        self.assertIn('tmdb.org', result['poster_path'])
        self.assertIn('tmdb.org', result['backdrop_path'])

    def test_formats_tv_using_name_key(self):
        client = _make_client()
        item = {
            'id': 2, 'name': 'Succession', 'vote_average': 8.9, 'vote_count': 10000,
            'first_air_date': '2018-06-03', 'origin_country': ['US'],
            'original_language': 'en', 'poster_path': None,
            'overview': 'Drama.', 'genre_ids': [18], 'backdrop_path': None,
        }
        result = client._format_result(item, 'tv')
        self.assertEqual(result['title'], 'Succession')
        self.assertIsNone(result['poster_path'])

    def test_none_poster_when_no_poster_path(self):
        client = _make_client()
        item = {**_MOVIE_ITEM, 'poster_path': None, 'backdrop_path': None}
        result = client._format_result(item, 'movie')
        self.assertIsNone(result['poster_path'])
        self.assertIsNone(result['backdrop_path'])


# ---------------------------------------------------------------------------
# _fetch_page_data
# ---------------------------------------------------------------------------

class TestFetchPageData(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_returns_data_on_success(self):
        payload = {'results': [_MOVIE_ITEM], 'total_pages': 1}
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client._fetch_page_data(101, 'movie', 1)
        self.assertEqual(result['results'], [_MOVIE_ITEM])

    async def test_returns_none_on_http_error(self):
        resp = _mock_response(401)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client._fetch_page_data(101, 'movie', 1)
        self.assertIsNone(result)

    async def test_returns_none_on_network_error(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('refused'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client._fetch_page_data(101, 'movie', 1)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# _get_item_details
# ---------------------------------------------------------------------------

class TestGetItemDetails(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_returns_runtime_and_imdb_id_for_movie(self):
        payload = {'runtime': 148, 'imdb_id': 'tt1375666'}
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client._get_item_details(101, 'movie')
        self.assertEqual(result['runtime'], 148)
        self.assertEqual(result['imdb_id'], 'tt1375666')

    async def test_returns_episode_runtime_and_calls_external_ids_for_tv(self):
        details_payload = {'episode_run_time': [45]}
        resp = _mock_response(200, details_payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)), \
             patch.object(self.client, '_get_tv_imdb_id', AsyncMock(return_value='tt0903747')):
            result = await self.client._get_item_details(202, 'tv')
        self.assertEqual(result['runtime'], 45)
        self.assertEqual(result['imdb_id'], 'tt0903747')

    async def test_returns_empty_dict_on_http_error(self):
        resp = _mock_response(404)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client._get_item_details(999, 'movie')
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# _get_tv_imdb_id
# ---------------------------------------------------------------------------

class TestGetTvImdbId(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_returns_imdb_id_when_found(self):
        resp = _mock_response(200, {'imdb_id': 'tt0903747'})
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client._get_tv_imdb_id(1396)
        self.assertEqual(result, 'tt0903747')

    async def test_returns_none_when_imdb_id_missing(self):
        resp = _mock_response(200, {'tvdb_id': 81189})
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client._get_tv_imdb_id(1396)
        self.assertIsNone(result)

    async def test_returns_none_on_http_error(self):
        resp = _mock_response(404)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client._get_tv_imdb_id(9999)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# find_tmdb_id_from_tvdb
# ---------------------------------------------------------------------------

class TestFindTmdbIdFromTvdb(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_returns_tmdb_id_on_success(self):
        payload = {'tv_results': [{'id': 1396}]}
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.find_tmdb_id_from_tvdb('81189')
        self.assertEqual(result, 1396)

    async def test_returns_none_when_no_tv_results(self):
        payload = {'tv_results': []}
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.find_tmdb_id_from_tvdb('00000')
        self.assertIsNone(result)

    async def test_returns_none_on_http_error(self):
        resp = _mock_response(401)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.find_tmdb_id_from_tvdb('81189')
        self.assertIsNone(result)

    async def test_returns_none_on_network_error(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('refused'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.find_tmdb_id_from_tvdb('81189')
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# get_watch_providers
# ---------------------------------------------------------------------------

class TestGetWatchProviders(unittest.IsolatedAsyncioTestCase):

    async def test_returns_false_none_when_no_region_configured(self):
        client = _make_client(filter_region_provider=None, filter_streaming_services=[{'provider_id': '8'}])
        result = await client.get_watch_providers(101, 'movie')
        self.assertEqual(result, (False, None))

    async def test_returns_false_none_when_no_services_configured(self):
        client = _make_client(filter_region_provider='US', filter_streaming_services=None)
        result = await client.get_watch_providers(101, 'movie')
        self.assertEqual(result, (False, None))

    async def test_returns_true_provider_name_when_excluded_service_found(self):
        client = _make_client(
            filter_region_provider='US',
            filter_streaming_services=[{'provider_id': '8'}],
        )
        payload = {
            'results': {
                'US': {
                    'flatrate': [{'provider_id': 8, 'provider_name': 'Netflix'}]
                }
            }
        }
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(client, '_get_session', AsyncMock(return_value=session)):
            is_excluded, name = await client.get_watch_providers(101, 'movie')
        self.assertTrue(is_excluded)
        self.assertEqual(name, 'Netflix')

    async def test_returns_false_none_when_service_not_excluded(self):
        client = _make_client(
            filter_region_provider='US',
            filter_streaming_services=[{'provider_id': '999'}],
        )
        payload = {
            'results': {
                'US': {
                    'flatrate': [{'provider_id': 8, 'provider_name': 'Netflix'}]
                }
            }
        }
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(client, '_get_session', AsyncMock(return_value=session)):
            is_excluded, name = await client.get_watch_providers(101, 'movie')
        self.assertFalse(is_excluded)
        self.assertIsNone(name)


# ---------------------------------------------------------------------------
# search_movie / search_tv
# ---------------------------------------------------------------------------

class TestSearchMovieAndTv(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = _make_client()

    async def test_search_movie_returns_formatted_results(self):
        payload = {'results': [_MOVIE_ITEM]}
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.search_movie('Inception')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 101)

    async def test_search_movie_with_year(self):
        payload = {'results': [_MOVIE_ITEM]}
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.search_movie('Inception', year=2010)
        self.assertEqual(len(result), 1)

    async def test_search_movie_returns_empty_on_http_error(self):
        resp = _mock_response(401)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.search_movie('Unknown')
        self.assertEqual(result, [])

    async def test_search_tv_returns_formatted_results(self):
        payload = {'results': [_TV_ITEM]}
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.search_tv('Breaking Bad')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 202)

    async def test_search_tv_returns_empty_on_network_error(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('timeout'))
        with patch.object(self.client, '_get_session', AsyncMock(return_value=session)):
            result = await self.client.search_tv('Breaking Bad')
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
