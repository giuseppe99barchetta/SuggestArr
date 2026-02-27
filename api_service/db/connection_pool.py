"""
Database connection pool manager for SuggestArr.
Supports SQLite, PostgreSQL, and MySQL/MariaDB with proper connection pooling.
"""

import threading
import time
import sqlite3
import psycopg2
import mysql.connector
from contextlib import contextmanager
from typing import Dict, List, Optional, Any, Union
from queue import Queue, Empty, Full
from dataclasses import dataclass
from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.exceptions.database_exceptions import DatabaseError


@dataclass
class PoolConfig:
    """Configuration for database connection pools."""
    min_connections: int = 2
    max_connections: int = 10
    max_idle_time: int = 300  # 5 minutes
    max_lifetime: int = 3600  # 1 hour
    connection_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class PooledConnection:
    """Wrapper for pooled database connections."""
    connection: Any
    created_at: float
    last_used: float
    in_use: bool = False
    usage_count: int = 0


class DatabaseConnectionPool:
    """Thread-safe database connection pool."""
    
    def __init__(self, db_type: str, config: Dict[str, Any], pool_config: PoolConfig):
        self.db_type = db_type
        self.config = config
        self.pool_config = pool_config
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        
        # Pool management
        self._pool: Queue[PooledConnection] = Queue(maxsize=pool_config.max_connections)
        self._all_connections: List[PooledConnection] = []
        self._lock = threading.RLock()
        self._initialized = False
        self._closed = False
        
        # Statistics
        self._stats = {
            'created': 0,
            'reused': 0,
            'expired': 0,
            'errors': 0,
            'active_connections': 0,
            'pool_hits': 0,
            'pool_misses': 0
        }

        self.logger.debug(f"Initialized connection pool for {db_type} with config: {pool_config}")

    def _create_connection(self) -> Any:
        """Create a new database connection based on type."""
        try:
            if self.db_type == 'postgres':
                conn = psycopg2.connect(
                    host=self.config['DB_HOST'],
                    port=self.config['DB_PORT'],
                    user=self.config['DB_USER'],
                    password=self.config['DB_PASSWORD'],
                    dbname=self.config['DB_NAME'],
                    connect_timeout=self.pool_config.connection_timeout
                )
                # Configure PostgreSQL connection
                conn.autocommit = False
                
            elif self.db_type in ['mysql', 'mariadb']:
                conn = mysql.connector.connect(
                    host=self.config['DB_HOST'],
                    port=self.config['DB_PORT'],
                    user=self.config['DB_USER'],
                    password=self.config['DB_PASSWORD'],
                    database=self.config['DB_NAME'],
                    connection_timeout=self.pool_config.connection_timeout,
                    autocommit=False,
                    pool_name=self.config.get('DB_NAME', 'suggestarr_pool'),
                    pool_size=self.pool_config.min_connections
                )
                
            elif self.db_type == 'sqlite':
                # SQLite doesn't support true connection pooling the same way
                conn = sqlite3.connect(
                    self.config['DB_PATH'],
                    timeout=self.pool_config.connection_timeout,
                    check_same_thread=False,
                    detect_types=sqlite3.PARSE_DECLTYPES,
                )
                conn.row_factory = sqlite3.Row
                
            else:
                raise DatabaseError(f"Unsupported database type: {self.db_type}")
            
            self._stats['created'] += 1
            self.logger.debug(f"Created new {self.db_type} connection")
            return conn
            
        except Exception as e:
            self._stats['errors'] += 1
            raise DatabaseError(
                error=f"Failed to create {self.db_type} connection: {str(e)}",
                db_type=self.db_type
            )
    
    def _is_connection_valid(self, conn: PooledConnection) -> bool:
        """Check if a connection is still valid."""
        try:
            if conn.connection is None:
                return False
                
            # Check age
            now = time.time()
            if now - conn.created_at > self.pool_config.max_lifetime:
                self.logger.debug("Connection expired due to max lifetime")
                return False
            
            if now - conn.last_used > self.pool_config.max_idle_time:
                self.logger.debug("Connection expired due to idle time")
                return False
            
            # Test connection with a simple query
            if self.db_type == 'postgres':
                cursor = conn.connection.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                
            elif self.db_type in ['mysql', 'mariadb']:
                if not conn.connection.is_connected():
                    return False
                conn.connection.ping(reconnect=False)
                
            elif self.db_type == 'sqlite':
                cursor = conn.connection.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                
            return True
            
        except Exception as e:
            self.logger.debug(f"Connection validation failed: {e}")
            return False
    
    def _close_connection(self, conn: PooledConnection) -> None:
        """Close a database connection."""
        try:
            if conn.connection:
                conn.connection.close()
                self.logger.debug("Closed database connection")
        except Exception as e:
            self.logger.warning(f"Error closing connection: {e}")
        finally:
            # Remove from all_connections if present
            if conn in self._all_connections:
                self._all_connections.remove(conn)
            # Decrement active connections counter
            with self._lock:
                if self._stats['active_connections'] > 0:
                    self._stats['active_connections'] -= 1
    
    def _initialize_pool(self) -> None:
        """Initialize the pool with minimum connections."""
        if self._initialized:
            return
            
        with self._lock:
            if self._initialized:
                return
                
            try:
                for i in range(self.pool_config.min_connections):
                    conn = None
                    try:
                        conn = PooledConnection(
                            connection=self._create_connection(),
                            created_at=time.time(),
                            last_used=time.time()
                        )
                        self._pool.put(conn, block=False)
                        self._all_connections.append(conn)
                        self._stats['active_connections'] += 1
                    except Full:
                        self.logger.warning("Pool full during initialization - closing connection")
                        if conn:
                            conn.connection.close()
                        break
                
                self._initialized = True
                self.logger.debug(f"Initialized pool with {min(len(self._all_connections), self.pool_config.min_connections)} connections")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize pool: {e}")
                # Clean up any partially created connections
                for conn in self._all_connections:
                    try:
                        conn.connection.close()
                    except:
                        pass
                self._all_connections.clear()
                self._stats['active_connections'] = 0
                raise
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        if self._closed:
            raise DatabaseError("Connection pool has been closed", db_type=self.db_type)
        
        # Ensure pool is initialized
        if not self._initialized:
            self._initialize_pool()
        
        conn = None
        retry_count = 0
        
        while retry_count < self.pool_config.retry_attempts:
            try:
                # Try to get connection from pool
                try:
                    conn = self._pool.get(timeout=self.pool_config.connection_timeout)
                    self._stats['pool_hits'] += 1
                except Empty:
                    # Pool empty, try to create new connection (with lock to prevent race conditions)
                    with self._lock:
                        if self._stats['active_connections'] < self.pool_config.max_connections:
                            conn = PooledConnection(
                                connection=self._create_connection(),
                                created_at=time.time(),
                                last_used=time.time()
                            )
                            self._all_connections.append(conn)
                            self._stats['active_connections'] += 1
                            self._stats['pool_misses'] += 1
                        else:
                            # Max connections reached, wait for a connection to become available
                            pass
                    
                    # If we didn't create a new connection, wait for one to become available
                    if conn is None:
                        conn = self._pool.get(timeout=self.pool_config.connection_timeout)
                        self._stats['pool_hits'] += 1
                
                # Validate connection
                if not self._is_connection_valid(conn):
                    self._close_connection(conn)
                    self._stats['expired'] += 1
                    retry_count += 1
                    continue
                
                # Mark as in use
                conn.in_use = True
                conn.last_used = time.time()
                conn.usage_count += 1
                
                try:
                    yield conn.connection
                    self._stats['reused'] += 1
                    break
                finally:
                    # Return connection to pool
                    if self._is_connection_valid(conn):
                        conn.in_use = False
                        conn.last_used = time.time()
                        try:
                            self._pool.put(conn, block=False)
                        except Full:
                            # Pool full, close connection properly
                            self._close_connection(conn)
                    else:
                        self._close_connection(conn)
                        self._stats['expired'] += 1
                        
            except Empty:
                retry_count += 1
                if retry_count >= self.pool_config.retry_attempts:
                    raise DatabaseError(
                        error=f"Failed to get connection after {retry_count} attempts",
                        db_type=self.db_type
                    )
                time.sleep(self.pool_config.retry_delay)
                
            except Exception as e:
                if conn:
                    self._close_connection(conn)
                retry_count += 1
                if retry_count >= self.pool_config.retry_attempts:
                    raise DatabaseError(
                        error=f"Connection error after {retry_count} attempts: {str(e)}",
                        db_type=self.db_type
                    )
                time.sleep(self.pool_config.retry_delay)
    
    def close_all(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            if self._closed:
                return
                
            self._closed = True
            
            # Close all connections from the list
            connections_to_close = list(self._all_connections)  # Create a copy to avoid modification during iteration
            for conn in connections_to_close:
                self._close_connection(conn)
            
            # Clear pools
            self._all_connections.clear()
            
            # Empty the queue
            while not self._pool.empty():
                try:
                    self._pool.get_nowait()
                except Empty:
                    break
            
            self.logger.debug("Closed all connections in pool")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            return {
                **self._stats,
                'pool_size': self._pool.qsize(),
                'total_connections': len(self._all_connections),
                'initialized': self._initialized,
                'closed': self._closed
            }


class PoolManager:
    """Global manager for database connection pools."""
    
    _instance: Optional['PoolManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self._pools: Dict[str, DatabaseConnectionPool] = {}
        self._lock = threading.RLock()
        self._initialized = True
        
        # Register cleanup
        import atexit
        atexit.register(self.close_all_pools)
    
    def get_pool(self, db_type: str, config: Optional[Dict[str, Any]] = None, 
                 pool_config: Optional[PoolConfig] = None) -> DatabaseConnectionPool:
        """Get or create a connection pool for the specified database type."""
        if config is None:
            config = load_env_vars()
        
        # Ensure config is not None
        if config is None:
            config = {}
        
        if pool_config is None:
            # Default pool configuration
            pool_config = PoolConfig(
                min_connections=int(config.get('DB_MIN_CONNECTIONS', '2')),
                max_connections=int(config.get('DB_MAX_CONNECTIONS', '10')),
                max_idle_time=int(config.get('DB_MAX_IDLE_TIME', '300')),
                max_lifetime=int(config.get('DB_MAX_LIFETIME', '3600'))
            )
        
        pool_key = f"{db_type}_{config.get('DB_HOST', 'local')}_{config.get('DB_NAME', 'default')}"
        
        with self._lock:
            if pool_key not in self._pools:
                # Add SQLite path for local connections
                if db_type == 'sqlite':
                    import os
                    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                    config['DB_PATH'] = os.path.join(BASE_DIR, 'config', 'config_files', 'requests.db')
                
                self._pools[pool_key] = DatabaseConnectionPool(db_type, config, pool_config)
                self.logger.debug(f"Created new pool for {pool_key}")
            
            return self._pools[pool_key]
    
    def close_all_pools(self) -> None:
        """Close all connection pools."""
        with self._lock:
            for pool_key, pool in self._pools.items():
                try:
                    pool.close_all()
                except Exception as e:
                    self.logger.error(f"Error closing pool {pool_key}: {e}")
            
            self._pools.clear()
            self.logger.debug("Closed all connection pools")
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all pools."""
        with self._lock:
            return {key: pool.get_stats() for key, pool in self._pools.items()}


# Global pool manager instance
pool_manager = PoolManager()