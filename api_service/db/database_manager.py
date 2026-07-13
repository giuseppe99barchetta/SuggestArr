import os
import sqlite3
import psycopg2
import mysql.connector
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.exceptions.database_exceptions import DatabaseError

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(BASE_DIR, 'config', 'config_files', 'requests.db')

# Register explicit adapter/converter for datetime <-> SQLite TIMESTAMP to avoid
# the Python 3.12 DeprecationWarning about the default datetime adapter.
sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())
sqlite3.register_converter(
    "TIMESTAMP",
    lambda val: datetime.fromisoformat(val.decode()),
)

from api_service.db.components.ai_search_mixin import AiSearchMixin
from api_service.db.components.auth_mixin import AuthMixin
from api_service.db.components.cleanup_mixin import CleanupMixin
from api_service.db.components.integration_mixin import IntegrationMixin
from api_service.db.components.media_user_mixin import MediaUserMixin
from api_service.db.components.metadata_mixin import MetadataMixin
from api_service.db.components.request_mixin import RequestMixin
from api_service.db.components.request_queue_mixin import RequestQueueMixin
from api_service.db.components.schema_manager import SchemaManager


class DatabaseManager(IntegrationMixin, RequestMixin, MetadataMixin, RequestQueueMixin, AiSearchMixin, CleanupMixin, AuthMixin, MediaUserMixin):
    """Singleton database manager with connection pooling."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize database manager (only once)."""
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.db_path = DB_PATH
        self.env_vars = load_env_vars()
        self.db_type = self.env_vars.get('DB_TYPE', 'sqlite')
        self.logger.debug(f"Initialized DatabaseManager with {self.db_type} direct connections")
        self.initialize_db()
        # Only mark as initialized after a successful initialize_db() call so
        # that a failed first attempt can be retried on the next instantiation.
        self._initialized = True

    def refresh_config(self):
        """Re-read configuration and re-initialize the database.

        Call this after the application config is saved so that any change to
        DB_TYPE, DB_HOST, credentials, etc. is reflected in subsequent
        database connections without requiring a full process restart.
        """
        self.env_vars = load_env_vars(force_reload=True)
        self.db_type = self.env_vars.get('DB_TYPE', 'sqlite')
        self.logger.debug(f"DatabaseManager config refreshed (db_type={self.db_type})")
        self.initialize_db()

    @staticmethod
    def _load_env_vars(*args, **kwargs):
        """Resolve the historical module symbol so existing patches keep working."""
        return load_env_vars(*args, **kwargs)

    @contextmanager
    def get_connection(self):
        """Context manager for getting a database connection."""
        conn = None
        try:
            if self.db_type == 'sqlite':
                conn = sqlite3.connect(
                    self.db_path,
                    timeout=30,
                    check_same_thread=False,
                    detect_types=sqlite3.PARSE_DECLTYPES,
                )
                conn.row_factory = sqlite3.Row
            elif self.db_type == 'postgres':
                conn = psycopg2.connect(
                    host=self.env_vars['DB_HOST'],
                    port=self.env_vars['DB_PORT'],
                    user=self.env_vars['DB_USER'],
                    password=self.env_vars['DB_PASSWORD'],
                    dbname=self.env_vars['DB_NAME'],
                    connect_timeout=30
                )
                conn.autocommit = False
            elif self.db_type in ['mysql', 'mariadb']:
                conn = mysql.connector.connect(
                    host=self.env_vars['DB_HOST'],
                    port=self.env_vars['DB_PORT'],
                    user=self.env_vars['DB_USER'],
                    password=self.env_vars['DB_PASSWORD'],
                    database=self.env_vars['DB_NAME'],
                    connection_timeout=30,
                    autocommit=False
                )
            else:
                raise DatabaseError(f"Unsupported database type: {self.db_type}")
            
            yield conn
        except Exception as e:
            self.logger.error(f"Database operation failed: {e}")
            # For connection errors, don't rollback as connection will be discarded
            if self._is_connection_error(e):
                raise
            # For other errors, attempt rollback
            try:
                if conn and self.db_type != 'sqlite':
                    conn.rollback()
            except Exception as rollback_error:
                self.logger.warning(f"Failed to rollback transaction: {rollback_error}")
            raise
        finally:
            if conn:
                try:
                    if self.db_type == 'sqlite':
                        conn.close()
                    else:
                        conn.close()
                except Exception as e:
                    self.logger.warning(f"Error closing connection: {e}")
    
    def _is_connection_error(self, error: Exception) -> bool:
        """Check if an error is a connection-related error."""
        if isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError)):
            return True
        if isinstance(error, mysql.connector.Error):
            return True
        if isinstance(error, sqlite3.Error):
            error_str = str(error).lower()
            return any(keyword in error_str for keyword in ['connection', 'disk', 'timeout'])
        return False
    
    def initialize_db(self):
        """Initialize and migrate the configured database schema."""
        return SchemaManager(self).initialize_db()

    def ensure_connection(self):
        """Legacy method - now handled by connection pool."""
        # This method is kept for backward compatibility
        # Connection pooling handles connection management automatically
        pass
    
    def test_connection(self, db_config: Dict[str, Any]) -> Dict[str, str]:
        """Test database connection based on provided db_config."""
        
        try:
            db_type = db_config.get('DB_TYPE', 'sqlite')

            if db_type == 'postgres':
                conn = psycopg2.connect(
                    host=db_config['DB_HOST'],
                    port=db_config['DB_PORT'],
                    user=db_config['DB_USER'],
                    password=db_config['DB_PASSWORD'],
                    dbname=db_config['DB_NAME'],
                    connect_timeout=5
                )
                conn.close()
            elif db_type in ['mysql', 'mariadb']:
                conn = mysql.connector.connect(
                    host=db_config['DB_HOST'],
                    port=db_config['DB_PORT'],
                    user=db_config['DB_USER'],
                    password=db_config['DB_PASSWORD'],
                    database=db_config['DB_NAME'],
                    connection_timeout=5
                )
                conn.close()
            elif db_type == 'sqlite':
                # Test SQLite by opening and closing connection
                test_path = db_config.get('DB_PATH', self.db_path)
                conn = sqlite3.connect(test_path, timeout=5, detect_types=sqlite3.PARSE_DECLTYPES)
                conn.close()

            return {'status': 'success', 'message': 'Database connection successful!'}
        except Exception as e:
            self.logger.error(f"Error testing database connection: {str(e)}")
            return {'status': 'error', 'message': f"Error testing database connection: {str(e)}"}
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        return {
            'status': 'direct_connection',
            'db_type': self.db_type,
            'message': 'No connection pooling - using direct connections for better performance'
        }
