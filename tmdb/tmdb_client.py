"""
This module provides a client for interacting with The Movie Database (TMDb) API.
It includes functionality to retrieve similar movies, similar TV shows, and convert
TVDb IDs to TMDb IDs.

Classes:
    - TMDbClient: A class to interact with the TMDb API.
"""

import logging
import requests

# Constants for HTTP status codes and timeout
HTTP_OK = {200, 201}
REQUEST_TIMEOUT = 10  # Timeout in seconds for HTTP requests

class TMDbClient:
    """
    A client to interact with The Movie Database (TMDb) API to retrieve information
    related to movies, TV shows, and external IDs.
    """

    def __init__(self, api_key):
        """
        Initializes the TMDbClient with the provided API key.
        :param api_key: API key to authenticate requests to TMDb.
        """
        self.api_key = api_key
        self.tmdb_api_url = "https://api.themoviedb.org/3"

    def find_similar_movies(self, movie_id):
        """
        Finds movies similar to the one with the given movie_id using the TMDb API.
        :param movie_id: The ID of the movie to find recommendations for.
        :return: A list of movie IDs similar to the specified movie.
        """
        url = f"{self.tmdb_api_url}/movie/{movie_id}/recommendations?api_key={self.api_key}"
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code in HTTP_OK:
                data = response.json()
                return [movie['id'] for movie in data['results']]
            logging.error("Error retrieving movie recommendations: %d", response.status_code)
        except requests.Timeout:
            logging.error("Request to TMDb timed out.")
        except requests.RequestException as e:
            logging.error("An error occurred while requesting movie recommendations: %s", str(e))
        return []

    def find_similar_tvshows(self, tvshow_id):
        """
        Finds TV shows similar to the one with the given tvshow_id using the TMDb API.
        :param tvshow_id: The ID of the TV show to find recommendations for.
        :return: A list of TV show IDs similar to the specified TV show.
        """
        url = f"{self.tmdb_api_url}/tv/{tvshow_id}/recommendations?api_key={self.api_key}"
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code in HTTP_OK:
                data = response.json()
                return [tvshow['id'] for tvshow in data['results']]
            logging.error("Error retrieving TV show recommendations: %d", response.status_code)
        except requests.Timeout:
            logging.error("Request to TMDb timed out.")
        except requests.RequestException as e:
            logging.error("An error occurred while requesting TV show recommendations: %s", str(e))
        return []

    def find_tmdb_id_from_tvdb(self, tvdb_id):
        """
        Finds the TMDb ID for a TV show using its TVDb ID.
        :param tvdb_id: The TVDb ID to convert to TMDb ID.
        :return: The TMDb ID corresponding to the provided TVDb ID, or None if not found.
        """
        url = f"{self.tmdb_api_url}/find/{tvdb_id}?api_key={self.api_key}&external_source=tvdb_id"
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code in HTTP_OK:
                data = response.json()
                if 'tv_results' in data and data['tv_results']:
                    return data['tv_results'][0]['id']
                logging.warning("No results found on TMDb for TVDb ID: %s", tvdb_id)
            else:
                logging.error("Error converting TVDb ID to TMDb ID: %d", response.status_code)
        except requests.Timeout:
            logging.error("Request to TMDb timed out.")
        except requests.RequestException as e:
            logging.error("An error occurred while converting TVDb ID: %s", str(e))
        return None
