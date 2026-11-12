"""Database type spellings are folded once, and MySQL keeps long text long."""
import re
from unittest.mock import MagicMock, patch

import pytest

from api_service.db import database_manager
from api_service.db.components.schema_manager import MYSQL_LONG_TEXT_COLUMNS, SchemaManager
from api_service.db.database_manager import DatabaseManager, normalize_db_type
from api_service.exceptions.database_exceptions import DatabaseError
from api_service.test.test_mysql_ddl import _mysql_ddl


@pytest.mark.parametrize('raw,expected', [
    ('sqlite', 'sqlite'), (None, 'sqlite'), ('', 'sqlite'),
    ('mysql', 'mysql'), ('MySQL', 'mysql'), (' mariadb ', 'mysql'), ('MariaDB', 'mysql'),
    ('postgres', 'postgres'), ('PostgreSQL', 'postgres'), ('pg', 'postgres'),
])
def test_db_type_spellings_are_folded(raw, expected):
    assert normalize_db_type(raw) == expected


@pytest.mark.parametrize('raw,expected', [('mariadb', 'mysql'), ('MySQL', 'mysql'), ('Postgres', 'postgres')])
def test_the_manager_uses_the_folded_type_everywhere_it_reads_the_setting(raw, expected):
    manager = object.__new__(DatabaseManager)
    manager.logger = MagicMock()
    with patch.object(database_manager, 'load_env_vars', return_value={'DB_TYPE': raw}),             patch.object(DatabaseManager, 'initialize_db'):
        manager.refresh_config()
    assert manager.db_type == expected


def test_connection_test_accepts_a_differently_spelled_type():
    manager = object.__new__(DatabaseManager)
    manager.logger = MagicMock()
    manager.db_path = ':memory:'
    result = manager.test_connection({'DB_TYPE': 'SQLite', 'DB_PATH': ':memory:'})
    assert result['status'] == 'success'


# --- MySQL: every column that stays VARCHAR(512) is short on purpose -------------------------------

SHORT_ON_PURPOSE = {
    'ai_search_feedback.title', 
    'auth_users.username', 'auth_users.password_hash', 'auth_users.role',
    'auth_users.visible_tabs', 'cleanup_log.tmdb_id', 'cleanup_log.media_type',
    'cleanup_log.title', 'cleanup_log.action', 'cleanup_log.reason',
    'cleanup_settings.last_run_status', 'discover_jobs.name',
    'discover_jobs.job_type', 'discover_jobs.media_type', 'discover_jobs.schedule_type',
    'discover_jobs.delivery_mode',
    'discover_jobs.seer_identity_mode', 'discover_jobs.approval_pause_mode',
    'integrations.service', 'job_execution_history.status', 'job_list_state.source_key',
    'job_list_state.lease_token', 'list_import_runs.id', 'list_import_runs.status',
    'list_import_runs.lease_token', 'media_user_identities.provider', 'media_user_identities.external_user_id',
    'media_user_identities.external_username', 'metadata.media_id', 'metadata.media_type',
    'metadata.title', 'metadata.release_date', 'metadata.poster_path',
    'metadata.origin_country', 'metadata.genre_ids', 'metadata.logo_path',
    'metadata.backdrop_path', 'metadata_translations.title', 'pending_requests.tmdb_id',
    'pending_requests.media_type', 'pending_requests.user_id', 'pending_requests.status',
    'rating_prompts.title', 'refresh_tokens.token_hash', 'request_expiry_log.tmdb_id',
    'request_expiry_log.media_type', 'request_expiry_log.action', 'request_expiry_log.reason',
    'request_replacements.status', 'request_replacements.reason', 'requests.tmdb_request_id',
    'requests.media_type', 'requests.tmdb_source_id', 'requests.source_origin',
    'requests.requested_by', 'requests.user_id', 'simkl_account_links.simkl_user_id',
    'simkl_account_links.simkl_username', 'simkl_account_links.token_source', 'simkl_account_links.status',
    'simkl_account_links.pending_device_code', 'simkl_account_links.pending_code_verifier', 'simkl_watched_cache.title',
    'suggestion_feedback.title', 'trakt_account_links.trakt_user_id', 'trakt_account_links.trakt_username',
    'trakt_account_links.token_source', 'trakt_account_links.status', 'trakt_sources.source_type',
    'trakt_sources.source_key', 'trakt_sources.list_id', 'trakt_sources.list_slug',
    'trakt_sources.username', 'user_media_profiles.provider', 'user_media_profiles.external_user_id',
    'user_media_profiles.external_username', 'users.user_id', 'users.user_name',
    'watched_media.tmdb_id', 'watched_media.media_type', 'watched_media.title',
    'watched_media.source', 'webhook_deliveries.secret',
}


def test_every_mysql_varchar_512_column_is_short_on_purpose():
    ddl = _mysql_ddl()
    still_short = {f'{table}.{name}' for table, query in ddl.items()
                   for name in re.findall(r'^\s*(\w+)\s+VARCHAR\(512\)', query, re.MULTILINE)}
    unexpected = still_short - SHORT_ON_PURPOSE
    assert not unexpected, (
        f'{sorted(unexpected)} would store free text or JSON in VARCHAR(512), which MySQL rejects or truncates '
        'beyond 512 characters: add the column to MYSQL_LONG_TEXT_COLUMNS, or to SHORT_ON_PURPOSE if it is short.')
    assert not SHORT_ON_PURPOSE - still_short, 'stale entries in SHORT_ON_PURPOSE'


def test_the_long_text_columns_are_longtext_in_a_fresh_mysql_schema():
    ddl = _mysql_ddl()
    for table, columns in MYSQL_LONG_TEXT_COLUMNS.items():
        for column in columns:
            assert re.search(r'(?<![A-Za-z_])' + column + r'\s+LONGTEXT', ddl[table]), f'{table}.{column}'


# --- existing MySQL installs ---------------------------------------------------------------------------

def mysql_manager(columns):
    """SchemaManager whose information_schema says each (table, column) has the given (type, nullable)."""
    manager = object.__new__(SchemaManager)
    manager.logger = MagicMock()
    manager.db_type = 'mysql'
    manager._database = MagicMock()
    cursor = MagicMock()
    state = {}

    def execute(sql, params=None):
        state['sql'] = sql
        state['params'] = params
        if sql.startswith('SELECT'):
            state['row'] = columns.get(tuple(params))
    cursor.execute.side_effect = execute
    cursor.fetchone.side_effect = lambda: state.get('row')
    connection = MagicMock()
    connection.cursor.return_value = cursor
    manager.get_connection = MagicMock()
    manager.get_connection.return_value.__enter__.return_value = connection
    return manager, cursor


def alters(cursor):
    return [call.args[0] for call in cursor.execute.call_args_list if call.args[0].startswith('ALTER')]


def test_existing_varchar_columns_are_widened_keeping_their_nullability():
    columns = {('pending_requests', 'payload'): ('varchar', 'NO'), ('pending_requests', 'last_error'): ('varchar', 'YES')}
    manager, cursor = mysql_manager(columns)
    manager._widen_mysql_long_text_columns()
    statements = alters(cursor)
    assert 'ALTER TABLE pending_requests MODIFY payload LONGTEXT NOT NULL' in statements
    assert 'ALTER TABLE pending_requests MODIFY last_error LONGTEXT NULL' in statements
    assert len(statements) == 2  # every other column was not found: nothing else is touched


def test_columns_already_long_are_not_altered_again():
    columns = {(table, column): ('longtext', 'NO') for table, cols in MYSQL_LONG_TEXT_COLUMNS.items() for column in cols}
    manager, cursor = mysql_manager(columns)
    manager._widen_mysql_long_text_columns()
    assert alters(cursor) == []


def test_other_engines_are_left_alone():
    manager, cursor = mysql_manager({})
    manager.db_type = 'sqlite'
    manager._widen_mysql_long_text_columns()
    cursor.execute.assert_not_called()


# --- migrations no longer hide failures ----------------------------------------------------------------

@pytest.mark.parametrize('method', ['_migrate_auth_users_table', '_migrate_user_media_profiles_table',
                                    '_migrate_discover_jobs_table', '_migrate_viewer_role_to_user'])
def test_a_failing_migration_raises_instead_of_leaving_the_schema_half_done(method):
    manager = object.__new__(SchemaManager)
    manager.logger = MagicMock()
    manager.db_type = 'sqlite'
    manager.get_connection = MagicMock(side_effect=RuntimeError('database is locked'))
    with pytest.raises((DatabaseError, RuntimeError)):
        getattr(manager, method)()


def test_startup_corrections_do_not_narrow_the_long_text_columns():
    source = open(SchemaManager.__module__.replace('.', '/') + '.py', encoding='utf-8').read() if False else None
    import inspect
    text = inspect.getsource(SchemaManager)
    for table, columns in MYSQL_LONG_TEXT_COLUMNS.items():
        for column in columns:
            assert f'ALTER TABLE {table} MODIFY {column} TEXT' not in text, f'{table}.{column} is narrowed on every start'


def test_queue_indexes_are_created_once_on_sqlite():
    import sqlite3
    from contextlib import contextmanager
    connection = sqlite3.connect(':memory:')
    for ddl in ('CREATE TABLE pending_requests (id INTEGER, status TEXT, next_attempt_at TIMESTAMP, execution_id INTEGER)',
                'CREATE TABLE webhook_deliveries (id INTEGER, status TEXT, next_attempt_at TIMESTAMP)',
                'CREATE TABLE job_execution_history (id INTEGER, job_id INTEGER, started_at TIMESTAMP)'):
        connection.execute(ddl)
    manager = object.__new__(SchemaManager)
    manager.logger = MagicMock()
    manager.db_type = 'sqlite'

    @contextmanager
    def get_connection():
        yield connection
    manager.get_connection = get_connection
    manager._create_queue_indexes()
    manager._create_queue_indexes()  # repeatable
    names = {row[1] for table in ('pending_requests', 'webhook_deliveries', 'job_execution_history')
             for row in connection.execute(f'PRAGMA index_list({table})')}
    assert {name for name, _, _ in SchemaManager.QUEUE_INDEXES} <= names


def test_mysql_indexes_use_a_prefix_for_the_text_columns():
    manager, cursor = mysql_manager({})
    state = {'row': None}
    cursor.fetchall.side_effect = lambda: []  # information_schema: no index yet (one row per indexed column)
    manager._create_queue_indexes()
    statements = [call.args[0] for call in cursor.execute.call_args_list if call.args[0].startswith('CREATE INDEX')]
    assert 'CREATE INDEX idx_pending_requests_due ON pending_requests (status(32), next_attempt_at)' in statements
    assert 'CREATE INDEX idx_job_history_job_started ON job_execution_history (job_id, started_at)' in statements
    assert len(statements) == 4


def test_existing_text_columns_are_widened_too():
    columns = {('discover_jobs', 'request_profiles'): ('text', 'YES'), ('simkl_oauth_tokens', 'access_token'): ('text', 'NO')}
    manager, cursor = mysql_manager(columns)
    manager._widen_mysql_long_text_columns()
    assert 'ALTER TABLE discover_jobs MODIFY request_profiles LONGTEXT NULL' in alters(cursor)
    assert 'ALTER TABLE simkl_oauth_tokens MODIFY access_token LONGTEXT NOT NULL' in alters(cursor)


@pytest.mark.parametrize('spelling', ['sqlite', 'SQLite', ' sqlite ', None])
def test_setup_validation_uses_the_same_folded_type(spelling):
    from api_service.config.config import is_setup_complete
    config = {'SELECTED_SERVICE': 'plex', 'PLEX_API_URL': 'http://p', 'PLEX_TOKEN': 't', 'TMDB_API_KEY': 'k',
              'DB_TYPE': spelling, 'REQUEST_BACKEND': 'seer', 'SEER_API_URL': 'http://s', 'SEER_TOKEN': 'x'}
    assert is_setup_complete(config) is True
    external = dict(config, DB_TYPE='MariaDB')  # needs the external database credentials
    assert is_setup_complete(external) is False
