"""
This module provides a client to interact with the Jellyseer API.
It includes functionality to log in, check if media has already been requested,
and request new media.

Classes:
    - JellyseerClient: A class to interact with the Jellyseer API.
"""

import logging
import requests

# Constants for HTTP status codes and request timeout
HTTP_OK = 200
REQUEST_TIMEOUT = 10  # Timeout in seconds for HTTP requests

class JellyseerClient:
    """
    A client to interact with the Jellyseer API for handling media requests and authentication.
    """

    def __init__(self, api_url, api_key):
        """
        Initializes the JellyseerClient with the API URL and logs in the user.
        :param api_url: The URL of the Jellyseer API.
        :param username: The username for Jellyseer login.
        :param password: The password for Jellyseer login.
        """
        self.api_url = api_url
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({'X-Api-Key': self.api_key})

    def check_already_requested(self, tmdb_id, media_type):
        """
        Checks if a media item has already been requested in Jellyseer.
        :param tmdb_id: The TMDb ID of the media item.
        :param media_type: The type of media ('movie' or 'tv').
        :return: True if the media has already been requested, False otherwise.
        """
        url = f"{self.api_url}/api/v1/request?take=100&skip=0&sort=added&requestedBy=1"

        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == HTTP_OK:
                data = response.json()
                for item in data.get('results', []):
                    if item['media']['tmdbId'] == tmdb_id \
                            and item['media']['mediaType'].lower() == media_type.lower():
                        return True
                return False
            logging.error(
                "Failed to verify %s request status: %d", media_type, response.status_code
            )
        except requests.Timeout:
            logging.error("Request to check if media was already requested timed out.")
        except requests.RequestException as e:
            logging.error("An error occurred while checking media request: %s", str(e))

        return False

    def request_media(self, media_type, media_id, tvdb_id=None):
        """
        Requests a media item (movie or TV show) from Jellyseer.
        :param media_type: The type of media ('movie' or 'tv').
        :param media_id: The TMDb ID of the media item.
        :param tvdb_id: The TVDb ID of the media item (optional, only for TV shows).
        :return: The response JSON from Jellyseer or None if an error occurs.
        """
        data = {"mediaType": media_type, "mediaId": media_id}

        if media_type == 'tv':
            data["tvdbId"] = tvdb_id if tvdb_id else media_id
            data["seasons"] = "all"

        try:
            response = self.session.post(
                f"{self.api_url}/api/v1/request",
                json=data,
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == HTTP_OK:
                return response.json()
            logging.error("Failed to request media (ID: %s): %d", media_id, response.status_code)
        except requests.Timeout:
            logging.error("Request to Jellyseer timed out while requesting media: %s", media_id)
        except requests.RequestException as e:
            logging.error("An error occurred while requesting media (ID: %s): %s", media_id, str(e))

        return None
