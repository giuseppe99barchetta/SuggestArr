import sqlite3

from api_service.db.components.request_queue_mixin import RequestQueueMixin


class Queue(RequestQueueMixin):
    db_type = "sqlite"

    def __init__(self, connection):
        self.connection = connection

    def get_connection(self):
        return self.connection


def test_owner_can_only_approve_own_suggestions():
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        CREATE TABLE pending_requests (id INTEGER PRIMARY KEY, tmdb_id TEXT, media_type TEXT,
            status TEXT, owner_id INTEGER, decided_by INTEGER, decided_at TIMESTAMP);
        CREATE TABLE suggestion_blacklist (tmdb_id TEXT, media_type TEXT, created_by INTEGER,
            PRIMARY KEY (tmdb_id, media_type));
        INSERT INTO pending_requests VALUES (1,'10','movie','awaiting_approval',7,NULL,NULL);
        INSERT INTO pending_requests VALUES (2,'20','movie','awaiting_approval',8,NULL,NULL);
    """)
    assert Queue(connection).decide_suggestions([1, 2], 7, 7, True) == 1
    assert connection.execute("SELECT status FROM pending_requests WHERE id=1").fetchone()[0] == "queued"
    assert connection.execute("SELECT status FROM pending_requests WHERE id=2").fetchone()[0] == "awaiting_approval"
