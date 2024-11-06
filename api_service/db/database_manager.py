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
                    logo_path TEXT,
                    backdrop_path TEXT,
                    UNIQUE(media_id, media_type)
                )
            """)
            
            # Check and add new columns if they don't exist
            cursor.execute("PRAGMA table_info(metadata)")
            existing_columns = [row[1] for row in cursor.fetchall()]
    
            if "logo_path" not in existing_columns:
                cursor.execute("ALTER TABLE metadata ADD COLUMN logo_path TEXT")
                print("Added column 'logo_path' to 'metadata' table.")
    
            if "backdrop_path" not in existing_columns:
                cursor.execute("ALTER TABLE metadata ADD COLUMN backdrop_path TEXT")
                print("Added column 'backdrop_path' to 'metadata' table.")
    
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
        logo_path = media.get('logo_path', '')
        backdrop_path = media.get('backdrop_path', '')

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO metadata (media_id, media_type, title, overview, release_date, 
                                                     poster_path, rating, votes, origin_country, genre_ids, logo_path, backdrop_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (media_id, media_type, title, overview, release_date, poster_path, rating, votes, origin_country, genre_ids, logo_path, backdrop_path))
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
            
    def get_all_requests_grouped_by_source(self, page=1, per_page=8):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
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
            """)
            rows = cursor.fetchall()
            
            # Group requests by source_id
            sources = {}
            for row in rows:
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
                        "backdrop_path": row[10],  # Added backdrop_path
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
                    "backdrop_path": row[17],  # Added backdrop_path for request
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
