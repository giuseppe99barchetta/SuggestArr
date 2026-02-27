import json
import os
import sqlite3
import psycopg2
import mysql.connector
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Tuple

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.exceptions.database_exceptions import DatabaseError

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(BASE_DIR, 'config', 'config_files', 'requests.db')

# Required fields that must be non-empty for an integration to be considered valid.
_INTEGRATION_REQUIRED_FIELDS: Dict[str, List[str]] = {
    'jellyfin': ['api_url', 'api_key'],
    'seer':     ['api_url', 'api_key'],
    'tmdb':     ['api_key'],
    'omdb':     ['api_key'],
    # OpenAI/LLM: no hard required fields — either api_key (cloud) or base_url (local) is sufficient.
    # An existing row (even empty) is considered valid to prevent overwriting user configuration.
    'openai':   [],
}


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
            # auth_users MUST come before refresh_tokens (foreign key dependency).
            'auth_users': """
                CREATE TABLE IF NOT EXISTS auth_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
            """,
            'refresh_tokens': """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE
                )
            """,
            'user_media_profiles': """
                CREATE TABLE IF NOT EXISTS user_media_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    external_user_id TEXT NOT NULL,
                    external_username TEXT NOT NULL,
                    access_token TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE,
                    UNIQUE (user_id, provider)
                )
            """,
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
            """,
            'integrations': """
                CREATE TABLE IF NOT EXISTS integrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service TEXT UNIQUE NOT NULL,
                    config_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

        # Migrate 'viewer' role to 'user' for all existing accounts
        self._migrate_viewer_role_to_user()

    def _migrate_viewer_role_to_user(self):
        """Migrate any existing auth_users with role='viewer' to role='user'."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                ph = self._ph()
                cursor.execute(
                    f"UPDATE auth_users SET role = {ph} WHERE role = {ph}",
                    ('user', 'viewer'),
                )
                affected = cursor.rowcount
                conn.commit()
                if affected:
                    self.logger.info(
                        "Migrated %d auth_user(s) from role 'viewer' to 'user'.", affected
                    )
        except Exception as e:
            self.logger.warning("Could not migrate viewer roles (table may not exist yet): %s", e)

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

    # ------------------------------------------------------------------
    # Integrations helpers
    # ------------------------------------------------------------------

    def get_integration(self, service: str) -> Optional[dict]:
        """
        Retrieve the stored config for a named service integration.

        Args:
            service: Integration service name (e.g. 'jellyfin', 'seer').

        Returns:
            dict with stored config, or None if no row exists.
        """
        query = "SELECT config_json FROM integrations WHERE service = ?"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if self.db_type in ['mysql', 'mariadb', 'postgres']:
                query = query.replace("?", "%s")
            cursor.execute(query, (service,))
            row = cursor.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def get_all_integrations(self) -> dict:
        """
        Retrieve all service integrations from the database.

        Returns:
            dict mapping service name to its config dict.
        """
        query = "SELECT service, config_json FROM integrations"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
        return {row[0]: json.loads(row[1]) for row in rows}

    def set_integration(self, service: str, config: dict) -> None:
        """
        Insert or replace the config for a named service integration.

        Args:
            service: Integration service name.
            config: Configuration dict to persist as JSON.
        """
        config_json = json.dumps(config)
        now = datetime.utcnow()

        if self.db_type == 'sqlite':
            query = (
                "INSERT OR REPLACE INTO integrations (service, config_json, updated_at) "
                "VALUES (?, ?, ?)"
            )
            params = (service, config_json, now)
        elif self.db_type == 'postgres':
            query = (
                "INSERT INTO integrations (service, config_json, updated_at) VALUES (%s, %s, %s) "
                "ON CONFLICT (service) DO UPDATE SET config_json = EXCLUDED.config_json, "
                "updated_at = EXCLUDED.updated_at"
            )
            params = (service, config_json, now)
        else:  # mysql / mariadb
            query = (
                "INSERT INTO integrations (service, config_json, updated_at) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE config_json = VALUES(config_json), updated_at = VALUES(updated_at)"
            )
            params = (service, config_json, now)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()

    @staticmethod
    def _is_integration_valid(service: str, config: dict) -> bool:
        """
        Return True if *config* contains all required non-empty fields for *service*.

        Args:
            service: Integration service name (e.g. 'jellyfin', 'tmdb').
            config:  Stored config dict retrieved from the integrations table.

        Returns:
            True when every required field is present and non-empty.
        """
        required = _INTEGRATION_REQUIRED_FIELDS.get(service, [])
        return all(config.get(field) for field in required)

    def migrate_integrations_from_config(self) -> None:
        """
        Startup migration: seed or repair the integrations table from config.yaml.

        Rules applied per service:
        - Row does not exist            → insert from config (if config has required fields).
        - Row exists but invalid/empty  → update from config (if config has required fields).
        - Row exists and valid          → leave untouched.

        This is safe to call on every startup.
        """
        env_vars = load_env_vars()
        candidates = {
            'jellyfin': {
                'api_url': env_vars.get('JELLYFIN_API_URL', ''),
                'api_key': env_vars.get('JELLYFIN_TOKEN', ''),
            },
            'seer': {
                'api_url': env_vars.get('SEER_API_URL', ''),
                'api_key': env_vars.get('SEER_TOKEN', ''),
                'session_token': env_vars.get('SEER_SESSION_TOKEN'),
            },
            'tmdb': {
                'api_key': env_vars.get('TMDB_API_KEY', ''),
            },
            'omdb': {
                'api_key': env_vars.get('OMDB_API_KEY', ''),
            },
        }

        # AI provider: only seed the DB when YAML already has a key or base_url configured.
        # No required fields are enforced (either api_key for cloud or base_url for local providers).
        _openai_key = env_vars.get('OPENAI_API_KEY', '')
        _openai_base = env_vars.get('OPENAI_BASE_URL', '')
        if _openai_key or _openai_base:
            candidates['openai'] = {
                'api_key': _openai_key,
                'base_url': _openai_base,
                'model': env_vars.get('LLM_MODEL', ''),
            }

        for service, config in candidates.items():
            existing = self.get_integration(service)

            if existing is not None and self._is_integration_valid(service, existing):
                self.logger.debug(
                    "Integration '%s' already in DB with valid credentials — skipping migration", service
                )
                continue

            # Check whether config.yaml provides the required fields.
            required = _INTEGRATION_REQUIRED_FIELDS.get(service, [])
            if not all(config.get(field) for field in required):
                self.logger.debug(
                    "Integration '%s': config.yaml missing required fields %s — skipping",
                    service, required,
                )
                continue

            action = "Updating" if existing is not None else "Migrating"
            safe_log = {k: v for k, v in config.items() if k not in ('api_key', 'session_token')}
            self.logger.info(
                "%s '%s' credentials from config.yaml → integrations table %s",
                action, service, safe_log,
            )
            self.set_integration(service, config)

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

    # ---------------------------------------------------------------------------
    # Auth-user methods (SuggestArr internal accounts — NOT external service users)
    # ---------------------------------------------------------------------------

    def _ph(self) -> str:
        """Return the SQL placeholder character for the current DB type."""
        return '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'

    def get_auth_user_count(self) -> int:
        """
        Return the total number of SuggestArr auth accounts.

        Used by the setup-mode check in the auth middleware: if the count is 0
        the system is in first-run mode and all routes are temporarily public.

        Returns:
            int: Number of rows in the auth_users table.
        """
        ph = self._ph()
        query = "SELECT COUNT(*) FROM auth_users"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def create_auth_user(self, username: str, password_hash: str, role: str = 'user') -> int:
        """
        Insert a new SuggestArr auth account and return its primary key.

        Args:
            username:      Unique login name.
            password_hash: bcrypt hash string produced by AuthService.hash_password.
            role:          'admin' or 'user' (default 'user').

        Returns:
            int: The new row's primary key (id).

        Raises:
            DatabaseError: If the username already exists or the insert fails.
        """
        ph = self._ph()

        if self.db_type == 'postgres':
            query = (
                f"INSERT INTO auth_users (username, password_hash, role) "
                f"VALUES ({ph}, {ph}, {ph}) RETURNING id"
            )
        else:
            query = (
                f"INSERT INTO auth_users (username, password_hash, role) "
                f"VALUES ({ph}, {ph}, {ph})"
            )

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (username, password_hash, role))
                if self.db_type == 'postgres':
                    row = cursor.fetchone()
                    new_id = row[0]
                else:
                    new_id = cursor.lastrowid
                conn.commit()
                self.logger.info("Created auth user: %s (role=%s)", username, role)
                return int(new_id)
        except Exception as exc:
            raise DatabaseError(
                error=f"Failed to create auth user: {exc}",
                db_type=self.db_type,
            ) from exc

    def get_auth_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Look up a SuggestArr auth user by their login name.

        Args:
            username: Login name to search for (case-sensitive).

        Returns:
            dict | None: Row as a dict with keys id, username, password_hash,
                         role, is_active, last_login — or None if not found.
        """
        ph = self._ph()
        query = (
            f"SELECT id, username, password_hash, role, is_active, last_login "
            f"FROM auth_users WHERE username = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (username,))
            row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "role": row[3],
            "is_active": bool(row[4]),
            "last_login": row[5],
        }

    def get_auth_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Look up a SuggestArr auth user by their primary key.

        Args:
            user_id: Integer primary key from the auth_users table.

        Returns:
            dict | None: Same shape as get_auth_user_by_username, or None.
        """
        ph = self._ph()
        query = (
            f"SELECT id, username, password_hash, role, is_active, last_login "
            f"FROM auth_users WHERE id = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "role": row[3],
            "is_active": bool(row[4]),
            "last_login": row[5],
        }

    def update_last_login(self, user_id: int) -> None:
        """
        Record the current UTC timestamp as the last successful login time.

        Args:
            user_id: Primary key of the auth user who just logged in.
        """
        ph = self._ph()
        now = datetime.utcnow().isoformat()
        query = f"UPDATE auth_users SET last_login = {ph} WHERE id = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (now, user_id))
            conn.commit()

    # ---------------------------------------------------------------------------
    # Refresh-token methods
    # ---------------------------------------------------------------------------

    def store_refresh_token(self, user_id: int, token_hash: str, expires_at: datetime) -> None:
        """
        Persist the SHA-256 hash of a newly issued refresh token.

        Only the hash is stored, never the raw token, so a database dump does
        not yield usable refresh tokens.

        Args:
            user_id:    Primary key of the owning auth user.
            token_hash: SHA-256 hex digest of the raw refresh token.
            expires_at: Expiry timestamp (timezone-aware recommended).
        """
        ph = self._ph()
        if expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        query = (
            f"INSERT INTO refresh_tokens (user_id, token_hash, expires_at) "
            f"VALUES ({ph}, {ph}, {ph})"
        )
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (user_id, token_hash, expires_at))
                conn.commit()
        except Exception as exc:
            raise DatabaseError(
                error=f"Failed to store refresh token: {exc}",
                db_type=self.db_type,
            ) from exc

    def get_refresh_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a non-revoked refresh token record by its hash.

        Args:
            token_hash: SHA-256 hex digest of the raw token received from the cookie.

        Returns:
            dict | None: Row with keys id, user_id, expires_at — or None if
                         not found or already revoked.
        """
        ph = self._ph()
        query = (
            f"SELECT id, user_id, expires_at FROM refresh_tokens "
            f"WHERE token_hash = {ph} AND revoked = 0"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (token_hash,))
            row = cursor.fetchone()
        if row is None:
            return None
        return {"id": row[0], "user_id": row[1], "expires_at": row[2]}

    def revoke_refresh_token(self, token_hash: str) -> None:
        """
        Mark a refresh token as revoked so it can no longer be used.

        Called on logout.  The row is kept (not deleted) so that token-reuse
        attacks (presenting a revoked token) can be detected in the future.

        Args:
            token_hash: SHA-256 hex digest of the token to invalidate.
        """
        ph = self._ph()
        query = f"UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (token_hash,))
            conn.commit()

    def cleanup_expired_refresh_tokens(self) -> int:
        """
        Delete refresh tokens that have expired or been revoked.

        Intended to be called periodically (e.g. daily) to keep the table small.

        Returns:
            int: Number of rows deleted.
        """
        ph = self._ph()
        now = datetime.utcnow().isoformat()
        query = (
            f"DELETE FROM refresh_tokens "
            f"WHERE expires_at < {ph} OR revoked = 1"
        )
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (now,))
                deleted = cursor.rowcount
                conn.commit()
                if deleted:
                    self.logger.debug("Cleaned up %d expired/revoked refresh tokens.", deleted)
                return deleted
        except Exception as exc:
            self.logger.error("Failed to clean up refresh tokens: %s", exc)
            return 0

    # ---------------------------------------------------------------------------
    # Auth user management methods
    # ---------------------------------------------------------------------------

    def get_all_auth_users(self) -> List[Dict[str, Any]]:
        """
        Return all SuggestArr auth users, excluding password hashes.

        Returns:
            list[dict]: Each dict has keys id, username, role, is_active,
                        created_at, last_login.
        """
        query = (
            "SELECT id, username, role, is_active, created_at, last_login "
            "FROM auth_users ORDER BY id"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "username": row[1],
                "role": row[2],
                "is_active": bool(row[3]),
                "created_at": row[4],
                "last_login": row[5],
            }
            for row in rows
        ]

    def update_auth_user(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update allowed fields of an auth user record.

        Only 'role' and 'is_active' may be changed through this method.

        Args:
            user_id: Primary key of the user to update.
            updates: Dict containing any subset of {'role', 'is_active'}.

        Returns:
            bool: True if a row was updated, False if the user was not found.
        """
        allowed = {'role', 'is_active'}
        fields = {k: v for k, v in updates.items() if k in allowed}
        if not fields:
            return False
        ph = self._ph()
        set_clause = ", ".join(f"{k} = {ph}" for k in fields)
        query = f"UPDATE auth_users SET {set_clause} WHERE id = {ph}"
        values = list(fields.values()) + [user_id]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, values)
            updated = cursor.rowcount
            conn.commit()
        return updated > 0

    def update_auth_user_profile(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update a user's own profile fields: username and/or password_hash.

        This is intentionally separate from update_auth_user (which handles
        admin-level role/active changes) so that the two call-sites stay
        clearly distinct.

        Args:
            user_id: Primary key of the user to update.
            updates: Dict containing any subset of {'username', 'password_hash'}.

        Returns:
            bool: True if a row was updated, False if the user was not found.

        Raises:
            Exception: Propagates DB-level unique-constraint violations
                       (e.g. duplicate username) so the caller can handle them.
        """
        allowed = {'username', 'password_hash'}
        fields = {k: v for k, v in updates.items() if k in allowed}
        if not fields:
            return False
        ph = self._ph()
        set_clause = ", ".join(f"{k} = {ph}" for k in fields)
        query = f"UPDATE auth_users SET {set_clause} WHERE id = {ph}"
        values = list(fields.values()) + [user_id]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, values)
            updated = cursor.rowcount
            conn.commit()
        return updated > 0

    def delete_auth_user(self, user_id: int) -> bool:
        """
        Permanently delete a SuggestArr auth user.

        Cascade deletes their refresh_tokens and user_media_profiles.

        Args:
            user_id: Primary key of the user to remove.

        Returns:
            bool: True if a row was deleted, False if the user was not found.
        """
        ph = self._ph()
        query = f"DELETE FROM auth_users WHERE id = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            deleted = cursor.rowcount
            conn.commit()
        return deleted > 0

    def get_admin_count(self) -> int:
        """
        Count active admin accounts.

        Used to prevent removing the last active admin.

        Returns:
            int: Number of auth_users rows where role='admin' AND is_active=1.
        """
        query = "SELECT COUNT(*) FROM auth_users WHERE role = 'admin' AND is_active = 1"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
        return row[0] if row else 0

    # ---------------------------------------------------------------------------
    # User media profile methods
    # ---------------------------------------------------------------------------

    def create_user_media_profile(
        self,
        user_id: int,
        provider: str,
        external_user_id: str,
        external_username: str,
        access_token: Optional[str] = None,
    ) -> None:
        """
        Insert or replace a media profile link for a SuggestArr user.

        The UNIQUE (user_id, provider) constraint ensures only one link per
        provider per user.  A second call for the same user+provider updates
        the existing record in-place (preserving the row id).

        Args:
            user_id:           Primary key of the auth user.
            provider:          One of 'jellyfin', 'plex', 'emby'.
            external_user_id:  The user's ID on the external media server.
            external_username: Human-readable name on the external server.
            access_token:      Optional token for the external server (nullable).
        """
        ph = self._ph()
        if self.db_type == 'sqlite':
            query = (
                f"INSERT INTO user_media_profiles "
                f"(user_id, provider, external_user_id, external_username, access_token) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}) "
                f"ON CONFLICT(user_id, provider) DO UPDATE SET "
                f"external_user_id = excluded.external_user_id, "
                f"external_username = excluded.external_username, "
                f"access_token = excluded.access_token, "
                f"created_at = CURRENT_TIMESTAMP"
            )
        elif self.db_type == 'postgres':
            query = (
                f"INSERT INTO user_media_profiles "
                f"(user_id, provider, external_user_id, external_username, access_token) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}) "
                f"ON CONFLICT (user_id, provider) DO UPDATE SET "
                f"external_user_id = EXCLUDED.external_user_id, "
                f"external_username = EXCLUDED.external_username, "
                f"access_token = EXCLUDED.access_token, "
                f"created_at = CURRENT_TIMESTAMP"
            )
        else:
            # MySQL / MariaDB
            query = (
                f"INSERT INTO user_media_profiles "
                f"(user_id, provider, external_user_id, external_username, access_token) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}) "
                f"ON DUPLICATE KEY UPDATE "
                f"external_user_id = VALUES(external_user_id), "
                f"external_username = VALUES(external_username), "
                f"access_token = VALUES(access_token), "
                f"created_at = CURRENT_TIMESTAMP"
            )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id, provider, external_user_id, external_username, access_token))
            conn.commit()

    def get_user_media_profiles(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Return all media profile links for a SuggestArr user.

        Access tokens are intentionally excluded from the result so they are
        never serialised into API responses.

        Args:
            user_id: Primary key of the auth user.

        Returns:
            list[dict]: Each dict has keys id, provider, external_username,
                        created_at.
        """
        ph = self._ph()
        query = (
            f"SELECT id, provider, external_username, created_at "
            f"FROM user_media_profiles WHERE user_id = {ph} ORDER BY provider"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "provider": row[1],
                "external_username": row[2],
                "created_at": row[3],
            }
            for row in rows
        ]

    def get_user_media_profile_token(self, user_id: int, provider: str) -> Optional[str]:
        """
        Retrieve the access token for a specific media profile link.

        This method is intentionally separate from get_user_media_profiles so
        that tokens are only fetched when explicitly needed (not on every list).

        Args:
            user_id:  Primary key of the auth user.
            provider: Provider name ('jellyfin', 'plex', 'emby').

        Returns:
            str | None: Raw access token, or None if no link exists.
        """
        ph = self._ph()
        query = (
            f"SELECT access_token FROM user_media_profiles "
            f"WHERE user_id = {ph} AND provider = {ph}"
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id, provider))
            row = cursor.fetchone()
        return row[0] if row else None

    def delete_user_media_profile(self, user_id: int, provider: str) -> bool:
        """
        Remove a media profile link.

        Args:
            user_id:  Primary key of the auth user.
            provider: Provider to unlink ('jellyfin', 'plex', 'emby').

        Returns:
            bool: True if a row was deleted, False if no link existed.
        """
        ph = self._ph()
        query = f"DELETE FROM user_media_profiles WHERE user_id = {ph} AND provider = {ph}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id, provider))
            deleted = cursor.rowcount
            conn.commit()
        return deleted > 0
