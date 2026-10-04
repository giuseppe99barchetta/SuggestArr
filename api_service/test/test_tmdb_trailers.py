"""Tests for picking a YouTube trailer from TMDb videos, and the route serving it."""
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask, g

from api_service.blueprints.tmdb import routes
from api_service.utils.tmdb_trailers import youtube_trailer_url


def _video(key, video_type='Trailer', site='YouTube', language='en', official=True):
    return {'key': key, 'type': video_type, 'site': site, 'iso_639_1': language, 'official': official}


def test_builds_youtube_url_from_trailer():
    assert youtube_trailer_url([_video('abc123XYZ_-')]) == "https://www.youtube.com/watch?v=abc123XYZ_-"


def test_prefers_trailer_over_teaser_and_other_types():
    videos = [_video('featurette1', 'Featurette'), _video('teaser12345', 'Teaser'), _video('trailer1234')]
    assert youtube_trailer_url(videos).endswith('trailer1234')


def test_falls_back_to_teaser_when_no_trailer():
    videos = [_video('clip1234567', 'Clip'), _video('teaser12345', 'Teaser')]
    assert youtube_trailer_url(videos).endswith('teaser12345')


def test_prefers_reader_language_then_official():
    videos = [
        _video('english1234'),
        _video('unofficial1', language='de', official=False),
        _video('german12345', language='de'),
    ]
    assert youtube_trailer_url(videos, 'de-DE').endswith('german12345')
    assert youtube_trailer_url(videos, 'fr').endswith('english1234')


def test_ignores_other_sites_and_unsafe_keys():
    videos = [_video('vimeo123456', site='Vimeo'), _video('bad key&x=1'), _video(None), None]
    assert youtube_trailer_url(videos) is None
    assert youtube_trailer_url(None) is None


class TestTrailerRoute(unittest.TestCase):
    def setUp(self):
        routes.clear_cache()
        app = Flask(__name__)
        app.register_blueprint(routes.tmdb_bp, url_prefix='/api/tmdb')

        @app.before_request
        def _user():
            g.current_user = {'id': '1'}

        self.client = app.test_client()
        db = MagicMock()
        db.get_integration.return_value = {'api_key': 'secret'}
        db.get_user_language.return_value = 'de'
        self.patches = [
            patch.object(routes, 'DatabaseManager', return_value=db),
            patch.object(routes, 'load_env_vars', return_value={}),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        routes.clear_cache()

    def test_returns_trailer_url_and_caches_it(self):
        with patch.object(routes, '_run', return_value=({'results': [_video('german12345', language='de')]}, 200)) as run, \
                patch.object(routes, '_fetch_tmdb', new=MagicMock()) as fetch:
            first = self.client.get('/api/tmdb/trailer/movie/10950')
            second = self.client.get('/api/tmdb/trailer/movie/10950')

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()['url'], 'https://www.youtube.com/watch?v=german12345')
        self.assertEqual(second.get_json(), first.get_json())
        self.assertEqual(run.call_count, 1)
        fetch.assert_called_once_with(
            '/movie/10950/videos', 'secret',
            {'language': 'de', 'include_video_language': 'de,en,null'},
        )

    def test_returns_null_url_when_title_has_no_trailer(self):
        with patch.object(routes, '_run', return_value=({'results': []}, 200)), \
                patch.object(routes, '_fetch_tmdb', new=MagicMock()):
            response = self.client.get('/api/tmdb/trailer/tv/1399')

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()['url'])

    def test_rejects_unknown_media_type(self):
        self.assertEqual(self.client.get('/api/tmdb/trailer/person/1').status_code, 400)

    def test_reports_tmdb_failure(self):
        with patch.object(routes, '_run', return_value=(None, 404)), \
                patch.object(routes, '_fetch_tmdb', new=MagicMock()):
            self.assertEqual(self.client.get('/api/tmdb/trailer/movie/1').status_code, 502)
