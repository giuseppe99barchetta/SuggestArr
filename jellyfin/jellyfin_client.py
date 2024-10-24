"""
This module provides the JellyfinClient class for interacting with the Jellyfin API.
The client can retrieve users, recent items, and provider IDs for media content.

Classes:
    - JellyfinClient: A class that handles communication with the Jellyfin API.
"""
import re
import aiohttp
from config.logger_manager import LoggerManager

# Constants
REQUEST_TIMEOUT = 10  # Timeout in seconds for HTTP requests


class JellyfinClient:
    """
    A client to interact with the Jellyfin API, allowing the retrieval of users, recent items,
    and media provider IDs.
    """

    def __init__(self, api_url, token, max_content=10, library_ids=None):
        """
        Initializes the JellyfinClient with the provided API URL and token.
        :param api_url: The base URL for the Jellyfin API.
        :param token: The authentication token for Jellyfin.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.max_content_fetch = max_content
        self.api_url = api_url
        self.libraries = library_ids
        self.headers = {"X-Emby-Token": token}

    async def get_all_users(self):
        """
        Retrieves a list of all users from the Jellyfin server asynchronously.
        :return: A list of users in JSON format if successful, otherwise an empty list.
        """
        url = f"{self.api_url}/Users"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    self.logger.error("Failed to retrieve users: %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving users: %s", str(e))

        return []

    async def get_recent_items(self, user_id):
        """
        Retrieves a list of recently played items for a given user from specific libraries asynchronously.
        :param user_id: The ID of the user whose recent items are to be retrieved.
        :return: A combined list of recent items from all specified libraries.
        """
        self.logger.info("Searching for last %s viewed content for user: %s.", self.max_content_fetch, user_id)

        results_by_library = {}

        url = f"{self.api_url}/Users/{user_id}/Items"

        for library in self.libraries:
            params = {
                "SortBy": "DatePlayed",
                "SortOrder": "Descending",
                "Filters": "IsPlayed",
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Episode",
                "Limit": self.max_content_fetch,
                "ParentID": library.get('id')
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=self.headers, params=params, timeout=REQUEST_TIMEOUT) as response:
                        if response.status == 200:
                            library_items = await response.json()
                            results_by_library[library.get('name')] = library_items.get('Items', [])
                        else:
                            self.logger.error(
                                "Failed to get recent items for library %s (user %s): %d", library.get('name'), user_id, response.status)
            except aiohttp.ClientError as e:
                self.logger.error(
                    "An error occurred while retrieving recent items for library %s (user %s): %s", library.get('name'), user_id, str(e))

        return results_by_library if results_by_library else None
    
    async def get_libraries(self):
        """
        Retrieves list of library asynchronously.
        """
        self.logger.info("Searching Jellyfin libraries.")

        url = f"{self.api_url}/Library/VirtualFolders"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        return await response.json()
                    self.logger.error(
                        "Failed to get libraries %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error(
                "An error occurred while retrieving libraries: %s", str(e))

    async def get_item_provider_id(self, user_id, item_id, provider='Tmdb'):
        """
        Retrieves the provider ID (e.g., TMDb or TVDb) for a specific media item asynchronously.
        :param user_id: The ID of the user.
        :param item_id: The ID of the media item.
        :param provider: The provider ID to retrieve (default is 'Tmdb').
        :return: The provider ID if found, otherwise None.
        """
        url = f"{self.api_url}/Users/{user_id}/Items/{item_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        item_data = await response.json()
                        return item_data.get('ProviderIds', {}).get(provider)

                    self.logger.error("Failed to retrieve ID for item %s: %d", item_id, response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving ID for item %s: %s", item_id, str(e))

        return None
