"""Exercise the actual WSGI proxy boundary, not just patched remote_addr values."""
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

from api_service.auth.middleware import (
    enforce_authentication, invalidate_setup_cache, _is_setup_mode,
)
from api_service.auth.limiter import suggestarr_rate_limit_key
from api_service.blueprints.auth.routes import auth_bp


@pytest.fixture
def proxy_app(monkeypatch):
    monkeypatch.setenv('AUTH_MODE', 'local_bypass')
    monkeypatch.delenv('SUGGESTARR_AUTH_DISABLED', raising=False)
    monkeypatch.setenv('AUTH_TRUSTED_CIDRS', '192.168.0.0/16,127.0.0.0/8,::1/128')
    monkeypatch.setenv('AUTH_TRUSTED_PROXY_CIDRS', '10.0.0.1/32,10.0.0.2/32')
    db = MagicMock()
    db.get_auth_user_count.return_value = 1
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.before_request(enforce_authentication)

    @app.get('/api/protected')
    def protected():
        return jsonify(user=g.current_user, rate_key=suggestarr_rate_limit_key())

    with patch('api_service.auth.middleware.DatabaseManager', return_value=db), \
         patch('api_service.blueprints.auth.routes.DatabaseManager', return_value=db), \
         patch('api_service.blueprints.auth.routes.ConfigService.get_runtime_config', return_value={}), \
         patch('api_service.auth.middleware._load_bypass_user_context', return_value={'id': 1, 'role': 'admin'}), \
         patch('api_service.blueprints.auth.routes._load_bypass_user_context', return_value={'id': 1, 'role': 'admin'}):
        invalidate_setup_cache()
        yield app, db
        invalidate_setup_cache()


@pytest.mark.parametrize('peer,forwarded,allowed', [
    ('8.8.8.8', '127.0.0.1', False),
    ('192.168.1.5', None, True),
    ('192.168.1.5', '127.0.0.1', False),
    ('10.0.0.1', '8.8.8.8', False),
    ('10.0.0.1', '192.168.1.5', True),
    ('10.0.0.1', '127.0.0.1, 8.8.8.8', False),
    ('10.0.0.1', '192.168.1.5, 10.0.0.2', True),
    ('10.0.0.1', '8.8.8.8, 10.0.0.2', False),
    ('10.0.0.1', None, False),
    ('10.0.0.1', '10.0.0.2', False),
    ('10.0.0.1', 'invalid, 192.168.1.5', False),
    ('10.0.0.1', '192.168.1.5,', False),
    ('::1', None, True),
])
def test_proxy_boundary_and_status_agree(proxy_app, peer, forwarded, allowed):
    app, _ = proxy_app
    headers = {'X-Forwarded-For': forwarded} if forwarded is not None else {}
    args = dict(headers=headers, environ_base={'REMOTE_ADDR': peer})
    with app.test_client() as client:
        result = client.get('/api/protected', **args)
        assert result.status_code == (200 if allowed else 401)
        status = client.get('/api/auth/status', **args)
        assert status.status_code == 200
        assert status.json['authenticated'] is allowed
        assert status.json.get('bypass', False) is allowed


@pytest.mark.parametrize('key', ['AUTH_TRUSTED_CIDRS', 'AUTH_TRUSTED_PROXY_CIDRS'])
@pytest.mark.parametrize('value', ['', 'bad', '127.0.0.0/8,bad'])
def test_explicit_invalid_trust_never_restores_defaults(proxy_app, monkeypatch, key, value):
    from api_service.auth.middleware import _load_trusted_cidrs
    monkeypatch.setenv(key, value)
    assert _load_trusted_cidrs(key) == []


def test_rate_limit_key_ignores_forged_client(proxy_app):
    app, _ = proxy_app
    with app.test_request_context(environ_base={'REMOTE_ADDR': '8.8.8.8'},
                                  headers={'X-Forwarded-For': '127.0.0.1'}):
        assert suggestarr_rate_limit_key() == '8.8.8.8'
    with app.test_request_context(environ_base={'REMOTE_ADDR': '10.0.0.1'},
                                  headers={'X-Forwarded-For': '8.8.4.4'}):
        assert suggestarr_rate_limit_key() == '8.8.4.4'


def test_missing_original_peer_is_never_replaced_by_forwarded_address(proxy_app):
    from api_service.auth.middleware import _local_bypass_allowed
    app, _ = proxy_app
    with app.test_request_context(headers={'X-Forwarded-For': '192.168.1.5'},
                                  environ_base={'REMOTE_ADDR': '10.0.0.1'}):
        from flask import request
        request.environ['werkzeug.proxy_fix.orig'] = {'REMOTE_ADDR': ''}
        assert _local_bypass_allowed() is False


def test_setup_error_never_reuses_cached_zero_users(proxy_app, monkeypatch):
    app, db = proxy_app
    monkeypatch.setenv('AUTH_MODE', 'enabled')
    db.get_auth_user_count.return_value = 0
    assert _is_setup_mode() is True
    db.get_auth_user_count.side_effect = OSError('private database details')
    with app.test_client() as client:
        for path in ('/api/protected', '/api/auth/status'):
            result = client.get(path)
            assert result.status_code == 503
            assert result.json == {'error': 'Authentication service unavailable'}
    db.get_auth_user_count.side_effect = None
    db.get_auth_user_count.return_value = 1
    assert _is_setup_mode() is False


def test_explicit_credentials_keep_precedence(proxy_app):
    from api_service.auth.auth_service import AuthService
    app, _ = proxy_app
    with app.test_client() as client:
        result = client.get('/api/protected', headers={'Authorization': 'Bearer invalid'},
                            environ_base={'REMOTE_ADDR': '192.168.1.5'})
        assert result.status_code == 401
        with patch.object(AuthService, 'verify_access_token', return_value={'sub': '2', 'role': 'user'}):
            result = client.get('/api/protected', headers={'Authorization': 'Bearer valid'})
            assert result.status_code == 200
            assert result.json['user']['role'] == 'user'


def test_explicit_empty_trust_lists_survive_yaml_save(tmp_path):
    import yaml
    from api_service.config.config import save_env_vars
    target = tmp_path / 'config.yaml'
    with patch('api_service.config.config.CONFIG_PATH', str(target)):
        save_env_vars({'AUTH_TRUSTED_CIDRS': '', 'AUTH_TRUSTED_PROXY_CIDRS': ''})
    config = yaml.safe_load(target.read_text())
    assert config['AUTH_TRUSTED_CIDRS'] == ''
    assert config['AUTH_TRUSTED_PROXY_CIDRS'] == ''
