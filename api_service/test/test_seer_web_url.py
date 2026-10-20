"""Tests for the browser address used by "Open in Seer" links."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from flask import Flask

from api_service.blueprints.seer import routes


@pytest.fixture
def client():
    routes._web_url_cache.update(url=None, at=0.0)
    app = Flask(__name__)
    app.register_blueprint(routes.seer_bp, url_prefix='/api/seer')
    yield app.test_client()
    routes._web_url_cache.update(url=None, at=0.0)


def _seer(application_url):
    seer = MagicMock(get_application_url=AsyncMock(return_value=application_url))
    seer.__aenter__ = AsyncMock(return_value=seer)
    seer.__aexit__ = AsyncMock(return_value=False)
    return seer


def test_prefers_seers_public_application_url_and_caches_it(client):
    seer = _seer('https://requests.example.com')
    with patch.object(routes, '_load_seer_config', return_value=('http://jellyseerr:5055/', 'key', None)), \
            patch.object(routes, 'SeerClient', return_value=seer) as factory:
        first = client.get('/api/seer/web-url').get_json()
        second = client.get('/api/seer/web-url').get_json()
    assert first == second == {'url': 'https://requests.example.com'}
    assert factory.call_count == 1


def test_falls_back_to_the_configured_address(client):
    with patch.object(routes, '_load_seer_config', return_value=('http://192.168.1.5:5055/', 'key', None)), \
            patch.object(routes, 'SeerClient', return_value=_seer(None)):
        assert client.get('/api/seer/web-url').get_json() == {'url': 'http://192.168.1.5:5055'}


def test_unconfigured_seer_has_no_link(client):
    with patch.object(routes, '_load_seer_config', return_value=('', '', None)):
        assert client.get('/api/seer/web-url').get_json() == {'url': None}
