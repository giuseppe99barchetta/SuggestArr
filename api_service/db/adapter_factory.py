"""
Database adapter factory for creating appropriate database connections.
"""
import os
from typing import Any, Dict

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.exceptions.database_exceptions import DatabaseError
from api_service.db.adapters.base_adapter import DatabaseAdapter
from api_service.db.adapters.sqlite_adapter import SQLiteAdapter
from api_service.db.adapters.postgresql_adapter import PostgreSQLAdapter
from api_service.db.adapters.mysql_adapter import MySQLAdapter


class DatabaseAdapterFactory:
    """Factory class for creating database adapters."""
    
    @staticmethod
    def create_adapter(config: Dict[str, Any] = None) -> DatabaseAdapter:
        """
        Create and return appropriate database adapter based on configuration.
        
        Args:
            config: Database configuration dictionary. If None, loads from environment.
            
        Returns:
            DatabaseAdapter: Configured database adapter instance.
            
        Raises:
            DatabaseError: If unsupported database type is specified.
        """
        logger = LoggerManager.get_logger(DatabaseAdapterFactory.__name__)
        
        if config is None:
            config = DatabaseAdapterFactory._load_config()
        
        db_type = config.get('db_type', 'sqlite').lower()
        logger.info(f"Creating database adapter for type: {db_type}")
        
        if db_type == 'sqlite':
            return SQLiteAdapter(config)
        elif db_type == 'postgres':
            return PostgreSQLAdapter(config)
        elif db_type in ['mysql', 'mariadb']:
            return MySQLAdapter(config)
        else:
            raise DatabaseError(db_type, f"Unsupported database type: {db_type}")
    
    @staticmethod
    def _load_config() -> Dict[str, Any]:
        """Load database configuration from environment variables."""
        env_vars = load_env_vars()
        db_type = env_vars.get('DB_TYPE', 'sqlite').lower()
        
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        default_db_path = os.path.join(base_dir, 'config', 'config_files', 'requests.db')
        
        if db_type == 'sqlite':
            return {
                'db_type': 'sqlite',
                'db_path': env_vars.get('DB_PATH', default_db_path)
            }
        elif db_type == 'postgres':
            return {
                'db_type': 'postgres',
                'host': env_vars.get('DB_HOST', 'localhost'),
                'port': int(env_vars.get('DB_PORT', 5432)),
                'user': env_vars.get('DB_USER'),
                'password': env_vars.get('DB_PASSWORD'),
                'database': env_vars.get('DB_NAME', 'suggestarr')
            }
        elif db_type in ['mysql', 'mariadb']:
            return {
                'db_type': db_type,
                'host': env_vars.get('DB_HOST', 'localhost'),
                'port': int(env_vars.get('DB_PORT', 3306)),
                'user': env_vars.get('DB_USER'),
                'password': env_vars.get('DB_PASSWORD'),
                'database': env_vars.get('DB_NAME', 'suggestarr')
            }
        else:
            raise DatabaseError(db_type, f"Unsupported database type: {db_type}")