import aiohttp
import asyncio
from config.logger_manager import LoggerManager

# Constants for HTTP status codes and request timeout
HTTP_OK = {200, 201, 202}
REQUEST_TIMEOUT = 10  # Timeout in seconds for HTTP requests
BATCH_SIZE = 20  # Number of requests fetched per batch


class JellyseerClient:
    """
    A client to interact with the Jellyseer API for handling media requests and authentication.
    """

    def __init__(self, api_url, api_key, jellyseer_user_name=None, jellyseer_password=None):
        """
        Initializes the JellyseerClient with the API URL and logs in the user.
        :param api_url: The URL of the Jellyseer API.
        :param api_key: The API KEY for Jellyseer.
        :param jellyseer_user_id: (Optional) The Jellyseer user ID for making requests.
        :param jellyseer_user_name: (Optional) The Jellyseer username for authentication.
        :param jellyseer_password: (Optional) The Jellyseer password for authentication.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.api_url = api_url
        self.api_key = api_key
        self.username = jellyseer_user_name
        self.password = jellyseer_password
        self.session_token = None  # Token for authenticated session
        self.requests_cache = []  # Cache to store all requests

    async def init(self):
        """
        Asynchronous initialization method to fetch all requests.
        This is typically called after creating an instance of JellyseerClient
        to ensure that the requests cache is populated.
        """
        await self.fetch_all_requests()

    async def login(self):
        """
        Authenticate with Jellyseer and obtain a session token.
        """
        if not self.username or not self.password:
            self.logger.error("Login failed: Username or password not provided.")
            return

        login_url = f"{self.api_url}/api/v1/auth/local"
        async with aiohttp.ClientSession() as session:
            try:
                login_data = {
                    "email": self.username,
                    "password": self.password
                }
                async with session.post(login_url, json=login_data, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200 and 'connect.sid' in response.cookies:
                        self.session_token = response.cookies['connect.sid'].value
                        self.logger.info("Successfully logged in as %s", self.username)
                    else:
                        self.logger.error("Login failed: %d. No session cookie found.", response.status)
                        self.logger.error("Error response: %s", await response.json())
            except asyncio.TimeoutError:
                self.logger.error("Login request to %s timed out.", login_url)
            except aiohttp.ClientError as e:
                self.logger.error("An error occurred during login: %s", str(e))

    def _get_headers_and_cookies(self, use_cookie):
        """
        Helper function to prepare headers and cookies based on the use_cookie flag.
        """
        headers = {
            'Content-Type': 'application/json',
            'accept': 'application/json',
        }
        cookies = {}

        if self.session_token and use_cookie:
            # Use session cookie if token is available and use_cookie is True
            cookies['connect.sid'] = self.session_token
        else:
            # Fallback to API key authentication
            headers['X-Api-Key'] = self.api_key

        return headers, cookies

    async def _make_request(self, method, endpoint, use_cookie=False, **kwargs):
        """
        Helper function to handle API requests asynchronously.
        If use_cookie is True, use the session cookie for authentication.
        """
        url = f"{self.api_url}/{endpoint}"
        headers, cookies = self._get_headers_and_cookies(use_cookie)

        async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
            try:
                async with session.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs) as response:
                    if response.status in HTTP_OK:
                        return await response.json()

                    error_response = await response.json()
                    self.logger.error("API call to %s failed with status %d", url, response.status)
                    self.logger.error("Error details: %s", error_response)
                    return error_response

            except asyncio.TimeoutError:
                self.logger.error("Request to %s timed out.", url)
            except aiohttp.ClientError as e:
                self.logger.error("An error occurred while calling %s: %s", url, str(e))
        return None

    async def fetch_all_requests(self):
        """
        Fetch all requests made in Jellyseer and store them in self.requests_cache.
        """
        total_jellyseer_request = await self.get_total_request()
        self.requests_cache = []  # Reset cache

        async def fetch_batch(skip):
            """Fetch a batch of requests and add them to the cache."""
            data = await self._make_request("GET", f"api/v1/request?take={BATCH_SIZE}&skip={skip}")
            if data:
                self.requests_cache.extend(data.get('results', []))

        tasks = [fetch_batch(skip) for skip in range(0, total_jellyseer_request, BATCH_SIZE)]
        await asyncio.gather(*tasks)

        self.logger.info("Fetched %d total requests from Jellyseer.", len(self.requests_cache))

    async def check_already_requested(self, tmdb_id, media_type):
        """
        Checks if a media item has already been requested 
        in Jellyseer by checking the cached requests.
        """
        return any(item['media']['tmdbId'] == tmdb_id and \
                item['media']['mediaType'].lower() == media_type.lower()
                for item in self.requests_cache)

    async def get_total_request(self):
        """
        Get total requests made in Jellyseer.
        :return: Total number of requests or 0 if error occurs.
        """
        data = await self._make_request("GET", "api/v1/request/count")
        return data.get('total', 0) if data else 0

    async def request_media(self, media_type, media_id, tvdb_id=None):
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

        if media_type == 'tv':
            data["tvdbId"] = tvdb_id or media_id
            data["seasons"] = "all"

        # Ensure login if necessary, use cookie-based authentication
        if self.username and self.password and not self.session_token:
            await self.login()

        use_cookie = bool(self.session_token)  # Use cookie if we have a session token

        return await self._make_request("POST", "api/v1/request", json=data, use_cookie=use_cookie)

    async def get_all_users(self):
        """Fetch all users from Jellyseer API, returning a list of user IDs and names."""
        data = await self._make_request("GET", "api/v1/user")
        if data:
            return [{'id': user['id'], 'name': user.get('displayName', user.get('jellyfinUsername', 'Unknown User'))}
                    for user in data.get('results', [])]
        return []
