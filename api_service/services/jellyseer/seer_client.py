import aiohttp
import asyncio
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager

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
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.api_url = api_url
        self.api_key = api_key
        self.username = seer_user_name
        self.password = seer_password
        self.session_token = session_token
        self.is_logged_in = False
        self._login_lock = asyncio.Lock()
        self.number_of_seasons = number_of_seasons
        
    async def init(self):
        """
        Asynchronous initialization method to fetch all requests.
        This is typically called after creating an instance of JellyseerClient
        to ensure that the requests cache is populated.
        """
        await self.fetch_all_requests()

    def _get_auth_headers(self, use_cookie):
        """Prepare headers and cookies based on `use_cookie` flag."""
        headers = {'Content-Type': 'application/json', 'accept': 'application/json'}
        cookies = {}

        if use_cookie and self.session_token:
            cookies['connect.sid'] = self.session_token
        elif not use_cookie:
            headers['X-Api-Key'] = self.api_key

        return headers, cookies

    async def _make_request(self, method, endpoint, data=None, use_cookie=False, retries=3, delay=2):
        """Unified API request handling with retry logic and error handling."""
        url = f"{self.api_url}/{endpoint}"
        headers, cookies = self._get_auth_headers(use_cookie)

        for attempt in range(retries):
            async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
                try:
                    async with session.request(method, url, json=data, timeout=REQUEST_TIMEOUT) as response:
                        if response.status in HTTP_OK:
                            return await response.json()
                        elif response.status in (403, 404) and attempt < retries - 1:
                            await self.login()
                        else:
                            resp = await response.json()
                            self.logger.error(
                                f"Request to {url} failed with status: {response.status}, {resp['message'] if 'message' in resp else resp['error']}"
                            )
                except aiohttp.ClientError as e:
                    self.logger.error(f"Client error during request to {url}: {e}")
                await asyncio.sleep(delay)
        return None

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
                        self.is_logged_in = True
                        self.logger.info("Successfully logged in as %s", self.username)
                    else:
                        self.logger.error("Login failed: %d", response.status)
            except asyncio.TimeoutError:
                self.logger.error("Login request to %s timed out.", login_url)

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
    
    async def fetch_all_requests(self):
        """Fetch all requests made in Jellyseer and save them to the database."""
        total_requests = await self.get_total_request()
        tasks = [self._fetch_batch(skip) for skip in range(0, total_requests, BATCH_SIZE)]
        await asyncio.gather(*tasks)
        self.logger.info("Fetched all requests and saved to database.")

    async def _fetch_batch(self, skip):
        """Fetch a batch of requests and save them to the database."""
        try:
            data = await self._make_request("GET", f"api/v1/request?take={BATCH_SIZE}&skip={skip}")
            if data:
                requests = data.get('results', [])
                DatabaseManager().save_requests_batch(requests)
        except Exception as e:
            self.logger.error(f"Failed to fetch batch at skip {skip}: {e}")

    async def get_total_request(self):
        """Get total requests made in Jellyseer."""
        data = await self._make_request("GET", "api/v1/request/count")
        return data.get('total', 0) if data else 0

    async def request_media(self, media_type, media, source=None, tvdb_id=None):
        """Request media and save it to the database if successful."""
        data = {"mediaType": media_type, "mediaId": media['id']}
        if media_type == 'tv':
            data["tvdbId"] = tvdb_id or media['id']
            data["seasons"] = "all" if self.number_of_seasons == "all" else list(range(1, int(self.number_of_seasons) + 1))

        response = await self._make_request("POST", "api/v1/request", data=data, use_cookie=bool(self.session_token))
        if response and 'error' not in response:
            databaseManager = DatabaseManager()
            databaseManager.save_request(media_type, media['id'], source['id'])
            databaseManager.save_metadata(source, media_type)
            databaseManager.save_metadata(media, media_type)
            
    async def check_already_requested(self, tmdb_id, media_type):
        """Check if a media request is cached in the current cycle."""
        return DatabaseManager().check_request_exists(media_type, tmdb_id)

    async def check_already_downloaded(self, tmdb_id, media_type, local_content={}):
        """Check if a media item has already been downloaded based on local content."""
        return any(item['tmdb_id'] == str(tmdb_id) for item in local_content.get(media_type, []))

    async def get_metadata(self, media_id, media_type):
        """Retrieve metadata for a specific media item."""
        return DatabaseManager().get_metadata(media_id, media_type)