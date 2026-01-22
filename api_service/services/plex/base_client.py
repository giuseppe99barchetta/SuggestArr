"""
Plex API client base class with common HTTP functionality.
"""
import asyncio
import aiohttp
from typing import Optional, Dict, Any

from api_service.config.logger_manager import LoggerManager
from api_service.exceptions.api_exceptions import PlexConnectionError


class PlexBaseClient:
    """
    Base Plex client with common HTTP functionality.
    Handles authentication, HTTP requests, and basic utilities.
    """
    
    def __init__(self, token: str, api_url: Optional[str] = None, request_timeout: int = 10):
        """
        Initialize base Plex client.
        
        Args:
            token: Plex authentication token
            api_url: Plex server URL
            request_timeout: HTTP request timeout in seconds
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.token = token
        self.api_url = api_url
        self.request_timeout = request_timeout
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self.session is None or self.session.closed:
            headers = {
                'X-Plex-Token': self.token,
                'Accept': 'application/json'
            }
            timeout = aiohttp.ClientTimeout(total=self.request_timeout)
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self.session
    
    async def _make_request(self, url: str) -> Dict[str, Any]:
        """
        Make HTTP GET request to Plex API.
        
        Args:
            url: Full URL to request
            
        Returns:
            JSON response data
            
        Raises:
            PlexConnectionError: If request fails
        """
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_msg = f"HTTP {response.status}: {response.reason}"
                    self.logger.error(f"Plex API request failed: {error_msg}")
                    raise PlexConnectionError(error_msg)
                    
        except aiohttp.ClientError as e:
            error_msg = f"Network error: {str(e)}"
            self.logger.error(f"Plex connection failed: {error_msg}")
            raise PlexConnectionError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(f"Plex request failed: {error_msg}")
            raise PlexConnectionError(error_msg)
    
    async def close(self):
        """Close HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()