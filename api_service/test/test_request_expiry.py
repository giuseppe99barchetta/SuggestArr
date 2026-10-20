import asyncio
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
import aiohttp
from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.automation.routes import automation_bp
from api_service.config.config import validate_seer_expiry_settings
from api_service.db.components.request_expiry_mixin import RequestExpiryMixin
from api_service.db.components.schema_manager import SchemaManager
from api_service.jobs import request_expiry
from api_service.jobs.queue_worker import _run_worker
from api_service.services.seer.seer_client import SeerClient, normalize_seer_url, parse_seer_timestamp


class MemoryDB(RequestExpiryMixin):
    db_type = 'sqlite'
    logger = logging.getLogger('expiry-test')

    def __init__(self):
        self.connection = sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES)

    @contextmanager
    def get_connection(self):
        yield self.connection


@pytest.fixture
def db():
    database = MemoryDB()
    SchemaManager(database).initialize_db()
    yield database
    database.connection.close()


def add_delivery(db, *, row_id=1, age=8, status='submitted', instance='http://seer.local', tracked=True, media_type='movie'):
    created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=age)
    db.connection.execute(
        'INSERT INTO pending_requests(id,tmdb_id,media_type,payload,status) VALUES(?,?,?,?,?)',
        (row_id, str(row_id + 100), media_type, '{}', status),
    )
    if tracked:
        db.track_seer_request(row_id, row_id + 10, created_at, instance)
    return dict(id=row_id + 10, createdAt=created_at.isoformat() + 'Z', status=1,
                type=media_type, media={'tmdbId': row_id + 100})


def run_expiry(db, remote, *, dry_run=True, days=7, post_status=200, get_status=200):
    seer = MagicMock()
    seer.__aenter__ = AsyncMock(return_value=seer)
    seer.__aexit__ = AsyncMock(return_value=False)
    seer._is_pending_request = SeerClient._is_pending_request
    seer.request_expiry_action = AsyncMock(side_effect=[(get_status, remote), (post_status, {**remote, 'status': 3})])
    env = dict(SEER_API_URL='http://seer.local/', SEER_TOKEN='test-key', SEER_AUTO_DECLINE_DAYS=days,
               SEER_AUTO_DECLINE_DRY_RUN=dry_run)
    with patch.object(request_expiry, 'DatabaseManager', return_value=db), \
            patch.object(request_expiry.ConfigService, 'get_runtime_config', return_value=env), \
            patch.object(request_expiry, 'SeerClient', return_value=seer):
        result = asyncio.run(request_expiry.execute_request_expiry())
    return result, seer.request_expiry_action


@pytest.mark.parametrize('dry_run,action', [(True, 'simulated'), (False, 'declined')])
@pytest.mark.parametrize('media_type', ['movie', 'tv'])
def test_only_verified_expired_pending_requests_are_declined(db, dry_run, action, media_type):
    remote = add_delivery(db, media_type=media_type)
    result, calls = run_expiry(db, remote, dry_run=dry_run)
    assert result[action] == 1
    assert calls.await_count == (1 if dry_run else 2)
    if not dry_run:
        calls.assert_awaited_with(11, decline=True)
    assert db.get_request_expiry_log()[0]['action'] == action
    assert db.connection.execute('SELECT status FROM pending_requests').fetchone()[0] == 'submitted'


@pytest.mark.parametrize('overrides', [
    {'tracked': False}, {'age': 1}, {'status': 'queued'}, {'status': 'awaiting_approval'},
    {'instance': 'http://other.local'},
])
def test_untracked_recent_unsent_or_other_instance_requests_are_excluded(db, overrides):
    remote = add_delivery(db, **overrides)
    result, calls = run_expiry(db, remote, dry_run=False)
    assert result['candidates'] == 0
    calls.assert_not_awaited()


@pytest.mark.parametrize('change', [
    {'id': 99}, {'createdAt': '2000-01-01T00:00:00Z'}, {'type': 'tv'},
    {'media': {'tmdbId': 99}}, {'createdAt': None}, {'media': None}, {'status': 2}, {'status': 3},
])
def test_changed_identity_or_already_decided_request_is_skipped(db, change):
    remote = {**add_delivery(db), **change}
    result, calls = run_expiry(db, remote, dry_run=False)
    assert result['skipped'] == 1
    assert calls.await_count == 1


@pytest.mark.parametrize('status,key', [(404, 'skipped'), (403, 'errors'), (500, 'errors'), (0, 'errors')])
def test_lookup_failure_never_declines(db, status, key):
    result, calls = run_expiry(db, add_delivery(db), dry_run=False, get_status=status)
    assert result[key] == 1
    assert calls.await_count == 1


@pytest.mark.parametrize('status', [403, 503])
def test_decline_failure_is_logged_and_can_be_retried(db, status):
    remote = add_delivery(db)
    result, _ = run_expiry(db, remote, dry_run=False, post_status=status)
    assert result['errors'] == 1
    result, _ = run_expiry(db, remote, dry_run=False)
    assert result['declined'] == 1


@pytest.mark.parametrize('dry_run,overrides', [
    (False, {}),                               # declined
    (False, {'post_status': 404}),             # removed during expiry
    (False, {'post_status': 409}),             # decided during expiry
    (False, {'get_status': 404}),              # already gone
    (True, {'get_status': 404}),               # a dry run sees the same final state
])
def test_finished_requests_are_never_checked_again(db, dry_run, overrides):
    remote = add_delivery(db)
    run_expiry(db, remote, dry_run=dry_run, **overrides)
    logged = len(db.get_request_expiry_log())
    result, calls = run_expiry(db, remote, dry_run=False)
    assert result['candidates'] == 0
    calls.assert_not_awaited()
    assert len(db.get_request_expiry_log()) == logged


def test_already_decided_in_seer_is_checked_only_once(db):
    remote = {**add_delivery(db), 'status': 2}
    assert run_expiry(db, remote, dry_run=False)[0]['skipped'] == 1
    assert run_expiry(db, remote, dry_run=False)[0]['candidates'] == 0


def test_a_simulated_decline_is_evaluated_again(db):
    remote = add_delivery(db)
    assert run_expiry(db, remote, dry_run=True)[0]['simulated'] == 1
    assert run_expiry(db, remote, dry_run=True)[0]['simulated'] == 1


def test_disabled_gate_and_shared_run_lock(db):
    result, calls = run_expiry(db, add_delivery(db), days=0, dry_run=False)
    assert result['status'] == 'disabled'
    calls.assert_not_awaited()
    assert request_expiry._run_lock.acquire(blocking=False)
    try:
        result = asyncio.run(request_expiry.execute_request_expiry(dry_run=False))
        assert result == {'status': 'already_running'}
    finally:
        request_expiry._run_lock.release()


def test_exact_cutoff_is_not_expired_and_microseconds_are_preserved(db):
    remote = add_delivery(db)
    created_at = parse_seer_timestamp(remote['createdAt'])
    assert db.get_expiring_seer_requests(created_at, 'http://seer.local') == []
    candidates = db.get_expiring_seer_requests(created_at + timedelta(microseconds=1), 'http://seer.local')
    assert len(candidates) == 1
    assert candidates[0]['seer_created_at'] == created_at


def test_timezones_representing_the_same_creation_time_match():
    item = dict(seer_request_id=1, tmdb_id='101', media_type='tv', seer_created_at=datetime(2026, 1, 1))
    remote = dict(id=1, media={'tmdbId': 101}, type='tv', createdAt='2026-01-01T03:00:00+03:00')
    assert request_expiry._matches_request(item, remote)


def test_missing_configuration_never_contacts_seer():
    for url, token in [('', 'test'), ('http://seer.local', '')]:
        env = dict(SEER_AUTO_DECLINE_DAYS=7, SEER_API_URL=url, SEER_TOKEN=token)
        with patch.object(request_expiry.ConfigService, 'get_runtime_config', return_value=env), \
                patch.object(request_expiry, 'SeerClient') as client:
            result = asyncio.run(request_expiry.execute_request_expiry(dry_run=False))
        assert result['status'] == 'not_configured'
        client.assert_not_called()


@pytest.mark.parametrize('status', [200, 403, 404, 409, 500])
@pytest.mark.parametrize('decline', [False, True])
def test_expiry_http_uses_admin_key_and_preserves_status_without_redirects(status, decline):
    client = SeerClient('http://seer.local', 'test-key', session_token='old-cookie')
    response = AsyncMock()
    response.status = status
    response.json.return_value = {'id': 11}
    response.__aenter__.return_value = response
    session = MagicMock()
    session.request.return_value = response
    with patch.object(client, '_get_session', AsyncMock(return_value=session)):
        result = asyncio.run(client.request_expiry_action(11, decline=decline))
    assert result == (status, {'id': 11} if status == 200 else None)
    session.request.assert_called_once_with(
        'POST' if decline else 'GET', 'http://seer.local/api/v1/request/11' + ('/decline' if decline else ''),
        headers=ANY, cookies={}, timeout=client.REQUEST_TIMEOUT, allow_redirects=False,
    )
    assert session.request.call_args.kwargs['headers']['X-Api-Key'] == 'test-key'


@pytest.mark.parametrize('error', [aiohttp.ClientError(), asyncio.TimeoutError(), ValueError('invalid JSON')])
def test_expiry_http_failure_is_an_error_not_a_decision(error):
    client = SeerClient('http://seer.local', 'test-key')
    session = MagicMock()
    session.request.side_effect = error
    with patch.object(client, '_get_session', AsyncMock(return_value=session)):
        assert asyncio.run(client.request_expiry_action(11)) == (0, None)


def test_expiry_migration_is_additive_and_repeatable():
    db = MemoryDB()
    db.connection.execute('CREATE TABLE pending_requests(id INTEGER, status TEXT)')
    db.connection.execute("INSERT INTO pending_requests VALUES (1, 'submitted')")
    manager = SchemaManager(db)
    manager._migrate_request_expiry()
    manager._migrate_request_expiry()
    assert db.connection.execute('SELECT * FROM pending_requests').fetchone() == (1, 'submitted', None, None, None)
    db.connection.close()


@pytest.mark.parametrize('db_type', ['postgres', 'mysql', 'mariadb'])
def test_external_database_migration_uses_native_column_introspection(db_type):
    db = MagicMock(db_type=db_type)
    conn = db.get_connection.return_value.__enter__.return_value
    conn.cursor.return_value.fetchall.return_value = []
    manager = SchemaManager(db)
    manager._migrate_request_expiry()
    queries = [call.args[0] for call in conn.cursor.return_value.execute.call_args_list]
    assert len([sql for sql in queries if sql.startswith('ALTER TABLE')]) == 3
    timestamp_type = 'TIMESTAMP NULL' if db_type == 'postgres' else 'TIMESTAMP(6) NULL'
    assert any(timestamp_type in sql for sql in queries)
    ddl = manager._prepare_create_table_query_for_db(
        'request_expiry_log', 'CREATE TABLE request_expiry_log (id INTEGER PRIMARY KEY AUTOINCREMENT, reason TEXT)', db_type)
    assert 'AUTOINCREMENT' not in ddl
    assert ('SERIAL PRIMARY KEY' if db_type == 'postgres' else 'AUTO_INCREMENT PRIMARY KEY') in ddl
    ddl = manager._prepare_create_table_query_for_db(
        'pending_requests', 'CREATE TABLE pending_requests (seer_created_at TIMESTAMP NULL, seer_instance TEXT)', db_type)
    assert timestamp_type in ddl
    assert 'seer_instance TEXT' in ddl


@pytest.mark.parametrize('days', [-1, 366, True, '7', 1.5, None])
def test_config_rejects_invalid_days(days):
    with pytest.raises(ValueError):
        validate_seer_expiry_settings({'SEER_AUTO_DECLINE_DAYS': days})


def test_config_defaults_and_boolean_validation():
    validate_seer_expiry_settings({})
    validate_seer_expiry_settings({'SEER_AUTO_DECLINE_DAYS': 365, 'SEER_AUTO_DECLINE_DRY_RUN': False})
    with pytest.raises(ValueError):
        validate_seer_expiry_settings({'SEER_AUTO_DECLINE_DRY_RUN': 'false'})


def test_url_and_utc_normalization():
    assert normalize_seer_url(' HTTPS://SEER.LOCAL:443/seerr/ ') == 'https://seer.local/seerr'
    assert normalize_seer_url('http://[::1]:80/') == 'http://[::1]'
    assert parse_seer_timestamp('2026-01-01T03:00:00+03:00') == datetime(2026, 1, 1)
    with pytest.raises(ValueError):
        normalize_seer_url('https://user:secret@seer.local')


@pytest.mark.parametrize('tracking_fails', [False, True])
@pytest.mark.parametrize('response', [
    {'id': 11, 'createdAt': '2026-01-01T00:00:00Z'}, {'id': 11}, {'id': True, 'createdAt': 'invalid'},
])
def test_delivery_preserves_success_with_or_without_expiry_metadata(response, tracking_fails):
    db = MagicMock()
    db.expire_pending_approvals.return_value = 0
    db.check_request_exists.return_value = False
    db.get_due_requests.return_value = [{'id': 1, 'tmdb_id': '101', 'media_type': 'movie',
                                         'retry_count': 0, 'payload': '{}'}]
    if tracking_fails:
        db.track_seer_request.side_effect = sqlite3.OperationalError('tracking failed')
    seer = MagicMock()
    seer.__aenter__ = AsyncMock(return_value=seer)
    seer.__aexit__ = AsyncMock(return_value=False)
    seer.init = AsyncMock()
    seer.submit_queued_request = AsyncMock(return_value=response)
    with patch('api_service.jobs.queue_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.queue_worker.ConfigService.get_runtime_config', return_value={'SEER_API_URL': 'http://seer.local/'}), \
            patch('api_service.jobs.queue_worker.SeerClient', return_value=seer):
        assert asyncio.run(_run_worker()) == 1
    db.mark_pending_submitted.assert_called_once_with(1, 0)
    db.mark_pending_failed.assert_not_called()
    if 'createdAt' in response and type(response['id']) is int:
        db.track_seer_request.assert_called_once_with(1, 11, datetime(2026, 1, 1), 'http://seer.local')
    else:
        db.track_seer_request.assert_not_called()


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
    limiter.init_app(app)
    app.register_blueprint(automation_bp, url_prefix='/api/automation')
    caller = {'id': 1, 'role': 'admin'}

    @app.before_request
    def set_caller():
        g.current_user = caller

    return app.test_client(), caller


def test_routes_require_admin(client):
    client, caller = client
    caller['role'] = 'user'
    assert client.post('/api/automation/requests/expiry/run', json={}).status_code == 403
    assert client.get('/api/automation/requests/expiry/log').status_code == 403


def test_run_route_validation_and_conflict(client):
    client, _ = client
    for invalid in [{'dry_run': 'false'}, {'dry_run': None}, []]:
        assert client.post('/api/automation/requests/expiry/run', json=invalid).status_code == 400
    assert client.post('/api/automation/requests/expiry/run', data='{bad', content_type='application/json').status_code == 400
    with patch('api_service.blueprints.automation.routes.execute_request_expiry', AsyncMock(return_value={'status': 'already_running'})):
        assert client.post('/api/automation/requests/expiry/run', json={}).status_code == 409


def test_run_and_log_routes(client, db):
    client, _ = client
    with patch('api_service.blueprints.automation.routes.execute_request_expiry', AsyncMock(return_value={'status': 'disabled'})) as run:
        response = client.post('/api/automation/requests/expiry/run', json={'dry_run': True})
    assert response.status_code == 200
    run.assert_awaited_once_with(dry_run=True)
    run_expiry(db, add_delivery(db))
    with patch('api_service.blueprints.automation.routes.DatabaseManager', return_value=db):
        response = client.get('/api/automation/requests/expiry/log?limit=1')
        assert len(response.json['log']) == 1
    assert client.get('/api/automation/requests/expiry/log?limit=bad').status_code == 400
