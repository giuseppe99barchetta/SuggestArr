import asyncio
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.automation.routes import automation_bp
from api_service.config.config import get_default_values, validate_seer_expiry_settings
from api_service.db.components.request_expiry_mixin import RequestExpiryMixin
from api_service.db.components.request_mixin import RequestMixin
from api_service.db.components.request_queue_mixin import RequestQueueMixin
from api_service.db.components.request_replacement_mixin import RequestReplacementMixin
from api_service.db.components.schema_manager import SchemaManager
from api_service.jobs import request_replacement
from api_service.jobs.job_manager import JobManager
from api_service.jobs.discover_automation import DiscoverAutomation
from api_service.jobs.trakt_recommendations_automation import TraktRecommendationsAutomation
from api_service.services.seer.seer_client import SeerClient


class MemoryDB(RequestReplacementMixin, RequestExpiryMixin, RequestQueueMixin, RequestMixin):
    db_type = 'sqlite'
    logger = logging.getLogger('replacement-test')

    def __init__(self):
        self.connection = sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES)
        self._automated_submission_skip_reason = lambda *args: None
        self.enqueue_webhook_event = MagicMock()

    @contextmanager
    def get_connection(self):
        yield self.connection


@pytest.fixture
def db():
    database = MemoryDB()
    SchemaManager(database).initialize_db()
    yield database
    database.connection.close()


def add_delivery(db, row_id=1, *, instance='http://seer.local', tracked=True, status='submitted'):
    db.connection.execute(
        'INSERT INTO pending_requests(id,tmdb_id,media_type,payload,status,job_id,owner_id,user_id) '
        'VALUES(?,?,?,?,?,1,7,?)', (row_id, str(row_id + 100), 'movie', '{}', status, 'u1'),
    )
    if tracked:
        db.track_seer_request(row_id, row_id + 10, datetime(2026, 10, 1), instance)
    db.connection.commit()
    return dict(id=row_id + 10, type='movie', media={'tmdbId': row_id + 100},
                createdAt='2026-10-01T00:00:00Z', status=3)


def make_manager(db, **changes):
    manager = object.__new__(JobManager)
    job = dict(id=1, enabled=True, job_type='recommendation', media_type='both', user_ids=['u1', 'u2'],
               owner_id=7, max_results=5, filters={'genres': [18]}, approval_pause_mode='never')
    job.update(changes)
    manager.repository = MagicMock(db=db)
    manager.repository.get_job.side_effect = lambda _: dict(job)

    async def executor(job_id, *, overrides):
        queued = db.enqueue_request('201', overrides['media_type'], 'u1',
                                    {'_replacement_for': overrides['_replacement_for']},
                                    status='awaiting_approval', job_id=job_id, owner_id=overrides['owner_id'])
        return SimpleNamespace(success=True, requested_count=int(queued))

    execute = AsyncMock(side_effect=executor)
    manager._job_executors = {job['job_type']: execute}
    return manager, job, execute


def run_check(db, remote, *, manager=None, http_status=200, enabled=True):
    manager = manager or make_manager(db)[0]
    seer = MagicMock()
    seer.__aenter__ = AsyncMock(return_value=seer)
    seer.__aexit__ = AsyncMock(return_value=False)
    seer.request_expiry_action = AsyncMock(return_value=(http_status, remote))
    if isinstance(remote, list):
        seer.request_expiry_action.side_effect = [(http_status, value) for value in remote]
    with patch.object(request_replacement, 'DatabaseManager', return_value=db), \
            patch.object(request_replacement.ConfigService, 'get_runtime_config', return_value={
                'REPLACE_REJECTED_REQUESTS': enabled, 'SEER_API_URL': 'http://seer.local/', 'SEER_TOKEN': 'test-key',
            }), patch.object(request_replacement, 'SeerClient', return_value=seer), \
            patch.object(request_replacement.JobManager, 'get_instance', return_value=manager):
        result = asyncio.run(request_replacement.execute_request_replacements())
    return result, seer.request_expiry_action


def test_rejection_queues_exactly_one_alternative_and_keeps_scope(db):
    remote = add_delivery(db)
    manager, job, executor = make_manager(db)
    result, calls = run_check(db, remote, manager=manager)
    assert result['queued'] == 1
    executor.assert_awaited_once_with(1, overrides={
        'media_type': 'movie', 'max_results': 1, 'owner_id': 7, '_replacement_for': 1, 'user_ids': ['u1'],
    })
    assert job['filters'] == {'genres': [18]}
    assert db.connection.execute('SELECT status FROM pending_requests WHERE id=1').fetchone()[0] == 'submitted'
    assert db.connection.execute('SELECT status FROM pending_requests WHERE id=2').fetchone()[0] == 'awaiting_approval'
    log = db.get_request_replacement_log()[0]
    assert log['replacement_delivery_id'] == 2 and log['status'] == 'queued'
    run_check(db, remote, manager=manager)
    assert executor.await_count == 1
    calls.assert_awaited_once_with(11)


def test_durable_slot_prevents_second_alternative_and_survives_repeated_observation(db):
    add_delivery(db)
    db.record_seer_request_check(1, 3, 'pending', 'Rejected')
    assert db.enqueue_request('201', 'movie', 'u1', {'_replacement_for': 1}, job_id=1)
    db.record_seer_request_check(1, 3, 'pending', 'Repeated observation')
    assert not db.enqueue_request('202', 'movie', 'u1', {'_replacement_for': 1}, job_id=1)
    assert db.connection.execute('SELECT COUNT(*) FROM pending_requests').fetchone()[0] == 2
    assert db.get_request_replacement_log()[0]['status'] == 'queued'


def test_list_replacement_uses_owner_without_media_user(db):
    remote = add_delivery(db)
    db.connection.execute('UPDATE pending_requests SET user_id=NULL')
    db.connection.commit()
    manager, _, executor = make_manager(db, job_type='list_import', user_ids=[])
    result, _ = run_check(db, remote, manager=manager)
    assert result['queued'] == 1
    executor.assert_awaited_once_with(1, overrides={
        'media_type': 'movie', 'max_results': 1, 'owner_id': 7, '_replacement_for': 1,
    })


@pytest.mark.parametrize('changes', [{'tracked': False}, {'instance': 'http://other.local'}, {'status': 'queued'}])
def test_only_tracked_submitted_current_instance_deliveries_are_checked(db, changes):
    remote = add_delivery(db, **changes)
    result, calls = run_check(db, remote)
    assert result['checked'] == 0
    calls.assert_not_awaited()


@pytest.mark.parametrize('remote_status', [1, 2, 4, 5])
def test_non_rejected_remote_status_never_triggers_alternative(db, remote_status):
    remote = {**add_delivery(db), 'status': remote_status}
    manager, _, executor = make_manager(db)
    run_check(db, remote, manager=manager)
    executor.assert_not_awaited()
    assert len(db.get_seer_requests_to_check('http://seer.local')) == (1 if remote_status == 1 else 0)


@pytest.mark.parametrize('http_status', [404, 403, 500, 0])
def test_removed_or_unreachable_request_is_never_treated_as_rejection(db, http_status):
    manager, _, executor = make_manager(db)
    result, _ = run_check(db, add_delivery(db), http_status=http_status, manager=manager)
    executor.assert_not_awaited()
    assert result['errors'] == (0 if http_status == 404 else 1)
    assert len(db.get_seer_requests_to_check('http://seer.local')) == (0 if http_status == 404 else 1)


@pytest.mark.parametrize('change', [
    {'id': 99}, {'type': 'tv'}, {'media': {'tmdbId': 999}}, {'createdAt': '2000-01-01T00:00:00Z'},
    {'status': None}, {'status': True}, {'status': 99},
])
def test_identity_and_status_are_verified(db, change):
    manager, _, executor = make_manager(db)
    run_check(db, {**add_delivery(db), **change}, manager=manager)
    executor.assert_not_awaited()


@pytest.mark.parametrize('action', ['declined', 'decline_requested'])
def test_automatic_declines_and_crashes_after_expiry_intent_do_not_trigger_replacement(db, action):
    remote = add_delivery(db)
    db.add_request_expiry_log(dict(delivery_id=1, seer_request_id=11, tmdb_id='101', media_type='movie'),
                             action, 'Expiry', False)
    manager, _, executor = make_manager(db)
    run_check(db, remote, manager=manager)
    executor.assert_not_awaited()
    assert db.get_request_replacement_log()[0]['reason'] == 'Automatic expiry decline'


@pytest.mark.parametrize('changes,expected', [
    ({'enabled': False}, 'pending'), ({'owner_id': 8}, 'ignored'),
    ({'media_type': 'tv'}, 'ignored'), ({'user_ids': ['u2']}, 'ignored'),
])
def test_current_job_scope_and_enabled_state_are_respected(db, changes, expected):
    remote = add_delivery(db)
    manager, _, executor = make_manager(db, **changes)
    run_check(db, remote, manager=manager)
    executor.assert_not_awaited()
    assert db.get_request_replacement_log()[0]['status'] == expected


def test_disabled_job_retries_after_reenabled_without_another_remote_check(db):
    remote = add_delivery(db)
    manager, job, executor = make_manager(db, enabled=False)
    run_check(db, remote, manager=manager)
    job['enabled'] = True
    result, calls = run_check(db, remote, manager=manager)
    assert result['queued'] == 1
    calls.assert_not_awaited()


def test_approval_and_unwatched_gates_defer_alternatives(db):
    remote = add_delivery(db)
    manager, job, executor = make_manager(db, pause_if_pending_requests=True)
    manager._should_pause_for_pending_requests = AsyncMock(return_value=True)
    run_check(db, remote, manager=manager)
    executor.assert_not_awaited()
    job.update(pause_if_pending_requests=False, prevent_suggestions_if_unwatched=True)
    manager._should_pause_for_pending_requests.return_value = False
    with patch('api_service.jobs.unwatched_suggestion_gate.UnwatchedSuggestionGate') as gate:
        gate.return_value.allowed_slices = AsyncMock(return_value=[])
        run_check(db, remote, manager=manager)
    executor.assert_not_awaited()
    assert db.get_request_replacement_log()[0]['status'] == 'pending'


def test_no_candidates_finishes_once_but_provider_failure_retries(db):
    remote = add_delivery(db)
    manager, _, executor = make_manager(db)
    executor.side_effect = None
    executor.return_value = SimpleNamespace(success=False, requested_count=0)
    run_check(db, remote, manager=manager)
    assert db.get_request_replacement_log()[0]['status'] == 'pending'
    executor.return_value = SimpleNamespace(success=True, requested_count=0)
    run_check(db, remote, manager=manager)
    assert db.get_request_replacement_log()[0]['status'] == 'exhausted'
    run_check(db, remote, manager=manager)
    assert executor.await_count == 2


def test_disabled_option_and_shared_expiry_lock_do_no_work(db):
    result, calls = run_check(db, add_delivery(db), enabled=False)
    assert result['status'] == 'disabled'
    calls.assert_not_awaited()
    assert request_replacement._run_lock.acquire(blocking=False)
    try:
        assert asyncio.run(request_replacement.execute_request_replacements()) == {'status': 'already_running'}
    finally:
        request_replacement._run_lock.release()


def test_replacement_context_reaches_queue_without_bypassing_approval():
    db = MagicMock()
    db.check_request_exists.return_value = False
    db.enqueue_request.return_value = True
    client = SeerClient('http://seer.local', 'test-key', queue_context={
        'job_id': 4, 'owner_id': 7, '_replacement_for': 9, 'delivery_mode': 'inherit',
    })
    with patch('api_service.services.seer.seer_client.DatabaseManager', return_value=db), \
            patch('api_service.services.seer.seer_client.load_env_vars', return_value={'REQUIRE_REQUEST_APPROVAL': True}):
        assert asyncio.run(client.request_media('movie', {'id': 201}, user={'id': 'u1'})) is True
    args, kwargs = db.enqueue_request.call_args
    assert args[3]['_replacement_for'] == 9
    assert kwargs['status'] == 'awaiting_approval'
    assert kwargs['job_id'] == 4 and kwargs['owner_id'] == 7


@pytest.mark.parametrize('job_type,user_id', [('discover', None), ('trakt_recommendations', 'u1')])
def test_other_job_types_preserve_original_media_scope(db, job_type, user_id):
    add_delivery(db)
    manager, _, executor = make_manager(db, job_type=job_type)
    item = dict(delivery_id=1, job_id=1, owner_id=7, user_id=user_id, media_type='tv')
    executor.side_effect = None
    executor.return_value = SimpleNamespace(success=True, requested_count=0)
    assert asyncio.run(manager.execute_replacement(item))[0] == 'exhausted'
    overrides = executor.call_args.kwargs['overrides']
    assert overrides['media_type'] == 'tv' and overrides['max_results'] == 1
    assert overrides.get('user_ids') == (['u1'] if user_id else None)


@pytest.mark.parametrize('db_type', ['postgres', 'mysql', 'mariadb'])
def test_remote_check_upsert_and_table_ddl_support_external_databases(db_type):
    db = MagicMock(db_type=db_type)
    RequestReplacementMixin.record_seer_request_check(db, 1, 3, 'pending', 'Rejected')
    sql, params = db.get_connection.return_value.__enter__.return_value.cursor.return_value.execute.call_args.args
    assert '?' not in sql and params == (1, 3, 'pending', 'Rejected')
    assert ('ON CONFLICT(delivery_id)' if db_type == 'postgres' else 'ON DUPLICATE KEY UPDATE') in sql
    ddl = SchemaManager(db)._prepare_create_table_query_for_db('request_replacements',
        'CREATE TABLE IF NOT EXISTS request_replacements (delivery_id INTEGER PRIMARY KEY, '
        'remote_status INTEGER NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL, '
        'replacement_delivery_id INTEGER, checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)', db_type)
    assert ('delivery_id INTEGER PRIMARY KEY' if db_type == 'postgres' else 'delivery_id INT PRIMARY KEY') in ddl
    if db_type != 'postgres':
        assert 'ENGINE=InnoDB' in ddl


def test_initialization_is_additive_and_preserves_deliveries(db):
    add_delivery(db)
    before = db.connection.execute('SELECT * FROM pending_requests').fetchall()
    SchemaManager(db).initialize_db()
    assert db.connection.execute('SELECT * FROM pending_requests').fetchall() == before


def test_oldest_unchecked_and_failed_requests_are_checked_fairly(db):
    for n in range(1, 4):
        add_delivery(db, n)
    db.record_seer_request_check(1, 1, 'observing', 'HTTP 500')
    assert [row['delivery_id'] for row in db.get_seer_requests_to_check('http://seer.local', 2)] == [2, 3]


def test_multiple_rejections_respect_job_budget_per_check(db):
    db.connection.execute(
        'INSERT INTO discover_jobs(id,name,media_type,filters,schedule_type,schedule_value,max_results) '
        "VALUES (1,'Test','both','{}','preset','daily',1)")
    remotes = [add_delivery(db, n) for n in [1, 2]]
    manager, _, executor = make_manager(db, max_results=1)
    result, _ = run_check(db, remotes, manager=manager)
    assert result['queued'] == 1 and result['pending'] == 1
    assert executor.await_count == 1
    states = dict(db.connection.execute('SELECT delivery_id,status FROM request_replacements'))
    assert states == {1: 'queued', 2: 'pending'}


def test_existing_title_does_not_consume_replacement_slot(db):
    add_delivery(db)
    db.record_seer_request_check(1, 3, 'pending', 'Rejected')
    assert not db.enqueue_request('101', 'movie', 'u1', {'_replacement_for': 1}, job_id=1)
    assert db.enqueue_request('201', 'movie', 'u1', {'_replacement_for': 1}, job_id=1)


def test_unknown_media_user_or_deleted_job_never_broadens_scope(db):
    manager, _, executor = make_manager(db)
    item = dict(delivery_id=1, job_id=1, owner_id=7, user_id=None, media_type='movie')
    assert asyncio.run(manager.execute_replacement(item))[0] == 'ignored'
    manager.repository.get_job.side_effect = lambda _: None
    assert asyncio.run(manager.execute_replacement(item))[0] == 'ignored'
    executor.assert_not_awaited()


def test_suggestarr_approval_gate_defers_replacement(db):
    manager, _, executor = make_manager(db, approval_pause_mode='always')
    db.has_pending_approvals = MagicMock(return_value=True)
    item = dict(delivery_id=1, job_id=1, owner_id=7, user_id='u1', media_type='movie')
    assert asyncio.run(manager.execute_replacement(item))[0] == 'pending'
    executor.assert_not_awaited()


@pytest.mark.parametrize('url,token', [('', 'test-key'), ('http://seer.local', '')])
def test_missing_configuration_never_calls_remote(url, token):
    with patch.object(request_replacement.ConfigService, 'get_runtime_config', return_value={
        'REPLACE_REJECTED_REQUESTS': True, 'SEER_API_URL': url, 'SEER_TOKEN': token,
    }), patch.object(request_replacement, 'SeerClient') as seer:
        assert asyncio.run(request_replacement.execute_request_replacements())['status'] == 'not_configured'
        seer.assert_not_called()


@pytest.mark.parametrize('automation_class', [DiscoverAutomation, TraktRecommendationsAutomation])
def test_alternative_search_skips_existing_title_and_stops_after_one(automation_class):
    automation = automation_class()
    automation.job_data = dict(media_type='movie', user_ids=['u1'], _replacement_for=1)
    automation.db_manager = MagicMock()
    automation.db_manager.check_request_exists.side_effect = lambda _type, tmdb: tmdb == '101'
    automation.seer_client = MagicMock()
    automation.seer_client.check_already_downloaded = AsyncMock(return_value=False)
    automation.seer_client.check_already_requested = AsyncMock(return_value=False)
    automation.seer_client.request_media = AsyncMock(return_value=True)
    automation.local_content = {}
    automation.seer_discovered_ids = set()
    result, _ = asyncio.run(automation.filter_and_request([{'id': n, 'title': str(n)} for n in [101, 201, 202]]))
    assert result == 1
    assert automation.seer_client.request_media.await_count == 1
    assert automation.seer_client.request_media.call_args.args[1]['id'] == 201


def test_config_is_opt_in_and_rejects_non_boolean():
    assert get_default_values()['REPLACE_REJECTED_REQUESTS']() is False
    with pytest.raises(ValueError, match='REPLACE_REJECTED_REQUESTS'):
        validate_seer_expiry_settings({'REPLACE_REJECTED_REQUESTS': 'true'})


def test_routes_are_admin_only_and_report_conflicts_and_log(db):
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
    limiter.init_app(app)
    app.register_blueprint(automation_bp, url_prefix='/api/automation')
    caller = {'id': 7, 'role': 'user'}

    @app.before_request
    def authenticate():
        g.current_user = caller

    client = app.test_client()
    base = '/api/automation/requests/replacements'
    assert client.post(base + '/run').status_code == 403
    assert client.get(base + '/log').status_code == 403
    caller['role'] = 'admin'
    with patch('api_service.blueprints.automation.routes.execute_request_replacements',
               AsyncMock(return_value={'status': 'already_running'})):
        assert client.post(base + '/run').status_code == 409
    with patch('api_service.blueprints.automation.routes.execute_request_replacements',
               AsyncMock(return_value={'status': 'disabled'})):
        assert client.post(base + '/run').json['result']['status'] == 'disabled'
    with patch('api_service.blueprints.automation.routes.DatabaseManager', return_value=db):
        assert client.get(base + '/log').json['log'] == []
        assert client.get(base + '/log?limit=bad').status_code == 400
