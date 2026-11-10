"""Request backend selection: configuration rules, direct Radarr/Sonarr delivery, per-row routing."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api_service.config.config import validate_request_backend
from api_service.jobs.queue_worker import _run_worker
from api_service.services.arr.arr_client import ArrClient
from api_service.services.arr.arr_request_client import ArrRequestClient

SEER = {'SEER_API_URL': 'http://seer:5055', 'SEER_TOKEN': 'k'}
RADARR = {'RADARR_API_URL': 'http://radarr:7878', 'RADARR_TOKEN': 'k'}
SONARR = {'SONARR_API_URL': 'http://sonarr:8989', 'SONARR_TOKEN': 'k'}
PROFILES = {'default_movie': {'profileId': 4, 'rootFolder': '/movies', 'tags': [1]},
            'default_tv': {'profileId': 6, 'rootFolder': '/tv'}}
ARR_ENV = {**RADARR, **SONARR, 'ARR_PROFILE_CONFIG': PROFILES, 'REQUEST_BACKEND': 'arr'}


# --- validate_request_backend ---------------------------------------------

def test_unrelated_saves_pass_on_an_install_without_seer():
    current = {'SETUP_COMPLETED': True, 'SELECTED_SERVICE': 'plex'}  # no backend key: 'seer', no Seer configured
    # a full services form resubmits every backend field unchanged
    validate_request_backend({**current, 'REQUEST_BACKEND': 'seer', 'SEER_API_URL': '', 'SEER_TOKEN': '',
                              'ARR_PROFILE_CONFIG': {}, 'LOG_LEVEL': 'DEBUG'}, current)
    validate_request_backend({'LOG_LEVEL': 'DEBUG'}, None)  # fresh install


def test_invalid_backend_value_is_always_rejected():
    with pytest.raises(ValueError):
        validate_request_backend({'REQUEST_BACKEND': 'plex'}, None)


@pytest.mark.parametrize('config,message', [
    ({'REQUEST_BACKEND': 'arr'}, 'at least one Radarr or Sonarr'),
    ({'REQUEST_BACKEND': 'arr', **RADARR}, 'default quality profile'),
    ({'REQUEST_BACKEND': 'both', **RADARR}, 'Seer URL'),
    ({'REQUEST_BACKEND': 'both', **SEER}, 'at least one Radarr or Sonarr'),
])
def test_choosing_a_backend_requires_its_prerequisites(config, message):
    with pytest.raises(ValueError, match=message):
        validate_request_backend(config, {'SETUP_COMPLETED': True})


def test_valid_backends_are_accepted():
    validate_request_backend(ARR_ENV, {})
    validate_request_backend({'REQUEST_BACKEND': 'both', **SEER, **SONARR}, {})  # no profiles needed: Arr does not deliver
    validate_request_backend({'REQUEST_BACKEND': 'arr', **RADARR, 'ARR_PROFILE_CONFIG': PROFILES}, {})  # one instance is enough


def test_changing_prerequisites_of_the_active_backend_is_validated_after_setup():
    current = {**ARR_ENV, 'SETUP_COMPLETED': True}
    cleared = {**current, 'ARR_PROFILE_CONFIG': {'default_tv': PROFILES['default_tv']}}  # profile-only update
    with pytest.raises(ValueError, match='Radarr'):
        validate_request_backend(cleared, current)
    validate_request_backend({**current, 'LOG_LEVEL': 'DEBUG'}, current)
    # before setup completes the same change is not validated
    validate_request_backend({**cleared, 'SETUP_COMPLETED': False}, {**current, 'SETUP_COMPLETED': False})


def test_removing_seer_credentials_of_the_active_backend_is_rejected():
    current = {**SEER, 'SETUP_COMPLETED': True}
    with pytest.raises(ValueError, match='Seer'):
        validate_request_backend({**current, 'SEER_TOKEN': ''}, current)


# --- ArrClient -------------------------------------------------------------

def _client(service, responses):
    client = ArrClient(service, 'http://arr.test/', 'k')
    client._request = AsyncMock(side_effect=responses)
    return client


RADARR_LOOKUP = [{'title': 'Inception', 'tmdbId': 27205, 'year': 2010}]
SONARR_LOOKUP = [{'title': 'GoT', 'tmdbId': 1399, 'tvdbId': 121361,
                  'seasons': [{'seasonNumber': 0, 'monitored': False}, {'seasonNumber': 1, 'monitored': False},
                              {'seasonNumber': 2, 'monitored': False}]}]
PAYLOAD = {'mediaType': 'movie', 'mediaId': 27205, 'profileId': 4, 'rootFolder': '/movies', 'tags': [1]}


def test_add_movie_posts_the_lookup_object_with_profile_and_search():
    client = _client('radarr', [(200, RADARR_LOOKUP), (201, {})])
    assert asyncio.run(client.add(PAYLOAD)) is True
    method, path = client._request.call_args.args
    body = client._request.call_args.kwargs['json']
    assert (method, path) == ('POST', 'movie')
    assert (body['qualityProfileId'], body['rootFolderPath'], body['tags'], body['monitored']) == (4, '/movies', [1], True)
    assert body['addOptions'] == {'searchForMovie': True} and body['title'] == 'Inception'


@pytest.mark.parametrize('seasons,expected', [('all', [False, True, True]), ([1], [False, True, False])])
def test_add_series_monitors_the_requested_seasons_only(seasons, expected):
    client = _client('sonarr', [(200, SONARR_LOOKUP), (201, {})])
    payload = {'mediaType': 'tv', 'mediaId': 1399, 'profileId': 6, 'rootFolder': '/tv', 'seasons': seasons,
               '_is_anime': True}
    assert asyncio.run(client.add(payload)) is True
    body = client._request.call_args.kwargs['json']
    assert [s['monitored'] for s in body['seasons']] == expected
    assert body['seriesType'] == 'anime' and body['addOptions'] == {'searchForMissingEpisodes': True}


def test_already_added_titles_are_a_successful_delivery():
    exists = [{'errorCode': 'MovieExistsValidator', 'errorMessage': 'This movie has already been added'}]
    assert asyncio.run(_client('radarr', [(200, RADARR_LOOKUP), (400, exists)]).add(PAYLOAD)) is True


@pytest.mark.parametrize('responses', [
    [(200, RADARR_LOOKUP), (500, None)],
    [(200, RADARR_LOOKUP), (400, [{'errorCode': 'RootFolderValidator'}])],
    [(200, [])],  # not found by lookup
])
def test_other_failures_raise(responses):
    with pytest.raises(RuntimeError):
        asyncio.run(_client('radarr', responses).add(PAYLOAD))


def test_options_expose_ids_and_names_only():
    client = ArrClient('radarr', 'http://radarr', 'k')
    answers = {'qualityprofile': [{'id': 4, 'name': 'HD', 'cutoff': 1}], 'rootfolder': [{'path': '/movies', 'id': 1}],
               'tag': [{'id': 1, 'label': 'anime'}]}
    client._get = AsyncMock(side_effect=lambda path: answers[path])
    assert asyncio.run(client.get_options()) == {
        'profiles': [{'id': 4, 'name': 'HD'}], 'rootFolders': [{'path': '/movies'}],
        'tags': [{'id': 1, 'label': 'anime'}]}


# --- ArrRequestClient ------------------------------------------------------

def _enqueue(env, media_type='movie', context=None, is_anime=False):
    client = ArrRequestClient(env, exclude_downloaded=False, exclude_requested=False,
                              queue_context=context or {})
    with patch('api_service.services.seer.seer_client.DatabaseManager') as manager, \
            patch('api_service.services.seer.seer_client.load_env_vars', return_value={'SELECTED_SERVICE': 'plex'}):
        db = manager.return_value
        db.enqueue_request.return_value = True
        db.resolve_suggestion_owner.return_value = None
        accepted = asyncio.run(client.request_media(media_type, {'id': 10}, is_anime=is_anime))
    return accepted, db


def test_enqueue_records_the_backend_and_uses_arr_profiles_not_job_profiles():
    context = {'job_id': 1, 'request_profiles': {'movie': {'serverId': 0, 'profileId': 99, 'rootFolder': '/seer'}}}
    accepted, db = _enqueue(ARR_ENV, context=context)
    payload = db.enqueue_request.call_args.args[3]
    assert accepted and payload['_backend'] == 'arr'
    assert (payload['profileId'], payload['rootFolder'], payload['tags']) == (4, '/movies', [1])
    assert 'serverId' not in payload and 'userId' not in payload


def test_anime_without_its_own_profile_falls_back_to_the_default():
    _, db = _enqueue(ARR_ENV, is_anime=True)
    assert db.enqueue_request.call_args.args[3]['profileId'] == 4
    env = {**ARR_ENV, 'ARR_PROFILE_CONFIG': {**PROFILES, 'anime_movie': {'profileId': 8, 'rootFolder': '/anime'}}}
    _, db = _enqueue(env, is_anime=True)
    assert db.enqueue_request.call_args.args[3]['profileId'] == 8
    # a partly filled anime profile keeps the default for the fields left empty
    env = {**ARR_ENV, 'ARR_PROFILE_CONFIG': {**PROFILES, 'anime_movie': {'profileId': None, 'rootFolder': '/anime', 'tags': []}}}
    _, db = _enqueue(env, is_anime=True)
    payload = db.enqueue_request.call_args.args[3]
    assert (payload['profileId'], payload['rootFolder'], payload['tags']) == (4, '/anime', [1])


@pytest.mark.parametrize('env', [
    {**ARR_ENV, 'SONARR_API_URL': ''},  # no Sonarr for a series
    {**ARR_ENV, 'ARR_PROFILE_CONFIG': {'default_movie': PROFILES['default_movie']}},  # no default tv profile
])
def test_a_type_without_instance_or_default_profile_is_refused_at_enqueue(env):
    accepted, db = _enqueue(env, media_type='tv')
    assert accepted is False
    db.enqueue_request.assert_not_called()


def test_direct_backend_has_no_pending_requests_and_no_seer_calls():
    client = ArrRequestClient(ARR_ENV)
    assert asyncio.run(client.has_pending_requests()) is False
    assert asyncio.run(client.get_available_tmdb_ids()) == {}
    asyncio.run(client.init())  # must not touch the network


def test_submit_delivers_to_the_instance_serving_the_type_and_reports_failures():
    client = ArrRequestClient(ARR_ENV)
    fake = MagicMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=False)
    fake.add = AsyncMock(return_value=True)
    with patch('api_service.services.arr.arr_request_client.ArrClient', return_value=fake) as factory:
        assert asyncio.run(client.submit_queued_request({'mediaType': 'tv', 'mediaId': 1})) is True
        factory.assert_called_once_with('sonarr', 'http://sonarr:8989', 'k')
        fake.add.side_effect = RuntimeError('rejected')
        assert asyncio.run(client.submit_queued_request({'mediaType': 'movie', 'mediaId': 1})) is False
    assert asyncio.run(ArrRequestClient({'REQUEST_BACKEND': 'arr'}).submit_queued_request({'mediaType': 'movie'})) is False


# --- queue worker routes each row by its recorded backend -------------------

class _Client:
    def __init__(self, result):
        self.submit_queued_request = AsyncMock(return_value=result)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def init(self):
        return None


def _worker(rows, env, seer, arr):
    db = MagicMock()
    db.expire_pending_approvals.return_value = 0
    db.check_request_exists.return_value = False
    db.get_due_requests.return_value = rows
    with patch('api_service.jobs.queue_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.queue_worker.ConfigService.get_runtime_config', return_value=env), \
            patch('api_service.jobs.queue_worker.SeerClient', return_value=seer) as seer_cls, \
            patch('api_service.jobs.queue_worker.ArrRequestClient', return_value=arr) as arr_cls:
        submitted = asyncio.run(_run_worker())
    return submitted, db, seer_cls, arr_cls


def _row(row_id, backend=None):
    payload = '{"mediaType": "movie"}' if backend is None else f'{{"mediaType": "movie", "_backend": "{backend}"}}'
    return {'id': row_id, 'tmdb_id': str(row_id), 'media_type': 'movie', 'retry_count': 0, 'job_id': 1, 'payload': payload}


def test_rows_are_delivered_by_their_recorded_backend_whatever_the_current_setting():
    seer, arr = _Client({'id': 5, 'createdAt': '2026-01-01T00:00:00.000Z'}), _Client(True)
    env = {**ARR_ENV, **SEER}  # currently 'arr', with Seer credentials still saved
    submitted, db, seer_cls, arr_cls = _worker([_row(1), _row(2, 'seer'), _row(3, 'arr')], env, seer, arr)
    assert submitted == 3
    assert seer.submit_queued_request.await_count == 2  # the legacy row (no _backend) and the seer row
    assert arr.submit_queued_request.await_count == 1
    assert db.track_seer_request.call_count == 2  # only Seer returns a remote id to track


def test_a_backend_that_cannot_be_built_retries_its_rows_without_blocking_the_others():
    arr = _Client(True)
    seer_cls_error = MagicMock(side_effect=ValueError('no url'))
    db = MagicMock()
    db.expire_pending_approvals.return_value = 0
    db.check_request_exists.return_value = False
    db.get_due_requests.return_value = [_row(1, 'seer'), _row(2, 'arr')]
    with patch('api_service.jobs.queue_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.queue_worker.ConfigService.get_runtime_config', return_value=ARR_ENV), \
            patch('api_service.jobs.queue_worker.SeerClient', seer_cls_error), \
            patch('api_service.jobs.queue_worker.ArrRequestClient', return_value=arr):
        assert asyncio.run(_run_worker()) == 1
    db.increment_pending_retry.assert_called_once()


# --- import: validate before writing, restore on failure --------------------

def _import_env():
    return {'SETUP_COMPLETED': True, **SEER, 'SELECTED_SERVICE': 'plex'}


def test_admin_import_that_would_blank_the_active_backends_credentials_writes_nothing():
    from flask import Flask
    from api_service.blueprints.admin import routes as admin_routes

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(admin_routes.admin_bp, url_prefix='/api/admin')
    with patch('api_service.auth.middleware.require_role', lambda *_: (lambda f: f)), \
            patch.object(admin_routes, 'load_env_vars', return_value=_import_env()), \
            patch.object(admin_routes, 'DatabaseManager') as db:
        view = admin_routes.import_config.__wrapped__ if hasattr(admin_routes.import_config, '__wrapped__') \
            else admin_routes.import_config
        with app.test_request_context('/api/admin/import-config', method='POST',
                                      json={'schema_version': 2, 'integrations': {'seer': {'api_url': '', 'api_key': ''}}}):
            response, status = view()
    assert status == 400 and 'Seer' in response.get_json()['error']
    db.return_value.set_integration.assert_not_called()


def _import_service(tmp_path, save_env_vars=None):
    """Run ConfigService.import_config against a temp config file and a fake DB."""
    from api_service.config import config as config_module
    from api_service.services import config_service

    config_file = tmp_path / 'config.yaml'
    config_file.write_text('LOG_LEVEL: INFO\n', encoding='utf-8')
    db = MagicMock()
    db.get_integration.side_effect = lambda service: {'api_key': 'old'} if service == 'tmdb' else None
    patches = [patch.object(config_service, 'DatabaseManager', return_value=db),
               patch.object(config_module, 'CONFIG_PATH', str(config_file)),
               patch.object(config_service, 'load_env_vars', return_value={'LOG_LEVEL': 'INFO'})]
    if save_env_vars:
        patches.append(patch.object(config_service, 'save_env_vars', save_env_vars))
    return config_service, config_file, db, patches


def _run_import(service, data, patches):
    from contextlib import ExitStack
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        service.ConfigService.import_config(data)


DATA = {'version': 2, 'integrations': {'tmdb': {'api_key': 'new'}, 'omdb': {'api_key': 'fresh'}},
        'settings': {'LOG_LEVEL': 'DEBUG'}}


def test_import_with_an_invalid_setting_writes_nothing(tmp_path):
    service, _, db, patches = _import_service(tmp_path)
    with pytest.raises(ValueError):
        _run_import(service, {**DATA, 'settings': {'CRON_TIMES': 'not a cron'}}, patches)
    db.set_integration.assert_not_called()


def test_a_persistence_failure_restores_integrations_and_the_config_file(tmp_path):
    def failing_save(config):
        (tmp_path / 'config.yaml').write_text('LOG_LEVEL: BROKEN\n', encoding='utf-8')
        raise OSError('disk full')

    service, config_file, db, patches = _import_service(tmp_path, save_env_vars=failing_save)
    with pytest.raises(OSError):
        _run_import(service, DATA, patches)
    assert config_file.read_text(encoding='utf-8') == 'LOG_LEVEL: INFO\n'
    restored = [c for c in db.set_integration.call_args_list if c.args[1] == {'api_key': 'old'}]
    assert restored, 'the previous tmdb integration was not restored'
    db.delete_integration.assert_called_once_with('omdb')  # a row created by the failed import is removed


# --- regressions found by the independent inspection -------------------------

def test_adding_radarr_credentials_on_a_seer_install_without_seer_is_not_validated():
    current = {'SETUP_COMPLETED': True}  # default 'seer' backend, no Seer configured
    validate_request_backend({**current, **RADARR}, current)  # optional extra, unrelated to the active backend
    with pytest.raises(ValueError, match='Seer'):  # but touching Seer's own keys is
        validate_request_backend({**current, **SEER, 'SEER_TOKEN': ''}, {**current, **SEER})


def test_an_already_added_conflict_is_a_successful_delivery():
    assert asyncio.run(_client('radarr', [(200, RADARR_LOOKUP), (409, None)]).add(PAYLOAD)) is True


def test_health_reports_configured_arr_instances_without_failing_readiness():
    from api_service.blueprints.health import routes as health

    fake = MagicMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=False)
    fake.test_connection = AsyncMock(side_effect=[None, RuntimeError('down')])
    with patch('api_service.services.arr.arr_client.ArrClient', return_value=fake):
        assert health._run_arr_checks({**RADARR, **SONARR}) == {'radarr': 'ok', 'sonarr': 'error'}
    assert health._run_arr_checks({}) == {}  # nothing configured: the key is omitted from the response


def test_a_failing_admin_import_restores_the_integrations_it_already_wrote():
    from flask import Flask
    from api_service.blueprints.admin import routes as admin_routes

    app = Flask(__name__)
    db = MagicMock()
    db.get_integration.side_effect = lambda service: {'api_key': 'old'} if service == 'tmdb' else None
    db.set_integration.side_effect = [None, None, RuntimeError('disk full'), None]  # third write fails
    payload = {'schema_version': 2, 'integrations': {'tmdb': {'api_key': 'n'}, 'omdb': {'api_key': 'n'},
                                                     'mdblist': {'api_key': 'n'}}}
    view = admin_routes.import_config.__wrapped__ if hasattr(admin_routes.import_config, '__wrapped__') \
        else admin_routes.import_config
    with patch.object(admin_routes, 'DatabaseManager', return_value=db), \
            patch.object(admin_routes, 'load_env_vars', return_value={}), \
            app.test_request_context('/api/admin/import-config', method='POST', json=payload):
        with pytest.raises(RuntimeError):
            view()
    deleted = {c.args[0] for c in db.delete_integration.call_args_list}
    assert 'omdb' in deleted  # created by the failed import (the row that failed to write is cleared too, harmlessly)
    assert any(c.args == ('tmdb', {'api_key': 'old'}) for c in db.set_integration.call_args_list)  # restored


def test_radarr_and_sonarr_settings_travel_through_the_settings_export_and_import():
    """They are flat settings (like Plex), not DB integrations: export redacts the tokens and import restores them."""
    from api_service.services.config_secrets import redact_settings
    from api_service.services.config_service import _DB_INTEGRATION_KEYS, _VALID_SETTING_KEYS
    from api_service.services.integration_security import bind_flat_credentials

    keys = {'RADARR_API_URL', 'RADARR_TOKEN', 'SONARR_API_URL', 'SONARR_TOKEN', 'REQUEST_BACKEND', 'ARR_PROFILE_CONFIG'}
    assert keys <= _VALID_SETTING_KEYS and not keys & _DB_INTEGRATION_KEYS
    exported = redact_settings({**RADARR, 'ARR_PROFILE_CONFIG': PROFILES})
    assert exported['RADARR_TOKEN'] == '***' and exported['RADARR_API_URL'] == RADARR['RADARR_API_URL']
    # restoring a redacted export keeps the saved key, but a changed URL needs a fresh key
    bind_flat_credentials({**RADARR, 'RADARR_TOKEN': '***'}, RADARR)
    with pytest.raises(ValueError):
        bind_flat_credentials({'RADARR_API_URL': 'http://elsewhere:7878', 'RADARR_TOKEN': '***'}, RADARR)
