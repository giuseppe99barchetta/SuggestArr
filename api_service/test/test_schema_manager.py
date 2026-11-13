from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from api_service.db.components.schema_manager import SchemaManager


def test_mysql_discover_jobs_ddl_uses_longtext_filters():
    manager = SchemaManager(None)
    source = """
        CREATE TABLE IF NOT EXISTS discover_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filters TEXT NOT NULL
        )
    """

    query = manager._prepare_create_table_query_for_db(
        'discover_jobs', source, 'mysql'
    )

    assert 'filters LONGTEXT NOT NULL' in query
    assert 'filters VARCHAR(512)' not in query


class _MysqlDatabase:
    db_type = 'mysql'

    def __init__(self):
        self.logger = MagicMock()
        self.cursor = MagicMock()
        self.connection = MagicMock()
        self.connection.cursor.return_value = self.cursor

    @contextmanager
    def get_connection(self):
        yield self.connection


@pytest.mark.parametrize('has_generation', [True, False])
def test_mysql_auth_migration_consumes_empty_prompt_result(has_generation):
    database = _MysqlDatabase()
    cursor = database.cursor
    pending = False
    auth_columns = [(name,) for name in (
        'can_manage_ai', 'visible_tabs', 'seer_user_id', 'language', 'notify_config',
        'ai_search_shareable', 'rating_prompt_config', 'rating_prompt_generation',
    )]

    def execute(sql):
        nonlocal pending
        assert not pending, 'Unread result found'
        if sql.startswith('SHOW COLUMNS'):
            pending = True
        elif sql.startswith('SELECT * FROM rating_prompts'):
            pending = True
            cursor.description = [('id',)] + ([('generation',)] if has_generation else [])

    def fetchall():
        nonlocal pending
        assert pending
        pending = False
        return auth_columns if cursor.execute.call_args.args[0].startswith('SHOW COLUMNS') else []

    cursor.execute.side_effect = execute
    cursor.fetchall.side_effect = fetchall
    database.connection.commit.side_effect = lambda: pytest.fail('Unread result found') if pending else None

    SchemaManager(database)._migrate_auth_users_table()

    assert not pending
    alterations = [call.args[0] for call in cursor.execute.call_args_list if call.args[0].startswith('ALTER')]
    assert bool(alterations) is not has_generation


def test_mysql_discover_jobs_migration_expands_legacy_filters_column():
    database = _MysqlDatabase()
    database.cursor.fetchall.side_effect = [
        [
            ('id', 'int', 'NO', 'PRI', None, 'auto_increment'),
            ('filters', 'varchar(512)', 'NO', '', None, ''),
            ('job_type', 'varchar(50)', 'NO', '', 'discover', ''),
            ('user_ids', 'varchar(512)', 'YES', '', None, ''),
            ('is_system', 'tinyint(1)', 'YES', '', '0', ''),
            ('owner_id', 'int', 'YES', '', None, ''),
            ('pause_if_pending_requests', 'tinyint(1)', 'YES', '', '0', ''),
            ('prevent_suggestions_if_unwatched', 'tinyint(1)', 'YES', '', '0', ''),
            ('unwatched_suggestion_days', 'int', 'YES', '', '7', ''),
            ('delivery_mode', 'varchar(20)', 'NO', '', 'inherit', ''),
            ('seer_identity_mode', 'varchar(30)', 'NO', '', 'technical_user', ''),
            ('request_profiles', 'text', 'YES', '', None, ''),
            ('approval_pause_mode', 'varchar(20)', 'NO', '', 'inherit', ''),
            ('max_requests_per_user', 'int', 'NO', '', '0', ''),
            ('request_limit_window_hours', 'int', 'NO', '', '24', ''),
        ],
        [],
    ]

    SchemaManager(database)._migrate_discover_jobs_table()

    database.cursor.execute.assert_any_call(
        'ALTER TABLE discover_jobs MODIFY COLUMN filters LONGTEXT NOT NULL;'
    )
    database.connection.commit.assert_called()


def test_mysql_metadata_ddl_keeps_overview_as_text():
    source = "CREATE TABLE IF NOT EXISTS metadata (media_id TEXT PRIMARY KEY, title TEXT, overview TEXT, UNIQUE(media_id, media_type))"

    query = SchemaManager(None)._prepare_create_table_query_for_db('metadata', source, 'mysql')

    assert 'overview TEXT' in query
    assert 'title VARCHAR(512)' in query


def test_mysql_overview_migration_widens_only_varchar_columns():
    database = _MysqlDatabase()
    database.cursor.fetchone.side_effect = [('varchar',), ('text',)]

    SchemaManager(database)._widen_mysql_overview_columns()

    database.cursor.execute.assert_any_call("ALTER TABLE metadata MODIFY overview TEXT")
    altered = [c.args[0] for c in database.cursor.execute.call_args_list if c.args[0].startswith('ALTER')]
    assert altered == ["ALTER TABLE metadata MODIFY overview TEXT"]
