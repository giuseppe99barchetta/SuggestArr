"""
Tests for OmdbClient.get_rating() and TMDbClient._apply_imdb_filter().

Covers:
- OmdbClient.get_rating(): HTTP success/failure, N/A values, parsing errors
- TMDbClient._apply_imdb_filter(): rating threshold, vote count, None data,
  include_no_ratings flag
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from api_service.services.omdb.omdb_client import OmdbClient
from api_service.services.tmdb.tmdb_client import TMDbClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tmdb_client(
    rating_source='imdb',
    imdb_threshold=60,
    imdb_min_votes=100,
    include_no_ratings=False,
):
    """Return a TMDbClient with minimal required args for filter testing."""
    return TMDbClient(
        api_key='fake_tmdb_key',
        search_size=10,
        tmdb_threshold=60,
        tmdb_min_votes=100,
        include_no_ratings=include_no_ratings,
        filter_release_year=None,
        filter_language=None,
        filter_genre=None,
        filter_region_provider=None,
        filter_streaming_services=None,
        rating_source=rating_source,
        imdb_threshold=imdb_threshold,
        imdb_min_votes=imdb_min_votes,
        omdb_client=None,
    )


MOVIE_ITEM = {'title': 'Inception', 'id': 27205}
TV_ITEM = {'name': 'Breaking Bad', 'id': 1396}


# ---------------------------------------------------------------------------
# OmdbClient.get_rating()
# ---------------------------------------------------------------------------

class TestOmdbClientGetRating(unittest.IsolatedAsyncioTestCase):
    """Unit tests for OmdbClient.get_rating()."""

    def setUp(self):
        self.client = OmdbClient(api_key='test_key')

    # --- guard clauses ---

    async def test_returns_none_when_no_imdb_id(self):
        result = await self.client.get_rating(None)
        self.assertIsNone(result)

    async def test_returns_none_when_empty_imdb_id(self):
        result = await self.client.get_rating('')
        self.assertIsNone(result)

    async def test_returns_none_when_no_api_key(self):
        client = OmdbClient(api_key='')
        result = await client.get_rating('tt0816692')
        self.assertIsNone(result)

    # --- successful response ---

    async def test_returns_rating_and_votes_on_success(self):
        payload = {
            'Response': 'True',
            'imdbRating': '8.8',
            'imdbVotes': '2,400,000',
        }
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=payload)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await self.client.get_rating('tt0816692')

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['imdb_rating'], 8.8)
        self.assertEqual(result['imdb_votes'], 2_400_000)

    # --- OMDb Response == False ---

    async def test_returns_none_when_omdb_response_false(self):
        payload = {'Response': 'False', 'Error': 'Movie not found!'}
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=payload)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await self.client.get_rating('tt9999999')

        self.assertIsNone(result)

    # --- N/A values ---

    async def test_returns_none_when_rating_is_na(self):
        payload = {'Response': 'True', 'imdbRating': 'N/A', 'imdbVotes': '1,000'}
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=payload)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await self.client.get_rating('tt1234567')

        self.assertIsNone(result)

    async def test_returns_none_when_votes_is_na(self):
        payload = {'Response': 'True', 'imdbRating': '7.5', 'imdbVotes': 'N/A'}
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=payload)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await self.client.get_rating('tt1234567')

        self.assertIsNone(result)

    # --- HTTP error ---

    async def test_returns_none_on_http_error(self):
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await self.client.get_rating('tt0816692')

        self.assertIsNone(result)

    # --- network error ---

    async def test_returns_none_on_client_error(self):
        import aiohttp
        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=aiohttp.ClientError('connection refused'))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await self.client.get_rating('tt0816692')

        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# TMDbClient._apply_imdb_filter()
# ---------------------------------------------------------------------------

class TestApplyImdbFilter(unittest.TestCase):
    """Unit tests for TMDbClient._apply_imdb_filter()."""

    # --- imdb_data is None ---

    def test_none_data_excluded_when_no_ratings_not_allowed(self):
        client = _make_tmdb_client(include_no_ratings=False)
        result = client._apply_imdb_filter(None, MOVIE_ITEM, 'movie')
        self.assertFalse(result)

    def test_none_data_allowed_when_include_no_ratings_true(self):
        client = _make_tmdb_client(include_no_ratings=True)
        result = client._apply_imdb_filter(None, MOVIE_ITEM, 'movie')
        self.assertTrue(result)

    # --- rating threshold (imdb_threshold is on 0-100 scale, divided by 10) ---

    def test_passes_when_rating_above_threshold(self):
        # threshold=60 → 6.0; rating 7.5 should pass
        client = _make_tmdb_client(imdb_threshold=60)
        imdb_data = {'imdb_rating': 7.5, 'imdb_votes': 1000}
        result = client._apply_imdb_filter(imdb_data, MOVIE_ITEM, 'movie')
        self.assertTrue(result)

    def test_passes_when_rating_exactly_at_threshold(self):
        # threshold=60 → 6.0; rating 6.0 should pass (not strictly less than)
        client = _make_tmdb_client(imdb_threshold=60)
        imdb_data = {'imdb_rating': 6.0, 'imdb_votes': 1000}
        result = client._apply_imdb_filter(imdb_data, MOVIE_ITEM, 'movie')
        self.assertTrue(result)

    def test_excluded_when_rating_below_threshold(self):
        # threshold=60 → 6.0; rating 5.9 should be excluded
        client = _make_tmdb_client(imdb_threshold=60)
        imdb_data = {'imdb_rating': 5.9, 'imdb_votes': 1000}
        result = client._apply_imdb_filter(imdb_data, MOVIE_ITEM, 'movie')
        self.assertFalse(result)

    def test_excluded_when_rating_is_zero(self):
        client = _make_tmdb_client(imdb_threshold=60)
        imdb_data = {'imdb_rating': 0.0, 'imdb_votes': 500}
        result = client._apply_imdb_filter(imdb_data, TV_ITEM, 'tv')
        self.assertFalse(result)

    # --- vote count threshold ---

    def test_passes_when_votes_above_minimum(self):
        client = _make_tmdb_client(imdb_min_votes=100)
        imdb_data = {'imdb_rating': 8.0, 'imdb_votes': 500}
        result = client._apply_imdb_filter(imdb_data, MOVIE_ITEM, 'movie')
        self.assertTrue(result)

    def test_passes_when_votes_exactly_at_minimum(self):
        client = _make_tmdb_client(imdb_min_votes=100)
        imdb_data = {'imdb_rating': 8.0, 'imdb_votes': 100}
        result = client._apply_imdb_filter(imdb_data, MOVIE_ITEM, 'movie')
        self.assertTrue(result)

    def test_excluded_when_votes_below_minimum(self):
        client = _make_tmdb_client(imdb_min_votes=100)
        imdb_data = {'imdb_rating': 8.0, 'imdb_votes': 99}
        result = client._apply_imdb_filter(imdb_data, MOVIE_ITEM, 'movie')
        self.assertFalse(result)

    # --- both filters combined ---

    def test_excluded_when_both_rating_and_votes_fail(self):
        client = _make_tmdb_client(imdb_threshold=70, imdb_min_votes=1000)
        imdb_data = {'imdb_rating': 5.0, 'imdb_votes': 50}
        result = client._apply_imdb_filter(imdb_data, TV_ITEM, 'tv')
        self.assertFalse(result)

    def test_excluded_when_only_votes_fail(self):
        client = _make_tmdb_client(imdb_threshold=60, imdb_min_votes=1000)
        imdb_data = {'imdb_rating': 8.5, 'imdb_votes': 50}
        result = client._apply_imdb_filter(imdb_data, TV_ITEM, 'tv')
        self.assertFalse(result)

    def test_excluded_when_only_rating_fails(self):
        client = _make_tmdb_client(imdb_threshold=80, imdb_min_votes=10)
        imdb_data = {'imdb_rating': 7.9, 'imdb_votes': 5000}
        result = client._apply_imdb_filter(imdb_data, MOVIE_ITEM, 'movie')
        self.assertFalse(result)

    def test_passes_when_both_rating_and_votes_pass(self):
        client = _make_tmdb_client(imdb_threshold=60, imdb_min_votes=100)
        imdb_data = {'imdb_rating': 7.0, 'imdb_votes': 200}
        result = client._apply_imdb_filter(imdb_data, TV_ITEM, 'tv')
        self.assertTrue(result)

    # --- edge cases with missing keys in imdb_data ---

    def test_passes_when_imdb_data_has_no_rating_key(self):
        """If rating key is absent, the rating check is skipped → only votes checked."""
        client = _make_tmdb_client(imdb_threshold=60, imdb_min_votes=100)
        imdb_data = {'imdb_votes': 500}
        result = client._apply_imdb_filter(imdb_data, MOVIE_ITEM, 'movie')
        self.assertTrue(result)

    def test_passes_when_imdb_data_has_no_votes_key(self):
        """If votes key is absent, the votes check is skipped → only rating checked."""
        client = _make_tmdb_client(imdb_threshold=60, imdb_min_votes=100)
        imdb_data = {'imdb_rating': 7.5}
        result = client._apply_imdb_filter(imdb_data, MOVIE_ITEM, 'movie')
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
