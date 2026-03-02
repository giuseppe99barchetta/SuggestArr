"""
OMDb API client for fetching IMDB ratings.

The OMDb API (Open Movie Database) provides IMDB rating data
using IMDB IDs (tt... format).
"""

import aiohttp
from api_service.config.logger_manager import LoggerManager

HTTP_OK = {200, 201}
REQUEST_TIMEOUT = 10


class OmdbClient:
    """
    Client for interacting with the OMDb API to retrieve IMDB ratings.

    Uses the free OMDb API (https://www.omdbapi.com/) which returns
    IMDB ratings, vote counts, and other metadata by IMDB ID.
    """

    def __init__(self, api_key):
        """
        Initialize the OmdbClient.

        Args:
            api_key (str): OMDb API key (free tier at omdbapi.com).
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.api_key = api_key
        self.base_url = "https://www.omdbapi.com/"
        self.session = None
        self.logger.debug("OmdbClient initialized")

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def get_rating(self, imdb_id):
        """
        Fetch IMDB rating and vote count for a given IMDB ID.

        Args:
            imdb_id (str): IMDB ID in tt... format (e.g., 'tt0816692').

        Returns:
            dict | None: Dictionary with 'imdb_rating' (float) and
                         'imdb_votes' (int), or None if unavailable or
                         the request fails.
        """
        if not imdb_id or not self.api_key:
            return None

        url = f"{self.base_url}?i={imdb_id}&apikey={self.api_key}"
        self.logger.debug("Fetching OMDb rating for IMDB ID %s", imdb_id)

        try:
            session = await self._get_session()
            async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                if response.status in HTTP_OK:
                    data = await response.json()

                    if data.get('Response') == 'False':
                        self.logger.debug("OMDb returned no result for IMDB ID %s: %s",
                                          imdb_id, data.get('Error'))
                        return None

                    raw_rating = data.get('imdbRating', 'N/A')
                    raw_votes = data.get('imdbVotes', 'N/A')

                    if raw_rating == 'N/A' or raw_votes == 'N/A':
                        self.logger.debug("No IMDB rating/votes data for IMDB ID %s", imdb_id)
                        return None

                    try:
                        imdb_rating = float(raw_rating)
                        imdb_votes = int(raw_votes.replace(',', ''))
                        self.logger.debug("IMDB rating for %s: %.1f (%d votes)",
                                          imdb_id, imdb_rating, imdb_votes)
                        return {
                            'imdb_rating': imdb_rating,
                            'imdb_votes': imdb_votes,
                        }
                    except (ValueError, TypeError) as e:
                        self.logger.warning("Failed to parse IMDB rating data for %s: %s",
                                            imdb_id, str(e))
                        return None
                else:
                    self.logger.warning("OMDb request failed for IMDB ID %s: HTTP %d",
                                        imdb_id, response.status)
        except aiohttp.ClientError as e:
            self.logger.error("OMDb request error for IMDB ID %s: %s", imdb_id, str(e))

        return None
