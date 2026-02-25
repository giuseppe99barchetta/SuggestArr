"""
This module provides the JellyfinClient class for interacting with the Jellyfin API.
The client can retrieve users, recent items, and provider IDs for media content.

Classes:
    - JellyfinClient: A class that handles communication with the Jellyfin API.
"""
import aiohttp
from api_service.config.logger_manager import LoggerManager

# Constants
REQUEST_TIMEOUT = 10       # Timeout in seconds for regular HTTP requests
LIBRARY_FETCH_TIMEOUT = 120  # Timeout in seconds for full-library bulk fetches


class JellyfinClient:
    """
    A client to interact with the Jellyfin API, allowing the retrieval of users, recent items,
    and media provider IDs.
    """

    def __init__(self, api_url, token, max_content=10, library_ids=None):
        """
        Initializes the JellyfinClient with the provided API URL and token.
        :param api_url: The base URL for the Jellyfin API.
        :param token: The authentication token for Jellyfin.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.max_content_fetch = max_content
        self.api_url = api_url
        self.libraries = library_ids
        self.headers = {"X-Emby-Token": token}
        self.existing_content = {}
        self.session = None

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
        
    async def init_existing_content(self):
        self.logger.info('Initializing existing content.')
        self.existing_content = await self.get_all_library_items()
        self.logger.debug(f'Existing content initialized: {self.existing_content}')

    async def get_all_users(self):
        """
        Retrieves a list of all users from the Jellyfin server asynchronously.
        :return: A list of users in JSON format if successful, otherwise an empty list.
        """
        url = f"{self.api_url}/Users"
        self.logger.debug(f'Requesting all users from {url}')
        try:
            session = await self._get_session()
            async with session.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.debug(f'Users retrieved: {data}')
                    return [{"id": user["Id"], "name": user["Name"], "policy": user["Policy"]} for user in data]
                self.logger.error("Failed to retrieve users: %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving users: %s", str(e))

        return []
    
    async def get_all_library_items(self):
        """
        Retrieves all Movie and Series items from the specified libraries.
        Returns a dict with keys: 'movie' and 'tv'.
        """
        results_by_library = {"movie": [], "tv": []}

        if not self.libraries:
            raw = await self.get_libraries() or []
            # get_libraries() returns raw Jellyfin VirtualFolders format (ItemId/Name).
            # Normalize to the internal {id, name} shape expected by all callers so
            # that get_recent_items() works correctly when libraries weren't pre-configured.
            self.libraries = [
                {"id": lib["ItemId"], "name": lib["Name"]}
                for lib in raw
                if lib.get("ItemId") and lib.get("Name")
            ]
        libraries = self.libraries
        self.logger.debug(f"Libraries type: {type(libraries)}, content: {libraries}")

        if not libraries:
            self.logger.error("No libraries found.")
            return None

        for library in libraries:
            self.logger.debug(f"Processing library - type: {type(library)}, content: {library}")
            library_id = library.get('id') if isinstance(library, dict) else None
            library_name = library.get('name') if isinstance(library, dict) else None

            if not library_id:
                self.logger.error(f"Library item is not a dict or missing 'id': {library}")
                continue

            params = {
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Episode",
                "Fields": "ProviderIds",
                "ParentID": library_id
            }

            self.logger.debug(
                f"Requesting items for library {library_name} with params: {params}"
            )

            try:
                session = await self._get_session()
                async with session.get(
                    f"{self.api_url}/Items",
                    headers=self.headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=LIBRARY_FETCH_TIMEOUT)
                ) as response:
                    if response.status != 200:
                        self.logger.error(
                            "Failed to get items for library %s: %d",
                            library_name, response.status
                        )
                        continue

                    data = await response.json()
                    items = data.get("Items", [])

                    added = 0
                    for item in items:
                        item_type = item.get("Type")

                        if item_type not in ("Movie", "Series"):
                            continue

                        tmdb_id = item.get("ProviderIds", {}).get("Tmdb")
                        if not tmdb_id:
                            continue

                        item["tmdb_id"] = tmdb_id
                        bucket = "tv" if item_type == "Series" else "movie"
                        results_by_library[bucket].append(item)
                        added += 1

                    self.logger.info(
                        "Retrieved %d valid items in %s",
                        added,
                        library_name
                    )

            except (aiohttp.ClientError, TimeoutError) as e:
                self.logger.error(
                    "Error retrieving items for library %s: %s",
                    library_name, str(e)
                )

        return results_by_library

    async def get_recent_items(self, user):
        """
        Retrieves a list of recently played items for a given user from specific libraries asynchronously.
        Uses the user-scoped endpoint /Users/{userId}/Items to respect per-user library visibility.
        Falls back to a simpler query if the primary request returns 404 (e.g. Collections library).
        :param user: Dict with 'id' and 'name' keys for the target user.
        :return: A combined dict of recent items keyed by library name, or None if nothing retrieved.
        """
        results_by_library = {}
        seen_series = set()  # Track seen series to avoid duplicates

        user_id = user['id']
        user_name = user.get('name', user_id)

        self.logger.debug(f'Fetching recent items for user {user_name} (id={user_id})')

        for library in self.libraries:
            library_id = library.get('id')
            library_name = library.get('name', library_id)

            # Use the proper user-scoped endpoint so Jellyfin enforces per-user library
            # visibility correctly. Using /Items?userId=... on the admin endpoint caused
            # 404 for users whose library visibility excludes certain virtual folders
            # (e.g. Collections) in Jellyfin 10.9+.
            url = f"{self.api_url}/Users/{user_id}/Items"
            params = {
                "SortBy": "DatePlayed",
                "SortOrder": "Descending",
                "IsPlayed": "true",
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Episode",
                "Limit": self.max_content_fetch,
                "ParentId": library_id,
                "Fields": "ProviderIds",
            }

            self.logger.debug(
                "[library=%s] [userId=%s] GET %s params=%s",
                library_name, user_id, url, params
            )

            try:
                session = await self._get_session()
                async with session.get(url, headers=self.headers, params=params, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        library_items = await response.json()
                        items = library_items.get('Items', [])
                        self.logger.debug(
                            "[library=%s] [user=%s] Raw item count: %d",
                            library_name, user_name, len(items)
                        )

                        filtered_items = []
                        for item in items:
                            if len(filtered_items) >= int(self.max_content_fetch):
                                break
                            if item['Type'] == 'Episode':
                                series_title = item['SeriesName']
                                if series_title not in seen_series:
                                    seen_series.add(series_title)
                                    filtered_items.append(item)
                            else:
                                filtered_items.append(item)

                        results_by_library[library_name] = filtered_items
                        self.logger.info(
                            "Retrieved %d watched items in %s for user %s",
                            len(filtered_items), library_name, user_name
                        )

                    elif response.status == 404:
                        raw_body = await response.text()
                        self.logger.warning(
                            "[library=%s] [user=%s] Recent items returned 404 — library may not be "
                            "visible to this user or does not support DatePlayed sorting. "
                            "URL=%s body=%.300s. Trying fallback query.",
                            library_name, user_name, url, raw_body
                        )
                        fallback_items = await self._fallback_recent_items(
                            user_id, user_name, library_id, library_name
                        )
                        if fallback_items is not None:
                            results_by_library[library_name] = fallback_items

                    else:
                        self.logger.error(
                            "Failed to get recent items for library %s (user %s): %d",
                            library_name, user_name, response.status
                        )

            except aiohttp.ClientError as e:
                self.logger.error(
                    "An error occurred while retrieving recent items for library %s (user %s): %s",
                    library_name, user_name, str(e)
                )
            except Exception as e:
                self.logger.error(
                    "Unexpected error retrieving recent items for library %s (user %s): %s",
                    library_name, user_name, str(e)
                )

        return results_by_library if results_by_library else None

    async def _fallback_recent_items(self, user_id, user_name, library_id, library_name):
        """
        Fallback for when the primary recent-items query returns 404.
        Omits SortBy=DatePlayed, which some virtual libraries (e.g. Collections) do not support.
        Uses /Users/{userId}/Items?ParentId=...&IsPlayed=true without date sorting.
        :return: List of items, or None if the fallback also fails.
        """
        url = f"{self.api_url}/Users/{user_id}/Items"
        params = {
            "IsPlayed": "true",
            "Recursive": "true",
            "IncludeItemTypes": "Movie,Episode",
            "Limit": self.max_content_fetch,
            "ParentId": library_id,
            "Fields": "ProviderIds",
        }

        self.logger.debug(
            "[library=%s] [userId=%s] Fallback GET %s params=%s",
            library_name, user_id, url, params
        )

        try:
            session = await self._get_session()
            async with session.get(url, headers=self.headers, params=params, timeout=REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get('Items', [])
                    self.logger.info(
                        "[library=%s] [user=%s] Fallback retrieved %d items",
                        library_name, user_name, len(items)
                    )
                    return items
                else:
                    raw_body = await response.text()
                    self.logger.warning(
                        "[library=%s] [user=%s] Fallback also failed: %d body=%.300s — skipping library.",
                        library_name, user_name, response.status, raw_body
                    )
                    return None
        except Exception as e:
            self.logger.error(
                "[library=%s] [user=%s] Fallback error: %s",
                library_name, user_name, str(e)
            )
            return None

    
    async def get_libraries(self):
        """
        Retrieves list of library asynchronously.
        """
        self.logger.info("Searching Jellyfin libraries.")

        url = f"{self.api_url}/Library/VirtualFolders"
        self.logger.debug(f'Requesting libraries from {url}')

        try:
            session = await self._get_session()
            async with session.get(
                url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    libraries = await response.json()
                    self.logger.debug(f'Libraries retrieved: {libraries}')
                    return libraries
                self.logger.error(
                    "Failed to get libraries %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error(
                "An error occurred while retrieving libraries: %s", str(e))
