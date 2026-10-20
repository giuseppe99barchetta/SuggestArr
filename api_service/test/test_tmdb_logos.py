"""Tests for title logo selection and lazy backfill."""
from unittest.mock import MagicMock

from api_service.services.tmdb import logos
from api_service.services.tmdb.logos import fill_logos, pick_logo


def test_pick_logo_prefers_reader_language_then_english_then_neutral_then_any():
    candidates = [
        {'file_path': '/ja.png', 'iso_639_1': 'ja', 'vote_average': 9},
        {'file_path': '/null.png', 'iso_639_1': None, 'vote_average': 5},
        {'file_path': '/en-low.png', 'iso_639_1': 'en', 'vote_average': 1},
        {'file_path': '/en-high.png', 'iso_639_1': 'en', 'vote_average': 4},
        {'file_path': '/it.png', 'iso_639_1': 'it', 'vote_average': 0},
    ]
    assert pick_logo(candidates, 'it-IT') == '/it.png'
    assert pick_logo(candidates, 'de') == '/en-high.png'
    assert pick_logo(candidates[:2], 'en') == '/null.png'
    assert pick_logo(candidates[:1], 'en') == '/ja.png'
    assert pick_logo([], 'en') is None


def test_fill_logos_stores_found_logos_in_background_and_skips_known_ones():
    logos._NO_LOGO.clear()
    logos._in_flight.clear()
    items = [
        {'request_id': '1', 'media_type': 'movie', 'logo_path': None},
        {'request_id': '2', 'media_type': 'tv', 'logo_path': 'https://x/kept.png'},
        {'request_id': '3', 'media_type': 'movie', 'logo_path': ''},
        {'request_id': 'ai_search', 'media_type': 'movie', 'logo_path': None},
    ]
    db = MagicMock()
    asked = []

    def run(coro):
        asked.extend(coro.cr_frame.f_locals['pairs'])
        coro.close()
        return {('1', 'movie'): 'https://img/1.png', ('3', 'movie'): None}

    groups = [(items, [('request_id', 'media_type', 'title', 'overview')])]
    fill_logos(groups, 'en', db, 'key', run).join(timeout=5)

    assert sorted(asked) == [('1', 'movie'), ('3', 'movie')]
    db.update_logo.assert_called_once_with('1', 'movie', 'https://img/1.png')
    assert ('3', 'movie') in logos._NO_LOGO
    assert not logos._in_flight
    # The title without a logo on TMDb is not asked again.
    items[0]['logo_path'] = 'https://img/1.png'
    assert fill_logos(groups, 'en', db, 'key', run) is None
