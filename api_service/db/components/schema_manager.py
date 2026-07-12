import json

from api_service.exceptions.database_exceptions import DatabaseError

class SchemaManager:
    def __init__(self, database):
        self._database = database

    def __getattr__(self, name):
        return getattr(self._database, name)
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
                    is_active INTEGER NOT NULL DEFAULT 1,
                    can_manage_ai INTEGER DEFAULT 0,
                    visible_tabs TEXT DEFAULT 'suggestions,requests,jobs,profile'
                    , seer_user_id INTEGER
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
                    source_origin TEXT,
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
                    owner_id INTEGER,
                    pause_if_pending_requests INTEGER DEFAULT 0,
                    prevent_suggestions_if_unwatched INTEGER DEFAULT 0,
                    unwatched_suggestion_days INTEGER DEFAULT 7,
                    delivery_mode TEXT NOT NULL DEFAULT 'automatic',
                    seer_identity_mode TEXT NOT NULL DEFAULT 'technical_user',
                    request_profiles TEXT,
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
            'unwatched_suggestion_cycles': """
                CREATE TABLE IF NOT EXISTS unwatched_suggestion_cycles (
                    job_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    reset_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (job_id, user_id, media_type),
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
                    job_id INTEGER,
                    owner_id INTEGER,
                    decided_at TIMESTAMP,
                    decided_by INTEGER,
                    last_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tmdb_id, media_type)
                )
            """,
            'suggestion_blacklist': """
                CREATE TABLE IF NOT EXISTS suggestion_blacklist (
                    tmdb_id TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tmdb_id, media_type)
                )
            """,
            'cleanup_settings': """
                CREATE TABLE IF NOT EXISTS cleanup_settings (
                    id INTEGER PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    dry_run INTEGER NOT NULL DEFAULT 1,
                    grace_days INTEGER NOT NULL DEFAULT 7,
                    last_run_at TIMESTAMP,
                    last_run_status TEXT,
                    last_run_summary TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'cleanup_log': """
                CREATE TABLE IF NOT EXISTS cleanup_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ran_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tmdb_id TEXT,
                    media_type TEXT,
                    title TEXT,
                    action TEXT NOT NULL,
                    was_dry_run INTEGER NOT NULL DEFAULT 0,
                    user_rating REAL,
                    reason TEXT
                )
            """,
            'ai_search_seen': """
                CREATE TABLE IF NOT EXISTS ai_search_seen (
                    tmdb_id TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tmdb_id, media_type)
                )
            """,
            'ai_search_feedback': """
                CREATE TABLE IF NOT EXISTS ai_search_feedback (
                    tmdb_id TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    feedback TEXT NOT NULL,
                    title TEXT,
                    year INTEGER,
                    rationale TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tmdb_id, media_type)
                )
            """,
            'integrations': """
                CREATE TABLE IF NOT EXISTS integrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service TEXT UNIQUE NOT NULL,
                    config_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'media_user_identities': """
                CREATE TABLE IF NOT EXISTS media_user_identities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    external_user_id TEXT NOT NULL,
                    external_username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (provider, external_user_id)
                )
            """,
            'trakt_account_links': """
                CREATE TABLE IF NOT EXISTS trakt_account_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_user_identity_id INTEGER NOT NULL,
                    trakt_user_id TEXT,
                    trakt_username TEXT,
                    token_source TEXT NOT NULL DEFAULT 'manual_oauth',
                    status TEXT NOT NULL DEFAULT 'connected',
                    last_synced_at TIMESTAMP,
                    last_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (media_user_identity_id) REFERENCES media_user_identities(id) ON DELETE CASCADE,
                    UNIQUE (media_user_identity_id)
                )
            """,
            'trakt_oauth_tokens': """
                CREATE TABLE IF NOT EXISTS trakt_oauth_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    link_id INTEGER NOT NULL UNIQUE,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    expires_at BIGINT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (link_id) REFERENCES trakt_account_links(id) ON DELETE CASCADE
                )
            """,
            'trakt_sources': """
                CREATE TABLE IF NOT EXISTS trakt_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_user_identity_id INTEGER NOT NULL,
                    source_type TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    list_id TEXT,
                    list_slug TEXT,
                    username TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    use_as_seed INTEGER NOT NULL DEFAULT 1,
                    use_as_exclusion INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (media_user_identity_id) REFERENCES media_user_identities(id) ON DELETE CASCADE,
                    UNIQUE (media_user_identity_id, source_type, source_key)
                )
            """
        }
        
        # Create tables
        for table_name, query in queries.items():
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    query = self._prepare_create_table_query_for_db(
                        table_name,
                        query,
                        self.db_type,
                    )

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
        
        if self.db_type in ('mysql', 'mariadb'):
            try:
                corrections = [
                    ("ALTER TABLE trakt_account_links MODIFY media_user_identity_id INTEGER NOT NULL", ()),
                    ("ALTER TABLE trakt_account_links MODIFY token_source TEXT NOT NULL", ()),
                    ("ALTER TABLE trakt_account_links MODIFY last_error TEXT", ()),
                    ("ALTER TABLE trakt_oauth_tokens MODIFY access_token TEXT NOT NULL", ()),
                    ("ALTER TABLE trakt_oauth_tokens MODIFY refresh_token TEXT NOT NULL", ()),
                    ("ALTER TABLE trakt_sources MODIFY media_user_identity_id INTEGER NOT NULL", ()),
                ]
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    for stmt, params in corrections:
                        cursor.execute(stmt, params)
                    conn.commit()
                self.logger.debug("Applied MySQL column type corrections for new tables")
            except Exception as e:
                self.logger.error(f"Failed to apply MySQL column corrections: {e}")
                raise DatabaseError(
                    error=f"MySQL column correction failed: {str(e)}",
                    db_type=self.db_type
                )

        # Add missing columns
        self.add_missing_columns()

        # Create submission lock table (separate to control column types per DB engine)
        self._create_submission_locks_table()

    def _prepare_create_table_query_for_db(self, table_name: str, query: str, db_type: str) -> str:
        """Apply database-specific DDL rewrites for a table creation query."""
        if db_type in ['mysql', 'mariadb']:
            # Keep full VARCHAR storage but constrain indexed prefixes to stay
            # under InnoDB's key-length limit when using utf8mb4.
            if table_name == 'requests':
                query = query.replace(
                    "UNIQUE(media_type, tmdb_request_id, tmdb_source_id),",
                    "UNIQUE KEY uniq_requests_identity (media_type(191), tmdb_request_id(191), tmdb_source_id(191)),"
                )
            elif table_name == 'metadata':
                query = query.replace(
                    "UNIQUE(media_id, media_type)",
                    "UNIQUE KEY uniq_metadata_media_type (media_id(191), media_type(191))"
                )
            elif table_name == 'pending_requests':
                query = query.replace(
                    "UNIQUE(tmdb_id, media_type)",
                    "UNIQUE KEY uniq_pending_tmdb_media_type (tmdb_id(191), media_type(191))"
                )
            elif table_name == 'suggestion_blacklist':
                query = """
                    CREATE TABLE IF NOT EXISTS suggestion_blacklist (
                        tmdb_id VARCHAR(32) NOT NULL,
                        media_type VARCHAR(16) NOT NULL,
                        created_by INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (tmdb_id, media_type)
                    ) ENGINE=InnoDB
                """
            elif table_name == 'unwatched_suggestion_cycles':
                query = """
                    CREATE TABLE IF NOT EXISTS unwatched_suggestion_cycles (
                        job_id INT NOT NULL,
                        user_id VARCHAR(191) NOT NULL,
                        media_type VARCHAR(16) NOT NULL,
                        reset_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (job_id, user_id, media_type),
                        FOREIGN KEY (job_id) REFERENCES discover_jobs(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB
                """
            elif table_name == 'ai_search_seen':
                query = """
                    CREATE TABLE IF NOT EXISTS ai_search_seen (
                        tmdb_id VARCHAR(64) NOT NULL,
                        media_type VARCHAR(16) NOT NULL,
                        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (tmdb_id, media_type)
                    ) ENGINE=InnoDB
                """
            elif table_name == 'ai_search_feedback':
                query = """
                    CREATE TABLE IF NOT EXISTS ai_search_feedback (
                        tmdb_id VARCHAR(64) NOT NULL,
                        media_type VARCHAR(16) NOT NULL,
                        feedback VARCHAR(16) NOT NULL,
                        title VARCHAR(512),
                        year INTEGER,
                        rationale VARCHAR(512),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (tmdb_id, media_type)
                    ) ENGINE=InnoDB
                """

            # Order matters: do specific replacements first.
            query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "INT AUTO_INCREMENT PRIMARY KEY")
            query = query.replace("INTEGER", "INT")
            query = query.replace("TEXT", "VARCHAR(512)")
            query = query.replace("REAL", "DOUBLE")

            # Add ENGINE=InnoDB for foreign key support.
            if not query.strip().endswith("ENGINE=InnoDB"):
                query = query.rstrip().rstrip(")").rstrip() + ") ENGINE=InnoDB"
        elif db_type == 'postgres':
            query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            query = query.replace("AUTOINCREMENT", "")

        return query

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
                    elif self.db_type == 'postgres':
                        cursor.execute("ALTER TABLE requests ADD COLUMN is_anime BOOLEAN DEFAULT FALSE;")
                    else:
                        cursor.execute("ALTER TABLE requests ADD COLUMN is_anime BOOLEAN DEFAULT 0;")
                    conn.commit()

                    
                # Add missing rationale column
                if 'rationale' not in existing_columns:
                    self.logger.debug("Adding column rationale...")
                    cursor.execute("ALTER TABLE requests ADD COLUMN rationale TEXT;")
                    conn.commit()

                # Add missing source_origin column
                if 'source_origin' not in existing_columns:
                    self.logger.debug("Adding column source_origin...")
                    cursor.execute("ALTER TABLE requests ADD COLUMN source_origin TEXT;")
                    conn.commit()
                    
            except Exception as e:
                self.logger.error(f"Failed to add missing columns to requests: {e}")
                raise DatabaseError(
                    error=f"Column addition failed: {str(e)}",
                    db_type=self.db_type
                )

        # Check and add missing columns to auth_users table
        self._migrate_auth_users_table()

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

    def _migrate_auth_users_table(self):
        """Add missing columns to auth_users table for RBAC permissions."""
        self.logger.debug("Checking for missing columns in auth_users table...")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            try:
                # Get existing columns
                if self.db_type == 'sqlite':
                    query = "PRAGMA table_info(auth_users);"
                    cursor.execute(query)
                    existing_columns = {row[1] for row in cursor.fetchall()}
                elif self.db_type == 'postgres':
                    query = """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = 'auth_users';
                    """
                    cursor.execute(query)
                    existing_columns = {row[0] for row in cursor.fetchall()}
                elif self.db_type in ['mysql', 'mariadb']:
                    query = "SHOW COLUMNS FROM auth_users;"
                    cursor.execute(query)
                    existing_columns = {row[0] for row in cursor.fetchall()}
                else:
                    self.logger.warning(f"Unsupported DB type for column check: {self.db_type}")
                    return

                # Add missing can_manage_ai column
                if 'can_manage_ai' not in existing_columns:
                    self.logger.info("Adding column can_manage_ai to auth_users...")
                    if self.db_type in ['mysql', 'mariadb']:
                        cursor.execute("ALTER TABLE auth_users ADD COLUMN can_manage_ai TINYINT(1) DEFAULT 0;")
                    elif self.db_type == 'postgres':
                        cursor.execute("ALTER TABLE auth_users ADD COLUMN can_manage_ai SMALLINT DEFAULT 0;")
                    else:
                        cursor.execute("ALTER TABLE auth_users ADD COLUMN can_manage_ai INTEGER DEFAULT 0;")
                    conn.commit()

                # Add missing visible_tabs column
                if 'visible_tabs' not in existing_columns:
                    self.logger.info("Adding column visible_tabs to auth_users...")
                    if self.db_type in ['mysql', 'mariadb']:
                        cursor.execute("ALTER TABLE auth_users ADD COLUMN visible_tabs VARCHAR(255) DEFAULT 'requests,jobs,profile';")
                    else:
                        cursor.execute("ALTER TABLE auth_users ADD COLUMN visible_tabs TEXT DEFAULT 'requests,jobs,profile';")
                    conn.commit()
                if 'seer_user_id' not in existing_columns:
                    cursor.execute("ALTER TABLE auth_users ADD COLUMN seer_user_id INTEGER")
                    conn.commit()
                if self.db_type in ('mysql', 'mariadb'):
                    cursor.execute("UPDATE auth_users SET visible_tabs=CONCAT('suggestions,',visible_tabs) WHERE visible_tabs NOT LIKE '%suggestions%'")
                else:
                    cursor.execute("UPDATE auth_users SET visible_tabs='suggestions,' || visible_tabs WHERE visible_tabs NOT LIKE '%suggestions%'")
                conn.commit()

            except Exception as e:
                self.logger.error(f"Failed to migrate auth_users table: {e}")
                # Don't raise - table might not exist yet

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
                # Add missing owner_id column for RBAC
                if 'owner_id' not in existing_columns:
                    self.logger.info("Adding column owner_id to discover_jobs for job ownership...")
                    if self.db_type in ['mysql', 'mariadb']:
                        cursor.execute("ALTER TABLE discover_jobs ADD COLUMN owner_id INTEGER;")
                    else:
                        cursor.execute("ALTER TABLE discover_jobs ADD COLUMN owner_id INTEGER;")
                    conn.commit()
                    
                    # Set default owner_id to primary admin for existing jobs
                    try:
                        ph = self._ph()
                        # Get the first admin user ID
                        cursor.execute(
                            f"SELECT id FROM auth_users WHERE role = {ph} ORDER BY id LIMIT 1",
                            ('admin',)
                        )
                        admin_row = cursor.fetchone()
                        if admin_row:
                            admin_id = admin_row[0]
                            cursor.execute(
                                f"UPDATE discover_jobs SET owner_id = {ph} WHERE owner_id IS NULL",
                                (admin_id,)
                            )
                            conn.commit()
                            self.logger.info(f"Set default owner_id to admin (ID: {admin_id}) for existing jobs")
                    except Exception as e:
                        self.logger.warning(f"Could not set default owner_id: {e}")

                # Add missing pause_if_pending_requests column
                if 'pause_if_pending_requests' not in existing_columns:
                    self.logger.info("Adding column pause_if_pending_requests to discover_jobs...")
                    if self.db_type in ['mysql', 'mariadb']:
                        cursor.execute("ALTER TABLE discover_jobs ADD COLUMN pause_if_pending_requests TINYINT(1) DEFAULT 0;")
                    elif self.db_type == 'postgres':
                        cursor.execute("ALTER TABLE discover_jobs ADD COLUMN pause_if_pending_requests SMALLINT DEFAULT 0;")
                    else:
                        cursor.execute("ALTER TABLE discover_jobs ADD COLUMN pause_if_pending_requests INTEGER DEFAULT 0;")
                    conn.commit()

                additions = {
                    'prevent_suggestions_if_unwatched': (
                        "TINYINT(1) DEFAULT 0" if self.db_type in ['mysql', 'mariadb'] else
                        "SMALLINT DEFAULT 0" if self.db_type == 'postgres' else "INTEGER DEFAULT 0"
                    ),
                    'unwatched_suggestion_days': "INTEGER DEFAULT 7",
                    'delivery_mode': ("VARCHAR(20) NOT NULL DEFAULT 'automatic'" if self.db_type in ['mysql', 'mariadb'] else "TEXT NOT NULL DEFAULT 'automatic'"),
                    'seer_identity_mode': ("VARCHAR(30) NOT NULL DEFAULT 'technical_user'" if self.db_type in ['mysql', 'mariadb'] else "TEXT NOT NULL DEFAULT 'technical_user'"),
                    'request_profiles': "TEXT",
                }
                for column, definition in additions.items():
                    if column not in existing_columns:
                        cursor.execute(f"ALTER TABLE discover_jobs ADD COLUMN {column} {definition};")
                conn.commit()

                # Keep the existing delivery queue and add approval metadata in place.
                if self.db_type == 'sqlite':
                    cursor.execute("PRAGMA table_info(pending_requests)")
                    pending_columns = {row[1] for row in cursor.fetchall()}
                elif self.db_type == 'postgres':
                    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='pending_requests'")
                    pending_columns = {row[0] for row in cursor.fetchall()}
                else:
                    cursor.execute("SHOW COLUMNS FROM pending_requests")
                    pending_columns = {row[0] for row in cursor.fetchall()}
                for column, definition in {
                    'job_id': 'INTEGER', 'owner_id': 'INTEGER',
                    'decided_at': 'TIMESTAMP', 'decided_by': 'INTEGER',
                    'last_error': 'TEXT',
                }.items():
                    if column not in pending_columns:
                        cursor.execute(f"ALTER TABLE pending_requests ADD COLUMN {column} {definition}")
                conn.commit()

            except Exception as e:
                self.logger.error(f"Failed to migrate discover_jobs table: {e}")
                # Don't raise - table might not exist yet

    # ------------------------------------------------------------------
    # Integrations helpers
    # ------------------------------------------------------------------

