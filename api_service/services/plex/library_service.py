"""
Plex library management service.
"""
from typing import List, Dict, Any

from api_service.services.plex.base_client import PlexBaseClient


class PlexLibraryService(PlexBaseClient):
    """
    Service for managing Plex libraries.
    Handles library retrieval and content management.
    """
    
    async def get_libraries(self) -> List[Dict[str, Any]]:
        """
        Retrieve all libraries from the Plex server.
        
        Returns:
            List of library dictionaries with title, type, key, etc.
            
        Raises:
            PlexConnectionError: If API request fails
        """
        url = f"{self.api_url}/library/sections"
        response_data = await self._make_request(url)
        
        if not response_data or 'Directory' not in response_data:
            return []
        
        libraries = response_data['Directory']
        self.logger.info(f"Successfully retrieved {len(libraries)} libraries from Plex")
        
        return libraries
    
    async def get_library_by_id(self, library_id: str) -> Dict[str, Any]:
        """
        Retrieve specific library by ID.
        
        Args:
            library_id: Library ID to retrieve
            
        Returns:
            Library dictionary
            
        Raises:
            PlexConnectionError: If API request fails
        """
        url = f"{self.api_url}/library/sections/{library_id}"
        return await self._make_request(url)
    
    async def get_library_items(self, library_id: str, start: int = 0, size: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve items from a specific library.
        
        Args:
            library_id: Library ID
            start: Starting offset
            size: Number of items to retrieve
            
        Returns:
            List of library items
            
        Raises:
            PlexConnectionError: If API request fails
        """
        url = f"{self.api_url}/library/sections/{library_id}/all"
        params = f"X-Plex-Container-Start={start}&X-Plex-Container-Size={size}"
        full_url = f"{url}?{params}"
        
        response_data = await self._make_request(full_url)
        
        if not response_data or 'Metadata' not in response_data:
            return []
            
        items = response_data['Metadata']
        self.logger.info(f"Retrieved {len(items)} items from library {library_id}")
        
        return items
    
    async def filter_libraries_by_type(self, media_type: str = None) -> List[Dict[str, Any]]:
        """
        Filter libraries by media type.
        
        Args:
            media_type: Media type to filter ('movie', 'show', 'artist')
            
        Returns:
            List of filtered libraries
        """
        libraries = await self.get_libraries()
        
        if media_type is None:
            return libraries
        
        # Map media types to Plex types
        type_mapping = {
            'movie': 'movie',
            'show': 'show', 
            'series': 'show',
            'artist': 'artist',
            'music': 'artist'
        }
        
        plex_type = type_mapping.get(media_type.lower())
        if plex_type is None:
            return []
        
        return [lib for lib in libraries if lib.get('type') == plex_type]