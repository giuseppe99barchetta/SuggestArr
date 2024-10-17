"""
This module provides a client to interact with the Jellyseer API.
It includes functionality to log in, check if media has already been requested,
and request new media.

Classes:
    - JellyseerClient: A class to interact with the Jellyseer API.
"""

import concurrent.futures
import requests

from config.logger_manager import LoggerManager

# Constants for HTTP status codes and request timeout
HTTP_OK = {200, 201, 202}
REQUEST_TIMEOUT = 10  # Timeout in seconds for HTTP requests

class JellyseerClient:
    """
    A client to interact with the Jellyseer API for handling media requests and authentication.
    """

    def __init__(self, api_url, api_key, jellyseer_user = None):
        """
        Initializes the JellyseerClient with the API URL and logs in the user.
        :param api_url: The URL of the Jellyseer API.
        :param api_key: The API KEY for Jellyseer.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.api_url = api_url
        self.api_key = api_key
        self.user_id = jellyseer_user if jellyseer_user else "default"
        self.session = requests.Session()
        self.session.headers.update({'X-Api-Key': self.api_key})

    def check_already_requested(self, tmdb_id, media_type):
        """
        Checks if a media item has already been requested in Jellyseer.
        """
        total_jellyseer_request = self.get_total_request()
        batch_size = 20

        def fetch_batch(skip):
            """Fetch and process a batch of requests."""
            url = f"{self.api_url}/api/v1/request?take={batch_size}&skip={skip}"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code in HTTP_OK:
                data = response.json()
                # Check if any request matches the given tmdb_id and media_type
                for item in data.get('results', []):
                    if item['media']['tmdbId'] == tmdb_id and item['media']['mediaType'].lower() == media_type.lower():
                        return True
            return False

        try:
            # Use ThreadPoolExecutor to run requests concurrently
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(fetch_batch, skip) for skip in range(0, total_jellyseer_request, batch_size)]
                for future in concurrent.futures.as_completed(futures):
                    if future.result():  # Stop early if any batch returns True
                        return True
        except Exception as e:
            self.logger.error("Error during concurrent execution: %s", str(e))

        return False

    def get_total_request(self):
        """
        Get total request made in Jellyseer.
        """
        url = f"{self.api_url}/api/v1/request/count"

        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code in HTTP_OK:
                data = response.json()
                return data.get('total')

        except requests.Timeout:
            self.logger.error("Request to check if media was already requested timed out.")
        except requests.RequestException as e:
            self.logger.error("An error occurred while checking media request: %s", str(e))

        return 0

    def request_media(self, media_type, media_id, tvdb_id=None):
        """
        Requests a media item (movie or TV show) from Jellyseer.
        :param media_type: The type of media ('movie' or 'tv').
        :param media_id: The TMDb ID of the media item.
        :param tvdb_id: The TVDb ID of the media item (optional, only for TV shows).
        :return: The response JSON from Jellyseer or None if an error occurs.
        """
        data = {
            "mediaType": media_type,
            "mediaId": media_id,
        }

        # Only add userId if it's not "default"
        if self.user_id != "default":
            data["userId"] = int(self.user_id)

        if media_type == 'tv':
            data["tvdbId"] = tvdb_id if tvdb_id else media_id
            data["seasons"] = "all"

        try:
            response = self.session.post(
                f"{self.api_url}/api/v1/request",
                json=data,
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code in HTTP_OK:
                return response.json()
            self.logger.error(
                "Failed to request media (ID: %s): %d", media_id, response.status_code
            )
        except requests.Timeout:
            self.logger.error(
                "Request to Jellyseer timed out while requesting media: %s", media_id
            )
        except requests.RequestException as e:
            self.logger.error(
                "An error occurred while requesting media (ID: %s): %s", media_id, str(e)
            )

        return None

    def get_all_users(self):
        """Fetch all users from Jellyseer API, returning a list of user IDs and names."""
        try:
            response = self.session.get(
                f"{self.api_url}/api/v1/user",
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code in HTTP_OK:
                users_data = response.json().get('results', [])
                # Extracting only id and displayName or jellyfinUsername as fallback
                return [
                    {
                        'id': user['id'],
                        'name': (user.get('displayName') 
                                 or user.get('jellyfinUsername', 'Unknown User'))
                    }
                    for user in users_data
                ]

        except requests.Timeout:
            self.logger.error("Request to get all Jellyseer users timed out.")
        except requests.RequestException as e:
            self.logger.error("An error occurred while requesting users from Jellyseer: %s", str(e))

        return []
