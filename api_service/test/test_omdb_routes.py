"""
Tests for the OMDb key test endpoint (POST /api/omdb/test).

Covers:
- request validation (missing/empty/non-string key)
- success response
- 401 with OMDb JSON error body (invalid/unactivated key, request limit)
- non-JSON error responses
- timeout and network errors (handled, not a generic 500)
- key is stripped and sent as a query param
"""

import asyncio

import aiohttp
import pytest
from flask import Flask

from api_service.blueprints.omdb import routes


class FakeResponse:
    """Minimal aiohttp response stand-in."""

    def __init__(self, status, payload=None, json_error=None):
        self.status = status
        self._payload = payload
        self._json_error = json_error

    async def json(self, content_type='application/json'):
        if self._json_error:
            raise self._json_error
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Minimal aiohttp.ClientSession stand-in recording GET calls."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def make_client(monkeypatch):
    """Return a factory building a Flask test client with a fake OMDb session."""

    def _make(outcome):
        session = FakeSession(outcome)
        monkeypatch.setattr(routes.aiohttp, 'ClientSession', lambda **kwargs: session)
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.register_blueprint(routes.omdb_bp, url_prefix='/api/omdb')
        return app.test_client(), session

    return _make


@pytest.mark.parametrize('payload', [None, [], {}, {'api_key': None}, {'api_key': ''},
                                     {'api_key': '   '}, {'api_key': 123}])
def test_key_is_required(payload, make_client):
    client, session = make_client(FakeResponse(200, {'Response': 'True'}))
    response = client.post('/api/omdb/test', json=payload)
    assert response.status_code == 400
    assert session.calls == []


def test_valid_key_succeeds_and_is_stripped(make_client):
    client, session = make_client(FakeResponse(200, {'Response': 'True', 'Title': 'Interstellar'}))
    response = client.post('/api/omdb/test', json={'api_key': '  abc123 \n'})
    assert response.status_code == 200
    assert response.json['status'] == 'success'
    url, kwargs = session.calls[0]
    assert url == routes.OMDB_BASE_URL
    assert kwargs['params'] == {'i': routes._TEST_IMDB_ID, 'apikey': 'abc123'}


def test_invalid_or_unactivated_key_returns_actionable_message(make_client):
    client, _ = make_client(FakeResponse(401, {'Response': 'False', 'Error': 'Invalid API key!'}))
    response = client.post('/api/omdb/test', json={'api_key': 'bad'})
    assert response.status_code == 400
    assert 'activated' in response.json['message']


def test_other_omdb_errors_are_surfaced(make_client):
    client, _ = make_client(FakeResponse(401, {'Response': 'False', 'Error': 'Request limit reached!'}))
    response = client.post('/api/omdb/test', json={'api_key': 'key'})
    assert response.status_code == 400
    assert response.json['message'] == 'OMDb error: Request limit reached!'


def test_non_json_error_falls_back_to_status(make_client):
    client, _ = make_client(FakeResponse(503, json_error=ValueError('not json')))
    response = client.post('/api/omdb/test', json={'api_key': 'key'})
    assert response.status_code == 400
    assert response.json['message'] == 'OMDb API returned status 503'


@pytest.mark.parametrize('error,fragment', [
    (asyncio.TimeoutError(), 'timed out'),
    (aiohttp.ClientConnectionError('dns failure'), 'Failed to connect'),
])
def test_network_errors_are_handled(error, fragment, make_client):
    client, _ = make_client(error)
    response = client.post('/api/omdb/test', json={'api_key': 'key'})
    assert response.status_code == 400
    assert fragment in response.json['message']
