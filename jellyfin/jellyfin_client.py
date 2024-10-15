"""
This module provides the JellyfinClient class for interacting with the Jellyfin API.
The client can retrieve users, recent items, and provider IDs for media content.

Classes:
    - JellyfinClient: A class that handles communication with the Jellyfin API.
"""
import requests

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

    def get_all_users(self):
        """
        Retrieves a list of all users from the Jellyfin server.
        :return: A list of users in JSON format if successful, otherwise an empty list.
        """
        url = f"{self.api_url}/Users"
        try:
            response = requests.get(
                url, headers=self.headers, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                return response.json()

            self.logger.error("Failed to retrieve users: %d",
                              response.status_code)
        except requests.Timeout:
            self.logger.error("Request to get users timed out.")
        except requests.RequestException as e:
            self.logger.error(
                "An error occurred while retrieving users: %s", str(e))
        return []

    def get_recent_items(self, user_id, limit=100):
        """
        Retrieves a list of recently played items for a given user.
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
            "IncludeItemTypes": "Movie,Series,Episode",
            "Limit": limit
        }
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                return response.json()

            self.logger.error(
                "Failed to get recent items for %s: %d", user_id, response.status_code)
        except requests.Timeout:
            self.logger.error(
                "Request to get recent items for user %s timed out.", user_id)
        except requests.RequestException as e:
            self.logger.error(
                "Error while retrieving recent items for %s: %s", user_id, str(e))
        return None

    def get_item_provider_id(self, user_id, item_id, provider='Tmdb'):
        """
        Retrieves the provider ID (e.g., TMDb or TVDb) for a specific media item.
        :param user_id: The ID of the user.
        :param item_id: The ID of the media item.
        :param provider: The provider ID to retrieve (default is 'Tmdb').
        :return: The provider ID if found, otherwise None.
        """
        url = f"{self.api_url}/Users/{user_id}/Items/{item_id}"
        try:
            response = requests.get(
                url, headers=self.headers, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                item_data = response.json()
                return item_data.get('ProviderIds', {}).get(provider)

            self.logger.error(
                "Failed to retrieve ID for item %s: %d", item_id, response.status_code)
        except requests.Timeout:
            self.logger.error(
                "Request to get provider ID for item %s timed out.", item_id)
        except requests.RequestException as e:
            self.logger.error(
                "An error occurred while retrieving ID for item %s: %s", item_id, str(e))
        return None
