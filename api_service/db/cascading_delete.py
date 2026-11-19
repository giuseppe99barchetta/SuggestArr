"""Parent-row deletes that apply the schema's ON DELETE CASCADE rules on every engine."""


def delete_cascading(db, query: str, params: tuple) -> int:
    """
    Run a parent-row DELETE so ON DELETE CASCADE applies on SQLite as well.

    SQLite enforces foreign keys only when ``PRAGMA foreign_keys`` is on for the
    connection, and the pragma is a no-op inside an open transaction, so it is the
    first statement here. It stays off for every other connection on purpose: turning
    it on globally could start rejecting inserts that work today. Parent and children
    go in one statement, so a failure (for example a child table without an ON DELETE
    rule, which no schema version has created) deletes nothing and is raised.

    Args:
        db: Object with ``get_connection()`` and ``db_type`` (a DatabaseManager).
        query: DELETE statement with engine-specific placeholders.
        params: Bound parameters for ``query``.

    Returns:
        int: Number of parent rows deleted.
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()
        if db.db_type == 'sqlite':
            cursor.execute("PRAGMA foreign_keys = ON")
        try:
            cursor.execute(query, params)
            deleted = cursor.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return deleted
