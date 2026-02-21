"""
SQLite database adapter implementation.
"""
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from api_service.config.logger_manager import LoggerManager
from api_service.db.adapters.base_adapter import DatabaseAdapter


class SQLiteAdapter(DatabaseAdapter):
    """SQLite implementation of DatabaseAdapter."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize SQLite adapter with database path."""
        super().__init__(config)
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.db_path = config.get('db_path', 'requests.db')
        self.connection = None
    
    def connect(self) -> None:
        """Establish SQLite connection."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Enable dict-like access
            self.logger.info(f"Connected to SQLite database at {self.db_path}")
        except Exception as e:
            self.logger.error(f"Failed to connect to SQLite: {e}")
            raise
    
    def disconnect(self) -> None:
        """Close SQLite connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.logger.info("Disconnected from SQLite database")

    def initialize_db(self) -> None:
        """Initialize SQLite database schema."""
        if not self.connection:
            self.connect()
        
        # Create the users table first (required for the foreign key)
        create_users_query = '''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            user_name TEXT
        )
        '''
        
        # Create the matching requests table
        create_requests_query = '''
        CREATE TABLE IF NOT EXISTS requests (
            tmdb_request_id TEXT NOT NULL PRIMARY KEY,
            media_type TEXT NOT NULL,
            tmdb_source_id TEXT,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            requested_by TEXT,
            user_id TEXT,
            UNIQUE(media_type, tmdb_request_id, tmdb_source_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        '''
        
        # Create the metadata table 
        create_metadata_query = '''
        CREATE TABLE IF NOT EXISTS metadata (
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
        '''
        
        try:
            # Enable foreign keys before creating tables
            self.execute_query("PRAGMA foreign_keys = ON")
            
            # Execute creations in the correct order
            self.execute_query(create_users_query)
            self.execute_query(create_requests_query)
            self.execute_query(create_metadata_query)
            self.logger.info("SQLite database initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize SQLite database: {e}")
            raise
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Execute a query and return results."""
        if not self.connection:
            self.connect()
        
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # For SELECT queries, return results
            if query.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            else:
                self.connection.commit()
                return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            self.connection.rollback()
            raise
    
    def execute_many(self, query: str, params_list: List[Tuple]) -> None:
        """Execute a query multiple times with different parameters."""
        if not self.connection:
            self.connect()
        
        try:
            cursor = self.connection.cursor()
            cursor.executemany(query, params_list)
            self.connection.commit()
        except Exception as e:
            self.logger.error(f"Bulk query execution failed: {e}")
            self.connection.rollback()
            raise
    
    def execute_script(self, script: str) -> None:
        """Execute a SQL script."""
        if not self.connection:
            self.connect()
        
        try:
            self.connection.executescript(script)
            self.connection.commit()
        except Exception as e:
            self.logger.error(f"Script execution failed: {e}")
            self.connection.rollback()
            raise
    
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict]:
        """Execute query and fetch one result."""
        if not self.connection:
            self.connect()
        
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            self.logger.error(f"Fetch one failed: {e}")
            raise
    
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict]:
        """Execute query and fetch all results."""
        if not self.connection:
            self.connect()
        
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Fetch all failed: {e}")
            raise
    
    def get_last_insert_id(self) -> int:
        """Get the ID of the last inserted row."""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        cursor.execute("SELECT last_insert_rowid()")
        return cursor.fetchone()[0]
