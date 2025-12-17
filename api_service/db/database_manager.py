import os
import re
import sqlite3
import psycopg2
import mysql.connector

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.exceptions.database_exceptions import DatabaseError

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(BASE_DIR, 'config', 'config_files', 'requests.db')

class DatabaseManager:
    """Helper class for managing SQLite database interactions for media requests."""
    def __init__(self):
        """Initialize the connection based on the DB_TYPE."""
        self.logger = LoggerManager.get_logger(self.__class__.__name__) 
        self.db_path = DB_PATH
        self.env_vars = load_env_vars()
        self.db_type = self.env_vars.get('DB_TYPE', 'sqlite')
        self.db_connection = self._initialize_db_connection()
        
    def _initialize_db_connection(self):
        """Initialize the database connection based on the configured DB type."""

        if self.db_type == 'postgres':
            return psycopg2.connect(
                host=self.env_vars['DB_HOST'],
                port=self.env_vars['DB_PORT'],
                user=self.env_vars['DB_USER'],
                password=self.env_vars['DB_PASSWORD'],
                dbname=self.env_vars['DB_NAME']
            )
        elif self.db_type in ['mysql', 'mariadb']:
            return mysql.connector.connect(
                host=self.env_vars['DB_HOST'],
                port=self.env_vars['DB_PORT'],
                user=self.env_vars['DB_USER'],
                password=self.env_vars['DB_PASSWORD'],
                database=self.env_vars['DB_NAME']
            )
        else:
            # Default to SQLite if DB_TYPE is not specified or is sqlite
            return sqlite3.connect(self.db_path)

    def initialize_db(self):
        """Initialize the database and create the requests table if it doesn't exist."""
        self.logger.info(f"Initializing {self.db_type} database.")
            
        query_users = """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                user_name TEXT
            )
        """
        query_requests ="""
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
        
        if self.execute_query(query_users, commit=True):
            self.logger.info("User table created successfully.")
        else:
            self.logger.info("User table already exists. Skipping creation.")
        
        if self.execute_query(query_requests, commit=True):
            self.logger.info("Requests table created successfully.")
        else:
            self.logger.info("Requests table already exists. Skipping creation.")

        if self.execute_query(query_metadata, commit=True):
            self.logger.info("Metadata table created successfully.")
        else:
            self.logger.info("Metadata table already exists. Skipping creation.")
            
        self.add_missing_columns()
        
                
    def add_missing_columns(self):
        """Check and add missing columns to the requests table."""
        self.logger.info("Checking for missing columns in requests table...")

        if self.db_type == 'sqlite':
            query = "PRAGMA table_info(requests);"
            existing_columns = {row[1] for row in self.execute_query(query)}
        elif self.db_type == 'postgres':
            query = """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'requests';
            """
            existing_columns = {row[0] for row in self.execute_query(query)}
        elif self.db_type in ['mysql', 'mariadb']:
            query = "SHOW COLUMNS FROM requests;"
            existing_columns = {row[0] for row in self.execute_query(query)}
        else:
            self.logger.warning(f"Unsupported DB type: {self.db_type}")
            return

        if 'user_id' not in existing_columns:
            self.logger.info("Adding column user_id...")
            self.execute_query("ALTER TABLE requests ADD COLUMN user_id TEXT;", commit=True)
            
    def ensure_connection(self):
        """Check and reopen the database connection if necessary."""
        if self.db_type == 'mysql' and not self.db_connection.is_connected():
            self.logger.debug("Re-opening the database connection...")
            self.db_connection = self._initialize_db_connection()
        
    def save_request(self, media_type, media_id, source, user_id=None):
        """Save a new media request to the database, ignoring duplicates."""
        self.logger.debug(f"Saving request: {media_type} {media_id} from {source}")
        
        query = """
            INSERT OR IGNORE INTO requests (media_type, tmdb_request_id, tmdb_source_id, requested_by, user_id)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (media_type, media_id, source, 'SuggestArr', user_id)
        self.execute_query(query, params, commit=True)
        
    def save_user(self, user):
        """Save a new user to the database, ignoring duplicates."""
        self.logger.debug(f"Saving user: {user['id']} {user['name']}")
        
        query = """
            INSERT OR IGNORE INTO users (user_id, user_name)
            VALUES (?, ?)
        """
        params = (user['id'], user['name'])
        self.execute_query(query, params, commit=True)

    def check_request_exists(self, media_type, media_id):
        """Check if a media request already exists in the database."""
        self.logger.debug(f"Checking if request exists: {media_type} {media_id}")
        
        query = """
            SELECT 1 FROM requests WHERE tmdb_request_id = ? AND media_type = ?
        """
        params = (str(media_id), media_type)
        result = self.execute_query(query, params)
        return result is not None and len(result) > 0
        
    def save_metadata(self, media, media_type):
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
        params = (media_id, media_type, title, overview, release_date, poster_path, rating, votes, origin_country, genre_ids, logo_path, backdrop_path)
        self.execute_query(query, params, commit=True)
            
    def get_metadata(self, media_id, media_type):
        """Retrieve metadata for a media item if it exists in the database."""
        self.logger.debug(f"Retrieving metadata: {media_type} {media_id}")
        
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
        self.logger.debug(f"Saving batch of requests: {len(requests)} requests")

        for request in requests:
            media_type = request['media']['mediaType']
            media_id = request['media']['tmdbId']
            query = """
                INSERT OR IGNORE INTO requests (media_type, tmdb_request_id, requested_by)
                VALUES (?, ?, ?)
            """
            params = (media_type, media_id, 'Seer')
            self.execute_query(query, params, commit=True)
            
    def get_all_requests_grouped_by_source(self, page=1, per_page=8, sort_by='date-desc'):
        """Retrieve all requests grouped by source with dynamic sorting."""
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

        count_result = self.execute_query(count_query)
        total_sources = count_result[0][0] if count_result else 0
        total_requests = count_result[0][1] if count_result else 0

        # Map sort_by to SQL ORDER BY clause
        sort_mapping = {
            'date-desc': 's.media_id DESC, r.requested_at DESC',
            'date-asc': 's.media_id ASC, r.requested_at ASC',
            'title-asc': 's.title ASC, r.requested_at DESC',
            'title-desc': 's.title DESC, r.requested_at DESC',
            'rating-desc': 's.rating DESC NULLS LAST, r.requested_at DESC',
            'rating-asc': 's.rating ASC NULLS LAST, r.requested_at DESC'
        }

        # Get the ORDER BY clause, default to date-desc if invalid
        order_by_clause = sort_mapping.get(sort_by, sort_mapping['date-desc'])

        query = f"""
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
            ORDER BY {order_by_clause}
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

        # Sort the sources list based on sort_by BEFORE pagination
        source_list = list(sources.values())

        # Apply sorting to the source_list
        if sort_by == 'date-desc':
            source_list.sort(key=lambda x: x['source_id'], reverse=True)
        elif sort_by == 'date-asc':
            source_list.sort(key=lambda x: x['source_id'])
        elif sort_by == 'title-asc':
            source_list.sort(key=lambda x: (x['source_title'] or '').lower())
        elif sort_by == 'title-desc':
            source_list.sort(key=lambda x: (x['source_title'] or '').lower(), reverse=True)
        elif sort_by == 'rating-desc':
            source_list.sort(key=lambda x: (x['rating'] if x['rating'] is not None else -1), reverse=True)
        elif sort_by == 'rating-asc':
            source_list.sort(key=lambda x: (x['rating'] if x['rating'] is not None else float('inf')))

        # Paginate the sources AFTER sorting
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


    def test_connection(self, db_config):
        """Test the database connection based on the provided db_config."""
        self.logger.debug(f"Testing database connection with config: {db_config}")
        
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
        
    def execute_query(self, query, params=None, commit=False):
        """Execute a query on the database, handling different DB types."""
        self.ensure_connection()

        # Use the default parameter value as an empty tuple if None
        if params is None:
            params = ()

        try:
            with self.db_connection as conn:
                cursor = conn.cursor()
                
                if self.db_type == 'sqlite':
                    cursor.execute("PRAGMA foreign_keys = ON;") # Enable foreign key constraints
                    
                if self.db_type == 'mysql':
                    query = query.replace("INSERT OR IGNORE", "INSERT IGNORE", 1)
                    query = query.replace("?", "%s")
                    query = query.replace("TEXT", "VARCHAR(255)")
                elif self.db_type == 'postgres':
                    query = query.replace("INSERT OR IGNORE", "INSERT")
                    if "INSERT INTO" in query and "ON CONFLICT" not in query:
                        query = query.rstrip() + " ON CONFLICT DO NOTHING"
                    query = query.replace("?", "%s")  

                # Execute the query depending on the DB type
                cursor.execute(query, params)

                # Commit if specified
                if commit:
                    conn.commit()
                    
                # Check if the query is a CREATE TABLE statement and return True if the table was created successfully
                if 'CREATE TABLE' in query.upper():
                    return cursor.rowcount != -1

                if 'SELECT' in query.upper() or 'PRAGMA' in query.upper() or 'SHOW' in query.upper():
                    return cursor.fetchall() or []

        except (sqlite3.Error, psycopg2.Error, mysql.connector.Error) as e:
            raise DatabaseError(error=f"Error executing query. Details: {str(e)}", db_type=self.db_type)

    def get_requests_stats(self):
        """Get statistics about requests: total and today's count."""
        self.logger.debug("Retrieving request statistics")
        
        # Query for total requests
        total_query = """
            SELECT COUNT(*) FROM requests
            WHERE requested_by = 'SuggestArr'
        """
        total_result = self.execute_query(total_query)
        total = total_result[0][0] if total_result else 0
        
        # Query for today's requests
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
            
        today_result = self.execute_query(today_query)
        today = today_result[0][0] if today_result else 0
        
        return {
            "total": total,
            "approved": 0,  # Non gestito lato tuo
            "pending": 0,   # Non gestito lato tuo
            "today": today
        }
    