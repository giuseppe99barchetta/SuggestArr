"""A person can set up their own AI provider; everyone else uses the one the administrator shared."""
from unittest.mock import patch

import pytest
from flask import Flask, g

import api_service.db.database_manager as dm_mod
from api_service.blueprints.config import routes
from api_service.db.database_manager import DatabaseManager
from api_service.services.llm import llm_service

PUBLIC = 'https://api.example.com/v1'
SHARED = {'OPENAI_API_KEY': 'admin-key', 'OPENAI_BASE_URL': '', 'LLM_MODEL': 'shared-model'}


@pytest.fixture
def db(tmp_path):
    with patch.object(dm_mod, 'DB_PATH', str(tmp_path / 'ai.db')), \
            patch('api_service.db.database_manager.load_env_vars', return_value={'DB_TYPE': 'sqlite'}):
        DatabaseManager._instance = None
        yield DatabaseManager()
        DatabaseManager._instance = None


@pytest.fixture(autouse=True)
def no_dns():
    """Addresses are checked for real only where a test says so."""
    with patch.object(routes, 'validate_url'), patch.object(llm_service, 'validate_url'):
        yield


@pytest.fixture
def shared_config():
    with patch.object(llm_service.ConfigService, 'get_runtime_config', return_value=dict(SHARED)):
        yield


def make_user(db, name, role='user', can_manage_ai=0):
    user_id = db.create_auth_user(name, 'hash', role)
    db.update_auth_user(user_id, {'can_manage_ai': can_manage_ai})
    return user_id


def save_personal(db, user_id, **values):
    import json
    db.create_user_media_profile(user_id=user_id, provider='openai', external_user_id=str(user_id),
                                 external_username='x', access_token=json.dumps(
                                     {'api_key': '', 'base_url': '', 'model': '', **values}))


def test_a_person_with_permission_and_their_own_provider_uses_it(db, shared_config):
    user = make_user(db, 'ann', can_manage_ai=1)
    save_personal(db, user, api_key='ann-key', model='ann-model')
    config = llm_service.llm_runtime_config(user)
    assert (config['OPENAI_API_KEY'], config['LLM_MODEL']) == ('ann-key', 'ann-model')
    assert llm_service.get_llm_client(user).api_key == 'ann-key'


def test_everyone_else_gets_the_shared_provider(db, shared_config):
    user = make_user(db, 'bob', can_manage_ai=1)
    assert llm_service.llm_runtime_config(user)['OPENAI_API_KEY'] == 'admin-key'  # no personal provider yet
    assert llm_service.llm_runtime_config(None)['OPENAI_API_KEY'] == 'admin-key'  # scheduled work, no person
    save_personal(db, user, api_key='bob-key')
    db.update_auth_user(user, {'can_manage_ai': 0})  # permission taken away
    assert llm_service.llm_runtime_config(user)['OPENAI_API_KEY'] == 'admin-key'
    db.update_auth_user(user, {'can_manage_ai': 1, 'is_active': 0})  # account disabled
    assert llm_service.llm_runtime_config(user)['OPENAI_API_KEY'] == 'admin-key'


def test_an_administrator_may_have_a_personal_provider_too(db, shared_config):
    admin = make_user(db, 'root', role='admin')
    save_personal(db, admin, api_key='root-key')
    assert llm_service.llm_runtime_config(admin)['OPENAI_API_KEY'] == 'root-key'


def test_the_admin_key_never_goes_to_an_address_a_person_chose(db, shared_config):
    user = make_user(db, 'cy', can_manage_ai=1)
    save_personal(db, user, base_url='http://ollama.lan:11434/v1')  # a local provider, no key
    config = llm_service.llm_runtime_config(user)
    assert config['OPENAI_API_KEY'] == '' and config['OPENAI_BASE_URL'] == 'http://ollama.lan:11434/v1'
    assert config['LLM_MODEL'] == 'shared-model'  # no personal model: the shared setting
    client = llm_service.get_llm_client(user)
    assert client.api_key != 'admin-key' and 'ollama.lan' in str(client.base_url)


def test_a_personal_provider_is_not_a_media_server_account(db):
    user = make_user(db, 'di', can_manage_ai=1)
    save_personal(db, user, api_key='k')
    assert db.get_user_media_profiles(user) == []  # it would otherwise count as a media identity


# ---- the settings endpoints ---------------------------------------------------

def call(db, user_id, method, body=None):
    app = Flask(__name__)
    app.register_blueprint(routes.config_bp, url_prefix='/api/config')
    account = db.get_auth_user_by_id(user_id) if user_id else None

    @app.before_request
    def _caller():
        if account:
            g.current_user = {'id': str(account['id']), 'username': account['username'], 'role': account['role'],
                              'can_manage_ai': account['can_manage_ai']}

    with patch.object(routes, 'DatabaseManager', return_value=db):
        return getattr(app.test_client(), method)('/api/config/openai/user', json=body)


def test_only_people_allowed_to_manage_ai_reach_the_endpoints(db):
    plain = make_user(db, 'eve')
    assert call(db, None, 'get').status_code == 401
    for method in ('get', 'post', 'delete'):
        assert call(db, plain, method, {'openai_api_key': 'k'} if method == 'post' else None).status_code == 403


def test_save_read_edit_and_remove_a_personal_provider(db, shared_config):
    user = make_user(db, 'fay', can_manage_ai=1)
    assert call(db, user, 'get').status_code == 404
    assert call(db, user, 'post', {'openai_api_key': 'sk-secret-1234', 'llm_model': 'm1'}).status_code == 200
    shown = call(db, user, 'get').get_json()
    assert shown['openai_api_key'] == '****1234' and 'secret' not in str(shown) and shown['llm_model'] == 'm1'
    # editing only the model keeps the saved key
    assert call(db, user, 'post', {'llm_model': 'm2', 'openai_base_url': ''}).status_code == 200
    assert llm_service.llm_runtime_config(user)['OPENAI_API_KEY'] == 'sk-secret-1234'
    assert llm_service.llm_runtime_config(user)['LLM_MODEL'] == 'm2'
    assert call(db, user, 'delete').status_code == 200
    assert llm_service.llm_runtime_config(user)['OPENAI_API_KEY'] == 'admin-key'


def test_a_changed_address_does_not_keep_the_old_key(db):
    user = make_user(db, 'gus', can_manage_ai=1)
    call(db, user, 'post', {'openai_api_key': 'k-old', 'openai_base_url': 'https://a.example/v1'})
    call(db, user, 'post', {'openai_base_url': 'https://b.example/v1'})
    stored = llm_service.personal_llm_settings(user)
    assert stored['api_key'] == '' and stored['base_url'] == 'https://b.example/v1'


@pytest.mark.parametrize('body', [
    {}, {'openai_api_key': 5}, {'openai_base_url': 'ftp://x'}, {'openai_base_url': 'not a url'},
    {'openai_api_key': 'k' * 600}, {'openai_api_key': 'k', 'llm_model': ['m']},
])
def test_invalid_provider_settings_are_refused(db, body):
    user = make_user(db, 'hal', can_manage_ai=1)
    assert call(db, user, 'post', body).status_code == 400
    assert llm_service.personal_llm_settings(user) is None


# ---- where a personal address may point --------------------------------------

def test_only_an_administrator_may_point_the_server_at_a_private_address(db):
    from api_service.utils import ssrf_guard
    plain = make_user(db, 'ivy', can_manage_ai=1)
    admin = make_user(db, 'root2', role='admin')
    body = {'openai_base_url': 'http://127.0.0.1:11434/v1'}
    with patch.object(routes, 'validate_url', ssrf_guard.validate_url):
        assert call(db, plain, 'post', body).status_code == 400
        assert call(db, admin, 'post', body).status_code == 200
    assert llm_service.personal_llm_settings(plain) is None
    assert llm_service.personal_llm_settings(admin)['base_url'] == body['openai_base_url']


def test_an_address_that_stopped_being_public_is_not_used_and_the_shared_provider_answers(db, shared_config):
    user = make_user(db, 'jo', can_manage_ai=1)
    save_personal(db, user, api_key='jo-key', base_url=PUBLIC)
    with patch.object(llm_service, 'validate_url', side_effect=ValueError('Connections to non-public addresses are not allowed')):
        assert llm_service.llm_runtime_config(user)['OPENAI_API_KEY'] == 'admin-key'
