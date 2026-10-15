from unittest.mock import AsyncMock, MagicMock

import pytest
from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.mdblist import routes
from api_service.services.mdblist.mdblist_client import MDBListClient
from api_service.services.public_lists import PublicListError
from api_service.test.test_list_import import FakeResponse, FakeSession


def client_as(role, monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
    @app.before_request
    def authenticate():
        if role:
            g.current_user = {'id': 7, 'role': role}
    limiter.init_app(app)
    app.register_blueprint(routes.mdblist_bp, url_prefix='/api/mdblist')
    provider = MagicMock()
    provider.__aenter__ = AsyncMock(return_value=provider)
    provider.__aexit__ = AsyncMock(return_value=False)
    provider.test_connection = AsyncMock()
    factory = MagicMock(return_value=provider)
    monkeypatch.setattr(routes, 'MDBListClient', factory)
    monkeypatch.setattr(routes.ConfigService, 'get_runtime_config', lambda: {'MDBLIST_API_KEY': 'saved-test-key'})
    return app.test_client(), factory, provider


@pytest.mark.parametrize('role', ['user', 'viewer', None])
def test_connection_requires_admin(role, monkeypatch):
    client, factory, _ = client_as(role, monkeypatch)
    assert client.post('/api/mdblist/test', json={'api_key': 'test-key'}).status_code in (401, 403)
    factory.assert_not_called()


@pytest.mark.parametrize('payload', [None, [], {}, {'api_key': None}, {'api_key': ''}, {'api_key': '  '}, {'api_key': 123}])
def test_key_validation(payload, monkeypatch):
    client, factory, _ = client_as('admin', monkeypatch)
    assert client.post('/api/mdblist/test', json=payload).status_code == 400
    factory.assert_not_called()


@pytest.mark.parametrize('input_key,expected', [('  entered-test-key  ', 'entered-test-key'), ('***', 'saved-test-key')])
def test_connection_validates_entered_or_saved_key_without_returning_it(input_key, expected, monkeypatch):
    client, factory, provider = client_as('admin', monkeypatch)
    response = client.post('/api/mdblist/test', json={'api_key': input_key})
    assert response.status_code == 200 and response.json['status'] == 'success'
    factory.assert_called_once_with(expected)
    assert expected not in response.get_data(as_text=True)
    provider.test_connection.assert_awaited_once()
    provider.__aexit__.assert_awaited_once()


@pytest.mark.parametrize('error,code', [(PublicListError('private-key'), 400), (RuntimeError('private-key'), 502)])
def test_connection_errors_close_client_and_do_not_leak_secrets(error, code, monkeypatch, caplog):
    client, _, provider = client_as('admin', monkeypatch)
    provider.test_connection.side_effect = error
    response = client.post('/api/mdblist/test', json={'api_key': 'private-key'})
    assert response.status_code == code
    assert 'private-key' not in response.get_data(as_text=True)
    assert 'private-key' not in caplog.text
    provider.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [{'user_id': 1, 'api_requests': 1000}, {}, {'error': 'Invalid API key!'}, ['unexpected']])
async def test_client_uses_authenticated_user_endpoint(payload):
    client = MDBListClient('test-key')
    session = FakeSession([FakeResponse(200, payload)])
    client.session = session
    if isinstance(payload, dict) and payload.get('user_id'):
        await client.test_connection()
    else:
        with pytest.raises(PublicListError):
            await client.test_connection()
    assert session.calls[0][1] == 'https://api.mdblist.com/user'
    assert session.calls[0][2]['allow_redirects'] is False
    assert session.calls[0][2]['params'] == {'apikey': 'test-key'}
