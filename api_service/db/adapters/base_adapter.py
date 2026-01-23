"""
Abstract base class for database adapters.
Provides a consistent interface for different database implementations.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize adapter with database configuration."""
        self.config = config
        self.connection = None
    
    @abstractmethod
    def connect(self) -> None:
        """Establish database connection."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close database connection."""
        pass
    
    @abstractmethod
    def initialize_db(self) -> None:
        """Initialize database schema."""
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Execute a query and return results."""
        pass
    
    @abstractmethod
    def execute_many(self, query: str, params_list: List[Tuple]) -> None:
        """Execute a query multiple times with different parameters."""
        pass
    
    @abstractmethod
    def execute_script(self, script: str) -> None:
        """Execute a SQL script."""
        pass
    
    @abstractmethod
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict]:
        """Execute query and fetch one result."""
        pass
    
    @abstractmethod
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict]:
        """Execute query and fetch all results."""
        pass
    
    @abstractmethod
    def get_last_insert_id(self) -> int:
        """Get the ID of the last inserted row."""
        pass