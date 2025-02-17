
class DatabaseError(Exception):
    """Base class for all database-related exceptions."""
    def __init__(self, db_type, error):
        self.db_type = db_type
        self.error = error
        super().__init__(self._format_error())

    def _format_error(self):
        if self.db_type == 'sqlite':
            return f"SQLite error: {str(self.error)}"
        elif self.db_type == 'postgres':
            return f"PostgreSQL error: {str(self.error)}"
        elif self.db_type in ['mysql', 'mariadb']:
            return f"MySQL error: {str(self.error)}"
        else:
            return f"Unknown DB error: {str(self.error)}"