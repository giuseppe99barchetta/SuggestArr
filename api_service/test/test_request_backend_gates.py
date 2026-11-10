"""Seer-only features stay inert with direct Radarr/Sonarr, even when Seer credentials are still saved."""
import asyncio
import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.ai_search import routes as ai_routes
from api_service.blueprints.jobs import routes as jobs_routes
from api_service.db.components.request_queue_mixin import RequestQueueMixin
from api_service.handler.base_handler import BaseMediaHandler
from api_service.jobs import availability_sync, cleanup_automation, request_expiry, request_replacement
from api_service.jobs.job_manager import JobManager

SEER = {'SEER_API_URL': 'http://seer:5055', 'SEER_TOKEN': 'k'}
PROFILES = {'default_movie': {'profileId': 4, 'rootFolder': '/movies', 'tags': [1]},
            'default_tv': {'profileId': 6, 'rootFolder': '/tv'}}
ARR = {'REQUEST_BACKEND': 'arr', 'RADARR_API_URL': 'http://radarr:7878', 'RADARR_TOKEN': 'k',
       'ARR_PROFILE_CONFIG': PROFILES}
ARR_WITH_SEER = {**ARR, **SEER}


def _no_seer(module):
    return patch.object(module, 'SeerClient', side_effect=AssertionError('Seer must not be contacted'))


def test_expiry_is_disabled_and_replacement_skips_seer_for_direct_delivery_even_with_seer_saved():
    env = {**ARR_WITH_SEER, 'SEER_AUTO_DECLINE_DAYS': 3, 'SEER_AUTO_DECLINE_DRY_RUN': False,
           'REPLACE_REJECTED_REQUESTS': True}
    with patch.object(request_expiry.ConfigService, 'get_runtime_config', return_value=env), \
            _no_seer(request_expiry):
        assert asyncio.run(request_expiry.execute_request_expiry())['status'] == 'disabled_backend'
    db = MagicMock(get_pending_request_replacements=MagicMock(return_value=[]))
    with patch.object(request_replacement.ConfigService, 'get_runtime_config', return_value=env), \
            patch.object(request_replacement, 'DatabaseManager', return_value=db), \
            patch.object(request_replacement.JobManager, 'get_instance'), _no_seer(request_replacement):
        assert asyncio.run(request_replacement.execute_request_replacements())['status'] == 'ok'
    db.get_pending_request_replacements.assert_called_once_with(None)
    db.get_seer_requests_to_check.assert_not_called()


def test_availability_sync_reads_radarr_not_seer_in_direct_mode():
    radarr = MagicMock(get_media_statuses=AsyncMock(return_value={}))
    radarr.__aenter__ = AsyncMock(return_value=radarr)
    radarr.__aexit__ = AsyncMock(return_value=False)
    db = MagicMock(get_requested_media_keys=MagicMock(return_value={('movie', '1')}),
                   get_media_availability=MagicMock(return_value={}))
    with patch.object(availability_sync.ConfigService, 'get_runtime_config', return_value=ARR_WITH_SEER), \
            patch.object(availability_sync, 'DatabaseManager', return_value=db), \
            patch.object(availability_sync, 'ArrClient', return_value=radarr), _no_seer(availability_sync):
        assert asyncio.run(availability_sync.sync_availability())['status'] == 'ok'
    radarr.get_media_statuses.assert_awaited_once()


def test_cleanup_does_not_contact_seer_in_direct_mode():
    db = MagicMock()
    db.get_cleanup_settings.return_value = {'enabled': True, 'grace_days': 30, 'dry_run': False}
    db.get_suggestarr_requests_older_than.return_value = []
    env = {**ARR_WITH_SEER, 'SELECTED_SERVICE': 'jellyfin', 'JELLYFIN_API_URL': 'http://jf', 'JELLYFIN_TOKEN': 't'}
    with patch.object(cleanup_automation, 'DatabaseManager', return_value=db), \
            patch.object(cleanup_automation.ConfigService, 'get_runtime_config', return_value=env), \
            _no_seer(cleanup_automation):
        result = asyncio.run(cleanup_automation.execute_cleanup_job())
    assert result['status'] == 'ok'


@pytest.mark.parametrize('env,paused', [(ARR_WITH_SEER, False), ({}, None)])
def test_pending_request_pause_does_not_apply_to_direct_delivery(env, paused):
    manager = object.__new__(JobManager)
    manager.logger = MagicMock()
    with patch('api_service.jobs.job_manager.ConfigService.get_runtime_config', return_value=env), \
            patch('api_service.jobs.job_manager.SeerClient') as seer:
        if paused is None:  # seer mode: the Seer check still runs
            seer.return_value.__aenter__ = AsyncMock(return_value=seer.return_value)
            seer.return_value.__aexit__ = AsyncMock(return_value=False)
            seer.return_value.has_pending_requests = AsyncMock(return_value=True)
            env.update(SEER_API_URL='http://seer', SEER_TOKEN='k')
            assert asyncio.run(manager._should_pause_for_pending_requests({'pause_if_pending_requests': True})) is True
        else:
            assert asyncio.run(manager._should_pause_for_pending_requests({'pause_if_pending_requests': True})) is paused
            seer.assert_not_called()


def test_handler_without_seer_still_merges_radarr_and_sonarr_titles():
    handler_cls = type('Handler', (BaseMediaHandler,), {
        '_populate_existing_content_sets': lambda self: None,
        '_request_llm_recommendation': lambda self, *args, **kwargs: None})
    handler = object.__new__(handler_cls)
    handler.seer_client = None
    handler.existing_content_sets = {'movie': {'1'}}
    with patch('api_service.handler.base_handler.load_env_vars', return_value=ARR), \
            patch('api_service.handler.base_handler.load_library_content',
                  AsyncMock(return_value={'movie': {'27205'}})) as load:
        asyncio.run(handler.add_available_content())
    assert handler.existing_content_sets == {'movie': {'1', '27205'}}
    assert load.await_args.args[0] == ARR and load.await_args.args[1] is None


# --- AI Search --------------------------------------------------------------

def _ai_client(config):
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)

    @app.before_request
    def authenticate():
        g.current_user = {'id': 1, 'role': 'admin'}
    limiter.init_app(app)
    app.register_blueprint(ai_routes.ai_search_bp, url_prefix='/api/ai-search')
    return app.test_client()


@pytest.mark.parametrize('config', [ARR, ARR_WITH_SEER])
def test_ai_search_request_goes_to_arr_in_direct_mode_whatever_seer_credentials_exist(config):
    arr = MagicMock()
    arr.__aenter__ = AsyncMock(return_value=arr)
    arr.__aexit__ = AsyncMock(return_value=False)
    arr.add = AsyncMock(return_value=True)
    with patch.object(ai_routes.ConfigService, 'get_runtime_config', return_value=config), \
            patch.object(ai_routes, 'ArrClient', return_value=arr) as factory, \
            patch.object(ai_routes, 'DatabaseManager') as db, \
            patch.object(ai_routes.aiohttp, 'ClientSession', side_effect=AssertionError('Seer must not be contacted')):
        response = _ai_client(config).post('/api/ai-search/request', json={'tmdb_id': 27205, 'media_type': 'movie'})
    assert response.status_code == 200
    factory.assert_called_once_with('radarr', 'http://radarr:7878', 'k')
    sent = arr.add.await_args.args[0]
    assert (sent['profileId'], sent['rootFolder'], sent['tags']) == (4, '/movies', [1])
    db.return_value.save_request.assert_called_once()


def test_ai_search_request_for_a_type_without_instance_is_refused():
    with patch.object(ai_routes.ConfigService, 'get_runtime_config', return_value=ARR), \
            patch.object(ai_routes, 'ArrClient') as factory:
        response = _ai_client(ARR).post('/api/ai-search/request', json={'tmdb_id': 1399, 'media_type': 'tv'})
    assert response.status_code == 400
    factory.assert_not_called()


# --- job profiles -----------------------------------------------------------

def test_job_profiles_are_not_checked_against_seer_in_direct_mode_but_are_in_seer_mode():
    profiles = {'movie': {'serverId': 0, 'profileId': 1, 'rootFolder': '/m'}}
    with patch.object(jobs_routes.ConfigService, 'get_runtime_config', return_value=ARR), \
            patch.object(jobs_routes, 'validate_request_profiles_with_seer') as check:
        jobs_routes._validate_job_profiles(profiles)
        check.assert_not_called()
    with patch.object(jobs_routes.ConfigService, 'get_runtime_config', return_value=SEER), \
            patch.object(jobs_routes, 'validate_request_profiles_with_seer') as check:
        jobs_routes._validate_job_profiles(profiles)
        check.assert_called_once_with(profiles)


# --- approvals and listing --------------------------------------------------

class _Queue(RequestQueueMixin):
    db_type = 'sqlite'

    def __init__(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.executescript(
            "CREATE TABLE pending_requests (id INTEGER PRIMARY KEY, tmdb_id TEXT, media_type TEXT, user_id TEXT,"
            " payload TEXT, status TEXT, job_id INTEGER, owner_id INTEGER, execution_id TEXT, decided_by INTEGER,"
            " decided_at TIMESTAMP);"
            "CREATE TABLE suggestion_blacklist (tmdb_id TEXT, media_type TEXT, created_by INTEGER);")
        self.logger = MagicMock()
        self.enqueue_webhook_event = MagicMock()
        for row_id, backend in ((1, 'seer'), (2, 'arr'), (3, None)):
            payload = {'mediaType': 'movie', 'profileId': 1, 'rootFolder': '/own'}
            if backend:
                payload['_backend'] = backend
            self.connection.execute(
                "INSERT INTO pending_requests (id, tmdb_id, media_type, payload, status, owner_id) "
                "VALUES (?, ?, 'movie', ?, 'awaiting_approval', 1)", (row_id, str(row_id), json.dumps(payload)))

    def get_connection(self):
        queue = self

        class Conn:
            def __enter__(self):
                return queue.connection

            def __exit__(self, *_):
                return False
        return Conn()

    def payload(self, row_id):
        return json.loads(self.connection.execute('SELECT payload FROM pending_requests WHERE id=?',
                                                  (row_id,)).fetchone()[0])


def test_awaiting_rows_report_their_recorded_backend_and_legacy_rows_are_seer():
    queue = _Queue()
    assert queue.awaiting_backends([1, 2, 3], 1) == {'seer', 'arr'}
    assert queue.awaiting_backends([2], 1) == {'arr'}
    assert queue.awaiting_backends([3], 1) == {'seer'}


def test_a_profile_override_is_applied_to_seer_rows_only_and_reported():
    queue = _Queue()
    report = {}
    changed = queue.decide_suggestions([1, 2, 3], 1, 9, True, profiles={'movie': {'profileId': 7, 'rootFolder': '/x'}},
                                       report=report)
    assert changed == 3 and report['ignored_overrides'] == 1
    assert queue.payload(1)['profileId'] == 7 and queue.payload(3)['profileId'] == 7  # seer and legacy rows
    assert queue.payload(2)['profileId'] == 1 and queue.payload(2)['rootFolder'] == '/own'  # arr row keeps its own
