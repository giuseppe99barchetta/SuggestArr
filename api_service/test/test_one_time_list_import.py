from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api_service.db.list_import_repository import ListImportRepository, public_import_state
from api_service.db.components.schema_manager import SchemaManager
from api_service.jobs import one_time_list_import
from api_service.jobs.list_import_automation import ListImportAutomation
from api_service.services.public_lists import PublicListError
from api_service.test.test_list_import import repo, make_automation, entries, URL


CONFIG = {'filters': {'list_provider': 'mdblist', 'list_url': URL}, 'media_type': 'both',
          'delivery_mode': 'manual', 'seer_identity_mode': 'matching_user', 'request_profiles': {}}


def test_one_active_import_per_owner_claim_progress_resume_and_no_jobs(repo):
    runs = ListImportRepository(repo.db)
    run_id = runs.reserve(7, CONFIG)
    assert run_id and runs.reserve(7, CONFIG) is None
    assert runs.reserve(8, CONFIG)
    assert runs.get(8, run_id) is None
    token = runs.claim(7, run_id)
    assert token and runs.claim(7, run_id) is None
    assert runs.update(run_id, token, 100, 100, 25, 'failed', 'Provider error')
    assert not runs.update(run_id, 'wrong-token', 0, 0, 0)
    new_token = runs.claim(7, run_id)
    assert new_token
    assert runs.get(7)['scan_offset'] == 100
    assert runs.update(run_id, new_token, 0, 200, 50, 'completed')
    assert public_import_state(runs.get(7))['requested_count'] == 50
    assert 'config_json' not in public_import_state(runs.get(7))
    assert repo.db.connection.execute('SELECT COUNT(*) FROM discover_jobs').fetchone()[0] == 1
    assert runs.reserve(7, CONFIG) != run_id
    assert repo.db.connection.execute('SELECT COUNT(*) FROM list_import_runs WHERE owner_id=7').fetchone()[0] == 1


def test_interrupted_import_is_resumable_and_schema_repeatable(repo):
    SchemaManager(repo.db).initialize_db()
    runs = ListImportRepository(repo.db)
    run_id = runs.reserve(7, CONFIG)
    token = runs.claim(7, run_id)
    repo.db.connection.execute('UPDATE list_import_runs SET lease_until=?',
                              (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1),))
    repo.db.connection.commit()
    assert public_import_state(runs.get(7))['status'] == 'interrupted'
    replacement = runs.claim(7, run_id)
    assert replacement != token
    assert not runs.update(run_id, token, 1, 1, 1)


def test_start_claims_synchronously_and_only_launches_one_worker(repo, monkeypatch):
    runs = ListImportRepository(repo.db)
    run_id = runs.reserve(7, CONFIG)
    thread = MagicMock()
    monkeypatch.setattr(one_time_list_import, 'ListImportRepository', lambda: runs)
    monkeypatch.setattr(one_time_list_import.threading, 'Thread', thread)
    one_time_list_import.start_import(7, run_id)
    assert public_import_state(runs.get(7))['status'] == 'running'
    one_time_list_import.start_import(7, run_id)
    thread.assert_called_once()
    thread.return_value.start.assert_called_once()


@pytest.mark.parametrize('db_type', ['postgres', 'mysql', 'mariadb'])
def test_external_import_repository_uses_native_parameters_and_schema(db_type):
    db = MagicMock(db_type=db_type)
    cursor = db.get_connection.return_value.__enter__.return_value.cursor.return_value
    cursor.rowcount = 1
    runs = ListImportRepository(db)
    run_id = runs.reserve(7, CONFIG)
    query = cursor.execute.call_args_list[0].args[0]
    assert '?' not in query and '%s' in query
    assert ('ON CONFLICT' if db_type == 'postgres' else 'INSERT IGNORE') in query
    token = runs.claim(7, run_id)
    assert token and runs.update(run_id, token, 100, 100, 20, 'completed')
    assert cursor.execute.call_args.args[1][-2:] == (run_id, token)
    SchemaManager(db).initialize_db()
    ddl = next(call.args[0] for call in cursor.execute.call_args_list
               if 'CREATE TABLE IF NOT EXISTS list_import_runs' in call.args[0])
    assert 'owner_id INT' in ddl and 'UNIQUE NOT NULL' in ddl
    assert 'config_json TEXT NOT NULL' in ddl if db_type == 'postgres' else 'config_json LONGTEXT NOT NULL' in ddl


@pytest.mark.asyncio
async def test_transient_queue_preserves_identity_approval_profiles_and_duplicate_guard():
    from api_service.services.seer.seer_client import SeerClient
    db = MagicMock()
    db.check_request_exists.return_value = False
    db.get_auth_user_by_id.return_value = {'seer_user_id': 42}
    db.enqueue_request.return_value = True
    profile = {'serverId': 0, 'profileId': 3, 'rootFolder': '/movies', 'is4k': False}
    client = SeerClient('http://seer.local', 'test', queue_context={
        **CONFIG, 'job_type': 'list_import', 'job_id': None, 'owner_id': 7,
        'request_profiles': {'movie': profile}})
    with patch('api_service.services.seer.seer_client.DatabaseManager', return_value=db), \
            patch('api_service.services.seer.seer_client.load_env_vars', return_value={}):
        assert await client.request_media('movie', {'id': 7}, source={'id': 'list_import'})
        assert not await client.request_media('movie', {'id': 7}, source={'id': 'list_import'})
    args, kwargs = db.enqueue_request.call_args
    assert args[3]['userId'] == 42
    assert all(args[3][key] == value for key, value in profile.items())
    assert kwargs == {'status': 'awaiting_approval', 'job_id': None, 'owner_id': 7, 'execution_id': None}
    db.enqueue_request.assert_called_once()


@pytest.mark.asyncio
async def test_unsaved_factory_enforces_exclusions_and_creates_no_job(repo, monkeypatch):
    from api_service.jobs import list_import_automation
    from api_service.jobs.trakt_recommendations_automation import TraktRecommendationsAutomation
    async def initialize(instance, dry_run=False):
        instance.seer_client = MagicMock(exclude_downloaded=False, exclude_requested=False)
    monkeypatch.setattr(TraktRecommendationsAutomation, '_initialize_components', initialize)
    monkeypatch.setattr(list_import_automation, 'DatabaseManager', lambda: repo.db)
    monkeypatch.setattr(list_import_automation.ConfigService, 'get_runtime_config', lambda: {})
    instance = await ListImportAutomation.from_config(CONFIG, 7, dry_run=True)
    assert instance.seer_client.exclude_downloaded and instance.seer_client.exclude_requested
    assert instance.job_id is None and instance.repository is None
    assert instance.job_data['owner_id'] == 7 and instance.job_data['job_type'] == 'list_import'
    assert repo.db.connection.execute('SELECT COUNT(*) FROM list_import_runs').fetchone()[0] == 0


@pytest.mark.asyncio
async def test_import_entire_list_past_job_cap_skips_known_and_duplicates_without_job(repo, monkeypatch):
    runs = ListImportRepository(repo.db)
    run_id = runs.reserve(7, CONFIG)
    source = entries(1250) + entries(50)
    automation = make_automation(repo, source, limit=1000)
    automation.job_id = None
    automation.job_data.update(owner_id=7, id=None, delivery_mode='manual')
    queued = set(range(1, 1101))
    automation._candidate_available.side_effect = lambda item: int(item['tmdb_id']) not in queued
    async def enqueue(kind, item, **kwargs):
        assert kwargs == {'source': {'id': 'list_import'}, 'user': None}
        queued.add(item['id'])
        return True
    automation.seer_client.request_media.side_effect = enqueue
    automation._close_clients = AsyncMock()
    monkeypatch.setattr(one_time_list_import, 'ListImportRepository', lambda: runs)
    factory = AsyncMock(return_value=automation)
    monkeypatch.setattr(one_time_list_import.ListImportAutomation, 'from_config', factory)
    token = runs.claim(7, run_id)
    await one_time_list_import.execute_import(7, run_id, token)
    state = public_import_state(runs.get(7))
    assert state['status'] == 'completed'
    assert state['scanned_count'] == 1300 and state['requested_count'] == 150
    assert len(queued) == 1250
    assert repo.db.connection.execute('SELECT COUNT(*) FROM discover_jobs').fetchone()[0] == 1
    assert repo.db.connection.execute('SELECT COUNT(*) FROM job_execution_history').fetchone()[0] == 0
    assert repo.db.connection.execute('SELECT COUNT(*) FROM job_list_state').fetchone()[0] == 0
    factory.assert_awaited_once_with(CONFIG, 7)


@pytest.mark.asyncio
async def test_provider_failure_keeps_progress_and_retry_continues(repo, monkeypatch):
    runs = ListImportRepository(repo.db)
    run_id = runs.reserve(7, CONFIG)
    automation = make_automation(repo, entries(250), limit=1000)
    automation.job_id = None
    automation._close_clients = AsyncMock()
    automation.trakt_client.public_list_page.side_effect = [(entries(100), True), PublicListError('Try later')]
    monkeypatch.setattr(one_time_list_import, 'ListImportRepository', lambda: runs)
    monkeypatch.setattr(ListImportAutomation, 'from_config', AsyncMock(return_value=automation))
    await one_time_list_import.execute_import(7, run_id)
    state = runs.get(7)
    assert state['status'] == 'failed' and state['scan_offset'] == 100
    assert state['requested_count'] == 100
    recovered = make_automation(repo, entries(250), limit=1000)
    recovered.job_id = None
    recovered._close_clients = AsyncMock()
    monkeypatch.setattr(ListImportAutomation, 'from_config', AsyncMock(return_value=recovered))
    await one_time_list_import.execute_import(7, run_id)
    state = runs.get(7)
    assert state['status'] == 'completed' and state['requested_count'] == 250
    assert recovered.trakt_client.public_list_page.await_args_list[0].args[1] == 100


@pytest.mark.asyncio
async def test_unsaved_preview_is_paginated_and_read_only(repo):
    automation = make_automation(repo, entries(250), limit=1000)
    automation.job_id = None
    automation.SCAN_LIMIT = 100
    result = await automation.run(dry_run=True)
    assert result.success and len(result.dry_run_items) == 100
    assert automation.next_offset == 100 and not automation.scan_complete
    result = await automation.run(dry_run=True, start_offset=200)
    assert len(result.dry_run_items) == 50 and automation.scan_complete
    automation.seer_client.request_media.assert_not_awaited()
    assert repo.db.connection.execute('SELECT COUNT(*) FROM job_execution_history').fetchone()[0] == 0
    assert repo.db.connection.execute('SELECT COUNT(*) FROM list_import_runs').fetchone()[0] == 0


def test_routes_start_poll_resume_preview_and_owner_is_server_controlled(repo, monkeypatch):
    from api_service.blueprints.jobs import routes
    from api_service.test.test_jobs_routes_validation import _make_client
    from api_service.jobs.discover_automation import ExecutionResult
    client, jobs = _make_client(monkeypatch)
    runs = ListImportRepository(repo.db)
    monkeypatch.setattr(routes, 'ListImportRepository', lambda: runs)
    start = MagicMock()
    monkeypatch.setattr(routes, 'start_import', start)
    monkeypatch.setattr(routes, 'build_list_client', MagicMock())
    response = client.post('/api/jobs/lists/import', json={**CONFIG, 'owner_id': 7})
    assert response.status_code == 202
    run_id = response.json['data']['id']
    start.assert_called_once_with(1, run_id)
    assert client.get('/api/jobs/lists/import').json['data']['id'] == run_id
    assert client.post('/api/jobs/lists/import', json=CONFIG).status_code == 409
    assert client.post(f'/api/jobs/lists/import/{run_id}/resume').status_code == 409
    assert client.post('/api/jobs/lists/import/not-mine/resume').status_code == 404
    token = runs.claim(1, run_id)
    runs.update(run_id, token, 20, 20, 7, 'failed', 'Provider error')
    assert client.post(f'/api/jobs/lists/import/{run_id}/resume').status_code == 202
    automation = MagicMock(next_offset=100, scan_complete=False)
    automation.run = AsyncMock(return_value=ExecutionResult(True, 100, 1, dry_run_items=[{'tmdb_id': 7}]))
    monkeypatch.setattr(routes.ListImportAutomation, 'from_config', AsyncMock(return_value=automation))
    response = client.post('/api/jobs/lists/preview', json=CONFIG)
    assert response.status_code == 200 and response.json['has_more']
    assert response.json['next_offset'] == 100
    assert client.post('/api/jobs/lists/preview', json={**CONFIG, 'offset': -1}).status_code == 400
    jobs.create_job.assert_not_called()


@pytest.mark.parametrize('endpoint', ['/api/jobs/lists/import', '/api/jobs/lists/preview'])
@pytest.mark.parametrize('patch', [{'filters': {}}, {'media_type': 'person'}, {'delivery_mode': 'invalid'}, {'seer_identity_mode': 'invalid'}])
def test_unsaved_list_validation(endpoint, patch, monkeypatch):
    from api_service.test.test_jobs_routes_validation import _make_client
    client, _ = _make_client(monkeypatch)
    assert client.post(endpoint, json={**CONFIG, **patch}).status_code == 400


def test_new_routes_require_auth_and_hide_other_imports(repo, monkeypatch):
    from api_service.test.test_jobs_routes_validation import _make_client
    from api_service.blueprints.jobs import routes
    runs = ListImportRepository(repo.db)
    other = runs.reserve(7, CONFIG)
    client, _ = _make_client(monkeypatch)
    monkeypatch.setattr(routes, 'ListImportRepository', lambda: runs)
    assert client.get('/api/jobs/lists/import').json['data'] is None
    assert client.post(f'/api/jobs/lists/import/{other}/resume').status_code == 404
    client.application.before_request_funcs[None] = []
    for endpoint in ['/api/jobs/lists/import', '/api/jobs/lists/preview', f'/api/jobs/lists/import/{other}/resume']:
        assert client.post(endpoint, json=CONFIG).status_code == 401
