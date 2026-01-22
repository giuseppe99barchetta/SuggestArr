"""
Plex user management service.
"""
from typing import List, Dict, Any

from api_service.services.plex.base_client import PlexBaseClient


class PlexUserService(PlexBaseClient):
    """
    Service for managing Plex users.
    Handles user retrieval and filtering operations.
    """
    
    async def get_all_users(self) -> List[Dict[str, Any]]:
        """
        Retrieve all users from the Plex server.
        
        Returns:
            List of user dictionaries with id, name, email, etc.
            
        Raises:
            PlexConnectionError: If API request fails
        """
        url = f"{self.api_url}/users"
        response_data = await self._make_request(url)
        
        if not response_data or '_embedded' not in response_data:
            return []
        
        users_data = response_data['_embedded']['Account']
        
        # Filter unique users by ID
        unique_users = {}
        for user in users_data:
            user_id = user.get('id')
            if user_id not in unique_users:
                # Filter out unwanted fields
                filtered_user = {
                    'id': user.get('id'),
                    'title': user.get('title'),
                    'username': user.get('username'),
                    'email': user.get('email'),
                    'thumb': user.get('thumb'),
                    'realm': user.get('realm'),
                    'key': user.get('key')
                }
                unique_users[user_id] = filtered_user
        
        sorted_users = sorted(unique_users.values(), key=lambda x: x['id'])
        self.logger.info(f"Successfully retrieved {len(sorted_users)} unique users from Plex")
        
        return sorted_users
    
    async def get_user_by_id(self, user_id: str) -> Dict[str, Any]:
        """
        Retrieve specific user by ID.
        
        Args:
            user_id: Plex user ID
            
        Returns:
            User dictionary
            
        Raises:
            PlexConnectionError: If API request fails
        """
        url = f"{self.api_url}/users/{user_id}"
        return await self._make_request(url)
    
    async def filter_users_by_role(self, role: str = None) -> List[Dict[str, Any]]:
        """
        Filter users by role or criteria.
        
        Args:
            role: Optional role to filter by
            
        Returns:
            List of filtered users
        """
        users = await self.get_all_users()
        
        if role is None:
            return users
        
        # Example filtering logic - can be expanded
        if role == 'admins':
            return [user for user in users if user.get('realm') == 'com.plexapp.plugins.myplex']
        elif role == 'regular':
            return [user for user in users if user.get('realm') != 'com.plexapp.plugins.myplex']
        
        return users