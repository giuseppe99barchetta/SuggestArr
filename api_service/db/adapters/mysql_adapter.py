"""
MySQL/MariaDB database adapter implementation.
"""
import mysql.connector
from typing import Any, Dict, List, Optional, Tuple

from api_service.config.logger_manager import LoggerManager
from api_service.db.adapters.base_adapter import DatabaseAdapter


class MySQLAdapter(DatabaseAdapter):
    """MySQL/MariaDB implementation of DatabaseAdapter."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize MySQL adapter with connection parameters."""
        super().__init__(config)
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.connection = None
    
    def connect(self) -> None:
        """Establish MySQL connection."""
        try:
            self.connection = mysql.connector.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database']
            )
            self.logger.info(f"Connected to MySQL database at {self.config['host']}:{self.config['port']}")
        except Exception as e:
            self.logger.error(f"Failed to connect to MySQL: {e}")
            raise
    
    def disconnect(self) -> None:
        """Close MySQL connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.logger.info("Disconnected from MySQL database")
    
    def initialize_db(self) -> None:
        """Initialize MySQL database schema."""
        if not self.connection:
            self.connect()
        
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            user_id VARCHAR(255) NOT NULL,
            media_type VARCHAR(50) NOT NULL,
            media_title TEXT NOT NULL,
            media_id VARCHAR(255),
            request_status VARCHAR(20) DEFAULT 'pending',
            INDEX idx_user_id (user_id),
            INDEX idx_media_type (media_type),
            INDEX idx_status (request_status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        '''
        
        self.execute_query(create_table_query)
        self.logger.info("MySQL database initialized successfully")
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Execute a query and return results."""
        if not self.connection:
            self.connect()
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # For SELECT queries, return results
            if query.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            else:
                self.connection.commit()
                return cursor.lastrowid if hasattr(cursor, 'lastrowid') else None
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
            cursor = self.connection.cursor()
            # Split script into individual statements
            statements = [stmt.strip() for stmt in script.split(';') if stmt.strip()]
            for statement in statements:
                if statement:
                    cursor.execute(statement)
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
            cursor = self.connection.cursor(dictionary=True)
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            row = cursor.fetchone()
            return row
        except Exception as e:
            self.logger.error(f"Fetch one failed: {e}")
            raise
    
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict]:
        """Execute query and fetch all results."""
        if not self.connection:
            self.connect()
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            self.logger.error(f"Fetch all failed: {e}")
            raise
    
    def get_last_insert_id(self) -> int:
        """Get ID of the last inserted row."""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        cursor.execute("SELECT LAST_INSERT_ID()")
        return cursor.fetchone()[0]