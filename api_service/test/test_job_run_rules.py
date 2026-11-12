"""Every way of starting a job follows the same rules: pauses, one run at a time, webhooks, force."""
import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from flask import Flask, g

from api_service.api.v1.blueprint import public_api_v1_bp
from api_service.blueprints.jobs import routes as jobs_routes
from api_service.jobs.job_manager import JobBusyError, JobManager


def make_manager(job=None, executor=None):
    manager = object.__new__(JobManager)  # no scheduler, no database
    manager.logger = MagicMock()
    manager.repository = MagicMock()
    manager.repository.get_job.return_value = job or {'id': 1, 'name': 'Weekly', 'job_type': 'discover'}
    manager.repository.log_execution_start.return_value = 55
    manager._job_executors = {'discover': executor or AsyncMock(
        return_value=SimpleNamespace(success=True, results_count=3, requested_count=2, error_message=None))}
    return manager


def gates(approvals=False, pending=False):
    """Patch the three pauses; every other dependency of _execute_job stays real."""
    return (patch.object(JobManager, '_should_pause_for_suggestarr_approvals', return_value=approvals),
            patch.object(JobManager, '_should_pause_for_pending_requests', AsyncMock(return_value=pending)),
            patch.object(JobManager, '_pending_reason', staticmethod(lambda: 'Seer has pending requests')),
            patch.object(JobManager, '_queue_webhook'))


def run(manager, **kwargs):
    approvals, pending, reason, webhook = gates(**{k: kwargs.pop(k) for k in ('approvals', 'pending') if k in kwargs})
    with approvals, pending, reason, webhook as hook:
        return manager._execute_job(1, **kwargs), hook


# --- pauses and force -------------------------------------------------------------------------------

def test_a_pause_skips_the_run_and_force_overrides_it():
    manager = make_manager()
    report, hook = run(manager, approvals=True)
    assert report['status'] == 'skipped' and 'awaiting approval' in report['reason']
    manager._job_executors['discover'].assert_not_awaited()
    assert hook.call_args.args[0] == 'job.skipped'

    manager = make_manager()
    report, hook = run(manager, approvals=True, force=True)
    assert report['status'] == 'completed' and report['results_count'] == 3 and report['requested_count'] == 2
    manager._job_executors['discover'].assert_awaited_once()
    assert hook.call_args.args[0] == 'job.completed'


def test_the_queue_pause_also_applies_and_force_overrides_it():
    report, _ = run(make_manager(), pending=True)
    assert report['status'] == 'skipped' and 'Seer' in report['reason']
    report, _ = run(make_manager(), pending=True, force=True)
    assert report['status'] == 'completed'


def test_force_skips_the_unwatched_gate():
    job = {'id': 1, 'name': 'Rec', 'job_type': 'recommendation', 'prevent_suggestions_if_unwatched': 1}
    for force, expected in ((False, 'skipped'), (True, 'completed')):
        manager = make_manager(job, executor=AsyncMock(
            return_value=SimpleNamespace(success=True, results_count=1, requested_count=1, error_message=None)))
        manager._job_executors['recommendation'] = manager._job_executors['discover']
        with patch('api_service.jobs.unwatched_suggestion_gate.UnwatchedSuggestionGate') as gate:
            gate.return_value.allowed_slices = AsyncMock(return_value=[])
            report, _ = run(manager, force=force)
        assert report['status'] == expected, force


def test_a_scheduled_style_start_never_forces():
    report, _ = run(make_manager(), approvals=True)  # force defaults to False for cron and the public API
    assert report['status'] == 'skipped'


def test_an_unsuccessful_executor_result_is_a_failed_run_not_a_completed_one():
    failed = AsyncMock(return_value=SimpleNamespace(success=False, results_count=0, requested_count=0,
                                                    error_message='TMDb down'))
    manager = make_manager(executor=failed)
    report, hook = run(manager, execution_id=55)
    assert report['status'] == 'failed' and report['error_message'] == 'TMDb down'
    assert hook.call_args.args[0] == 'run.failed'
    manager.repository.finish_execution_if_open.assert_called_once_with(55, 'failed', 'TMDb down')
    assert manager.try_reserve(1) is True
    manager.release(1)


def test_a_successful_run_does_not_touch_the_history_row_it_did_not_leave_open():
    manager = make_manager()
    report, hook = run(manager, execution_id=55)
    assert report['status'] == 'completed' and hook.call_args.args[0] == 'job.completed'
    manager.repository.finish_execution_if_open.assert_not_called()


def test_finish_execution_if_open_only_closes_open_rows():
    import sqlite3
    from api_service.db.job_repository import JobRepository
    repo = object.__new__(JobRepository)
    repo.logger = MagicMock()
    connection = sqlite3.connect(':memory:')
    connection.execute('CREATE TABLE job_execution_history (id INTEGER, status TEXT, finished_at TEXT, error_message TEXT)')
    connection.executemany('INSERT INTO job_execution_history (id, status) VALUES (?, ?)',
                           [(1, 'running'), (2, 'completed'), (3, 'queued')])

    class Db:
        db_type = 'sqlite'

        def get_connection(self):
            from contextlib import contextmanager

            @contextmanager
            def ctx():
                yield connection
            return ctx()
    repo.db = Db()
    for row_id in (1, 2, 3):
        repo.finish_execution_if_open(row_id, 'failed', 'x')
    assert dict(connection.execute('SELECT id, status FROM job_execution_history').fetchall()) == {
        1: 'failed', 2: 'completed', 3: 'failed'}


def test_a_missing_job_or_executor_closes_the_history_row_that_was_prepared():
    manager = make_manager()
    manager.repository.get_job.return_value = None
    assert manager._execute_job(1, execution_id=9)['status'] == 'missing'
    manager.repository.finish_execution_if_open.assert_called_once_with(9, 'failed', 'Job not found')
    assert manager.try_reserve(1) is True
    manager.release(1)

    manager = make_manager()
    manager._job_executors = {}
    assert manager._execute_job(1, execution_id=9)['status'] == 'failed'
    manager.repository.finish_execution_if_open.assert_called_once()


# --- one run at a time ------------------------------------------------------------------------------

def test_a_second_start_is_refused_while_the_first_runs_and_force_does_not_bypass_it():
    started, release = threading.Event(), threading.Event()

    async def slow(job_id, execution_id=None):
        started.set()
        await asyncio.to_thread(release.wait, 5)
        return SimpleNamespace(success=True, results_count=1, requested_count=1, error_message=None)

    manager = make_manager(executor=slow)
    first = {}
    approvals, pending, reason, webhook = gates()
    with approvals, pending, reason, webhook:
        thread = threading.Thread(target=lambda: first.update(manager._execute_job(1)))
        thread.start()
        assert started.wait(5)
        assert manager._execute_job(1)['status'] == 'busy'
        assert manager._execute_job(1, force=True)['status'] == 'busy'
        release.set()
        thread.join(5)
    assert first['status'] == 'completed'
    assert manager.try_reserve(1) is True  # released when the run ended
    manager.release(1)


def test_the_reservation_is_released_when_the_executor_raises():
    manager = make_manager(executor=AsyncMock(side_effect=RuntimeError('boom')))
    report, hook = run(manager)
    assert report['status'] == 'failed'
    assert hook.call_args.args[0] == 'run.failed'
    assert manager.try_reserve(1) is True
    manager.release(1)


def test_reservations_are_per_job():
    manager = make_manager()
    assert manager.try_reserve(1) and manager.try_reserve(2) and not manager.try_reserve(1)
    manager.release(1)
    assert manager.try_reserve(1)
    manager.release(1)
    manager.release(2)


def test_enqueue_refuses_a_busy_job_without_creating_a_history_row():
    manager = make_manager()
    assert manager.try_reserve(1)
    with pytest.raises(JobBusyError):
        manager.enqueue_job_run(1, 7, None)
    manager.repository.create_queued_execution.assert_not_called()
    manager.release(1)


def test_enqueue_holds_the_reservation_for_the_started_run_and_releases_it_on_failure():
    manager = make_manager()
    manager.repository.create_queued_execution.return_value = 9
    with patch('api_service.jobs.job_manager.threading.Thread') as thread:
        assert manager.enqueue_job_run(1, 7, None) == 9
    thread.assert_called_once()
    assert thread.call_args.kwargs['args'] == (1, 9, False, True)  # (job, execution, force, already reserved)
    assert manager.try_reserve(1) is False  # still held until that run finishes
    manager.release(1)

    manager.repository.create_queued_execution.side_effect = RuntimeError('db down')
    with pytest.raises(RuntimeError):
        manager.enqueue_job_run(1, 7, None)
    assert manager.try_reserve(1) is True
    manager.release(1)


def test_alternative_generation_judges_the_pauses_while_holding_the_reservation():
    job = {'id': 1, 'name': 'Weekly', 'job_type': 'discover', 'enabled': True, 'owner_id': None, 'media_type': 'both'}
    manager = make_manager(job)
    item = {'job_id': 1, 'owner_id': None, 'media_type': 'movie', 'user_id': None, 'delivery_id': 4}
    seen = {}

    def approvals_check(_job):
        seen['reserved_when_checked'] = manager.try_reserve(1) is False  # a second reservation must fail
        return True  # approvals are waiting: the alternative must not run

    with patch.object(JobManager, '_should_pause_for_suggestarr_approvals', side_effect=approvals_check),             patch.object(JobManager, '_should_pause_for_pending_requests', AsyncMock(return_value=False)):
        state, _ = asyncio.run(manager.execute_replacement(item))
    assert seen['reserved_when_checked'] is True
    assert state == 'pending'
    manager._job_executors['discover'].assert_not_awaited()
    assert manager.try_reserve(1) is True  # released on the early return too
    manager.release(1)


def test_alternative_generation_waits_while_the_job_runs_and_releases_afterwards():
    job = {'id': 1, 'name': 'Weekly', 'job_type': 'discover', 'enabled': True, 'owner_id': None, 'media_type': 'both'}
    manager = make_manager(job)
    item = {'job_id': 1, 'owner_id': None, 'media_type': 'movie', 'user_id': None, 'delivery_id': 4}
    approvals, pending, reason, webhook = gates()
    with approvals, pending, reason, webhook:
        assert manager.try_reserve(1)
        state, why = asyncio.run(manager.execute_replacement(item))
        assert state == 'pending' and 'already running' in why
        manager._job_executors['discover'].assert_not_awaited()
        manager.release(1)
        state, _ = asyncio.run(manager.execute_replacement(item))
        assert state == 'queued'
    assert manager.try_reserve(1) is True
    manager.release(1)


# --- "Run now" route ----------------------------------------------------------------------------------

def jobs_client(manager, job=None, role='admin', owner_id=1):
    repository = MagicMock()
    repository.get_job.return_value = job or {'id': 1, 'name': 'Weekly', 'job_type': 'discover', 'owner_id': owner_id}
    repository.log_execution_start.return_value = 55
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.before_request
    def authenticate():
        g.current_user = {'id': '1', 'username': 'tester', 'role': role}

    app.register_blueprint(jobs_routes.jobs_bp, url_prefix='/api/jobs')
    patches = (patch.object(jobs_routes, 'JobRepository', MagicMock(return_value=repository)),
               patch.object(jobs_routes, 'get_job_manager', MagicMock(return_value=manager)),
               patch.object(jobs_routes.limiter, 'enabled', False))
    return app.test_client(), repository, patches


def post_run(client, patches, query=''):
    with patches[0], patches[1], patches[2]:
        return client.post(f'/api/jobs/1/run{query}')


def test_run_now_reports_a_pause_with_its_reason_and_force_runs_anyway():
    manager = make_manager()
    client, repository, patches = jobs_client(manager)
    approvals, pending, reason, webhook = gates(approvals=True)
    with approvals, pending, reason, webhook:
        paused = post_run(client, patches)
        forced = post_run(client, patches, '?force=true')
    assert paused.status_code == 200
    body = paused.get_json()
    assert body['status'] == 'paused' and 'awaiting approval' in body['reason'] and body['run_id'] == 55
    assert forced.status_code == 200 and forced.get_json()['status'] == 'success'
    assert forced.get_json()['results_count'] == 3 and forced.get_json()['requested_count'] == 2


def test_run_now_accepts_force_in_the_json_body():
    manager = make_manager()
    client, _, patches = jobs_client(manager)
    approvals, pending, reason, webhook = gates(approvals=True)
    with approvals, pending, reason, webhook, patches[0], patches[1], patches[2]:
        response = client.post('/api/jobs/1/run', json={'force': True})
    assert response.get_json()['status'] == 'success'


def test_run_now_returns_409_for_a_busy_job_even_with_force_and_creates_no_history_row():
    manager = make_manager()
    assert manager.try_reserve(1)
    client, repository, patches = jobs_client(manager)
    response = post_run(client, patches, '?force=true')
    assert response.status_code == 409 and response.get_json()['status'] == 'busy'
    repository.log_execution_start.assert_not_called()
    manager.release(1)


def test_run_now_failure_is_reported_and_releases_the_reservation():
    manager = make_manager(executor=AsyncMock(
        return_value=SimpleNamespace(success=False, results_count=0, requested_count=0, error_message='TMDb down')))
    client, _, patches = jobs_client(manager)
    approvals, pending, reason, webhook = gates()
    with approvals, pending, reason, webhook:
        response = post_run(client, patches)
    assert response.status_code == 500 and response.get_json()['message'] == 'TMDb down'
    assert manager.try_reserve(1) is True
    manager.release(1)


def test_run_now_keeps_the_owner_rule_for_regular_users():
    manager = make_manager()
    client, repository, patches = jobs_client(manager, role='user', owner_id=99)
    assert post_run(client, patches).status_code == 403
    assert manager.try_reserve(1) is True  # nothing was reserved
    manager.release(1)


def test_a_history_row_failure_does_not_leak_the_reservation():
    manager = make_manager()
    client, repository, patches = jobs_client(manager)
    repository.log_execution_start.side_effect = RuntimeError('db down')
    assert post_run(client, patches).status_code == 500
    assert manager.try_reserve(1) is True
    manager.release(1)


# --- run all --------------------------------------------------------------------------------------------

def test_run_all_response_lists_the_jobs_it_cannot_start():
    manager = make_manager()
    assert manager.try_reserve(2)
    repository = MagicMock()
    repository.get_all_jobs.return_value = [{'id': 1, 'enabled': True, 'name': 'a'}, {'id': 2, 'enabled': True, 'name': 'b'}]
    client, _, patches = jobs_client(manager)
    jobs_routes._run_all_running = False
    with patch.object(jobs_routes, 'JobRepository', MagicMock(return_value=repository)),             patch.object(jobs_routes, 'get_job_manager', MagicMock(return_value=manager)),             patch.object(jobs_routes.limiter, 'enabled', False),             patch.object(jobs_routes.threading, 'Thread'),             patch.object(jobs_routes, 'g', MagicMock(current_user={'id': '1', 'role': 'admin'})):
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.before_request
        def authenticate():
            g.current_user = {'id': '1', 'username': 'tester', 'role': 'admin'}
        app.register_blueprint(jobs_routes.jobs_bp, url_prefix='/api/jobs')
        response = app.test_client().post('/api/jobs/run-all')
    jobs_routes._run_all_running = False
    assert response.status_code == 202
    assert response.get_json()['busy_jobs'] == [2] and response.get_json()['jobs_count'] == 2
    manager.release(2)


def test_run_all_applies_the_same_rules_and_skips_busy_jobs():
    manager = make_manager()
    repository = MagicMock()
    repository.get_all_jobs.return_value = [{'id': 1, 'enabled': True, 'job_type': 'discover', 'name': 'a'},
                                            {'id': 2, 'enabled': True, 'job_type': 'discover', 'name': 'b'}]
    manager._execute_job = MagicMock(return_value={'status': 'completed'})
    with patch.object(jobs_routes, 'JobRepository', MagicMock(return_value=repository)), \
            patch.object(jobs_routes, 'get_job_manager', MagicMock(return_value=manager)):
        jobs_routes._run_all_jobs_in_background(force=True)
    assert [call.args[0] for call in manager._execute_job.call_args_list] == [1, 2]
    assert all(call.kwargs == {'force': True} for call in manager._execute_job.call_args_list)


# --- public API ---------------------------------------------------------------------------------------

def api_client():
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.before_request
    def authenticate():
        g.current_user = {'id': 1, 'username': 'tester', 'role': 'admin'}
        g.auth_method, g.api_key_id, g.api_key_name = 'test', None, None

    app.register_blueprint(public_api_v1_bp, url_prefix='/api/v1')
    return app.test_client()


def test_public_api_returns_409_for_a_running_job_without_creating_a_run():
    manager = make_manager()
    manager.repository.get_job.return_value = {'id': 1, 'owner_id': 1}
    assert manager.try_reserve(1)
    repository = MagicMock()
    repository.get_job.return_value = {'id': 1, 'owner_id': 1}
    with patch('api_service.api.v1.blueprint.JobRepository', return_value=repository), \
            patch('api_service.api.v1.blueprint.JobManager.get_instance', return_value=manager), \
            patch('api_service.api.v1.blueprint.limiter.enabled', False):
        response = api_client().post('/api/v1/jobs/1/runs')
    assert response.status_code == 409 and response.get_json()['error']['code'] == 'job_running'
    manager.repository.create_queued_execution.assert_not_called()
    manager.release(1)
