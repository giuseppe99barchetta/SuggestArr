import os
import aiohttp
import asyncio
from api_service.config.logger_manager import LoggerManager
from api_service.config.config import save_session_token

# Constants for HTTP status codes and request timeout
HTTP_OK = {200, 201, 202}
REQUEST_TIMEOUT = 10  # Timeout in seconds for HTTP requests
BATCH_SIZE = 20  # Number of requests fetched per batch


class SeerClient:
    """
    A client to interact with the Jellyseer API for handling media requests and authentication.
    """

    def __init__(self, api_url, api_key, seer_user_name=None, seer_password=None, session_token=None, number_of_seasons="all"):
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
        self.username = seer_user_name
        self.password = seer_password
        self.session_token = session_token
        self.is_logged_in = False
        self._login_lock = asyncio.Lock()
        self.requests_cache = []  # Cache to store all requests
        self.number_of_seasons = number_of_seasons
        
    async def init(self):
        """
        Asynchronous initialization method to fetch all requests.
        This is typically called after creating an instance of JellyseerClient
        to ensure that the requests cache is populated.
        """
        await self.fetch_all_requests()

    async def login(self):
        """Authenticate with Jellyseer and obtain a session token."""
        async with self._login_lock:
            if self.is_logged_in:
                return

        login_url = f"{self.api_url}/api/v1/auth/local"
        async with aiohttp.ClientSession() as session:
            try:
                login_data = {"email": self.username, "password": self.password}
                
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
                
    def _get_auth(self, use_cookie):
        """
        Prepare headers and cookies based on `use_cookie` flag.
        """
        if use_cookie and not self.session_token:
            return None
        headers = {'Content-Type': 'application/json', 'accept': 'application/json'}
        cookies = {'connect.sid': self.session_token} if use_cookie and self.session_token else {}
        if not use_cookie:
            headers['X-Api-Key'] = self.api_key
        return headers, cookies

    def _get_headers_and_cookies(self, use_cookie):
        """
        Prepares headers and cookies based on the availability of the session token and the use_cookie flag.
        If use_cookie is True and session_token is available, the session token is included in the cookies.
        Otherwise, API key authentication is used in the headers.
        Returns a tuple (headers, cookies). Returns None if a cookie is required but the session_token is missing.
        """

        # Return None if a cookie is required but the session_token is not available
        if use_cookie and not self.session_token:
            return None

        headers = {
            'Content-Type': 'application/json',
            'accept': 'application/json',
        }

        # Set cookies or use API key based on the use_cookie flag
        cookies = {}
        if use_cookie and self.session_token:
            cookies['connect.sid'] = self.session_token
        else:
            headers['X-Api-Key'] = self.api_key

        return headers, cookies

    async def _make_request(self, method, endpoint, use_cookie=False, retry_login=True, **kwargs):
        """Unified API request handling with error handling."""
        url = f"{self.api_url}/{endpoint}"
        headers, cookies = self._get_auth(use_cookie) or (None, None)

        if headers is None:
            self.logger.error("Authentication missing for %s", url)
            return None

        async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
            try:
                async with session.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs) as response:
                    if response.status in (403, 404) and retry_login:
                        self.is_logged_in = False
                        await self.login()
                        return await self._make_request(method, endpoint, use_cookie, retry_login=False, **kwargs)
                    return await self._process_response(response, url)
            except asyncio.TimeoutError:
                self.logger.error("Request to %s timed out.", url)
            except aiohttp.ClientError as e:
                self.logger.error("Error during request to %s: %s", url, str(e))
        return None
    
    async def _process_response(self, response, url):
        """Handle API response, logging errors if necessary."""
        if response.status in HTTP_OK:
            return await response.json()
        error = await response.json()
        self.logger.error("Request to %s failed: %s", url, error.get("error", "Unknown error"))
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
        in Jellyseer/Overseer by checking the cached requests.
        """
        return any(item['media']['tmdbId'] == tmdb_id and \
                item['media']['mediaType'].lower() == media_type.lower()
                for item in self.requests_cache)
        
    async def check_already_downloaded(self, tmdb_id, media_type, local_content={}):
        """
        Checks if a media item has already been downloaded 
        by checking the cached local content.
        """
        return any(item['tmdb_id'] == str(tmdb_id) for item in local_content.get(media_type))

    async def get_total_request(self):
        """
        Get total requests made in Jellyseer.
        :return: Total number of requests or 0 if error occurs.
        """
        data = await self._make_request("GET", "api/v1/request/count")
        return data.get('total', 0) if data else 0

    async def request_media(self, media_type, media_id, tvdb_id=None, retries=3, delay=2):
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
            
            if self.number_of_seasons.isdigit():
                data["seasons"] = list(range(1, int(self.number_of_seasons) + 1))  # List of seasons from 1 to the total number
            else:
                data["seasons"] = "all"

        use_cookie = bool(self.session_token)

        # Retry logic
        for attempt in range(retries):
            try:
                response = await self._make_request("POST", "api/v1/request", json=data, use_cookie=use_cookie)
                if response and 'error' not in response:
                    return response

            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {media_type.upper()} with ID {media_id} - {e}")

            if attempt < retries - 1:
                await asyncio.sleep(delay)

        # Log final failure after all retries
        self.logger.error(f"Failed to request {media_type} with ID {media_id} after {retries} attempts.")
        return {'message': f"Failed to request {media_type} with ID {media_id} after {retries} attempts."}, 500

    async def get_all_users(self, max_users=100):
        """Fetch all users from Jellyseer API, returning a list of user IDs, names, and local status."""
        data = await self._make_request("GET", f"api/v1/user?take={max_users}")
        if data:
            return [
                {
                    'id': user['id'],
                    'name': user.get('displayName', user.get('jellyfinUsername', 'Unknown User')),
                    'email': user.get('email'),
                    'isLocal': user.get('plexUsername') is None and user.get('jellyfinUsername') is None
                }
                for user in data.get('results', [])
            ]
        return []
