"""A movie and a show with the same TMDb id are two different titles and must both be stored."""
from unittest.mock import MagicMock, patch

import pytest

from api_service.db import database_manager as dm_mod
from api_service.db.components.schema_manager import SchemaManager
from api_service.db.database_manager import DatabaseManager
from api_service.test.test_mysql_ddl import _mysql_ddl

# The two tables exactly as the schema created them before the composite keys.
OLD_REQUESTS = """
    CREATE TABLE requests (
        tmdb_request_id TEXT NOT NULL PRIMARY KEY,
        media_type TEXT NOT NULL,
        tmdb_source_id TEXT,
        source_origin TEXT,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        requested_by TEXT,
        user_id TEXT,
        rationale TEXT,
        UNIQUE(media_type, tmdb_request_id, tmdb_source_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
"""
OLD_METADATA = """
    CREATE TABLE metadata (
        media_id TEXT PRIMARY KEY,
        media_type TEXT NOT NULL,
        title TEXT,
        overview TEXT,
        release_date TEXT,
        poster_path TEXT,
        rating REAL,
        votes INTEGER,
        origin_country TEXT,
        genre_ids TEXT,
        logo_path TEXT,
        backdrop_path TEXT,
        UNIQUE(media_id, media_type)
    )
"""


@pytest.fixture
def db(tmp_path):
    db_file = str(tmp_path / "keys.db")
    with (
        patch.object(dm_mod, "DB_PATH", db_file),
        patch("api_service.db.database_manager.load_env_vars", return_value={"DB_TYPE": "sqlite"}),
    ):
        DatabaseManager._instance = None
        yield DatabaseManager()
    DatabaseManager._instance = None


def _rows(db, query, params=()):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [tuple(row) for row in cursor.fetchall()]


def _execute(db, *statements):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        for statement in statements:
            cursor.execute(*statement) if isinstance(statement, tuple) else cursor.execute(statement)
        conn.commit()


def test_same_id_movie_and_show_are_both_stored(db):
    db.save_metadata({"id": "1399", "title": "A Movie"}, "movie")
    db.save_metadata({"id": "1399", "name": "A Show"}, "tv")
    db.save_request("movie", "1399", "27205")
    db.save_request("tv", "1399", "27205")

    assert sorted(_rows(db, "SELECT media_type, title FROM metadata WHERE media_id = '1399'")) == [
        ("movie", "A Movie"), ("tv", "A Show")]
    assert db.check_request_exists("movie", "1399") and db.check_request_exists("tv", "1399")
    assert len(_rows(db, "SELECT 1 FROM requests WHERE tmdb_request_id = '1399'")) == 2


def test_grouped_requests_join_one_source_row_when_ids_collide(db):
    """With movie 9 and show 9 both in metadata, a request from source 9 is listed once."""
    db.save_metadata({"id": "9", "title": "Source movie"}, "movie")
    db.save_metadata({"id": "9", "name": "Source show"}, "tv")
    db.save_metadata({"id": "50", "title": "Requested movie"}, "movie")
    db.save_request("movie", "50", "9")

    result = db.get_all_requests_grouped_by_source(page=1, per_page=10)

    assert result["total_requests"] == 1
    [group] = result["data"]
    assert group["source_title"] == "Source movie" and len(group["requests"]) == 1


def test_migration_keeps_every_row_and_column(db):
    _execute(
        db,
        "DROP TABLE requests", "DROP TABLE metadata", OLD_REQUESTS, OLD_METADATA,
        # Columns that add_missing_columns added to old installs after the table was created.
        "ALTER TABLE requests ADD COLUMN is_anime BOOLEAN DEFAULT 0",
        "CREATE INDEX idx_requests_user ON requests(user_id)",
        ("INSERT INTO requests (tmdb_request_id, media_type, tmdb_source_id, source_origin, requested_by, user_id, "
         "rationale, is_anime) VALUES ('1399', 'movie', '7', 'llm', 'SuggestArr', 'u1', 'because', 1)",),
        ("INSERT INTO metadata (media_id, media_type, title, logo_path, backdrop_path) "
         "VALUES ('1399', 'movie', 'A Movie', '/logo.png', '/back.png')",),
    )
    before = (_rows(db, "SELECT * FROM requests"), _rows(db, "SELECT * FROM metadata"))

    SchemaManager(db)._migrate_composite_media_keys()
    SchemaManager(db)._migrate_composite_media_keys()  # idempotent

    assert (_rows(db, "SELECT * FROM requests"), _rows(db, "SELECT * FROM metadata")) == before
    pk = {table: [row[1] for row in sorted(_rows(db, f"PRAGMA table_info({table})"), key=lambda r: r[5]) if row[5]]
          for table in ("requests", "metadata")}
    assert pk == {"requests": ["media_type", "tmdb_request_id"], "metadata": ["media_id", "media_type"]}
    assert _rows(db, "SELECT name FROM sqlite_master WHERE name = 'idx_requests_user'") == [("idx_requests_user",)]
    db.save_request("tv", "1399", "7")
    db.save_metadata({"id": "1399", "name": "A Show"}, "tv")
    assert len(_rows(db, "SELECT 1 FROM requests")) == 2 and len(_rows(db, "SELECT 1 FROM metadata")) == 2


def test_mysql_ddl_has_composite_keys_without_over_long_prefixes():
    ddl = _mysql_ddl()
    assert "tmdb_request_id VARCHAR(32) NOT NULL" in ddl["requests"]
    assert "PRIMARY KEY (media_type, tmdb_request_id)" in ddl["requests"]
    assert "uniq_requests_identity (media_type, tmdb_request_id, tmdb_source_id(191))" in ddl["requests"]
    assert "media_id VARCHAR(32) NOT NULL" in ddl["metadata"]
    assert "PRIMARY KEY (media_id, media_type)" in ddl["metadata"]
    assert "uniq_metadata_media_type (media_id, media_type)" in ddl["metadata"]


def test_mysql_migration_alters_key_and_rebuilds_prefixed_indexes():
    manager = SchemaManager(MagicMock(db_type='mysql'))
    cursor = MagicMock()
    # SHOW INDEX rows: Table, Non_unique, Key_name, Seq_in_index, Column_name, Collation, Cardinality, Sub_part
    cursor.fetchall.return_value = [
        ('requests', 0, 'PRIMARY', 1, 'tmdb_request_id', 'A', 0, None),
        ('requests', 0, 'uniq_requests_identity', 1, 'media_type', 'A', 0, 191),
        ('requests', 0, 'uniq_requests_identity', 2, 'tmdb_request_id', 'A', 0, 191),
        ('requests', 0, 'uniq_requests_identity', 3, 'tmdb_source_id', 'A', 0, 191),
        ('requests', 1, 'idx_requests_user', 1, 'user_id', 'A', 0, None),
    ]

    sql = manager._mysql_composite_key_alter(
        cursor, 'requests', ('media_type', 'tmdb_request_id'),
        {'media_type': 'VARCHAR(16)', 'tmdb_request_id': 'VARCHAR(32)'})

    assert sql == (
        "ALTER TABLE requests MODIFY media_type VARCHAR(16) NOT NULL, MODIFY tmdb_request_id VARCHAR(32) NOT NULL, "
        "DROP INDEX uniq_requests_identity, DROP PRIMARY KEY, ADD PRIMARY KEY (media_type, tmdb_request_id), "
        "ADD UNIQUE KEY uniq_requests_identity (media_type, tmdb_request_id, tmdb_source_id(191))")


def test_seer_discovery_keys_are_typed(db):
    """A movie requested in Seer must not hide the show that has the same TMDb id."""
    _execute(db, ("INSERT INTO requests (tmdb_request_id, media_type, requested_by) VALUES ('1399', 'movie', 'Seer')",))

    keys = db.get_seer_discovered_keys()

    assert keys == {"movie:1399"}
    assert "tv:1399" not in keys
