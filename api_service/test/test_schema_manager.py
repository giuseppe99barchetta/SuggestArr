from contextlib import contextmanager
from unittest.mock import MagicMock

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
