"""MySQL DDL stays within InnoDB's 3072-byte key limit (MySQL refuses longer keys; MariaDB hashes them)."""
import re

from api_service.db.components.schema_manager import SchemaManager
from api_service.test.test_request_replacement import MemoryDB


def _mysql_ddl():
    """The CREATE TABLE statements MySQL would receive, captured from a real schema initialization."""
    ddl = {}
    original = SchemaManager._prepare_create_table_query_for_db

    def capture(self, table_name, query, db_type):
        ddl[table_name] = original(self, table_name, query, 'mysql')
        return original(self, table_name, query, db_type)

    database = MemoryDB()
    SchemaManager._prepare_create_table_query_for_db = capture
    try:
        SchemaManager(database).initialize_db()
    finally:
        SchemaManager._prepare_create_table_query_for_db = original
        database.connection.close()
    return ddl


def _key_bytes(ddl, key_sql):
    """utf8mb4 bytes used by one UNIQUE/PRIMARY key: 4 per indexed character, 4 per INT."""
    columns = dict(re.findall(r'^\s*(\w+)\s+([A-Z]+(?:\(\d+\))?)', ddl, re.MULTILINE))
    total = 0
    for part in key_sql.split(','):
        name, prefix = re.match(r'\s*(\w+)(?:\((\d+)\))?', part).groups()
        kind = columns.get(name, 'INT')
        length = int(prefix) if prefix else int((re.search(r'\((\d+)\)', kind) or [0, 0])[1] or 0)
        total += 4 * length if 'CHAR' in kind else 4
    return total


def test_every_mysql_key_fits_innodb_limit():
    for table, ddl in _mysql_ddl().items():
        for key in re.findall(r'(?:UNIQUE(?: KEY \w+)?|PRIMARY KEY)\s*\(([^()]*(?:\(\d+\)[^()]*)*)\)', ddl):
            assert _key_bytes(ddl, key) <= 3072, f'{table}: key ({key}) is too long for MySQL'


def test_the_long_keys_found_on_mysql_8_are_prefixed():
    ddl = _mysql_ddl()
    assert 'provider(64), external_user_id(191)' in ddl['media_user_identities']
    assert 'source_type(64), source_key(191)' in ddl['trakt_sources']
    assert 'tmdb_id(64), media_type(16)' in ddl['watched_media']
