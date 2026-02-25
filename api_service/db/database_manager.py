import json
import os
import sqlite3
import psycopg2
import mysql.connector
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.exceptions.database_exceptions import DatabaseError

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(BASE_DIR, 'config', 'config_files', 'requests.db')

class DatabaseManager:
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
        self.env_vars = load_env_vars()
        self.db_type = self.env_vars.get('DB_TYPE', 'sqlite')
        self.logger.debug(f"DatabaseManager config refreshed (db_type={self.db_type})")
        self.initialize_db()

    @contextmanager
    def get_connection(self):
        """Context manager for getting a database connection."""
        conn = None
        try:
            if self.db_type == 'sqlite':
                conn = sqlite3.connect(
                    self.db_path,
                    timeout=30,
                    check_same_thread=False
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
        """Initialize the database and create tables if they don't exist."""
        self.logger.debug(f"Initializing {self.db_type} database with connection pooling")
        
        queries = {
            'users': """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    user_name TEXT
                )
            """,
            'requests': """
                CREATE TABLE IF NOT EXISTS requests (
                    tmdb_request_id TEXT NOT NULL PRIMARY KEY,
                    media_type TEXT NOT NULL,
                    tmdb_source_id TEXT,
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    requested_by TEXT,
                    user_id TEXT,
                    rationale TEXT,
                    UNIQUE(media_type, tmdb_request_id, tmdb_source_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """,
            'metadata': """
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
            """,
            'discover_jobs': """
                CREATE TABLE IF NOT EXISTS discover_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    job_type TEXT NOT NULL DEFAULT 'discover',
                    enabled INTEGER DEFAULT 1,
                    media_type TEXT NOT NULL,
                    filters TEXT NOT NULL,
                    schedule_type TEXT NOT NULL,
                    schedule_value TEXT NOT NULL,
                    max_results INTEGER DEFAULT 20,
                    user_ids TEXT,
                    is_system INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'job_execution_history': """
                CREATE TABLE IF NOT EXISTS job_execution_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    finished_at TIMESTAMP,
                    status TEXT NOT NULL,
                    results_count INTEGER DEFAULT 0,
                    requested_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    FOREIGN KEY (job_id) REFERENCES discover_jobs(id) ON DELETE CASCADE
                )
            """,
            'pending_requests': """
                CREATE TABLE IF NOT EXISTS pending_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tmdb_id TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    user_id TEXT,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    retry_count INTEGER DEFAULT 0,
                    last_attempt_at TIMESTAMP,
                    next_attempt_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tmdb_id, media_type)
                )
            """
        }
        
        # Create tables
        for table_name, query in queries.items():
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Database-specific modifications
                    if self.db_type == 'mysql':
                        # Order matters: do specific replacements first
                        query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "INT AUTO_INCREMENT PRIMARY KEY")
                        query = query.replace("INTEGER", "INT")
                        query = query.replace("TEXT", "VARCHAR(512)")
                        query = query.replace("REAL", "DOUBLE")
                        # Add ENGINE=InnoDB for foreign key support
                        if not query.strip().endswith("ENGINE=InnoDB"):
                            query = query.rstrip().rstrip(")").rstrip() + ") ENGINE=InnoDB"
                    elif self.db_type == 'postgres':
                        query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
                        query = query.replace("AUTOINCREMENT", "")

                    self.logger.info(f"Creating table '{table_name}'...")
                    cursor.execute(query)
                    
                    if self.db_type == 'sqlite':
                        # Enable foreign keys for SQLite
                        cursor.execute("PRAGMA foreign_keys = ON")
                    
                    conn.commit()
                    self.logger.debug(f"Table '{table_name}' created or verified successfully")
                    
            except Exception as e:
                self.logger.error(f"Failed to create table '{table_name}': {e}")
                raise DatabaseError(
                    error=f"Table creation failed: {str(e)}",
                    db_type=self.db_type
                )
        
        # Add missing columns
        self.add_missing_columns()

        # Create submission lock table (separate to control column types per DB engine)
        self._create_submission_locks_table()

    def _create_submission_locks_table(self):
        """Create the submission_locks table for cross-process submission deduplication."""
        if self.db_type in ['mysql', 'mariadb']:
            query = """
                CREATE TABLE IF NOT EXISTS submission_locks (
                    tmdb_id VARCHAR(64) NOT NULL,
                    media_type VARCHAR(16) NOT NULL,
                    locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tmdb_id, media_type)
                ) ENGINE=InnoDB
            """
        else:
            query = """
                CREATE TABLE IF NOT EXISTS submission_locks (
                    tmdb_id TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tmdb_id, media_type)
                )
            """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                conn.commit()
                self.logger.debug("Table 'submission_locks' created or verified successfully")
        except Exception as e:
            self.logger.error(f"Failed to create table 'submission_locks': {e}")
            raise DatabaseError(
                error=f"Table creation failed: {str(e)}",
                db_type=self.db_type
            )
    
    def add_missing_columns(self):
        """Check and add missing columns to the requests table."""
        self.logger.debug("Checking for missing columns in requests table...")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Get existing columns
                if self.db_type == 'sqlite':
                    query = "PRAGMA table_info(requests);"
                    cursor.execute(query)
                    existing_columns = {row[1] for row in cursor.fetchall()}
                elif self.db_type == 'postgres':
                    query = """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = 'requests';
                    """
                    cursor.execute(query)
                    existing_columns = {row[0] for row in cursor.fetchall()}
                elif self.db_type in ['mysql', 'mariadb']:
                    query = "SHOW COLUMNS FROM requests;"
                    cursor.execute(query)
                    existing_columns = {row[0] for row in cursor.fetchall()}
                else:
                    self.logger.warning(f"Unsupported DB type for column check: {self.db_type}")
                    return

                # Add missing user_id column
                if 'user_id' not in existing_columns:
                    self.logger.debug("Adding column user_id...")
                    cursor.execute("ALTER TABLE requests ADD COLUMN user_id TEXT;")
                    conn.commit()

                # Add missing is_anime column
                if 'is_anime' not in existing_columns:
                    self.logger.debug("Adding column is_anime...")
                    if self.db_type in ['mysql', 'mariadb']:
                        cursor.execute("ALTER TABLE requests ADD COLUMN is_anime TINYINT(1) DEFAULT 0;")
                    else:
                        cursor.execute("ALTER TABLE requests ADD COLUMN is_anime BOOLEAN DEFAULT 0;")
                    conn.commit()

                    
                # Add missing rationale column
                if 'rationale' not in existing_columns:
                    self.logger.debug("Adding column rationale...")
                    cursor.execute("ALTER TABLE requests ADD COLUMN rationale TEXT;")
                    conn.commit()
                    
            except Exception as e:
                self.logger.error(f"Failed to add missing columns to requests: {e}")
                raise DatabaseError(
                    error=f"Column addition failed: {str(e)}",
                    db_type=self.db_type
                )

        # Check and add missing columns to discover_jobs table
        self._migrate_discover_jobs_table()

    def _migrate_discover_jobs_table(self):
        """Add missing columns to discover_jobs table for job type support."""
        self.logger.debug("Checking for missing columns in discover_jobs table...")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            try:
                # Get existing columns
                if self.db_type == 'sqlite':
                    query = "PRAGMA table_info(discover_jobs);"
                    cursor.execute(query)
                    existing_columns = {row[1] for row in cursor.fetchall()}
                elif self.db_type == 'postgres':
                    query = """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = 'discover_jobs';
                    """
                    cursor.execute(query)
                    existing_columns = {row[0] for row in cursor.fetchall()}
                elif self.db_type in ['mysql', 'mariadb']:
                    query = "SHOW COLUMNS FROM discover_jobs;"
                    cursor.execute(query)
                    existing_columns = {row[0] for row in cursor.fetchall()}
                else:
                    self.logger.warning(f"Unsupported DB type for column check: {self.db_type}")
                    return

                # Add missing job_type column
                if 'job_type' not in existing_columns:
                    self.logger.info("Adding column job_type to discover_jobs...")
                    if self.db_type in ['mysql', 'mariadb']:
                        cursor.execute("ALTER TABLE discover_jobs ADD COLUMN job_type VARCHAR(50) NOT NULL DEFAULT 'discover';")
                    else:
                        cursor.execute("ALTER TABLE discover_jobs ADD COLUMN job_type TEXT NOT NULL DEFAULT 'discover';")
                    conn.commit()

                # Add missing user_ids column (for recommendation jobs)
                if 'user_ids' not in existing_columns:
                    self.logger.info("Adding column user_ids to discover_jobs...")
                    if self.db_type in ['mysql', 'mariadb']:
                        cursor.execute("ALTER TABLE discover_jobs ADD COLUMN user_ids VARCHAR(512);")
                    else:
                        cursor.execute("ALTER TABLE discover_jobs ADD COLUMN user_ids TEXT;")
                    conn.commit()

                # Add missing is_system column (for system-managed jobs from config)
                if 'is_system' not in existing_columns:
                    self.logger.info("Adding column is_system to discover_jobs...")
                    if self.db_type in ['mysql', 'mariadb']:
                        cursor.execute("ALTER TABLE discover_jobs ADD COLUMN is_system TINYINT(1) DEFAULT 0;")
                    else:
                        cursor.execute("ALTER TABLE discover_jobs ADD COLUMN is_system INTEGER DEFAULT 0;")
                    conn.commit()

            except Exception as e:
                self.logger.error(f"Failed to migrate discover_jobs table: {e}")
                # Don't raise - table might not exist yet

    def ensure_connection(self):
        """Legacy method - now handled by connection pool."""
        # This method is kept for backward compatibility
        # Connection pooling handles connection management automatically
        pass
    
    def save_request(self, media_type: str, media_id: str, source: str, user_id: Optional[str] = None, is_anime: bool = False, rationale: Optional[str] = None) -> None:
        """Save a new media request to the database, ignoring duplicates."""
        self.logger.debug(f"Saving request: {media_type} {media_id} from {source} (anime={is_anime})")

        query = """

            INSERT OR IGNORE INTO requests (media_type, tmdb_request_id, tmdb_source_id, requested_by, user_id, is_anime, rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (media_type, str(media_id), source, 'SuggestArr', user_id, 1 if is_anime else 0, rationale)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Database-specific query modifications
            if self.db_type == 'mysql':
                query = query.replace("INSERT OR IGNORE", "INSERT IGNORE")
                query = query.replace("?", "%s")
            elif self.db_type == 'postgres':
                query = query.replace("INSERT OR IGNORE", "INSERT")
                query = query.rstrip() + " ON CONFLICT DO NOTHING"
                query = query.replace("?", "%s")
            
            cursor.execute(query, params)
            conn.commit()
    
    def save_user(self, user: Dict[str, Any]) -> None:
        """Save a new user to the database, ignoring duplicates."""
        self.logger.debug(f"Saving user: {user['id']} {user['name']}")
        
        query = """
            INSERT OR IGNORE INTO users (user_id, user_name)
            VALUES (?, ?)
        """
        params = (user['id'], user['name'])
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Database-specific query modifications
            if self.db_type == 'mysql':
                query = query.replace("INSERT OR IGNORE", "INSERT IGNORE")
                query = query.replace("?", "%s")
            elif self.db_type == 'postgres':
                query = query.replace("INSERT OR IGNORE", "INSERT")
                query = query.rstrip() + " ON CONFLICT DO NOTHING"
                query = query.replace("?", "%s")
            
            cursor.execute(query, params)
            conn.commit()
    
    def check_request_exists(self, media_type: str, media_id: str) -> bool:
        """Check if a media request already exists in the database."""
        self.logger.debug(f"Checking if request exists: {media_type} {media_id}")
        
        query = """
            SELECT 1 FROM requests WHERE tmdb_request_id = ? AND media_type = ?
        """
        params = (str(media_id), media_type)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if self.db_type in ['mysql', 'postgres']:
                query = query.replace("?", "%s")
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result is not None
    
    def try_acquire_submission_lock(self, tmdb_id: str, media_type: str, ttl_seconds: int = 60) -> bool:
        """Attempt to acquire a per-media submission lock to prevent cross-process duplicates.

        Uses DB-native INSERT-ignore semantics (atomic check+acquire). Cleans stale locks
        (from crashes) before attempting acquisition. Fails open on DB errors so a broken
        lock table never blocks all submissions.

        :param tmdb_id: TMDB ID as string.
        :param media_type: 'movie' or 'tv'.
        :param ttl_seconds: Locks older than this are considered stale and deleted first.
        :return: True if lock acquired (caller should proceed), False if already held.
        """
        # Build stale-lock cleanup query (DB-specific timestamp arithmetic)
        if self.db_type == 'sqlite':
            cleanup_query = (
                "DELETE FROM submission_locks WHERE tmdb_id = ? AND media_type = ? "
                "AND locked_at < datetime('now', '-' || ? || ' seconds')"
            )
            cleanup_params = (str(tmdb_id), media_type, str(ttl_seconds))
        elif self.db_type == 'postgres':
            cleanup_query = (
                "DELETE FROM submission_locks WHERE tmdb_id = %s AND media_type = %s "
                "AND locked_at < NOW() - (INTERVAL '1 second' * %s)"
            )
            cleanup_params = (str(tmdb_id), media_type, ttl_seconds)
        else:  # mysql / mariadb
            cleanup_query = (
                "DELETE FROM submission_locks WHERE tmdb_id = %s AND media_type = %s "
                "AND locked_at < DATE_SUB(NOW(), INTERVAL %s SECOND)"
            )
            cleanup_params = (str(tmdb_id), media_type, ttl_seconds)

        # Build atomic lock-acquisition INSERT (INSERT OR IGNORE / INSERT IGNORE / ON CONFLICT DO NOTHING)
        insert_query = "INSERT OR IGNORE INTO submission_locks (tmdb_id, media_type) VALUES (?, ?)"
        insert_params = (str(tmdb_id), media_type)

        if self.db_type in ['mysql', 'mariadb']:
            insert_query = insert_query.replace("INSERT OR IGNORE", "INSERT IGNORE")
            insert_query = insert_query.replace("?", "%s")
        elif self.db_type == 'postgres':
            insert_query = insert_query.replace("INSERT OR IGNORE", "INSERT")
            insert_query = insert_query.rstrip() + " ON CONFLICT DO NOTHING"
            insert_query = insert_query.replace("?", "%s")

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(cleanup_query, cleanup_params)
                cursor.execute(insert_query, insert_params)
                acquired = cursor.rowcount > 0  # Read BEFORE commit
                conn.commit()
                self.logger.debug(
                    "Submission lock %s: tmdb_id=%s, media_type=%s",
                    "acquired" if acquired else "already held",
                    tmdb_id, media_type
                )
                return acquired
        except Exception as e:
            self.logger.error(
                "Error acquiring submission lock for tmdb_id=%s, media_type=%s: %s",
                tmdb_id, media_type, e
            )
            return True  # Fail open: don't block submissions if lock table has issues

    def release_submission_lock(self, tmdb_id: str, media_type: str) -> None:
        """Release a previously acquired submission lock.

        Should always be called in a finally block so the lock is never left dangling.
        Stale locks (from crashes) are cleaned automatically on the next acquire attempt.

        :param tmdb_id: TMDB ID as string.
        :param media_type: 'movie' or 'tv'.
        """
        query = "DELETE FROM submission_locks WHERE tmdb_id = ? AND media_type = ?"
        params = (str(tmdb_id), media_type)

        if self.db_type in ['mysql', 'mariadb', 'postgres']:
            query = query.replace("?", "%s")

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                self.logger.debug(
                    "Released submission lock: tmdb_id=%s, media_type=%s", tmdb_id, media_type
                )
        except Exception as e:
            self.logger.error(
                "Error releasing submission lock for tmdb_id=%s, media_type=%s: %s",
                tmdb_id, media_type, e
            )

    def save_metadata(self, media: Dict[str, Any], media_type: str) -> None:
        """Save metadata for a media item."""
        self.logger.debug(f"Saving metadata: {media_type} {media['id']}")
        
        media_id = str(media['id'])
        # Safely get title or fallback to name for TV shows
        title = media.get('title') or media.get('name') or 'Unknown Title'
        overview = media.get('overview', '')
        release_date = media.get('release_date')
        poster_path = media.get('poster_path', '')
        rating = media.get('rating', None)
        votes = media.get('votes', None)
        origin_country = ','.join(media.get('origin_country', []))
        genre_ids = ','.join(map(str, media.get('genre_ids', [])))
        logo_path = media.get('logo_path', '')
        backdrop_path = media.get('backdrop_path', '')

        query = """
            INSERT OR IGNORE INTO metadata (media_id, media_type, title, overview, release_date, 
                                             poster_path, rating, votes, origin_country, genre_ids, logo_path, backdrop_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (media_id, media_type, title, overview, release_date, poster_path, 
                 rating, votes, origin_country, genre_ids, logo_path, backdrop_path)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Database-specific query modifications
            if self.db_type == 'mysql':
                query = query.replace("INSERT OR IGNORE", "INSERT IGNORE")
                query = query.replace("?", "%s")
            elif self.db_type == 'postgres':
                query = query.replace("INSERT OR IGNORE", "INSERT")
                query = query.rstrip() + " ON CONFLICT DO NOTHING"
                query = query.replace("?", "%s")
            
            cursor.execute(query, params)
            conn.commit()
    
    def get_metadata(self, media_id: str, media_type: str) -> Optional[Dict[str, Any]]:
        """Retrieve metadata for a media item if it exists in the database."""
        self.logger.debug(f"Retrieving metadata: {media_type} {media_id}")
        
        query = """
            SELECT title, overview, release_date, poster_path FROM metadata
            WHERE media_id = ? AND media_type = ?
        """
        params = (media_id, media_type)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if self.db_type in ['mysql', 'postgres']:
                query = query.replace("?", "%s")
            
            cursor.execute(query, params)
            result = cursor.fetchone()

            if result:
                return {
                    "title": result[0],
                    "overview": result[1],
                    "release_date": result[2],
                    "poster_path": result[3]
                }
            return None
    
    def get_all_requests_grouped_by_source(self, page: int = 1, per_page: int = 8, sort_by: str = 'date-desc') -> Dict[str, Any]:
        """Retrieve all requests grouped by source with dynamic sorting and pagination."""
        self.logger.debug(f"Retrieving all requests grouped by source: page={page}, per_page={per_page}, sort_by={sort_by}")
    
        count_query = """
            SELECT 
                COUNT(DISTINCT s.media_id) as total_sources,
                COUNT(r.tmdb_request_id) as total_requests
            FROM requests r
            JOIN metadata m ON r.tmdb_request_id = m.media_id
            JOIN metadata s ON r.tmdb_source_id = s.media_id
            WHERE r.requested_by = 'SuggestArr'
        """
    
        total_sources = 0
        total_requests = 0
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get count
            if self.db_type in ['mysql', 'postgres']:
                count_query = count_query.replace("?", "%s")
            cursor.execute(count_query)
            count_result = cursor.fetchone()
            if count_result:
                total_sources, total_requests = count_result
        
        # Handle sorting for different database types
        if self.db_type in ['mysql', 'mariadb']:
            sort_mapping = {
                'date-desc': 'r.requested_at DESC, s.media_id DESC',
                'date-asc': 'r.requested_at ASC, s.media_id ASC',
                'title-asc': 's.title ASC, r.requested_at DESC',
                'title-desc': 's.title DESC, r.requested_at DESC',
                'rating-desc': 's.rating IS NULL, s.rating DESC, r.requested_at DESC',
                'rating-asc': 's.rating IS NULL, s.rating ASC, r.requested_at DESC'
            }
        else:
            # PostgreSQL and SQLite support NULLS LAST
            sort_mapping = {
                'date-desc': 'r.requested_at DESC, s.media_id DESC',
                'date-asc': 'r.requested_at ASC, s.media_id ASC',
                'title-asc': 's.title ASC, r.requested_at DESC',
                'title-desc': 's.title DESC, r.requested_at DESC',
                'rating-desc': 's.rating DESC NULLS LAST, r.requested_at DESC',
                'rating-asc': 's.rating ASC NULLS LAST, r.requested_at DESC'
            }

        order_by_clause = sort_mapping.get(sort_by, sort_mapping['date-desc'])
    
        query = f"""
            SELECT
                COALESCE(s.media_id, '0') AS source_id,
                COALESCE(s.title, 'LLM Recommendation') AS source_title,
                s.overview AS source_overview,
                s.release_date AS source_release_date, s.poster_path AS source_poster_path, s.rating as rating,
                r.tmdb_request_id, r.media_type, r.requested_at, s.logo_path, s.backdrop_path,
                m.title AS request_title, m.overview AS request_overview,
                m.release_date AS request_release_date, m.poster_path AS request_poster_path, m.rating as request_rating,
                m.logo_path, m.backdrop_path, r.is_anime, r.rationale,
                r.user_id, u.user_name
            FROM requests r
            JOIN metadata m ON r.tmdb_request_id = m.media_id
            LEFT JOIN metadata s ON r.tmdb_source_id = s.media_id
            LEFT JOIN users u ON r.user_id = u.user_id
            WHERE r.requested_by = 'SuggestArr'
            AND COALESCE(r.tmdb_source_id, '') != 'ai_search'
            ORDER BY {order_by_clause}
        """
        
        if self.db_type in ['mysql', 'postgres']:
            query = query.replace("?", "%s")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchall()
        
        # Group and sort results (maintaining existing logic)
        sources = {}
        source_max_dates = {}
        
        for row in result:
            source_id = row[0]
            requested_at = row[8]
            
            if source_id not in sources:
                sources[source_id] = {
                    "source_id": source_id,
                    "source_title": row[1],
                    "source_overview": row[2],
                    "source_release_date": row[3],
                    "source_poster_path": row[4],
                    "rating": round(row[5], 2) if row[5] is not None else None,
                    "media_type": row[7],
                    "logo_path": row[9],
                    "backdrop_path": row[10],
                    "is_anime": bool(row[18]) if len(row) > 18 and row[18] is not None else False,
                    "requests": []
                }
                source_max_dates[source_id] = requested_at
            else:
                if requested_at > source_max_dates[source_id]:
                    source_max_dates[source_id] = requested_at
    
            sources[source_id]["requests"].append({
                "request_id": row[6],
                "media_type": row[7],
                "requested_at": row[8],
                "title": row[11],
                "overview": row[12],
                "release_date": row[13],
                "poster_path": row[14],
                "backdrop_path": row[17],
                "rating": round(row[15], 2) if row[15] is not None else None,
                "logo_path": row[16],
                "rationale": row[19] if len(row) > 19 else None,
                "user_id": row[20] if len(row) > 20 else None,
                "user_name": row[21] if len(row) > 21 else None,
            })
    
        # Sort sources
        source_list = []
        for source_id, source_data in sources.items():
            source_data['max_requested_at'] = source_max_dates[source_id]
            source_list.append(source_data)
    
        # Apply sorting
        if sort_by == 'date-desc':
            source_list.sort(key=lambda x: x['max_requested_at'], reverse=True)
        elif sort_by == 'date-asc':
            source_list.sort(key=lambda x: x['max_requested_at'])
        elif sort_by == 'title-asc':
            source_list.sort(key=lambda x: (x['source_title'] or '').lower())
        elif sort_by == 'title-desc':
            source_list.sort(key=lambda x: (x['source_title'] or '').lower(), reverse=True)
        elif sort_by == 'rating-desc':
            source_list.sort(key=lambda x: (x['rating'] if x['rating'] is not None else -1), reverse=True)
        elif sort_by == 'rating-asc':
            source_list.sort(key=lambda x: (x['rating'] if x['rating'] is not None else float('inf')))
    
        # Clean up and paginate
        for source in source_list:
            del source['max_requested_at']
    
        total_pages = (total_sources + per_page - 1) // per_page  
        paginated_data = source_list[(page - 1) * per_page: page * per_page]
    
        return {
            "data": paginated_data,
            "total_pages": total_pages,
            "total_sources": total_sources,
            "total_requests": total_requests,
            "current_page": page,
            "per_page": per_page
        }
    
    def get_requested_tmdb_ids(self) -> set:
        """Return the set of TMDB IDs (as strings) that SuggestArr has already requested.

        Used by AI Search to exclude items that have already been sent to Jellyseer,
        whether through the normal automation or through the AI Search feature.

        :return: Set of tmdb_request_id strings.
        """
        query = "SELECT DISTINCT tmdb_request_id FROM requests WHERE requested_by = 'SuggestArr'"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return {str(row[0]) for row in cursor.fetchall()}

    def get_ai_search_requests(self, page: int = 1, per_page: int = 12, sort_by: str = 'date-desc') -> Dict[str, Any]:
        """Get requests made via AI Search, paginated and sorted.

        :param page: Page number (1-based).
        :param per_page: Results per page.
        :param sort_by: Sort key — one of 'date-desc', 'date-asc', 'title-asc', 'title-desc'.
        :return: Dict with 'data', 'total', 'total_pages', 'current_page', 'per_page'.
        """
        self.logger.debug("Retrieving AI search requests: page=%d, per_page=%d, sort_by=%s", page, per_page, sort_by)

        sort_mapping = {
            'date-desc': 'r.requested_at DESC',
            'date-asc': 'r.requested_at ASC',
            'title-asc': 'm.title ASC',
            'title-desc': 'm.title DESC',
        }
        order_by_clause = sort_mapping.get(sort_by, 'r.requested_at DESC')
        placeholder = '%s' if self.db_type in ('mysql', 'postgres') else '?'

        count_query = """
            SELECT COUNT(*)
            FROM requests r
            JOIN metadata m ON r.tmdb_request_id = m.media_id
            WHERE r.requested_by = 'SuggestArr'
            AND r.tmdb_source_id = 'ai_search'
        """

        select_query = f"""
            SELECT
                r.tmdb_request_id, r.media_type, r.requested_at, r.rationale,
                m.title, m.overview, m.poster_path, m.release_date, m.rating,
                m.backdrop_path, m.logo_path
            FROM requests r
            JOIN metadata m ON r.tmdb_request_id = m.media_id
            WHERE r.requested_by = 'SuggestArr'
            AND r.tmdb_source_id = 'ai_search'
            ORDER BY {order_by_clause}
            LIMIT {placeholder} OFFSET {placeholder}
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(count_query)
            total = (cursor.fetchone() or [0])[0]

            offset = (page - 1) * per_page
            cursor.execute(select_query, (per_page, offset))
            rows = cursor.fetchall()

        items = []
        for row in rows:
            items.append({
                "request_id": row[0],
                "media_type": row[1],
                "requested_at": row[2],
                "rationale": row[3],
                "title": row[4],
                "overview": row[5],
                "poster_path": row[6],
                "release_date": row[7],
                "rating": round(row[8], 2) if row[8] is not None else None,
                "backdrop_path": row[9],
                "logo_path": row[10],
            })

        total_pages = max(1, (total + per_page - 1) // per_page)
        return {
            "data": items,
            "total": total,
            "total_pages": total_pages,
            "current_page": page,
            "per_page": per_page,
        }

    def get_requests_stats(self) -> Dict[str, Any]:
        """Get statistics about requests: total, today, this week, and this month counts."""
        self.logger.debug("Retrieving request statistics")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total requests query
            total_query = """
                SELECT COUNT(*) FROM requests
                WHERE requested_by = 'SuggestArr'
            """

            if self.db_type in ['mysql', 'postgres']:
                total_query = total_query.replace("?", "%s")

            cursor.execute(total_query)
            total_result = cursor.fetchone()
            total = total_result[0] if total_result else 0

            # Today's requests query
            if self.db_type == 'sqlite':
                today_query = """
                    SELECT COUNT(*) FROM requests
                    WHERE requested_by = 'SuggestArr'
                    AND DATE(requested_at) = DATE('now')
                """
            elif self.db_type == 'postgres':
                today_query = """
                    SELECT COUNT(*) FROM requests
                    WHERE requested_by = 'SuggestArr'
                    AND DATE(requested_at) = CURRENT_DATE
                """
            elif self.db_type in ['mysql', 'mariadb']:
                today_query = """
                    SELECT COUNT(*) FROM requests
                    WHERE requested_by = 'SuggestArr'
                    AND DATE(requested_at) = CURDATE()
                """
            else:
                today_query = total_query

            if self.db_type in ['mysql', 'postgres']:
                today_query = today_query.replace("?", "%s")

            cursor.execute(today_query)
            today_result = cursor.fetchone()
            today = today_result[0] if today_result else 0

            # This week's requests query (from Monday to today)
            if self.db_type == 'sqlite':
                week_query = """
                    SELECT COUNT(*) FROM requests
                    WHERE requested_by = 'SuggestArr'
                    AND DATE(requested_at) >= DATE('now', '-' || ((CAST(strftime('%w', 'now') AS INTEGER) + 6) % 7) || ' days')
                """
            elif self.db_type == 'postgres':
                week_query = """
                    SELECT COUNT(*) FROM requests
                    WHERE requested_by = 'SuggestArr'
                    AND DATE(requested_at) >= DATE_TRUNC('week', CURRENT_DATE)
                """
            elif self.db_type in ['mysql', 'mariadb']:
                week_query = """
                    SELECT COUNT(*) FROM requests
                    WHERE requested_by = 'SuggestArr'
                    AND DATE(requested_at) >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)
                """
            else:
                week_query = total_query

            if self.db_type in ['mysql', 'postgres']:
                week_query = week_query.replace("?", "%s")

            cursor.execute(week_query)
            week_result = cursor.fetchone()
            this_week = week_result[0] if week_result else 0

            # This month's requests query
            if self.db_type == 'sqlite':
                month_query = """
                    SELECT COUNT(*) FROM requests
                    WHERE requested_by = 'SuggestArr'
                    AND strftime('%Y-%m', requested_at) = strftime('%Y-%m', 'now')
                """
            elif self.db_type == 'postgres':
                month_query = """
                    SELECT COUNT(*) FROM requests
                    WHERE requested_by = 'SuggestArr'
                    AND DATE_TRUNC('month', requested_at) = DATE_TRUNC('month', CURRENT_DATE)
                """
            elif self.db_type in ['mysql', 'mariadb']:
                month_query = """
                    SELECT COUNT(*) FROM requests
                    WHERE requested_by = 'SuggestArr'
                    AND YEAR(requested_at) = YEAR(CURDATE())
                    AND MONTH(requested_at) = MONTH(CURDATE())
                """
            else:
                month_query = total_query

            if self.db_type in ['mysql', 'postgres']:
                month_query = month_query.replace("?", "%s")

            cursor.execute(month_query)
            month_result = cursor.fetchone()
            this_month = month_result[0] if month_result else 0

            return {
                "total": total,
                "approved": 0,  # Not handled on your side
                "pending": 0,   # Not handled on your side
                "today": today,
                "this_week": this_week,
                "this_month": this_month
            }
    
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
                conn = sqlite3.connect(test_path, timeout=5)
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
        
    def save_requests_batch(self, requests: List[Dict[str, Any]]) -> None:
            """Save a batch of media requests to the database, handling different DB types."""
            if not requests:
                return

            self.logger.debug(f"Saving batch of requests: {len(requests)} requests")

            query = """
                INSERT OR IGNORE INTO requests (media_type, tmdb_request_id, requested_by)
                VALUES (?, ?, ?)
            """

            if self.db_type == 'mysql':
                query = query.replace("INSERT OR IGNORE", "INSERT IGNORE").replace("?", "%s")
            elif self.db_type == 'postgres':
                query = query.replace("INSERT OR IGNORE", "INSERT").rstrip() + " ON CONFLICT DO NOTHING"
                query = query.replace("?", "%s")

            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()

                    for request in requests:
                        try:
                            media = request.get('media') if isinstance(request, dict) else None
                            if not isinstance(media, dict):
                                self.logger.warning(f"Skipping request with invalid media object (type: {type(media).__name__}): {request}")
                                continue
                            media_type = media.get('mediaType')
                            media_id = media.get('tmdbId')
                            if not media_type or media_id is None:
                                self.logger.warning(f"Skipping request with missing mediaType or tmdbId: {media}")
                                continue
                            params = (media_type, str(media_id), 'Seer')

                            cursor.execute(query, params)
                        except (KeyError, TypeError) as e:
                            self.logger.error(f"Invalid request structure in batch: {e}")
                            continue
                        
                    conn.commit()
                    self.logger.debug(f"Batch di {len(requests)} salvato correttamente")
            except Exception as e:
                self.logger.error(f"Errore durante il salvataggio del batch: {e}")
                raise DatabaseError(f"Batch save failed: {str(e)}", db_type=self.db_type)

    # ---------------------------------------------------------------------------
    # Pending-request queue methods
    # ---------------------------------------------------------------------------

    def enqueue_request(self, tmdb_id: str, media_type: str, user_id: Optional[str],
                        payload: dict) -> bool:
        """Enqueue a Seer submission for background delivery.

        Idempotent: silently no-ops when an entry for (tmdb_id, media_type) already
        exists in any status.  Items that were already successfully submitted (present
        in the ``requests`` table) are also skipped.

        :param tmdb_id: TMDB media ID.
        :param media_type: 'movie' or 'tv'.
        :param user_id: Jellyseer user ID to attribute the request to (may be None).
        :param payload: Complete Seer request body plus private meta-keys prefixed
            with ``_`` (``_source_id``, ``_rationale``, ``_is_anime``).
        :return: True if a new row was inserted, False if already present or already
            submitted.
        """
        if self.check_request_exists(media_type, tmdb_id):
            self.logger.debug("enqueue_request: %s %s already submitted, skipping.", media_type, tmdb_id)
            return False

        query = """
            INSERT OR IGNORE INTO pending_requests
                (tmdb_id, media_type, user_id, payload, status)
            VALUES (?, ?, ?, ?, 'queued')
        """
        params = (str(tmdb_id), media_type, user_id, json.dumps(payload))

        if self.db_type in ['mysql', 'mariadb']:
            query = query.replace("INSERT OR IGNORE", "INSERT IGNORE").replace("?", "%s")
        elif self.db_type == 'postgres':
            query = (query.replace("INSERT OR IGNORE", "INSERT").replace("?", "%s").rstrip()
                     + " ON CONFLICT (tmdb_id, media_type) DO NOTHING")

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                inserted = cursor.rowcount > 0
                conn.commit()
                if inserted:
                    self.logger.debug("Enqueued %s tmdb:%s for Seer delivery.", media_type, tmdb_id)
                return inserted
        except Exception as e:
            self.logger.error("Failed to enqueue %s tmdb:%s: %s", media_type, tmdb_id, e)
            return False

    def get_due_requests(self, max_items: int = 50) -> List[Dict[str, Any]]:
        """Return up to *max_items* queued rows whose next_attempt_at is due.

        :param max_items: Maximum number of rows to return.
        :return: List of row dicts ordered by created_at ASC.
        """
        now_iso = datetime.utcnow().isoformat()
        placeholder = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'

        query = f"""
            SELECT id, tmdb_id, media_type, user_id, payload, retry_count
            FROM pending_requests
            WHERE status = 'queued'
              AND (next_attempt_at IS NULL OR next_attempt_at <= {placeholder})
            ORDER BY created_at ASC
            LIMIT {placeholder}
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (now_iso, max_items))
                cols = [d[0] for d in cursor.description]
                return [dict(zip(cols, row)) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error("Failed to fetch due pending_requests: %s", e)
            return []

    def _update_pending_status(self, row_id: int, status: str, retry_count: int,
                               last_attempt_at: Optional[str] = None,
                               next_attempt_at: Optional[str] = None) -> None:
        """Internal helper — update status / retry columns on a pending_requests row."""
        placeholder = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'
        query = (f"UPDATE pending_requests SET status={placeholder}, retry_count={placeholder}"
                 f", last_attempt_at={placeholder}, next_attempt_at={placeholder}"
                 f" WHERE id={placeholder}")
        params = (status, retry_count, last_attempt_at, next_attempt_at, row_id)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
        except Exception as e:
            self.logger.error("Failed to update pending_requests row %s: %s", row_id, e)

    def mark_pending_submitting(self, row_id: int, retry_count: int) -> None:
        """Mark a row as in-flight so concurrent workers skip it.

        :param row_id: Primary key of the pending_requests row.
        :param retry_count: Current retry count (unchanged at this point).
        """
        self._update_pending_status(row_id, 'submitting', retry_count,
                                    last_attempt_at=datetime.utcnow().isoformat())

    def mark_pending_submitted(self, row_id: int, retry_count: int) -> None:
        """Mark a row as successfully submitted.

        :param row_id: Primary key of the pending_requests row.
        :param retry_count: Final retry count at time of success.
        """
        self._update_pending_status(row_id, 'submitted', retry_count)

    def mark_pending_failed(self, row_id: int, retry_count: int) -> None:
        """Mark a row as permanently failed (max retries exceeded).

        :param row_id: Primary key of the pending_requests row.
        :param retry_count: Final retry count.
        """
        self._update_pending_status(row_id, 'failed', retry_count,
                                    last_attempt_at=datetime.utcnow().isoformat())

    def increment_pending_retry(self, row_id: int, new_retry_count: int,
                                next_attempt_at: str) -> None:
        """Bump retry counter and schedule next attempt with exponential backoff.

        :param row_id: Primary key of the pending_requests row.
        :param new_retry_count: Incremented retry count.
        :param next_attempt_at: ISO-8601 UTC timestamp for next eligible attempt.
        """
        self._update_pending_status(row_id, 'queued', new_retry_count,
                                    last_attempt_at=datetime.utcnow().isoformat(),
                                    next_attempt_at=next_attempt_at)

    def reset_stale_inflight(self, cutoff_minutes: int = 10) -> int:
        """Reset 'submitting' rows that have been stuck longer than *cutoff_minutes*.

        Called at queue worker startup to recover from crashes.

        :param cutoff_minutes: Rows locked for longer than this are re-queued.
        :return: Number of rows reset.
        """
        cutoff = (datetime.utcnow() - timedelta(minutes=cutoff_minutes)).isoformat()
        placeholder = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'
        query = (f"UPDATE pending_requests SET status='queued'"
                 f" WHERE status='submitting' AND last_attempt_at < {placeholder}")
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (cutoff,))
                reset = cursor.rowcount
                conn.commit()
                if reset:
                    self.logger.warning("reset_stale_inflight: re-queued %d stuck row(s).", reset)
                return reset
        except Exception as e:
            self.logger.error("Failed to reset stale in-flight rows: %s", e)
            return 0
