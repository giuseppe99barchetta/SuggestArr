"""
This module provides the JellyfinClient class for interacting with the Jellyfin API.
The client can retrieve users, recent items, and provider IDs for media content.

Classes:
    - JellyfinClient: A class that handles communication with the Jellyfin API.
"""
import aiohttp
from config.logger_manager import LoggerManager

# Constants
REQUEST_TIMEOUT = 10  # Timeout in seconds for HTTP requests


class JellyfinClient:
    """
    A client to interact with the Jellyfin API, allowing the retrieval of users, recent items,
    and media provider IDs.
    """

    def __init__(self, api_url, token):
        """
        Initializes the JellyfinClient with the provided API URL and token.
        :param api_url: The base URL for the Jellyfin API.
        :param token: The authentication token for Jellyfin.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.api_url = api_url
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
                        data = await response.json()  # 'await' for async json parsing
                        return data
                    self.logger.error("Failed to retrieve users: %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving users: %s", str(e))

        return []

    async def get_recent_items(self, user_id, limit=100):
        """
        Retrieves a list of recently played items for a given user asynchronously.
        :param user_id: The ID of the user whose recent items are to be retrieved.
        :param limit: The maximum number of recent items to retrieve (default is 100).
        :return: A list of recent items in JSON format if successful, otherwise None.
        """
        url = f"{self.api_url}/Users/{user_id}/Items"
        params = {
            "SortBy": "DatePlayed",
            "SortOrder": "Descending",
            "Filters": "IsPlayed",
            "Recursive": "true",
            "IncludeItemTypes": "Movie,Episode",
            "Limit": limit
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=self.headers, params=params, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        return await response.json()  # 'await' for async json parsing
                    self.logger.error(
                        "Failed to get recent items for %s: %d", user_id, response.status)
        except aiohttp.ClientError as e:
            self.logger.error(
                "An error occurred while retrieving recent items for %s: %s", user_id, str(e))

        return None

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
                        item_data = await response.json()  # 'await' for async json parsing
                        return item_data.get('ProviderIds', {}).get(provider)

                    self.logger.error("Failed to retrieve ID for item %s: %d", item_id, response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving ID for item %s: %s", item_id, str(e))

        return None
