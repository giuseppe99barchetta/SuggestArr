from unittest.mock import AsyncMock, MagicMock

import pytest
from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.arr import routes
from api_service.services.arr.arr_client import ArrClient

SAVED = {'RADARR_API_URL': 'http://radarr:7878', 'RADARR_TOKEN': 'saved-test-key'}


def client_as(role, monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)

    @app.before_request
    def authenticate():
        if role:
            g.current_user = {'id': 7, 'role': role}
    limiter.init_app(app)
    app.register_blueprint(routes.arr_bp, url_prefix='/api/arr')
    provider = MagicMock()
    provider.__aenter__ = AsyncMock(return_value=provider)
    provider.__aexit__ = AsyncMock(return_value=False)
    provider.test_connection = AsyncMock()
    factory = MagicMock(return_value=provider)
    monkeypatch.setattr(routes, 'ArrClient', factory)
    monkeypatch.setattr(routes.ConfigService, 'get_runtime_config', lambda: SAVED)
    return app.test_client(), factory, provider


@pytest.mark.parametrize('role', ['user', 'viewer', None])
def test_connection_requires_admin(role, monkeypatch):
    client, factory, _ = client_as(role, monkeypatch)
    assert client.post('/api/arr/test', json={'service': 'radarr'}).status_code in (401, 403)
    factory.assert_not_called()


@pytest.mark.parametrize('payload', [None, {}, {'service': 'plex'},
                                     {'service': 'radarr', 'RADARR_API_URL': 'http://x'},
                                     {'service': 'radarr', 'RADARR_API_URL': 'http://x', 'RADARR_TOKEN': '***'},
                                     {'service': 'sonarr'}])
def test_validation(payload, monkeypatch):
    client, factory, _ = client_as('admin', monkeypatch)
    assert client.post('/api/arr/test', json=payload).status_code == 400
    factory.assert_not_called()


def test_uses_saved_credentials_without_returning_them(monkeypatch):
    client, factory, provider = client_as('admin', monkeypatch)
    response = client.post('/api/arr/test', json={'service': 'radarr'})
    assert response.status_code == 200
    factory.assert_called_once_with('radarr', 'http://radarr:7878', 'saved-test-key')
    assert 'saved-test-key' not in response.get_data(as_text=True)
    provider.__aexit__.assert_awaited_once()


def test_failure_does_not_leak_secrets(monkeypatch, caplog):
    client, _, provider = client_as('admin', monkeypatch)
    provider.test_connection.side_effect = RuntimeError('private-key')
    response = client.post('/api/arr/test', json={'service': 'radarr', 'RADARR_API_URL': 'http://x', 'RADARR_TOKEN': 'private-key'})
    assert response.status_code == 400
    assert 'private-key' not in response.get_data(as_text=True)
    assert 'private-key' not in caplog.text


@pytest.mark.asyncio
async def test_get_tmdb_ids_reads_every_title_and_skips_entries_without_tmdb_id():
    client = ArrClient('sonarr', 'http://sonarr:8989/', 'k')
    client._get = AsyncMock(return_value=[{'tmdbId': 1399, 'monitored': False}, {'tmdbId': 0}, {'title': 'x'}])
    assert await client.get_tmdb_ids() == {'1399'}
    client._get.assert_awaited_once_with('series')
    assert client.api_url == 'http://sonarr:8989'


def test_job_owner_reads_saved_options_without_credentials(monkeypatch):
    client, factory, provider = client_as('user', monkeypatch)
    provider.get_options = AsyncMock(return_value={'profiles': [{'id': 4, 'name': 'HD'}], 'rootFolders': [], 'tags': []})
    response = client.get('/api/arr/options?service=radarr')
    assert response.status_code == 200
    assert response.get_json()['profiles'] == [{'id': 4, 'name': 'HD'}]
    factory.assert_called_once_with('radarr', 'http://radarr:7878', 'saved-test-key')
    assert 'saved-test-key' not in response.get_data(as_text=True)


@pytest.mark.parametrize('query', ['', '?service=plex', '?service=radarr&RADARR_API_URL=http://x',
                                   '?service=radarr&RADARR_TOKEN=k'])
def test_saved_options_refuse_overrides(query, monkeypatch):
    client, factory, _ = client_as('user', monkeypatch)
    assert client.get(f'/api/arr/options{query}').status_code == 400
    factory.assert_not_called()


def test_saved_options_need_login_and_the_jobs_page(monkeypatch):
    client, factory, _ = client_as(None, monkeypatch)
    assert client.get('/api/arr/options?service=radarr').status_code == 401
    client, factory, _ = client_as('user', monkeypatch)
    monkeypatch.setattr(routes, 'require_tab', lambda tab: ('refused', 403))
    assert client.get('/api/arr/options?service=radarr').status_code == 403
    factory.assert_not_called()


def test_explicit_options_still_require_admin(monkeypatch):
    client, factory, _ = client_as('user', monkeypatch)
    assert client.post('/api/arr/options', json={'service': 'radarr'}).status_code == 403
    factory.assert_not_called()
