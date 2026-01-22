"""
Simplified DatabaseManager using adapter pattern.
Provides a clean interface for database operations while delegating
to appropriate database-specific adapters.
"""
from typing import Any, Dict, List, Optional, Tuple

from api_service.config.logger_manager import LoggerManager
from api_service.db.adapter_factory import DatabaseAdapterFactory
from api_service.db.adapters.base_adapter import DatabaseAdapter


class DatabaseManager:
    """
    Simplified database manager using adapter pattern.
    Delegates database operations to appropriate adapter.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize database manager with appropriate adapter."""
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.adapter = DatabaseAdapterFactory.create_adapter(config)
        
        # Initialize database schema
        self.adapter.initialize_db()
        
    def connect(self) -> None:
        """Establish database connection."""
        self.adapter.connect()
    
    def disconnect(self) -> None:
        """Close database connection."""
        self.adapter.disconnect()
    
    def add_request(self, user_id: str, media_type: str, media_title: str, 
                   media_id: str = None) -> int:
        """Add a new media request to the database."""
        query = '''
        INSERT INTO requests (user_id, media_type, media_title, media_id)
        VALUES (?, ?, ?, ?)
        '''
        
        # Convert tuple placeholders based on database type
        if hasattr(self.adapter, '__class__') and 'PostgreSQL' in self.adapter.__class__.__name__:
            query = query.replace('?', '%s')
        elif hasattr(self.adapter, '__class__') and 'MySQL' in self.adapter.__class__.__name__:
            query = query.replace('?', '%s')
        
        params = (user_id, media_type, media_title, media_id)
        return self.adapter.execute_query(query, params)
    
    def get_all_requests(self) -> List[Dict]:
        """Retrieve all media requests."""
        query = 'SELECT * FROM requests ORDER BY created_at DESC'
        return self.adapter.fetch_all(query)
    
    def get_requests_by_user(self, user_id: str) -> List[Dict]:
        """Retrieve all requests for a specific user."""
        query = 'SELECT * FROM requests WHERE user_id = ? ORDER BY created_at DESC'
        
        # Convert tuple placeholders based on database type
        if hasattr(self.adapter, '__class__') and 'PostgreSQL' in self.adapter.__class__.__name__:
            query = query.replace('?', '%s')
        elif hasattr(self.adapter, '__class__') and 'MySQL' in self.adapter.__class__.__name__:
            query = query.replace('?', '%s')
        
        return self.adapter.fetch_all(query, (user_id,))
    
    def update_request_status(self, request_id: int, status: str) -> bool:
        """Update the status of a media request."""
        query = 'UPDATE requests SET request_status = ? WHERE id = ?'
        
        # Convert tuple placeholders based on database type
        if hasattr(self.adapter, '__class__') and 'PostgreSQL' in self.adapter.__class__.__name__:
            query = query.replace('?', '%s')
        elif hasattr(self.adapter, '__class__') and 'MySQL' in self.adapter.__class__.__name__:
            query = query.replace('?', '%s')
        
        params = (status, request_id)
        self.adapter.execute_query(query, params)
        return True
    
    def delete_request(self, request_id: int) -> bool:
        """Delete a media request."""
        query = 'DELETE FROM requests WHERE id = ?'
        
        # Convert tuple placeholders based on database type
        if hasattr(self.adapter, '__class__') and 'PostgreSQL' in self.adapter.__class__.__name__:
            query = query.replace('?', '%s')
        elif hasattr(self.adapter, '__class__') and 'MySQL' in self.adapter.__class__.__name__:
            query = query.replace('?', '%s')
        
        self.adapter.execute_query(query, (request_id,))
        return True
    
    def get_pending_requests(self) -> List[Dict]:
        """Retrieve all pending requests."""
        query = "SELECT * FROM requests WHERE request_status = 'pending' ORDER BY created_at"
        return self.adapter.fetch_all(query)
    
    def get_request_by_id(self, request_id: int) -> Optional[Dict]:
        """Retrieve a specific request by ID."""
        query = 'SELECT * FROM requests WHERE id = ?'
        
        # Convert tuple placeholders based on database type
        if hasattr(self.adapter, '__class__') and 'PostgreSQL' in self.adapter.__class__.__name__:
            query = query.replace('?', '%s')
        elif hasattr(self.adapter, '__class__') and 'MySQL' in self.adapter.__class__.__name__:
            query = query.replace('?', '%s')
        
        return self.adapter.fetch_one(query, (request_id,))
    
    # Context manager support
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()