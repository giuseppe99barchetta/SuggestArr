import os
import sqlite3
import psycopg2
import mysql.connector
import threading
from contextlib import contextmanager
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
        self._initialized = True
        

    
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
            """
        }
        
        # Create tables
        for table_name, query in queries.items():
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Database-specific modifications
                    if self.db_type == 'mysql':
                        query = query.replace("TEXT", "VARCHAR(255)")
                    
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
                    
            except Exception as e:
                self.logger.error(f"Failed to add missing columns: {e}")
                raise DatabaseError(
                    error=f"Column addition failed: {str(e)}",
                    db_type=self.db_type
                )
    
    def ensure_connection(self):
        """Legacy method - now handled by connection pool."""
        # This method is kept for backward compatibility
        # Connection pooling handles connection management automatically
        pass
    
    def save_request(self, media_type: str, media_id: str, source: str, user_id: Optional[str] = None) -> None:
        """Save a new media request to the database, ignoring duplicates."""
        self.logger.debug(f"Saving request: {media_type} {media_id} from {source}")
        
        query = """
            INSERT OR IGNORE INTO requests (media_type, tmdb_request_id, tmdb_source_id, requested_by, user_id)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (media_type, media_id, source, 'SuggestArr', user_id)
        
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
    
    def save_metadata(self, media: Dict[str, Any], media_type: str) -> None:
        """Save metadata for a media item."""
        self.logger.debug(f"Saving metadata: {media_type} {media['id']}")
        
        media_id = media['id']
        title = media['title']
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
                s.media_id AS source_id, s.title AS source_title, s.overview AS source_overview, 
                s.release_date AS source_release_date, s.poster_path AS source_poster_path, s.rating as rating,
                r.tmdb_request_id, r.media_type, r.requested_at, s.logo_path, s.backdrop_path,
                m.title AS request_title, m.overview AS request_overview, 
                m.release_date AS request_release_date, m.poster_path AS request_poster_path, m.rating as request_rating,
                m.logo_path, m.backdrop_path
            FROM requests r
            JOIN metadata m ON r.tmdb_request_id = m.media_id
            JOIN metadata s ON r.tmdb_source_id = s.media_id
            WHERE r.requested_by = 'SuggestArr'
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
    
    def get_requests_stats(self) -> Dict[str, Any]:
        """Get statistics about requests: total and today's count."""
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

            return {
                "total": total,
                "approved": 0,  # Not handled on your side
                "pending": 0,   # Not handled on your side
                "today": today
            }
    
    def test_connection(self, db_config: Dict[str, Any]) -> Dict[str, str]:
        """Test database connection based on provided db_config."""
        self.logger.debug(f"Testing database connection with config: {db_config}")
        
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
                            media_type = request['media']['mediaType']
                            media_id = str(request['media']['tmdbId'])
                            params = (media_type, media_id, 'Seer')

                            cursor.execute(query, params)
                        except KeyError as e:
                            self.logger.error(f"Struttura richiesta non valida nel batch: {e}")
                            continue
                        
                    conn.commit()
                    self.logger.debug(f"Batch di {len(requests)} salvato correttamente")
            except Exception as e:
                self.logger.error(f"Errore durante il salvataggio del batch: {e}")
                raise DatabaseError(f"Batch save failed: {str(e)}", db_type=self.db_type)