"""Authorization, destination binding and public integration projections."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from flask import Flask, g

from api_service.blueprints.plex.routes import plex_bp
from api_service.blueprints.jellyfin.routes import jellyfin_bp
from api_service.blueprints.seer.routes import seer_bp
from api_service.services.integration_security import bind_flat_credentials, select_credentials
from api_service.services.config_secrets import merge_integration_config


@pytest.fixture
def integration_app():
    app = Flask(__name__)
    app.config.update(TESTING=True, TEST_ROLE='user')

    @app.before_request
    def identity():
        role = app.config['TEST_ROLE']
        if role:
            g.current_user = {'id': '1', 'role': role}

    for name, blueprint in (('plex', plex_bp), ('jellyfin', jellyfin_bp), ('seer', seer_bp)):
        app.register_blueprint(blueprint, url_prefix=f'/api/{name}')
    return app


@pytest.mark.parametrize('role,status', [(None, 401), ('user', 403)])
@pytest.mark.parametrize('method,path', [
    ('post', '/api/plex/libraries'), ('post', '/api/plex/auth'), ('post', '/api/plex/callback'),
    ('get', '/api/plex/check-auth/1'), ('post', '/api/plex/servers'), ('post', '/api/plex/test'),
    ('post', '/api/plex/users'), ('post', '/api/plex/api/v1/auth/plex'),
    ('get', '/api/jellyfin/libraries'), ('post', '/api/jellyfin/users'), ('get', '/api/jellyfin/test'),
    ('get', '/api/seer/get_users'), ('post', '/api/seer/login'), ('get', '/api/seer/test'),
    ('post', '/api/seer/radarr-servers'), ('post', '/api/seer/sonarr-servers'),
])
def test_admin_operations_reject_before_network(integration_app, role, status, method, path):
    integration_app.config['TEST_ROLE'] = role
    with patch('api_service.services.http.guarded_session.aiohttp.ClientSession') as network:
        result = getattr(integration_app.test_client(), method)(path, json={})
        assert result.status_code == status
        network.assert_not_called()


@pytest.mark.parametrize('provider', ['radarr', 'sonarr'])
def test_user_profiles_use_saved_configuration_and_strip_upstream_secrets(integration_app, provider):
    upstream = [{
        'id': 0, 'name': 'Movies', 'is4k': False, 'apiKey': 'do-not-expose', 'hostname': 'internal',
        'profiles': [{'id': 1, 'name': 'HD', 'secret': 'do-not-expose'}],
        'rootFolders': [{'id': 2, 'path': '/media', 'internal': 'do-not-expose'}],
        'tags': [{'id': 3, 'label': 'Anime', 'secret': 'do-not-expose'}],
    }]
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock()
    setattr(client, f'get_{provider}_servers', AsyncMock(return_value=upstream))
    with patch('api_service.blueprints.seer.routes._load_seer_config', return_value=('http://seer/base', 'saved-key', 'saved-cookie')) as saved, \
         patch('api_service.blueprints.seer.routes.validate_url'), \
         patch('api_service.blueprints.seer.routes.SeerClient', return_value=client) as factory:
        result = integration_app.test_client().get(f'/api/seer/{provider}-servers')
        assert result.status_code == 200
        saved.assert_called_once()
        factory.assert_called_once_with(api_url='http://seer/base', api_key='saved-key', session_token='saved-cookie')
        assert 'do-not-expose' not in result.text and 'internal' not in result.text
        server = result.json['servers'][0]
        assert server['id'] == 0
        assert server['profiles'] == [{'id': 1, 'name': 'HD'}]
        assert server['rootFolders'] == [{'id': 2, 'path': '/media'}]


@pytest.mark.parametrize('role', ['user', 'admin'])
def test_configured_gets_refuse_query_and_body_overrides(integration_app, role):
    integration_app.config['TEST_ROLE'] = role
    with patch('api_service.blueprints.seer.routes._load_seer_config') as saved:
        client = integration_app.test_client()
        assert client.get('/api/seer/radarr-servers?SEER_API_URL=http://evil').status_code == 400
        assert client.get('/api/seer/sonarr-servers', json={'SEER_TOKEN': 'evil'}).status_code == 400
        saved.assert_not_called()


@pytest.mark.parametrize('data', [{'SEER_API_URL': 'http://evil'}, {'SEER_TOKEN': 'new'}, {'SEER_SESSION_TOKEN': 'new'}])
def test_admin_partial_credentials_do_not_load_saved_secrets(integration_app, data):
    integration_app.config['TEST_ROLE'] = 'admin'
    with patch('api_service.blueprints.seer.routes._load_seer_config') as saved:
        result = integration_app.test_client().post('/api/seer/test', json=data)
        assert result.status_code == 400
        saved.assert_not_called()


def test_complete_explicit_credentials_do_not_inherit_session():
    saved = MagicMock()
    assert select_credentials({'URL': 'http://new', 'KEY': 'new'}, ('URL', 'KEY'), saved, ('SESSION',)) == ('http://new', 'new', None)
    saved.assert_not_called()


@pytest.mark.parametrize('token', [None, '***', ''])
def test_url_change_requires_explicit_token(token):
    incoming = {'SEER_API_URL': 'https://new/base'}
    if token is not None:
        incoming['SEER_TOKEN'] = token
    with pytest.raises(ValueError):
        bind_flat_credentials(incoming, {'SEER_API_URL': 'https://old/base', 'SEER_TOKEN': 'saved'})


def test_same_destination_keeps_redaction_and_url_change_discards_session():
    existing = {'api_url': 'https://seer/base', 'api_key': 'saved', 'session_token': 'old-cookie'}
    same = merge_integration_config('seer', {'api_url': 'https://SEER:443/base/', 'api_key': '***'}, existing)
    assert same['api_key'] == 'saved' and same['session_token'] == 'old-cookie'
    changed = merge_integration_config('seer', {'api_url': 'https://new/base', 'api_key': 'new'}, existing)
    assert changed['api_key'] == 'new' and changed['session_token'] == ''
    rotated = merge_integration_config('seer', {'api_key': 'rotated'}, existing)
    assert rotated['session_token'] == ''


def test_config_route_rejects_cross_destination_redacted_secret():
    from api_service.blueprints.config.routes import _merge_secrets
    db = MagicMock()
    db.get_all_integrations.return_value = {'seer': {'api_url': 'http://old', 'api_key': 'saved'}}
    with patch('api_service.blueprints.config.routes.DatabaseManager', return_value=db):
        with pytest.raises(ValueError):
            _merge_secrets({'SEER_API_URL': 'http://new', 'SEER_TOKEN': '***'}, {})


def test_invalid_import_is_validated_before_any_integration_write():
    from api_service.services.config_service import ConfigService, CURRENT_VERSION
    db = MagicMock()
    db.get_integration.return_value = {}
    with patch('api_service.services.config_service.DatabaseManager', return_value=db), \
         patch('api_service.services.config_service.load_env_vars', return_value={}):
        with pytest.raises(ValueError):
            ConfigService.import_config({'version': CURRENT_VERSION, 'integrations': {
                'tmdb': {'api_key': 'new'}, 'seer': {'api_url': 'http://seer/?bad=1', 'api_key': 'new'},
            }})
        db.set_integration.assert_not_called()


def test_import_does_not_carry_legacy_login_credentials_to_new_seer():
    from api_service.services.config_service import ConfigService, CURRENT_VERSION
    db = MagicMock()
    db.get_integration.return_value = {'api_url': 'http://old', 'api_key': 'old-key'}
    old = {'SEER_API_URL': 'http://old', 'SEER_TOKEN': 'old-key',
           'SEER_USER_NAME': 'old-user', 'SEER_USER_PSW': 'old-password'}
    with patch('api_service.services.config_service.DatabaseManager', return_value=db), \
         patch('api_service.services.config_service.load_env_vars', return_value=old), \
         patch('api_service.services.config_service.save_env_vars') as save:
        ConfigService.import_config({'version': CURRENT_VERSION, 'integrations': {
            'seer': {'api_url': 'http://new', 'api_key': 'new-key'},
        }, 'settings': {'SEER_USER_PSW': '***'}})
        assert save.call_args.args[0]['SEER_USER_NAME'] == ''
        assert save.call_args.args[0]['SEER_USER_PSW'] == ''
