import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from api_service.auth.api_key_service import ApiKeyService
from api_service.db.api_key_repository import ApiKeyRepository
from api_service.db.components.schema_manager import SchemaManager


class SqliteDb:
    db_type = 'sqlite'

    def __init__(self, path):
        self.path = path
        with self.get_connection() as conn:
            conn.execute('CREATE TABLE api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, key_id TEXT UNIQUE, secret_hash TEXT UNIQUE, prefix TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_used_at TIMESTAMP, expires_at TIMESTAMP, revoked_at TIMESTAMP)')

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES)
        try:
            yield conn
        finally:
            conn.close()

    def get_auth_user_by_id(self, user_id):
        return {'id': user_id, 'username': 'tester', 'role': 'user', 'is_active': True}


def _test_db_path():
    return Path.cwd() / f'.api-key-test-{uuid4().hex}.db'


def test_api_key_is_hashed_resolvable_and_revocable():
    path = _test_db_path()
    try:
        service = ApiKeyService(SqliteDb(path))
        created = service.create_key(1, 'test')
        assert created['key'].startswith('sarr_')
        assert service.resolve(created['key'])['api_key_name'] == 'test'
        record = service.repository.get_key_by_public_id(created['key'].split('_')[1])
        assert created['key'] not in record['secret_hash']
        assert ApiKeyRepository(service.db).revoke_key(1, created['id'])
        assert service.resolve(created['key']) is None
    finally:
        path.unlink(missing_ok=True)


def test_expired_key_is_not_active():
    path = _test_db_path()
    try:
        service = ApiKeyService(SqliteDb(path))
        created = service.create_key(1, 'expired', datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1))
        assert service.repository.count_active_keys_for_user(1) == 0
        assert service.resolve(created['key']) is None
    finally:
        path.unlink(missing_ok=True)


def test_api_key_mysql_and_postgres_ddl_use_supported_indexed_types():
    manager = SchemaManager(None)
    source = '''CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, key_id TEXT, secret_hash TEXT)'''
    mysql = manager._prepare_create_table_query_for_db('api_keys', source, 'mysql')
    postgres = manager._prepare_create_table_query_for_db('api_keys', source, 'postgres')
    assert 'VARCHAR(32)' in mysql and 'CHAR(64)' in mysql
    assert 'SERIAL PRIMARY KEY' in postgres
