"""
This module provides the JellyfinClient class for interacting with the Jellyfin API.
The client can retrieve users, recent items, and provider IDs for media content.

Classes:
    - JellyfinClient: A class that handles communication with the Jellyfin API.
"""
import aiohttp
from api_service.config.logger_manager import LoggerManager

# Constants
REQUEST_TIMEOUT = 10  # Timeout in seconds for HTTP requests


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
            async with aiohttp.ClientSession() as session:
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

        libraries = self.libraries if self.libraries else await self.get_libraries()
        if not libraries:
            self.logger.error("No libraries found.")
            return None

        for library in libraries:
            library_id = library.get('id')
            library_name = library.get('name')

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
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.api_url}/Items",
                        headers=self.headers,
                        params=params,
                        timeout=REQUEST_TIMEOUT
                    ) as response:
                        if response.status != 200:
                            self.logger.error(
                                "Failed to get items for library %s: %d",
                                library_name, response.status
                            )
                            continue

                        data = await response.json()
                        items = data.get("Items", [])

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

                        self.logger.info(
                            "Retrieved %d valid items in %s",
                            len(results_by_library["tv"]) + len(results_by_library["movie"]),
                            library_name
                        )

            except aiohttp.ClientError as e:
                self.logger.error(
                    "Error retrieving items for library %s: %s",
                    library_name, str(e)
                )

        return results_by_library

    async def get_recent_items(self, user):
        """
        Retrieves a list of recently played items for a given user from specific libraries asynchronously.
        :param user_id: The ID of the user whose recent items are to be retrieved.
        :return: A combined list of recent items from all specified libraries, organized by library.
        """
        results_by_library = {}
        seen_series = set()  # Track seen series to avoid duplicates

        url = f"{self.api_url}/Items"
        self.logger.debug(f'Requesting recent items for user {user["name"]} from {url}')

        for library in self.libraries:
            library_id = library.get('id')

            params = {
                "SortBy": "DatePlayed",
                "SortOrder": "Descending",
                'isPlayed': "true",
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Episode",
                "userId": user['id'],
                "Limit": self.max_content_fetch,
                "ParentID": library_id,
                "Fields": "ProviderIds",
            }
            self.logger.debug(f'Requesting recent items for library {library.get("name")} with params: {params}')

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=self.headers, params=params, timeout=REQUEST_TIMEOUT) as response:
                        if response.status == 200:
                            library_items = await response.json()
                            items = library_items.get('Items', [])
                            self.logger.debug(f'Recent items retrieved for library {library.get("name")}: {items}')

                            filtered_items = []  # Store the filtered items for this library

                            for item in items:
                                # Check if we've reached the max content fetch limit
                                if len(filtered_items) >= int(self.max_content_fetch):
                                    break

                                # If the item is an episode, check for its series
                                if item['Type'] == 'Episode':
                                    series_title = item['SeriesName']
                                    if series_title not in seen_series:
                                        seen_series.add(series_title)
                                        filtered_items.append(item)  # Add the episode as part of the series
                                else:
                                    filtered_items.append(item)  # Add movies directly

                            results_by_library[library.get('name')] = filtered_items  # Add filtered items to the results by library
                            self.logger.info(f"Retrieved {len(filtered_items)} watched items in {library.get('name')}. for user {user['name']}")

                        else:
                            self.logger.error(
                                "Failed to get recent items for library %s (user %s): %d", library.get('name'), user['name'], response.status)
            except aiohttp.ClientError as e:
                self.logger.error(
                    "An error occurred while retrieving recent items for library %s (user %s): %s", library.get('name'), user['name'], str(e))
            except Exception as e:
                self.logger.error(e)

        return results_by_library if results_by_library else None

    
    async def get_libraries(self):
        """
        Retrieves list of library asynchronously.
        """
        self.logger.info("Searching Jellyfin libraries.")

        url = f"{self.api_url}/Library/VirtualFolders"
        self.logger.debug(f'Requesting libraries from {url}')

        try:
            async with aiohttp.ClientSession() as session:
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
