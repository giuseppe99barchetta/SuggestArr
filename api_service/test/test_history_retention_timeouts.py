"""Run history lookups, daily retention, outbound timeouts and AI search bounds."""
import asyncio
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from flask import Flask, g

import api_service.db.database_manager  # noqa: F401  registers the SQLite datetime adapter used in production
from api_service.api.v1.blueprint import public_api_v1_bp
from api_service.db.components.cleanup_mixin import CleanupMixin
from api_service.db.components.request_queue_mixin import RequestQueueMixin
from api_service.db.components.schema_manager import SchemaManager
from api_service.db.components.webhook_mixin import WebhookMixin
from api_service.db.job_repository import JobRepository
from api_service.jobs import retention


class MemoryDB(RequestQueueMixin, WebhookMixin, CleanupMixin):
    db_type = 'sqlite'
    logger = MagicMock()

    def __init__(self):
        self.connection = sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES)
        self.connection.row_factory = sqlite3.Row
        SchemaManager(self).initialize_db()

    @contextmanager
    def get_connection(self):
        yield self.connection


@pytest.fixture
def db():
    memory = MemoryDB()
    yield memory
    memory.connection.close()


def utc(**delta):
    return datetime.now(timezone.utc) + timedelta(**delta)


# --- run history ----------------------------------------------------------------------------------

@pytest.fixture
def repo(db):
    repository = object.__new__(JobRepository)
    repository.logger = MagicMock()
    repository.db = db
    for job_id, owner in ((1, 7), (2, 8)):
        db.connection.execute(
            "INSERT INTO discover_jobs (id, name, media_type, filters, schedule_type, schedule_value, owner_id) "
            "VALUES (?, ?, 'movie', '{}', 'preset', 'daily', ?)", (job_id, f'job{job_id}', owner))
    db.connection.commit()
    return repository


def add_run(db, job_id, status, minutes_ago):
    started = (datetime.now() - timedelta(minutes=minutes_ago)).isoformat()
    cursor = db.connection.execute("INSERT INTO job_execution_history (job_id, started_at, status) VALUES (?, ?, ?)",
                                   (job_id, started, status))
    db.connection.commit()
    return cursor.lastrowid


def test_get_execution_finds_a_run_older_than_the_newest_thousand(repo):
    oldest = add_run(repo.db, 1, 'completed', 5000)
    for minutes in range(1100):
        add_run(repo.db, 1, 'completed', minutes)
    assert repo.get_execution(oldest)['id'] == oldest
    assert repo.get_execution(10 ** 9) is None


def test_list_executions_filters_pages_and_counts_in_sql(repo):
    for minutes in range(1, 8):
        add_run(repo.db, 1, 'completed' if minutes % 2 else 'failed', minutes)
    add_run(repo.db, 2, 'completed', 1)
    rows, total = repo.list_executions(job_id=1, limit=3, offset=0)
    assert total == 7 and len(rows) == 3
    assert [r['started_at'] for r in rows] == sorted((r['started_at'] for r in rows), reverse=True)
    rows, total = repo.list_executions(job_id=1, limit=3, offset=6)
    assert total == 7 and len(rows) == 1
    _, failed = repo.list_executions(job_id=1, status='failed')
    assert failed == 3
    _, everything = repo.list_executions()
    assert everything == 8


def test_regular_users_only_see_the_runs_of_their_own_jobs(repo):
    add_run(repo.db, 1, 'completed', 1)
    add_run(repo.db, 2, 'completed', 1)
    rows, total = repo.list_executions(owner_id=7)
    assert total == 1 and rows[0]['job_id'] == 1


def api_client(role='admin', user_id=7):
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.before_request
    def authenticate():
        g.current_user = {'id': user_id, 'username': 't', 'role': role}
        g.auth_method, g.api_key_id, g.api_key_name = 'test', None, None

    app.register_blueprint(public_api_v1_bp, url_prefix='/api/v1')
    return app.test_client()


def test_the_runs_endpoint_pages_and_scopes_in_the_repository_not_in_python():
    repository = MagicMock()
    repository.list_executions.return_value = ([{'id': 3, 'job_id': 1, 'job_name': 'j', 'status': 'completed'}], 41)
    with patch('api_service.api.v1.blueprint.JobRepository', return_value=repository), \
            patch('api_service.api.v1.blueprint.limiter.enabled', False):
        admin = api_client().get('/api/v1/runs?page=2&per_page=10&job_id=1&status=failed')
        regular = api_client('user', 7).get('/api/v1/runs')
    assert admin.json['meta'] == {'page': 2, 'per_page': 10, 'total': 41, 'pages': 5}
    assert repository.list_executions.call_args_list[0].kwargs == {
        'job_id': 1, 'status': 'failed', 'owner_id': None, 'limit': 10, 'offset': 10}
    assert repository.list_executions.call_args_list[1].kwargs['owner_id'] == 7
    assert regular.status_code == 200


# --- retention ------------------------------------------------------------------------------------

def add_webhook(db, event, status, updated_at):
    db.connection.execute(
        "INSERT INTO webhook_deliveries (event_id, webhook_id, event_type, url, secret, payload, status, updated_at) "
        "VALUES (?, 'w', 'e', 'http://x', 's', '{}', ?, ?)", (event, status, updated_at))
    db.connection.commit()


def test_webhook_retention_removes_only_finished_deliveries_past_the_cutoff_on_the_same_day(db):
    # CURRENT_TIMESTAMP text; cutoff = 30 days ago, rows 5 minutes either side of it share a calendar day
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    before = (cutoff - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
    after = (cutoff + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
    add_webhook(db, 'old-delivered', 'delivered', before)
    add_webhook(db, 'old-failed', 'failed', before)
    add_webhook(db, 'old-queued', 'queued', before)       # still waiting: kept whatever its age
    add_webhook(db, 'recent-delivered', 'delivered', after)
    assert db.prune_webhook_deliveries(30) == 2
    remaining = {r[0] for r in db.connection.execute('SELECT event_id FROM webhook_deliveries')}
    assert remaining == {'old-queued', 'recent-delivered'}


def test_cleanup_log_retention_respects_the_cutoff(db):
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    for tmdb, when in (('1', cutoff - timedelta(minutes=5)), ('2', cutoff + timedelta(minutes=5))):
        db.connection.execute("INSERT INTO cleanup_log (tmdb_id, media_type, title, action, was_dry_run, ran_at) "
                              "VALUES (?, 'movie', 't', 'kept', 0, ?)", (tmdb, when.strftime('%Y-%m-%d %H:%M:%S')))
    db.connection.commit()
    assert db.prune_cleanup_log(90) == 1
    assert [r[0] for r in db.connection.execute('SELECT tmdb_id FROM cleanup_log')] == ['2']


def test_only_stale_submission_locks_are_purged(db):
    db.connection.execute("INSERT INTO submission_locks (tmdb_id, media_type, locked_at) "
                          "VALUES ('1', 'movie', datetime('now', '-2 hours'))")
    db.connection.execute("INSERT INTO submission_locks (tmdb_id, media_type, locked_at) "
                          "VALUES ('2', 'movie', datetime('now', '-5 minutes'))")
    db.connection.commit()
    assert db.purge_stale_submission_locks(3600) == 1
    assert [r[0] for r in db.connection.execute('SELECT tmdb_id FROM submission_locks')] == ['2']


def test_retention_runs_every_step_even_when_one_fails():
    manager = MagicMock()
    manager.cleanup_expired_refresh_tokens.side_effect = RuntimeError('locked')
    manager.prune_webhook_deliveries.return_value = 4
    manager.prune_cleanup_log.return_value = 5
    manager.purge_stale_submission_locks.return_value = 1
    with patch.object(retention, 'DatabaseManager', return_value=manager):
        deleted = retention.run_retention()
    assert deleted == {'refresh_tokens': 0, 'webhook_deliveries': 4, 'cleanup_log': 5, 'submission_locks': 1}
    manager.prune_webhook_deliveries.assert_called_once_with(retention.WEBHOOK_RETENTION_DAYS)


def test_retention_never_touches_the_tables_other_code_depends_on(db):
    for table in ('pending_requests', 'request_expiry_log', 'job_execution_history', 'request_replacements'):
        assert table not in open(retention.__file__, encoding='utf-8').read().split('"""', 2)[2], table


# --- timeouts -------------------------------------------------------------------------------------

def test_plex_pin_calls_have_a_timeout():
    from api_service.services.plex.plex_auth import PlexAuth
    auth = PlexAuth.__new__(PlexAuth)
    auth.base_url, auth.headers, auth.client_id = 'https://plex.tv/api/v2', {}, 'cid'
    response = MagicMock()
    response.json.return_value = {'id': 1, 'code': 'abc'}
    with patch('api_service.services.plex.plex_auth.requests.post', return_value=response) as post, \
            patch('api_service.services.plex.plex_auth.requests.get', return_value=response) as get:
        auth.get_authentication_pin()
        auth.check_authentication(1)
    assert post.call_args.kwargs['timeout'] == 10 and get.call_args.kwargs['timeout'] == 10


def test_tmdb_connection_test_reports_a_timeout_instead_of_failing():
    from api_service.blueprints.tmdb import routes

    class TimingOutSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def get(self, *args, **kwargs):
            raise asyncio.TimeoutError()

    app = Flask(__name__)
    app.register_blueprint(routes.tmdb_bp, url_prefix='/api/tmdb')
    with patch.object(routes.aiohttp, 'ClientSession', TimingOutSession):
        response = app.test_client().post('/api/tmdb/test', json={'api_key': 'k'})
    assert response.status_code == 400
    assert response.json['message'] == 'Connection to TMDB API timed out'


@pytest.mark.parametrize('path', ['services/tmdb/tmdb_client.py', 'services/trakt/trakt_client.py',
                                  'services/simkl/simkl_client.py'])
def test_provider_clients_treat_a_total_timeout_like_a_connection_error(path):
    import pathlib
    source = (pathlib.Path(__file__).resolve().parents[1] / path).read_text(encoding='utf-8')
    assert 'except aiohttp.ClientError' not in source  # aiohttp's total timeout is an asyncio.TimeoutError


# --- AI search bounds ------------------------------------------------------------------------------

@pytest.fixture
def ai_client():
    from api_service.blueprints.ai_search import routes
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.before_request
    def authenticate():
        g.current_user = {'id': '1', 'username': 't', 'role': 'admin', 'visible_tabs': ''}

    app.register_blueprint(routes.ai_search_bp, url_prefix='/api/ai-search')
    service = MagicMock()
    service.search = AsyncMock(return_value={'results': [], 'total': 0})
    service.config = {}
    with patch.object(routes, 'get_llm_client', return_value=object()), \
            patch.object(routes, 'AiSearchService', return_value=service), \
            patch.object(routes.limiter, 'enabled', False):
        yield app.test_client(), service


def post(client, **body):
    return client.post('/api/ai-search/query', json={'query': 'quiet sci-fi', **body})


def test_ai_search_rejects_an_oversized_query_and_bad_result_counts(ai_client):
    client, service = ai_client
    assert post(client, query='x' * 501).status_code == 400
    for bad in ('abc', -5, [1]):
        assert post(client, max_results=bad).status_code == 400, bad
    service.search.assert_not_awaited()


def test_ai_search_clamps_the_result_count_it_sends_to_the_llm(ai_client):
    client, service = ai_client
    assert post(client, max_results=500).status_code in (200, 500)
    assert service.search.await_args.kwargs['max_results'] == 24
    assert post(client).status_code in (200, 500)
    assert service.search.await_args.kwargs['max_results'] == 12
