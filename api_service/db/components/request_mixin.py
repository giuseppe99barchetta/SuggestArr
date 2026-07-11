import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from api_service.exceptions.database_exceptions import DatabaseError

class RequestMixin:
    def save_request(self, media_type: str, media_id: str, source: str, user_id: Optional[str] = None, is_anime: bool = False, rationale: Optional[str] = None, source_origin: Optional[str] = None) -> None:
        """Save a new media request to the database, ignoring duplicates."""
        self.logger.debug(f"Saving request: {media_type} {media_id} from {source} (anime={is_anime}, origin={source_origin})")

        query = """

            INSERT OR IGNORE INTO requests (media_type, tmdb_request_id, tmdb_source_id, source_origin, requested_by, user_id, is_anime, rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (media_type, str(media_id), source, source_origin, 'SuggestArr', user_id, is_anime, rationale)
        
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

    def check_requests_exist_batch(self, media_type: str, media_ids: List[str]) -> Set[str]:
        """Check which of the provided media IDs already have requests in the database.
        
        :param media_type: 'movie' or 'tv'.
        :param media_ids: List of TMDB IDs as strings.
        :return: Set of TMDB IDs that already exist in the database.
        """
        if not media_ids:
            return set()

        self.logger.debug("Checking bulk requests exists: %s for %d items", media_type, len(media_ids))
        
        placeholders = ', '.join(['%s' if self.db_type in ['mysql', 'postgres'] else '?' for _ in media_ids])
        query = f"SELECT tmdb_request_id FROM requests WHERE media_type = ? AND tmdb_request_id IN ({placeholders})"
        
        params = [media_type] + [str(mid) for mid in media_ids]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if self.db_type in ['mysql', 'postgres']:
                query = query.replace("?", "%s", 1) # Only replace the first ? for media_type
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            return {str(row[0]) for row in results}
    
    def get_all_requests_grouped_by_source(self, page: int = 1, per_page: int = 8, sort_by: str = 'date-desc') -> Dict[str, Any]:
        """Retrieve all requests grouped by source with dynamic sorting and pagination."""
        self.logger.debug(f"Retrieving all requests grouped by source: page={page}, per_page={per_page}, sort_by={sort_by}")
    
        count_query = """
            SELECT 
                COUNT(DISTINCT COALESCE(s.media_id, r.tmdb_source_id, '0')) as total_sources,
                COUNT(r.tmdb_request_id) as total_requests
            FROM requests r
            JOIN metadata m ON r.tmdb_request_id = m.media_id AND r.media_type = m.media_type
            LEFT JOIN metadata s ON r.tmdb_source_id = s.media_id
            WHERE r.requested_by = 'SuggestArr'
            AND COALESCE(r.tmdb_source_id, '') != 'ai_search'
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

        from api_service.services.request_sources import request_source_title_sql
        source_title_expr = request_source_title_sql("r")
    
        query = f"""
            SELECT
                COALESCE(s.media_id, r.tmdb_source_id, '0') AS source_id,
                {source_title_expr} AS source_title,
                s.overview AS source_overview,
                s.release_date AS source_release_date, s.poster_path AS source_poster_path, s.rating as rating,
                r.tmdb_request_id, r.media_type, r.requested_at, s.logo_path, s.backdrop_path,
                m.title AS request_title, m.overview AS request_overview,
                m.release_date AS request_release_date, m.poster_path AS request_poster_path, m.rating as request_rating,
                m.logo_path, m.backdrop_path, r.is_anime, r.rationale,
                r.user_id, u.user_name, r.source_origin
            FROM requests r
            JOIN metadata m ON r.tmdb_request_id = m.media_id AND r.media_type = m.media_type
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
                "source_origin": row[22] if len(row) > 22 else None,
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

        Used by AI Search to exclude items that have already been sent to Seer,
        whether through the normal automation or through the AI Search feature.

        :return: Set of tmdb_request_id strings.
        """
        query = "SELECT DISTINCT tmdb_request_id FROM requests WHERE requested_by = 'SuggestArr'"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return {str(row[0]) for row in cursor.fetchall()}

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

