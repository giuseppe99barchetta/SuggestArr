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

    def __init__(self, api_url, api_key, seer_user_name=None, seer_password=None, session_token=None,
                number_of_seasons="all", exclude_downloaded=True, exclude_watched=True,
                anime_profile_config=None):
        """
        Initializes the JellyseerClient with the API URL and logs in the user.
        :param anime_profile_config: Dict with anime/default profile routing settings.
            Expected keys: 'anime_movie', 'anime_tv', optionally 'default_movie', 'default_tv'.
            Each value is a dict with optional keys: serverId, profileId, rootFolder, tags, languageProfileId.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.api_url = api_url
        self.api_key = api_key
        self.username = seer_user_name
        self.password = seer_password
        self.session_token = session_token
        self.is_logged_in = False
        self._login_lock = None
        self.number_of_seasons = number_of_seasons
        self.pending_requests = set()
        self.exclude_downloaded = exclude_downloaded
        self.exclude_requested = exclude_watched
        self.anime_profile_config = anime_profile_config or {}
        self.session = None
        self.logger.debug("SeerClient initialized with API URL: %s", api_url)

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
        
    async def init(self):
        """
        Asynchronous initialization method to fetch all requests.
        This is typically called after creating an instance of JellyseerClient
        to ensure that the requests cache is populated.
        """
        self.logger.debug("Initializing SeerClient...")
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
            self.logger.debug("Attempt %d for request to %s", attempt + 1, url)
            
            # Use shared session but override headers/cookies for this request
            # since aiohttp allows passing request-level headers/cookies
            session = await self._get_session()
            try:
                async with session.request(method, url, json=data, headers=headers, cookies=cookies, timeout=REQUEST_TIMEOUT) as response:
                    self.logger.debug("Received response with status %d for request to %s", response.status, url)
                    if response.status in HTTP_OK:
                        return await response.json()
                    elif response.status == 403:
                        resp = await response.json()
                        message = resp.get('message') or resp.get('error', '')
                        self.logger.error(
                            f"Request to {url} failed with status: {response.status}, {message}"
                        )
                        # Quota-exceeded errors won't be resolved by re-logging in; abort immediately
                        if 'quota' in message.lower():
                            return None
                        # Otherwise treat as auth failure and retry with login
                        if attempt < retries - 1:
                            self.logger.debug("Retrying login due to 403")
                            await self.login()
                        else:
                            return None
                    elif response.status == 404 and attempt < retries - 1:
                        self.logger.debug("Retrying login due to status 404")
                        await self.login()
                    else:
                        resp = await response.json()
                        self.logger.error(
                            f"Request to {url} failed with status: {response.status}, {resp.get('message') or resp.get('error', 'Unknown error')}"
                        )
            except aiohttp.ClientError as e:
                self.logger.error(f"Client error during request to {url}: {e}")
            await asyncio.sleep(delay)
        return None

    async def login(self):
        """Authenticate with Jellyseer and obtain a session token."""
        if self._login_lock is None:
            self._login_lock = asyncio.Lock()

        async with self._login_lock:
            if self.is_logged_in:
                self.logger.debug("Already logged in.")
                return

        login_url = f"{self.api_url}/api/v1/auth/local"
        self.logger.debug("Logging in to %s", login_url)
        session = await self._get_session()
        try:
            async with session.post(login_url, json={"email": self.username, "password": self.password}, timeout=REQUEST_TIMEOUT) as response:
                self.logger.debug("Login response status: %d", response.status)
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
        self.logger.debug("Fetching all users with max_users=%d", max_users)
        data = await self._make_request("GET", f"api/v1/user?take={max_users}")
        if data:
            self.logger.debug("Fetched users data: %s", data)
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
        self.logger.debug("Fetching all requests...")
        total_requests = await self.get_total_request()
        self.logger.debug("Total requests to fetch: %d", total_requests)
        tasks = [self._fetch_batch(skip) for skip in range(0, total_requests, BATCH_SIZE)]
        await asyncio.gather(*tasks)
        self.logger.info("Fetched all requests and saved to database.")

    async def _fetch_batch(self, skip):
        """Fetch a batch of requests and save them to the database."""
        self.logger.debug("Fetching batch of requests starting at skip=%d", skip)
        try:
            data = await self._make_request("GET", f"api/v1/request?take={BATCH_SIZE}&skip={skip}")
            if data:
                requests = data.get('results', [])
                DatabaseManager().save_requests_batch(requests)
        except Exception as e:
            self.logger.error(f"Failed to fetch batch at skip {skip}: {e}")

    async def get_total_request(self):
        """Get total requests made in Jellyseer."""
        self.logger.debug("Getting total request count...")
        data = await self._make_request("GET", "api/v1/request/count")
        total = data.get('total', 0) if data else 0
        self.logger.debug("Total requests count: %d", total)
        return total

    async def get_radarr_servers(self):
        """Fetch available Radarr servers from Overseerr with their profiles, root folders, and tags."""
        self.logger.debug("Fetching Radarr servers from Overseerr")
        return await self._make_request("GET", "api/v1/service/radarr")

    async def get_sonarr_servers(self):
        """Fetch available Sonarr servers from Overseerr with their profiles, root folders, and tags."""
        self.logger.debug("Fetching Sonarr servers from Overseerr")
        return await self._make_request("GET", "api/v1/service/sonarr")

    def _apply_profile_config(self, data, profile_key, media_type):
        """Apply profile configuration (serverId, profileId, rootFolder, tags) to request data."""
        profile = self.anime_profile_config.get(profile_key, {})
        if not profile:
            return

        for key in ['serverId', 'profileId', 'rootFolder', 'tags']:
            if key in profile:
                data[key] = profile[key]
        if media_type == 'tv' and 'languageProfileId' in profile:
            data['languageProfileId'] = profile['languageProfileId']

        self.logger.info("Applied profile '%s': serverId=%s, profileId=%s, rootFolder=%s",
                        profile_key, profile.get('serverId'), profile.get('profileId'), profile.get('rootFolder'))

    def _build_seer_payload(self, media_type, media, source=None, user=None,
                            is_anime=False, rationale=None):
        """Build the Seer request payload dict.

        Private meta-keys (prefixed with ``_``) are stripped before the payload is
        sent to Seer but are preserved in the queue row so the worker can call
        ``save_request`` / ``save_metadata`` correctly after a successful submission.

        :return: payload dict ready for JSON serialisation.
        """
        data = {"mediaType": media_type, "mediaId": media['id']}

        if media_type == 'tv':
            data["seasons"] = (
                "all" if self.number_of_seasons == "all"
                else list(range(1, int(self.number_of_seasons) + 1))
            )

        if self.anime_profile_config:
            profile_key = f"anime_{media_type}" if is_anime else f"default_{media_type}"
            self._apply_profile_config(data, profile_key, media_type)

        # Private meta-keys — consumed by the worker, not sent to Seer
        data["_source_id"] = source.get('id') if source else None
        data["_user_id"] = user.get('id') if user else None
        data["_rationale"] = rationale
        data["_is_anime"] = is_anime
        data["_media_obj"] = media    # worker needs this for save_metadata
        data["_source_obj"] = source  # worker needs this for save_metadata

        return data

    async def request_media(self, media_type, media, source=None, tvdb_id=None, user=None, is_anime=False, rationale=None):
        """Enqueue a Seer submission for reliable background delivery.

        Replaces the old direct-submit behaviour. All pre-checks (already requested /
        downloaded / streaming-excluded) are still performed by the caller (handler
        layer) before this method is invoked.

        :return: True if the item was newly enqueued, False if skipped (duplicate or
            already submitted).
        """
        tmdb_id = str(media['id'])

        # Fast intra-process guard (asyncio is single-threaded: check+add are atomic)
        if (media_type, tmdb_id) in self.pending_requests:
            self.logger.debug("Skipping duplicate request for %s (ID: %s)", media_type, tmdb_id)
            return False

        db = DatabaseManager()

        # Double-check DB to close the TOCTOU gap between the handler's
        # check_already_requested() call and this point.
        if self.exclude_requested and db.check_request_exists(media_type, tmdb_id):
            self.logger.debug(
                "Skipping %s (ID: %s): already in DB (concurrent submission).", media_type, tmdb_id
            )
            return False

        # Mark in-memory to short-circuit further calls within this run
        self.pending_requests.add((media_type, tmdb_id))

        payload = self._build_seer_payload(media_type, media, source=source, user=user,
                                           is_anime=is_anime, rationale=rationale)
        user_id = user.get('id') if user else None

        if user:
            db.save_user(user)

        enqueued = db.enqueue_request(tmdb_id, media_type, user_id, payload)
        if enqueued:
            self.logger.info("Enqueued %s tmdb:%s for Seer delivery.", media_type, tmdb_id)
        return enqueued

    async def submit_queued_request(self, payload: dict) -> bool:
        """Perform the actual HTTP submission to Seer for a single queue row.

        Called by the queue worker.  Strips private meta-keys before sending.

        :param payload: The JSON-decoded payload stored in pending_requests.
        :return: True on HTTP success, False on any failure.
        """
        # Build clean Seer body (drop private meta-keys)
        data = {k: v for k, v in payload.items() if not k.startswith('_')}

        response = await self._make_request(
            "POST", "api/v1/request", data=data, use_cookie=bool(self.session_token)
        )
        if response and 'error' not in response:
            self.logger.debug("Seer submission successful: %s", response)
            return True

        self.logger.error("Seer submission failed: %s", response)
        return False
            
    async def check_already_requested(self, tmdb_id, media_type):
        """Check if a media request is cached in the current cycle."""
        if self.exclude_requested:
            self.logger.debug("Checking if media already requested: tmdb_id=%s, media_type=%s", tmdb_id, media_type)

            try:
                result = DatabaseManager().check_request_exists(media_type, tmdb_id)

                if not isinstance(result, bool):
                    self.logger.warning("Unexpected return value from check_request_exists: %s", result)
                    return False

                return result
            except Exception as e:
                self.logger.error("Error checking if media already requested: %s", e, exc_info=True)
        else:
            self.logger.info("Skipping check for already requested media.")
        
        return False

    async def check_already_downloaded(self, tmdb_id, media_type, local_content=None):
        """Check if a media item has already been downloaded based on local content."""
        if self.exclude_downloaded:
            self.logger.debug("Checking if media already downloaded: tmdb_id=%s, media_type=%s", tmdb_id, media_type)

            if local_content is None:
                self.logger.warning("local_content is None, skipping downloaded check")
                return False

            items = local_content.get(media_type, [])
            if not isinstance(items, list):
                self.logger.warning("Expected list for media_type '%s', but got %s", media_type, type(items))
                return False

            for item in items:
                if not isinstance(item, dict):
                    self.logger.warning("Skipping invalid item in local_content: %s", item)
                    continue
                if 'tmdb_id' not in item:
                    self.logger.warning("Skipping item without 'tmdb_id': %s", item)
                    continue
                if item['tmdb_id'] == str(tmdb_id):
                    return True
        else:
            self.logger.info("Skipping check for already downloaded media.")

        return False

    async def get_metadata(self, media_id, media_type):
        """Retrieve metadata for a specific media item."""
        self.logger.debug("Getting metadata for media_id=%s, media_type=%s", media_id, media_type)
        return DatabaseManager().get_metadata(media_id, media_type)
