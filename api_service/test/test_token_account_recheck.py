"""A signed access token is not enough: the account behind it must still exist, be active and keep its role."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from flask import Flask, g, jsonify

from api_service.auth import auth_service, middleware

KEY = 'token-recheck-test-signing-key-never-used-in-production'


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.before_request(middleware.enforce_authentication)

    @app.route('/api/protected')
    def protected():
        return jsonify(g.current_user)

    with patch.object(auth_service, 'load_secret_key', return_value=KEY), \
            patch.object(middleware, 'load_env_vars', return_value={'AUTH_MODE': 'enabled'}), \
            patch.object(middleware, '_is_setup_mode', return_value=False):
        yield app.test_client()


def token(sub='5', role='admin'):
    return jwt.encode({'sub': sub, 'role': role, 'username': 'old-name',
                       'exp': datetime.now(timezone.utc) + timedelta(minutes=5)}, KEY, algorithm='HS256')


def get(client, bearer, account=None, error=None):
    db = MagicMock()
    if error:
        db.get_auth_user_by_id.side_effect = error
    else:
        db.get_auth_user_by_id.return_value = account
    manager = MagicMock(return_value=db)
    with patch.object(middleware, '_get_database_manager', return_value=manager):
        return client.get('/api/protected', headers={'Authorization': f'Bearer {bearer}'}), db


def account(**fields):
    return {'id': 5, 'username': 'alice', 'role': 'user', 'is_active': True,
            'can_manage_ai': 0, 'visible_tabs': 'requests,profile', **fields}


def test_an_active_account_is_authenticated_with_its_current_role_not_the_tokens(client):
    response, db = get(client, token(role='admin'), account(role='user'))
    assert response.status_code == 200
    assert response.json['role'] == 'user' and response.json['username'] == 'alice'  # demoted since the token
    db.get_auth_user_by_id.assert_called_once_with(5)


def test_a_deactivated_account_loses_access_with_a_still_valid_token(client):
    response, _ = get(client, token(), account(is_active=False))
    assert response.status_code == 401


def test_a_deleted_account_loses_access_with_a_still_valid_token(client):
    response, _ = get(client, token(), None)
    assert response.status_code == 401


def test_a_token_without_a_valid_subject_is_refused_without_a_lookup(client):
    for sub in ('abc', ''):
        response, db = get(client, token(sub=sub), account())
        assert response.status_code == 401
        db.get_auth_user_by_id.assert_not_called()


def test_a_database_failure_is_reported_as_unavailable_not_as_a_bad_token(client):
    response, _ = get(client, token(), error=RuntimeError('database is locked'))
    assert response.status_code == 503
    assert response.json == {'error': 'Authentication service unavailable'}
