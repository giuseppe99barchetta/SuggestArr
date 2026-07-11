import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

class MetadataMixin:
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
    
