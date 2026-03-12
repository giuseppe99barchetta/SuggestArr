"""
Base HTTP client with shared session management for all API clients.
"""
import aiohttp
from api_service.config.logger_manager import LoggerManager


class BaseHTTPClient:
    """
    Base class for HTTP API clients with shared session management.
    
    Provides common functionality for:
    - Async HTTP session management with configurable timeout
    - Consistent timeout configuration
    - HTTP status code validation
    - Context manager support
    """
    
    # Shared constants across all clients
    REQUEST_TIMEOUT = 10  # Timeout in seconds for HTTP requests
    HTTP_OK = {200, 201}  # Standard success HTTP status codes
    
    def __init__(self):
        """Initialize base HTTP client with logger and session."""
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create an aiohttp session with timeout configuration.
        
        Returns:
            aiohttp.ClientSession: Active HTTP session with configured timeout
        """
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """Close the HTTP session if open."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
