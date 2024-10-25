"""
This module provides the PlexClient class for interacting with the Plex API.
The client can retrieve users, recent items, and libraries.

Classes:
    - PlexClient: A class that handles communication with the Plex API.
"""
import aiohttp
from api_service.config.logger_manager import LoggerManager

# Constants
REQUEST_TIMEOUT = 10  # Timeout in seconds for HTTP requests


class PlexClient:
    """
    A client to interact with the Plex API, allowing the retrieval of users, recent items,
    and libraries.
    """

    def __init__(self, token, api_url=None, max_content=10, library_ids=None, client_id=None):
        """
        Initializes the PlexClient with the provided API URL and token.
        :param api_url: The base URL for the Plex API.
        :param token: The authentication token for Plex.
        :param max_content: Maximum number of recent items to fetch.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.max_content_fetch = max_content
        self.api_url = api_url
        self.library_ids = library_ids
        self.base_url = 'https://plex.tv/api/v2'
        self.headers = {
            "X-Plex-Token": token, 
            "Accept": 'application/json'
        }
        
        if client_id:
            self.headers['X-Plex-Client-Identifier'] = client_id

    async def get_all_users(self):
        """
        Retrieves a list of all users from the Plex server asynchronously.
        :return: A list of users in JSON format if successful, otherwise an empty list.
        """
        url = f"{self.api_url}/accounts"  # Plex endpoint for users
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('accounts', [])
                    self.logger.error("Failed to retrieve users: %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving users: %s", str(e))

        return []

    async def get_recent_items(self):
        """
        Retrieves a list of recently viewed items asynchronously.
        :return: A list of recent items in JSON format if successful, otherwise an empty list.
        """
        url = f"{self.api_url}/status/sessions/history/all"
        params = {
            "sort": "viewedAt:desc",
        }
        
        if self.library_ids:
            params["librarySectionIDs"] = ','.join(self.library_ids)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        data = await response.json()
                        metadata = data.get('MediaContainer', {}).get('Metadata', [])
                        # Filter the items while respecting the max content fetch limit
                        filtered_items = await self.filter_recent_items(metadata)
                        self.logger.info(f"Returning {len(filtered_items)} filtered recent items.")
                        return filtered_items

                    self.logger.error("Failed to retrieve recent items: %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving recent items: %s", str(e))

        return []


    async def filter_recent_items(self, metadata):
        """
        Filters recent items to avoid duplicates and respects the max content fetch limit.
        :param metadata: List of items to filter.
        :return: Filtered list of items.
        """
        seen_series = set()
        filtered_items = []
        total_items = 0  # Counter for total filtered items
    
        for item in metadata:
            # Check if the item's librarySectionID is in the selected libraries
            if self.library_ids and item.get('librarySectionID') not in self.library_ids:
                continue  # Skip items not in the selected libraries
            
            # Check if we've reached the max content fetch limit
            if total_items >= int(self.max_content_fetch):
                break
            
            if item['type'] == 'episode':
                # Check if the series has already been counted
                series_title = item['grandparentTitle']
                if series_title not in seen_series:
                    seen_series.add(series_title)
                    filtered_items.append(item)
                    total_items += 1  # Increment total_items for series
            else:
                filtered_items.append(item)
                total_items += 1  # Increment total_items for movies
    
            # Allow fetching more content if we've only seen episodes from one series
            if total_items < int(self.max_content_fetch) and len(seen_series) == 1:
                continue  # Keep looking for more items
            
        return filtered_items

    async def get_libraries(self):
        """
        Retrieves a list of libraries (sections) from the Plex server asynchronously.
        :return: A list of libraries in JSON format if successful, otherwise an empty list.
        """
        self.logger.info("Fetching libraries from Plex.")

        url = f"{self.api_url}/library/sections"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('MediaContainer', {}).get('Directory', [])
                    self.logger.error("Failed to retrieve libraries: %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving libraries: %s", str(e))

        return []

    async def get_metadata_provider_id(self, item_id, provider='tmdb'):
        """
        Retrieves the TMDB ID (or other provider ID) for a specific media item asynchronously.
        :param item_id: The ID of the media item.
        :param provider: The provider ID to retrieve (default is 'themoviedb').
        :return: The TMDB ID if found, otherwise None.
        """
        url = f"{self.api_url}{item_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        item_data = await response.json()
                        guids = item_data.get('MediaContainer', {}).get('Metadata', [])[0].get('Guid', [])

                        for guid in guids:
                            guid_id = guid.get('id', '')
                            if guid_id.startswith(f'{provider}://'):
                                tmdb_id = guid_id.split(f'{provider}://')[-1]
                                return tmdb_id

                    self.logger.error("Failed to retrieve metadata for item %s: %d", item_id, response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving metadata for item %s: %s", item_id, str(e))

        return None
    
    async def get_servers(self):
        """
        obtain available Plex server for current user
        :return: Lista di server Plex se trovati, altrimenti None.
        """
        url = f"{self.base_url}/resources"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=10) as response:
                    if response.status == 200:
                        servers = await response.json()
                        return servers
                    else:
                        print(f"Errore durante il recupero dei server Plex: {response.status}")
                        return None
        except aiohttp.ClientError as e:
            print(f"Errore durante il recupero dei server Plex: {str(e)}")
            return None