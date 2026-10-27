import asyncio
import hashlib
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api_service.db.components.schema_manager import SchemaManager
from api_service.db.job_repository import JobRepository
from api_service.jobs.list_import_automation import ListImportAutomation, validate_list_job
from api_service.services.mdblist.mdblist_client import MDBListClient
from api_service.services.public_lists import PublicListError, normalize_list_item, parse_list_url
from api_service.services.trakt.trakt_client import TraktClient
from api_service.test.test_trakt_client import FakeResponse, FakeSession as TraktFakeSession


class FakeSession(TraktFakeSession):
    closed = False


URL = 'https://mdblist.com/lists/alice/favorites'
TRAKT_URL = 'https://trakt.tv/users/alice/lists/favorites'


@pytest.mark.parametrize('provider,url', [
    ('mdblist', URL), ('trakt', TRAKT_URL), ('mdblist', URL + '/'),
    ('trakt', TRAKT_URL.replace('trakt.tv', 'www.trakt.tv')),
])
def test_official_list_urls(provider, url):
    assert parse_list_url(provider, url) == ('alice', 'favorites')


@pytest.mark.parametrize('url', [
    URL.replace('https:', 'http:'), URL.replace('mdblist.com', 'mdblist.com.evil.test'),
    URL.replace('mdblist.com', 'localhost'), URL.replace('mdblist.com', 'secret@mdblist.com'),
    URL + '?apikey=secret', URL + '#secret', URL + '/items', URL.replace('alice', '..'),
    URL.replace('mdblist.com', 'mdblist.com:8443'), URL.replace('alice', '%2fadmin'),
    URL.replace('mdblist.com', 'mdblist.com:invalid'),
])
def test_untrusted_urls_rejected(url):
    with pytest.raises(PublicListError):
        parse_list_url('mdblist', url)


@pytest.mark.parametrize('raw,expected', [
    ({'type': 'movie', 'movie': {'ids': {'tmdb': 7}, 'title': 'Movie'}}, ('movie', '7')),
    ({'mediatype': 'show', 'tmdb_id': 7}, ('tv', '7')),
    ({'type': 'episode', 'episode': {'ids': {'tmdb': 7}}}, None),
    ({'type': 'movie', 'tmdb_id': -1}, None), ({'type': 'movie', 'tmdb_id': True}, None),
    ({'type': 'movie', 'ids': {'imdb': 'tt123'}}, None), (None, None),
])
def test_normalize_items(raw, expected):
    item = normalize_list_item(raw)
    assert ((item['media_type'], item['tmdb_id']) if item else None) == expected


@pytest.mark.asyncio
async def test_trakt_public_reads_never_send_oauth_and_resume_midpage():
    session = FakeSession([FakeResponse(200, {'privacy': 'public', 'name': 'Favorites'}),
                           FakeResponse(200, [{'type': 'movie'}] * 100, {'X-Pagination-Page-Count': '2'})])
    client = TraktClient('client', access_token='private-token', session=session, db=MagicMock())
    assert (await client.public_list_info(TRAKT_URL))['name'] == 'Favorites'
    items, more = await client.public_list_page(TRAKT_URL, 25)
    assert len(items) == 75 and more
    for _, _, kwargs in session.calls:
        assert 'Authorization' not in kwargs['headers']
        assert kwargs['allow_redirects'] is False
    assert session.calls[1][2]['params'] == {'page': 1, 'limit': 100}


@pytest.mark.asyncio
@pytest.mark.parametrize('metadata', [{}, {'privacy': 'private'}, {'privacy': 'link'}])
async def test_trakt_rejects_private_or_unknown_visibility(metadata):
    client = TraktClient('client', session=FakeSession([FakeResponse(200, metadata)]), db=MagicMock())
    with pytest.raises(PublicListError):
        await client.public_list_info(TRAKT_URL)


@pytest.mark.asyncio
async def test_mdblist_paging_and_mixed_rank():
    client = MDBListClient('private-key')
    client.session = FakeSession([FakeResponse(200, [{'name': 'List', 'private': False}]),
        FakeResponse(200, {'movies': [{'tmdb_id': 1, 'rank': 2}],
                           'shows': [{'tmdb_id': 2, 'rank': 1}]}, {'X-Has-More': 'true'})])
    assert (await client.public_list_info(URL))['name'] == 'List'
    items, more = await client.public_list_page(URL, 100)
    assert more and [normalize_list_item(item)['media_type'] for item in items] == ['tv', 'movie']
    assert client.session.calls[1][2]['params']['offset'] == 100
    assert 'mediatype' not in client.session.calls[1][2]['params']


@pytest.mark.asyncio
async def test_mdblist_official_list_uses_slug_and_media_filter():
    client = MDBListClient('key')
    client.session = FakeSession([FakeResponse(200, [{'name': 'Popular', 'private': False}]),
                                  FakeResponse(200, [{'tmdb_id': 1, 'mediatype': 'movie'}])])
    official = 'https://mdblist.com/lists/official/movies/popular'
    assert (await client.public_list_info(official))['name'] == 'Popular'
    await client.public_list_page(official, 0)
    assert [call[1] for call in client.session.calls] == [
        'https://api.mdblist.com/lists/official/popular', 'https://api.mdblist.com/lists/official/popular/items']
    assert client.session.calls[1][2]['params']['mediatype'] == 'movie'


@pytest.mark.parametrize('path', ['official/films/popular', 'alice/movies/popular', 'official/movies/popular/items'])
def test_mdblist_official_url_shape_enforced(path):
    with pytest.raises(PublicListError):
        parse_list_url('mdblist', f'https://mdblist.com/lists/{path}')


@pytest.mark.asyncio
@pytest.mark.parametrize('metadata', [[{'private': True}], [{}], [], {'privacy': 'private'}])
async def test_mdblist_rejects_private_or_unknown_visibility(metadata):
    client = MDBListClient('key')
    client.session = FakeSession([FakeResponse(200, metadata)])
    with pytest.raises(PublicListError):
        await client.public_list_info(URL)


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [301, 302, 401, 403, 404, 500])
async def test_provider_errors_are_safe_and_redirects_disabled(status):
    client = MDBListClient('super-secret')
    client.session = FakeSession([FakeResponse(status, {'message': 'super-secret'})])
    with pytest.raises(PublicListError) as error:
        await client.public_list_info(URL)
    assert 'super-secret' not in str(error.value)
    assert client.session.calls[0][2]['allow_redirects'] is False


@pytest.mark.asyncio
async def test_bounded_rate_limit_retry():
    client = MDBListClient('key')
    client.session = FakeSession([FakeResponse(429, headers={'Retry-After': '1'}), FakeResponse(429)])
    with patch('api_service.services.public_lists.asyncio.sleep', new_callable=AsyncMock) as sleep:
        with pytest.raises(PublicListError, match='rate limit'):
            await client.public_list_info(URL)
    sleep.assert_awaited_once_with(1)
    assert len(client.session.calls) == 2


class MemoryDB:
    db_type = 'sqlite'
    logger = logging.getLogger('list-test')

    def __init__(self):
        self.connection = sqlite3.connect(':memory:')

    @contextmanager
    def get_connection(self):
        yield self.connection


@pytest.fixture
def repo():
    db = MemoryDB()
    SchemaManager(db).initialize_db()
    repo = object.__new__(JobRepository)
    repo.db, repo.logger = db, db.logger
    repo.create_job({'name': 'List', 'job_type': 'list_import', 'media_type': 'both',
                     'filters': {'list_provider': 'mdblist', 'list_url': URL},
                     'schedule_type': 'preset', 'schedule_value': 'daily'})
    yield repo
    db.connection.close()


def test_state_migration_repeatable_lease_resume_reset_and_expiry(repo):
    SchemaManager(repo.db).initialize_db()
    token = repo.claim_list_scan(1, 'source')
    assert token and repo.claim_list_scan(1, 'source') is None
    assert repo.checkpoint_list_scan(1, token, 125, release=True)
    assert repo.list_scan_offset(1, 'source') == 125
    token = repo.claim_list_scan(1, 'source')
    assert repo.list_scan_offset(1, 'source') == 125
    assert not repo.checkpoint_list_scan(1, 'wrong-token', 999)
    repo.db.connection.execute('UPDATE job_list_state SET lease_until=?', (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),))
    repo.db.connection.commit()
    new_token = repo.claim_list_scan(1, 'changed-filters')
    assert new_token and repo.list_scan_offset(1, 'changed-filters') == 0
    assert not repo.checkpoint_list_scan(1, token, 999, release=True)


@pytest.mark.parametrize('db_type', ['sqlite', 'postgres', 'mysql', 'mariadb'])
def test_cursor_ddl_supported(db_type):
    sql = 'CREATE TABLE IF NOT EXISTS job_list_state (job_id INTEGER PRIMARY KEY, source_key TEXT NOT NULL, scan_offset INTEGER NOT NULL DEFAULT 0, lease_token TEXT, lease_until TIMESTAMP NULL, FOREIGN KEY (job_id) REFERENCES discover_jobs(id) ON DELETE CASCADE)'
    ddl = SchemaManager(MemoryDB())._prepare_create_table_query_for_db('job_list_state', sql, db_type)
    assert 'job_id' in ddl and 'ON DELETE CASCADE' in ddl
    if db_type in ('mysql', 'mariadb'):
        assert 'ENGINE=InnoDB' in ddl and 'VARCHAR(512)' in ddl


def make_automation(repo, items, *, limit=20):
    automation = ListImportAutomation()
    automation.repository, automation.db_manager = repo, repo.db
    automation.job_id = 1
    automation.job_data = repo.get_job(1)
    automation.job_data['max_results'] = limit
    automation.seer_client = MagicMock()
    automation.seer_client.__aenter__ = AsyncMock()
    automation.seer_client.__aexit__ = AsyncMock(return_value=False)
    automation.seer_client.queue_context = {}
    automation.seer_client.request_media = AsyncMock(return_value=True)
    automation.tmdb_client = MagicMock()
    automation.tmdb_client.__aenter__ = AsyncMock()
    automation.tmdb_client.__aexit__ = AsyncMock(return_value=False)
    automation.tmdb_client.omdb_client = None
    automation.trakt_client = MagicMock()
    automation.trakt_client.__aenter__ = AsyncMock()
    automation.trakt_client.__aexit__ = AsyncMock(return_value=False)
    automation.trakt_client.public_list_info = AsyncMock(return_value={'name': 'List'})

    async def page(url, offset, size):
        return items[offset:offset + size], offset + size < len(items)

    automation.trakt_client.public_list_page = AsyncMock(side_effect=page)
    automation._candidate_available = AsyncMock(return_value=True)
    automation._enrich_and_filter_item = AsyncMock(side_effect=lambda item: {'id': int(item['tmdb_id']), 'media_type': item['media_type']})
    return automation


def entries(count):
    return [{'mediatype': 'movie', 'tmdb_id': i + 1} for i in range(count)]


@pytest.mark.asyncio
async def test_skip_first_owned_page_count_only_successes_and_resume(repo):
    automation = make_automation(repo, entries(250), limit=2)
    automation._candidate_available.side_effect = lambda item: int(item['tmdb_id']) > 100
    automation.seer_client.request_media.side_effect = [False, True, True]
    result = await automation.run()
    assert result.success and result.requested_count == 2 and result.results_count == 103
    assert automation.trakt_client.public_list_page.await_count == 2
    for call in automation.seer_client.request_media.await_args_list:
        assert call.kwargs == {'source': {'id': 'list_import'}, 'user': None}
    second = make_automation(repo, entries(250), limit=1)
    await second.run()
    assert second.trakt_client.public_list_page.await_args_list[0].args[1] == 103


@pytest.mark.asyncio
async def test_scan_cap_and_reconsider_from_start_when_exhausted(repo):
    automation = make_automation(repo, entries(1101))
    automation._candidate_available.return_value = False
    result = await automation.run()
    assert result.success and result.results_count == 1000 and result.requested_count == 0
    second = make_automation(repo, entries(1101))
    second._candidate_available.return_value = False
    result = await second.run()
    assert result.results_count == 101
    third = make_automation(repo, entries(1101), limit=1)
    await third.run()
    assert third.trakt_client.public_list_page.await_args_list[0].args[1] == 0


@pytest.mark.asyncio
async def test_preview_no_cursor_history_or_requests(repo):
    automation = make_automation(repo, entries(25), limit=2)
    result = await automation.run(dry_run=True)
    assert result.success and len(result.dry_run_items) == 2
    automation.seer_client.request_media.assert_not_awaited()
    assert repo.db.connection.execute('SELECT COUNT(*) FROM job_list_state').fetchone()[0] == 0
    assert repo.db.connection.execute('SELECT COUNT(*) FROM job_execution_history').fetchone()[0] == 0


@pytest.mark.asyncio
async def test_partial_failure_keeps_count_and_cursor_and_releases_lease(repo):
    automation = make_automation(repo, entries(250), limit=150)
    automation.trakt_client.public_list_page.side_effect = [(entries(100), True), PublicListError('Provider timeout')]
    result = await automation.run()
    assert not result.success and result.requested_count == 100
    assert repo.db.connection.execute('SELECT scan_offset,lease_token FROM job_list_state').fetchone() == (100, None)
    assert repo.get_job_history(1)[0]['requested_count'] == 100


@pytest.mark.asyncio
async def test_mixed_duplicates_and_replacement_keeps_media_scope(repo):
    items = [{'mediatype': 'show', 'tmdb_id': 1}] + entries(2) + entries(2)
    automation = make_automation(repo, items)
    result = await automation.run(dry_run=True)
    assert result.requested_count == 3
    replacement = make_automation(repo, items, limit=1)
    replacement.job_data.update(_replacement_for=5, media_type='tv')
    result = await replacement.run()
    assert result.requested_count == 1
    assert repo.db.connection.execute('SELECT scan_offset FROM job_list_state').fetchone()[0] == 1


@pytest.mark.asyncio
async def test_preview_resumes_existing_cursor_without_advancing_it(repo):
    automation = make_automation(repo, entries(40), limit=2)
    await automation.run()
    result = await automation.run(dry_run=True)
    assert [item['tmdb_id'] for item in result.dry_run_items] == [3, 4]
    assert repo.db.connection.execute('SELECT scan_offset FROM job_list_state').fetchone()[0] == 2


@pytest.mark.asyncio
async def test_error_on_current_candidate_retries_it_and_closes_clients(repo):
    automation = make_automation(repo, entries(20))
    automation._enrich_and_filter_item.side_effect = [dict(id=1), RuntimeError('secret')]
    result = await automation.run()
    assert not result.success and result.requested_count == 1
    assert 'secret' not in result.error_message
    assert repo.db.connection.execute('SELECT scan_offset,lease_token FROM job_list_state').fetchone() == (1, None)
    automation.trakt_client.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_replacement_continues_after_scan_cap(repo):
    automation = make_automation(repo, entries(1100), limit=1)
    automation.job_data['_replacement_for'] = 5
    automation._candidate_available.side_effect = lambda item: int(item['tmdb_id']) > 1000
    result = await automation.run()
    assert not result.success and result.requested_count == 0
    result = await automation.run()
    assert result.success and result.requested_count == 1


@pytest.mark.asyncio
async def test_second_run_cannot_take_an_active_lease(repo):
    automation = make_automation(repo, entries(5))
    original_info = automation.trakt_client.public_list_info
    async def claim_before_run(*args):
        key = hashlib.sha256(json.dumps({'filters': repo.get_job(1)['filters'], 'media_type': 'both'}, sort_keys=True).encode()).hexdigest()
        assert repo.claim_list_scan(1, key)
        return await original_info(*args)
    automation.trakt_client.public_list_info = AsyncMock(side_effect=claim_before_run)
    result = await automation.run()
    assert not result.success and 'already running' in result.error_message
    automation.seer_client.request_media.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [429, 500, 404])
async def test_tmdb_transient_failure_not_consumed(status):
    automation = ListImportAutomation()
    automation.tmdb_client = MagicMock(tmdb_api_url='https://api.themoviedb.org/3', api_key='test', REQUEST_TIMEOUT=10)
    automation.tmdb_client._get_session = AsyncMock(return_value=FakeSession([FakeResponse(status)]))
    if status == 404:
        assert await automation._fetch_tmdb_details(1, 'movie') is None
    else:
        with pytest.raises(RuntimeError):
            await automation._fetch_tmdb_details(1, 'movie')


@pytest.mark.asyncio
async def test_candidate_guards_prevent_metadata_reads(repo):
    automation = make_automation(repo, entries(5))
    del automation._candidate_available
    db = MagicMock(db_type='sqlite')
    automation.db_manager = db
    db.check_request_exists.return_value = True
    assert not await automation._candidate_available({'media_type': 'movie', 'tmdb_id': '1'})
    db.get_connection.assert_not_called()
    db.check_request_exists.return_value = False
    cursor = db.get_connection.return_value.__enter__.return_value.cursor.return_value
    cursor.fetchone.return_value = (1,)
    assert not await automation._candidate_available({'media_type': 'movie', 'tmdb_id': '1'})
    db.is_suggestion_blacklisted.assert_not_called()
    cursor.fetchone.return_value = None
    db.is_suggestion_blacklisted.return_value = False
    db._automated_submission_skip_reason.return_value = 'limit'
    assert not await automation._candidate_available({'media_type': 'movie', 'tmdb_id': '1'})
    automation._enrich_and_filter_item.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,owner_mapping,expected_user', [('matching_user', 42, 42), ('matching_user', None, None), ('technical_user', 42, None)])
async def test_queue_manual_approval_uses_job_owner_mapping(mode, owner_mapping, expected_user):
    from api_service.services.seer.seer_client import SeerClient
    db = MagicMock()
    db.check_request_exists.return_value = False
    db.get_auth_user_by_id.return_value = {'seer_user_id': owner_mapping}
    db.enqueue_request.return_value = True
    client = SeerClient('http://seer.local', 'test', queue_context={
        'job_type': 'list_import', 'job_id': 1, 'owner_id': 7, 'seer_identity_mode': mode,
        'delivery_mode': 'manual', 'execution_id': 5})
    with patch('api_service.services.seer.seer_client.DatabaseManager', return_value=db), \
            patch('api_service.services.seer.seer_client.load_env_vars', return_value={}):
        assert await client.request_media('movie', {'id': 1}, source={'id': 'list_import'}, user=None)
    args, kwargs = db.enqueue_request.call_args
    assert args[2] is None
    assert args[3].get('userId') == expected_user
    assert kwargs == {'status': 'awaiting_approval', 'job_id': 1, 'owner_id': 7, 'execution_id': 5}


def test_list_route_create_update_verify_and_preview(monkeypatch):
    from api_service.test.test_jobs_routes_validation import _make_client
    from api_service.blueprints.jobs import routes
    job = dict(id=1, owner_id=1, job_type='list_import', name='List', enabled=True,
               media_type='both', filters={'list_provider': 'mdblist', 'list_url': URL}, max_results=20)
    client, repository = _make_client(monkeypatch, job)
    repository.create_job.return_value = 1
    response = client.post('/api/jobs', json={**job, 'owner_id': 999, 'schedule_type': 'preset', 'schedule_value': 'daily'})
    assert response.status_code == 201
    assert repository.create_job.call_args.args[0]['owner_id'] == 1
    assert repository.create_job.call_args.args[0]['user_ids'] == []
    assert client.put('/api/jobs/1', json={'max_results': 5}).status_code == 200
    assert client.put('/api/jobs/1', json={'filters': {'list_provider': 'mdblist', 'list_url': 'http://localhost/'}}).status_code == 400
    provider = MagicMock()
    provider.__aenter__ = AsyncMock(return_value=provider)
    provider.__aexit__ = AsyncMock(return_value=False)
    provider.public_list_info = AsyncMock(return_value={'name': 'Favorites', 'provider': 'mdblist'})
    monkeypatch.setattr(routes, 'build_list_client', lambda *args: provider)
    assert client.post('/api/jobs/lists/verify', json=job['filters']).get_json()['data']['name'] == 'Favorites'
    automation = MagicMock()
    from api_service.jobs.discover_automation import ExecutionResult
    automation.run = AsyncMock(return_value=ExecutionResult(True, 1, 1, dry_run_items=[]))
    create = AsyncMock(return_value=automation)
    monkeypatch.setattr(routes.ListImportAutomation, 'create', create)
    assert client.post('/api/jobs/1/dry-run').status_code == 200
    create.assert_awaited_once_with(1, dry_run=True)


@pytest.mark.parametrize('limit', [0, -1, 1001, True, 'bad', None, 1.5])
def test_job_limit_validation(limit):
    with pytest.raises(PublicListError):
        validate_list_job({'filters': {'list_provider': 'mdblist', 'list_url': URL}, 'max_results': limit})


def test_config_secret_registration():
    from api_service.config.config import INTEGRATION_TO_FLAT, get_default_values, get_config_sections
    from api_service.services.config_secrets import redact_settings
    from api_service.services.config_service import _DB_INTEGRATION_KEYS
    from api_service.blueprints.config.routes import _redact_config
    assert 'MDBLIST_API_KEY' in get_default_values()
    assert 'MDBLIST_API_KEY' in get_config_sections()['services']
    assert INTEGRATION_TO_FLAT['mdblist'] == {'api_key': 'MDBLIST_API_KEY'}
    assert 'MDBLIST_API_KEY' in _DB_INTEGRATION_KEYS
    assert redact_settings({'MDBLIST_API_KEY': 'secret'})['MDBLIST_API_KEY'] == '***'
    assert _redact_config({'MDBLIST_API_KEY': 'secret'})['MDBLIST_API_KEY'] != 'secret'


def test_config_db_merge_migration_export_and_masked_import(monkeypatch):
    from api_service.db.components.integration_mixin import IntegrationMixin
    from api_service.services.config_service import ConfigService
    from api_service.services import config_service
    from api_service.config.config import merge_db_integrations_into_flat
    from api_service.blueprints.config.routes import _sync_integrations_from_flat
    store = {'mdblist': {'api_key': 'test-key'}}
    db = MagicMock()
    db.get_all_integrations.return_value = store
    db.get_integration.side_effect = lambda service: store.get(service)
    db.get_all_media_user_identities.return_value = []
    monkeypatch.setattr(config_service, 'DatabaseManager', lambda: db)
    monkeypatch.setattr(config_service, 'load_env_vars', lambda: {'MDBLIST_API_KEY': 'test-key'})
    monkeypatch.setattr(config_service, 'save_env_vars', MagicMock())
    monkeypatch.setattr(config_service, '_export_media_users', lambda *args, **kwargs: [])
    assert merge_db_integrations_into_flat({}, store)['MDBLIST_API_KEY'] == 'test-key'
    snapshot = ConfigService.export_config()
    assert snapshot['integrations']['mdblist']['api_key'] == '***'
    assert 'MDBLIST_API_KEY' not in snapshot['settings']
    ConfigService.import_config({'version': 2, 'integrations': {'mdblist': {'api_key': '***'}}, 'settings': {}})
    db.set_integration.assert_any_call('mdblist', {'api_key': 'test-key'})
    _sync_integrations_from_flat(db, {'MDBLIST_API_KEY': 'new-test-key'})
    db.set_integration.assert_any_call('mdblist', {'api_key': 'new-test-key'})
    migration = MagicMock()
    migration._load_env_vars.return_value = {'MDBLIST_API_KEY': 'test-key'}
    migration.get_integration.return_value = None
    IntegrationMixin.migrate_integrations_from_config(migration)
    migration.set_integration.assert_any_call('mdblist', {'api_key': 'test-key'})


def test_non_owner_cannot_preview_or_update_and_verify_requires_auth(monkeypatch):
    from api_service.test.test_jobs_routes_validation import _make_client
    from flask import g
    job = dict(id=1, owner_id=1, job_type='list_import', media_type='both', filters={'list_provider': 'mdblist', 'list_url': URL})
    client, repository = _make_client(monkeypatch, job)
    def user():
        g.current_user = {'id': 7, 'role': 'user'}
    client.application.before_request_funcs[None] = [user]
    assert client.put('/api/jobs/1', json={'max_results': 1}).status_code == 403
    assert client.post('/api/jobs/1/dry-run').status_code == 403
    repository.update_job.assert_not_called()
    client.application.before_request_funcs[None] = []
    assert client.post('/api/jobs/lists/verify', json=job['filters']).status_code == 401


def test_public_api_v1_list_filter_and_preview(monkeypatch):
    from api_service.test.test_public_api_fields import _client
    from api_service.api.v1 import blueprint
    from api_service.jobs.discover_automation import ExecutionResult
    repo = MagicMock()
    repo.get_all_jobs.return_value = [dict(id=1, owner_id=1, job_type='list_import', enabled=True)]
    repo.get_job.return_value = repo.get_all_jobs.return_value[0]
    monkeypatch.setattr(blueprint, 'JobRepository', lambda: repo)
    automation = MagicMock()
    automation.run = AsyncMock(return_value=ExecutionResult(True, 1, 1, dry_run_items=[{'tmdb_id': 7}]))
    create = AsyncMock(return_value=automation)
    monkeypatch.setattr(blueprint.ListImportAutomation, 'create', create)
    client = _client()
    assert client.get('/api/v1/jobs?job_type=list_import').get_json()['meta']['total'] == 1
    assert client.post('/api/v1/jobs/1/preview').get_json()['data']['items'] == [{'tmdb_id': 7}]
    create.assert_awaited_once_with(1, dry_run=True)


@pytest.mark.parametrize('db_type', ['postgres', 'mysql', 'mariadb'])
def test_external_db_cursor_sql_uses_native_parameters_and_ignore(db_type):
    repo = object.__new__(JobRepository)
    repo.db = MagicMock(db_type=db_type)
    cursor = repo.db.get_connection.return_value.__enter__.return_value.cursor.return_value
    cursor.rowcount = 1
    token = repo.claim_list_scan(7, 'fingerprint')
    assert token
    insert = cursor.execute.call_args_list[0].args[0]
    assert '?' not in insert and '%s' in insert
    assert ('ON CONFLICT' if db_type == 'postgres' else 'INSERT IGNORE') in insert
    assert repo.checkpoint_list_scan(7, token, 100, release=True)
    assert cursor.execute.call_args.args[1] == (100, None, None, 7, token)


def test_mysql_unchanged_heartbeat_checks_lease_ownership():
    repo = object.__new__(JobRepository)
    repo.db = MagicMock(db_type='mysql')
    cursor = repo.db.get_connection.return_value.__enter__.return_value.cursor.return_value
    cursor.rowcount = 0
    cursor.fetchone.return_value = (1,)
    assert repo.checkpoint_list_scan(7, 'token', 100)
    cursor.fetchone.return_value = None
    assert not repo.checkpoint_list_scan(7, 'old-token', 100)


def test_delete_job_cascades_cursor(repo):
    token = repo.claim_list_scan(1, 'fingerprint')
    repo.checkpoint_list_scan(1, token, 20, release=True)
    assert repo.delete_job(1)
    assert repo.db.connection.execute('SELECT COUNT(*) FROM job_list_state').fetchone()[0] == 0


def test_owner_without_media_link_sees_and_rates_only_own_list_suggestions(repo):
    from api_service.db.components.request_queue_mixin import RequestQueueMixin
    from api_service.db.components.suggestion_feedback_mixin import SuggestionFeedbackMixin
    from api_service.utils.request_scope import suggestion_scope
    class Queue(MemoryDB, RequestQueueMixin, SuggestionFeedbackMixin):
        pass
    db = object.__new__(Queue)
    db.connection = repo.db.connection
    db.get_user_media_profiles = lambda user_id: []
    payload = json.dumps({'_source_id': 'list_import', '_user_id': None})
    for row_id, owner, source_payload in [(1, 7, payload), (2, 9, payload), (3, None, payload),
                                        (4, 7, json.dumps({'_source_id': 'discover', '_user_id': None}))]:
        db.connection.execute("INSERT INTO pending_requests(id,tmdb_id,media_type,payload,status,owner_id) VALUES(?,?,'movie',?,'awaiting_approval',?)",
                              (row_id, str(row_id), source_payload, owner))
    db.connection.execute("INSERT INTO auth_users(id,username,password_hash) VALUES(7,'owner','test')")
    db.connection.commit()
    scope = suggestion_scope(db, {'id': 7, 'role': 'user'}, {'REQUEST_VISIBILITY': 'own'})
    assert scope.media_user_ids == [] and scope.include_owned_list_imports
    items, total = db.list_suggestions(owner_id=7, media_user_ids=[], include_owned_list_imports=True)
    assert total == 1 and items[0]['id'] == 1
    assert db.list_suggestions(owner_id=7, media_user_ids=['other-media-user'])[1] == 0
    result = db.set_suggestion_feedback(1, 7, 7, 'not_interested', media_user_ids=[], include_owned_list_imports=True)
    assert result and db.should_skip_feedback(7, '1', 'movie', None)
    assert db.set_suggestion_feedback(2, 7, 7, 'not_interested', media_user_ids=[], include_owned_list_imports=True) is None
    assert db.clear_suggestion_feedback(1, 7, 7, media_user_ids=[], include_owned_list_imports=True)
