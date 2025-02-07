import os
import sqlite3
import psycopg2
import mysql.connector

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(BASE_DIR, 'config', 'config_files', 'requests.db')
ENV_VARS = load_env_vars()
class DatabaseManager:
    """Helper class for managing SQLite database interactions for media requests."""
    def __init__(self):
        """Initialize the connection based on the DB_TYPE."""
        self.logger = LoggerManager.get_logger(self.__class__.__name__) 
        self.db_path = DB_PATH
        self.db_type = ENV_VARS.get('DB_TYPE', 'sqlite')
        self.db_connection = self._initialize_db_connection()
        self._initialize_db()
        
    def _initialize_db_connection(self):
        """Initialize the database connection based on the configured DB type."""

        if self.db_type == 'postgres':
            self.logger.debug("Using PostgreSQL database.")
            return psycopg2.connect(
                host=ENV_VARS['DB_HOST'],
                port=ENV_VARS['DB_PORT'],
                user=ENV_VARS['DB_USER'],
                password=ENV_VARS['DB_PASSWORD'],
                dbname=ENV_VARS['DB_NAME']
            )
        elif self.db_type in ['mysql', 'mariadb']:
            self.logger.debug("Using MySQL database.")
            return mysql.connector.connect(
                host=ENV_VARS['DB_HOST'],
                port=ENV_VARS['DB_PORT'],
                user=ENV_VARS['DB_USER'],
                password=ENV_VARS['DB_PASSWORD'],
                database=ENV_VARS['DB_NAME']
            )
        else:
            # Default to SQLite if DB_TYPE is not specified or is sqlite
            self.logger.debug("Using SQLite database.")
            return sqlite3.connect(self.db_path)

    def _initialize_db(self):
        """Initialize the SQLite database and create the requests table if it doesn't exist."""
        with self.db_connection as conn:
            
            query_requests ="""
                CREATE TABLE IF NOT EXISTS requests (
                    tmdb_request_id TEXT NOT NULL PRIMARY KEY,
                    media_type TEXT NOT NULL,
                    tmdb_source_id TEXT,
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    requested_by TEXT,
                    UNIQUE(media_type, tmdb_request_id, tmdb_source_id)
                )
            """            
            query_metadata = """
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
            
            self.execute_query(query_requests, commit=True)
            self.execute_query(query_metadata, commit=True)
            
    def ensure_connection(self):
        """Check and reopen the database connection if necessary."""
        if self.db_type != 'sqlite' and not self.db_connection.is_connected():
            self.logger.debug("Re-opening the database connection...")
            self.db_connection = self._initialize_db_connection()
        
    def save_request(self, media_type, media_id, source):
        """Save a new media request to the database, ignoring duplicates."""
        query = """
            INSERT INTO requests (media_type, tmdb_request_id, tmdb_source_id, requested_by)
            VALUES (?, ?, ?, ?)
        """
        params = (media_type, media_id, source, 'SuggestArr')
        self.execute_query(query, params, commit=True)

    def check_request_exists(self, media_type, media_id):
        """Check if a media request already exists in the database."""
        query = """
            SELECT 1 FROM requests WHERE tmdb_request_id = ? AND media_type = ?
        """
        params = (media_id, media_type)
        result = self.execute_query(query, params)
        return result is not None and len(result) > 0
        
    def save_metadata(self, media, media_type):
        """Save metadata for a media item."""
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
            INSERT OR REPLACE INTO metadata (media_id, media_type, title, overview, release_date, 
                                             poster_path, rating, votes, origin_country, genre_ids, logo_path, backdrop_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (media_id, media_type, title, overview, release_date, poster_path, rating, votes, origin_country, genre_ids, logo_path, backdrop_path)
        self.execute_query(query, params, commit=True)
            
    def get_metadata(self, media_id, media_type):
        """Retrieve metadata for a media item if it exists in the database."""
        query = """
            SELECT title, overview, release_date, poster_path FROM metadata
            WHERE media_id = ? AND media_type = ?
        """
        params = (media_id, media_type)
        result = self.execute_query(query, params)

        if result:
            row = result[0]  # Assuming there's at least one row
            return {
                "title": row[0],
                "overview": row[1],
                "release_date": row[2],
                "poster_path": row[3]
            }
        return None

    def save_requests_batch(self, requests):
        """Save a batch of media requests to the database."""
        for request in requests:
            media_type = request['media']['mediaType']
            media_id = request['media']['tmdbId']
            query = """
                INSERT INTO requests (media_type, tmdb_request_id, requested_by)
                VALUES (?, ?, ?)
            """
            params = (media_type, media_id, 'Seer')
            self.execute_query(query, params, commit=True)
            
    def get_all_requests_grouped_by_source(self, page=1, per_page=8):
        """Retrieve all requests grouped by source."""
        query = """
            SELECT 
                s.media_id AS source_id, s.title AS source_title, s.overview AS source_overview, 
                s.release_date AS source_release_date, s.poster_path AS source_poster_path, s.rating as rating,
                r.tmdb_request_id, r.media_type, r.requested_at, s.logo_path, s.backdrop_path,
                m.title AS request_title, m.overview AS request_overview, 
                m.release_date AS request_release_date, m.poster_path AS request_poster_path, m.rating as rating,
                m.logo_path, m.backdrop_path
            FROM requests r
            JOIN metadata m ON r.tmdb_request_id = m.media_id
            JOIN metadata s ON r.tmdb_source_id = s.media_id
            WHERE r.requested_by = 'SuggestArr'
            ORDER BY s.media_id, r.requested_at
        """
        result = self.execute_query(query)

        # Group requests by source_id
        sources = {}
        for row in result:
            source_id = row[0]
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

            # Add the individual request to the source's list of requests
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

        # Paginate the sources
        source_list = list(sources.values())
        total_items = len(source_list)
        total_pages = (total_items + per_page - 1) // per_page  # Calculate total pages
        paginated_data = source_list[(page - 1) * per_page: page * per_page]

        return {
            "data": paginated_data,
            "total_pages": total_pages
        }

    def test_connection(self, db_config):
        """Test the database connection based on the provided db_config."""
        try:
            db_type = db_config.get('DB_TYPE', 'sqlite')

            if db_type == 'postgres':
                # Test PostgreSQL connection
                connection = psycopg2.connect(
                    host=db_config['DB_HOST'],
                    port=db_config['DB_PORT'],
                    user=db_config['DB_USER'],
                    password=db_config['DB_PASSWORD'],
                    dbname=db_config['DB_NAME']
                )
                connection.close()
            elif db_type in ['mysql', 'mariadb']:
                # Test MySQL/MariaDB connection
                connection = mysql.connector.connect(
                    host=db_config['DB_HOST'],
                    port=db_config['DB_PORT'],
                    user=db_config['DB_USER'],
                    password=db_config['DB_PASSWORD'],
                    database=db_config['DB_NAME']
                )
                connection.close()

            return {'status': 'success', 'message': 'Database connection successful!'}
        except Exception as e:
            self.logger.error(f"Error testing database connection: {str(e)}")
            return {'status': 'error', 'message': f"Error testing database connection: {str(e)}"}
        
    def handle_sql_error(self, error, db_type):
        """Centralized error handling for SQL operations."""
        if db_type == 'sqlite':
            error_msg = f"SQLite error: {str(error)}"
        elif db_type == 'postgres':
            error_msg = f"PostgreSQL error: {str(error)}"
        elif db_type in ['mysql', 'mariadb']:
            error_msg = f"MySQL error: {str(error)}"
        else:
            error_msg = f"Unknown DB error: {str(error)}"

        raise Exception(error_msg)
    
    def execute_query(self, query, params=None, commit=False):
        """Execute a query on the database, handling different DB types."""
        self.ensure_connection()

        # Use the default parameter value as an empty tuple if None
        if params is None:
            params = ()

        db_type = ENV_VARS.get('DB_TYPE', 'sqlite')

        try:
            with self.db_connection as conn:
                cursor = conn.cursor()

                if db_type == 'mysql':
                    query = query.replace("INSERT", "INSERT IGNORE", 1)
                    query = query.replace("?", "%s")
                    query = query.replace("TEXT", "VARCHAR(255)")
                elif db_type == 'sqlite':
                    query = query.replace("INSERT", "INSERT OR IGNORE", 1)
                elif db_type == 'postgres':
                    if "INSERT INTO" in query and "ON CONFLICT" not in query:
                        query = query.rstrip() + " ON CONFLICT DO NOTHING"
                    query = query.replace("?", "%s")  

                # Execute the query depending on the DB type
                cursor.execute(query, params)

                # Commit if specified
                if commit:
                    conn.commit()

                return cursor.fetchall()  # For SELECT queries

        except (sqlite3.Error, psycopg2.Error, mysql.connector.Error) as e:
            self.handle_sql_error(f"Error executing query: {e}", db_type, query)
            return None
