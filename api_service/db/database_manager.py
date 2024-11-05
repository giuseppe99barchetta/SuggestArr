import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(BASE_DIR, 'config', 'config_files', 'requests.db')

class DatabaseManager:
    """Helper class for managing SQLite database interactions for media requests."""

    def __init__(self):
        self.db_path = DB_PATH
        self._initialize_db()

    def _initialize_db(self):
        """Initialize the SQLite database and create the requests table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    tmdb_request_id TEXT NOT NULL PRIMARY KEY,
                    media_type TEXT NOT NULL,
                    tmdb_source_id TEXT,
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    requested_by TEXT,
                    UNIQUE(media_type, tmdb_request_id, tmdb_source_id)
                )
            """)
            
            cursor.execute("""
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
                    UNIQUE(media_id, media_type)
                )
            """)

            conn.commit()

    def save_request(self, media_type, media_id, source):
        """Save a new media request to the database, ignoring duplicates."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO requests (media_type, tmdb_request_id, tmdb_source_id, requested_by)
                    VALUES (?, ?, ?, ?)
                """, (media_type, media_id, source, 'SuggestArr'))
                conn.commit()
            except sqlite3.Error as e:
                raise Exception(f"Failed to save request: {e}")

    def check_request_exists(self, media_type, media_id):
        """Check if a media request already exists in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM requests WHERE tmdb_request_id = ? AND media_type = ?
            """, (media_id, media_type))
            return cursor.fetchone() is not None
        
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

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO metadata (media_id, media_type, title, overview, release_date, 
                                                     poster_path, rating, votes, origin_country, genre_ids)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (media_id, media_type, title, overview, release_date, poster_path, rating, votes, origin_country, genre_ids))
                conn.commit()
            except sqlite3.Error as e:
                raise Exception(f"Failed to save metadata: {e}")
            
    def get_metadata(self, media_id, media_type):
        """Retrieve metadata for a media item if it exists in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT title, overview, release_date, poster_path FROM metadata
                WHERE media_id = ? AND media_type = ?
            """, (media_id, media_type))
            row = cursor.fetchone()
            if row:
                return {
                    "title": row[0],
                    "overview": row[1],
                    "release_date": row[2],
                    "poster_path": row[3]
                }
            return None

    def save_requests_batch(self, requests):
        """Save a batch of media requests to the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for request in requests:
                media_type = request['media']['mediaType']
                media_id = request['media']['tmdbId']
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO requests (media_type, tmdb_request_id, requested_by)
                        VALUES (?, ?, ?)
                    """, (media_type, media_id, 'Seer'))
                except sqlite3.Error as e:
                    raise Exception(f"Failed to save request to database: {e}")
            conn.commit()