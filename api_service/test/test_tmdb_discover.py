"""
Tests for TMDbDiscover.

Covers:
- _build_query_params(): direct mapping, skip TMDB rating when rating_source='imdb',
  genres as list vs string, default sort_by, default include_adult
- _check_imdb_filter(): no data + include/exclude, rating pass/fail, votes pass/fail
- _format_result(): movie vs tv
- _fetch_discover_page(): success, HTTP error, network error, timeout
- discover_movies() / discover_tv(): basic success, max_results cap
- _get_imdb_id(): movie path, tv path, network error → None
- get_genres(): success, HTTP error
- get_languages(): success, HTTP error
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from api_service.services.tmdb.tmdb_discover import TMDbDiscover


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_discover(omdb_client=None):
    return TMDbDiscover(api_key='fake_key', omdb_client=omdb_client)


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


_RAW_MOVIE = {
    'id': 101, 'title': 'Dune', 'vote_average': 7.8, 'vote_count': 5000,
    'release_date': '2021-10-22', 'origin_country': ['US'],
    'original_language': 'en', 'poster_path': '/dune.jpg',
    'backdrop_path': '/bg.jpg', 'overview': 'Epic.', 'genre_ids': [878],
    'popularity': 1234.5,
}

_RAW_TV = {
    'id': 202, 'name': 'Succession', 'vote_average': 8.9, 'vote_count': 10000,
    'first_air_date': '2018-06-03', 'origin_country': ['US'],
    'original_language': 'en', 'poster_path': None,
    'backdrop_path': None, 'overview': 'Drama.', 'genre_ids': [18],
    'popularity': 987.6,
}


# ---------------------------------------------------------------------------
# _build_query_params
# ---------------------------------------------------------------------------

class TestBuildQueryParams(unittest.TestCase):

    def setUp(self):
        self.disc = _make_discover()

    def test_maps_vote_average_gte_to_api_key(self):
        params = self.disc._build_query_params({'vote_average_gte': 7.0})
        self.assertEqual(params['vote_average.gte'], 7.0)

    def test_skips_vote_average_and_count_when_rating_source_is_imdb(self):
        params = self.disc._build_query_params({
            'rating_source': 'imdb',
            'vote_average_gte': 7.0,
            'vote_count_gte': 500,
        })
        self.assertNotIn('vote_average.gte', params)
        self.assertNotIn('vote_count.gte', params)

    def test_genres_list_joined_with_comma(self):
        params = self.disc._build_query_params({'with_genres': [28, 12]})
        self.assertEqual(params['with_genres'], '28,12')

    def test_genres_string_passed_through(self):
        params = self.disc._build_query_params({'with_genres': '28,12'})
        self.assertEqual(params['with_genres'], '28,12')

    def test_default_sort_by_is_popularity_desc(self):
        params = self.disc._build_query_params({})
        self.assertEqual(params['sort_by'], 'popularity.desc')

    def test_explicit_sort_by_is_preserved(self):
        params = self.disc._build_query_params({'sort_by': 'vote_average.desc'})
        self.assertEqual(params['sort_by'], 'vote_average.desc')

    def test_default_include_adult_is_false(self):
        params = self.disc._build_query_params({})
        self.assertEqual(params['include_adult'], 'false')

    def test_internal_imdb_keys_not_in_output(self):
        params = self.disc._build_query_params({
            'imdb_rating_gte': 7.0,
            'imdb_min_votes': 100,
            'rating_source': 'imdb',
            'include_no_rating': True,
        })
        for key in params:
            self.assertNotIn('imdb', key.lower())
            self.assertNotIn('rating_source', key)


# ---------------------------------------------------------------------------
# _check_imdb_filter
# ---------------------------------------------------------------------------

class TestCheckImdbFilter(unittest.TestCase):

    def setUp(self):
        self.disc = _make_discover()
        self.item = {'title': 'Test Movie'}

    def test_passes_when_no_data_and_include_no_rating_true(self):
        result = self.disc._check_imdb_filter(None, self.item, None, None, include_no_rating=True)
        self.assertTrue(result)

    def test_excludes_when_no_data_and_include_no_rating_false(self):
        result = self.disc._check_imdb_filter(None, self.item, None, None, include_no_rating=False)
        self.assertFalse(result)

    def test_passes_when_rating_above_threshold(self):
        data = {'imdb_rating': 8.0, 'imdb_votes': 1000}
        result = self.disc._check_imdb_filter(data, self.item, 7.0, 100, include_no_rating=False)
        self.assertTrue(result)

    def test_excludes_when_rating_below_threshold(self):
        data = {'imdb_rating': 5.0, 'imdb_votes': 1000}
        result = self.disc._check_imdb_filter(data, self.item, 7.0, None, include_no_rating=False)
        self.assertFalse(result)

    def test_excludes_when_votes_below_minimum(self):
        data = {'imdb_rating': 8.5, 'imdb_votes': 50}
        result = self.disc._check_imdb_filter(data, self.item, None, 100, include_no_rating=False)
        self.assertFalse(result)

    def test_passes_when_no_thresholds_set(self):
        data = {'imdb_rating': 3.0, 'imdb_votes': 1}
        result = self.disc._check_imdb_filter(data, self.item, None, None, include_no_rating=False)
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# _format_result
# ---------------------------------------------------------------------------

class TestFormatResult(unittest.TestCase):

    def setUp(self):
        self.disc = _make_discover()

    def test_formats_movie_with_title(self):
        result = self.disc._format_result(_RAW_MOVIE, 'movie')
        self.assertEqual(result['id'], 101)
        self.assertEqual(result['title'], 'Dune')
        self.assertEqual(result['media_type'], 'movie')
        self.assertIn('tmdb.org', result['poster_path'])

    def test_formats_tv_with_name(self):
        result = self.disc._format_result(_RAW_TV, 'tv')
        self.assertEqual(result['title'], 'Succession')
        self.assertEqual(result['media_type'], 'tv')
        self.assertIsNone(result['poster_path'])

    def test_includes_popularity(self):
        result = self.disc._format_result(_RAW_MOVIE, 'movie')
        self.assertEqual(result['popularity'], 1234.5)


# ---------------------------------------------------------------------------
# _fetch_discover_page
# ---------------------------------------------------------------------------

class TestFetchDiscoverPage(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.disc = _make_discover()

    async def test_returns_data_on_success(self):
        payload = {'results': [_RAW_MOVIE], 'total_pages': 1}
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(self.disc, '_get_session', AsyncMock(return_value=session)):
            result = await self.disc._fetch_discover_page('movie', {}, 1)
        self.assertIn('results', result)

    async def test_returns_none_on_http_error(self):
        resp = _mock_response(401)
        session = _mock_session(resp)
        with patch.object(self.disc, '_get_session', AsyncMock(return_value=session)):
            result = await self.disc._fetch_discover_page('movie', {}, 1)
        self.assertIsNone(result)

    async def test_returns_none_on_client_error(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('refused'))
        with patch.object(self.disc, '_get_session', AsyncMock(return_value=session)):
            result = await self.disc._fetch_discover_page('movie', {}, 1)
        self.assertIsNone(result)

    async def test_returns_none_on_timeout(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=asyncio.TimeoutError())
        with patch.object(self.disc, '_get_session', AsyncMock(return_value=session)):
            result = await self.disc._fetch_discover_page('movie', {}, 1)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# discover_movies / discover_tv
# ---------------------------------------------------------------------------

class TestDiscoverMoviesAndTv(unittest.IsolatedAsyncioTestCase):

    async def test_discover_movies_returns_formatted_list(self):
        disc = _make_discover()
        payload = {'results': [_RAW_MOVIE], 'total_pages': 1}
        with patch.object(disc, '_fetch_discover_page', AsyncMock(return_value=payload)), \
             patch('asyncio.sleep', AsyncMock()):
            result = await disc.discover_movies({}, max_results=5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 101)

    async def test_discover_tv_returns_formatted_list(self):
        disc = _make_discover()
        payload = {'results': [_RAW_TV], 'total_pages': 1}
        with patch.object(disc, '_fetch_discover_page', AsyncMock(return_value=payload)), \
             patch('asyncio.sleep', AsyncMock()):
            result = await disc.discover_tv({}, max_results=5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 202)

    async def test_respects_max_results(self):
        disc = _make_discover()
        many_items = [dict(_RAW_MOVIE, id=i) for i in range(25)]
        payload = {'results': many_items, 'total_pages': 2}
        with patch.object(disc, '_fetch_discover_page', AsyncMock(return_value=payload)), \
             patch('asyncio.sleep', AsyncMock()):
            result = await disc.discover_movies({}, max_results=5)
        self.assertLessEqual(len(result), 5)

    async def test_stops_when_page_returns_none(self):
        disc = _make_discover()
        with patch.object(disc, '_fetch_discover_page', AsyncMock(return_value=None)), \
             patch('asyncio.sleep', AsyncMock()):
            result = await disc.discover_movies({}, max_results=20)
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# _get_imdb_id
# ---------------------------------------------------------------------------

class TestGetImdbId(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.disc = _make_discover()

    async def test_returns_imdb_id_for_movie(self):
        resp = _mock_response(200, {'imdb_id': 'tt1375666'})
        session = _mock_session(resp)
        with patch.object(self.disc, '_get_session', AsyncMock(return_value=session)):
            result = await self.disc._get_imdb_id(101, 'movie')
        self.assertEqual(result, 'tt1375666')

    async def test_returns_imdb_id_for_tv_via_external_ids(self):
        resp = _mock_response(200, {'imdb_id': 'tt0903747'})
        session = _mock_session(resp)
        with patch.object(self.disc, '_get_session', AsyncMock(return_value=session)):
            result = await self.disc._get_imdb_id(1396, 'tv')
        self.assertEqual(result, 'tt0903747')

    async def test_returns_none_on_network_error(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError('refused'))
        with patch.object(self.disc, '_get_session', AsyncMock(return_value=session)):
            result = await self.disc._get_imdb_id(101, 'movie')
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# get_genres / get_languages
# ---------------------------------------------------------------------------

class TestGetGenresAndLanguages(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.disc = _make_discover()

    async def test_get_genres_returns_list(self):
        payload = {'genres': [{'id': 28, 'name': 'Action'}]}
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(self.disc, '_get_session', AsyncMock(return_value=session)):
            result = await self.disc.get_genres('movie')
        self.assertEqual(result, [{'id': 28, 'name': 'Action'}])

    async def test_get_genres_returns_empty_on_http_error(self):
        resp = _mock_response(401)
        session = _mock_session(resp)
        with patch.object(self.disc, '_get_session', AsyncMock(return_value=session)):
            result = await self.disc.get_genres('movie')
        self.assertEqual(result, [])

    async def test_get_languages_returns_list(self):
        payload = [{'iso_639_1': 'en', 'english_name': 'English'}]
        resp = _mock_response(200, payload)
        session = _mock_session(resp)
        with patch.object(self.disc, '_get_session', AsyncMock(return_value=session)):
            result = await self.disc.get_languages()
        self.assertEqual(len(result), 1)

    async def test_get_languages_returns_empty_on_http_error(self):
        resp = _mock_response(401)
        session = _mock_session(resp)
        with patch.object(self.disc, '_get_session', AsyncMock(return_value=session)):
            result = await self.disc.get_languages()
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
