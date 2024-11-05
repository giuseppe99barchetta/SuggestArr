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
        self.logger.info('Searching all content in Jellyfin')
        self.existing_content = await self.get_all_library_items()

    async def get_all_users(self):
        """
        Retrieves a list of all users from the Jellyfin server asynchronously.
        :return: A list of users in JSON format if successful, otherwise an empty list.
        """
        url = f"{self.api_url}/Users"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [{"id": user["Id"], "name": user["Name"], "policy": user["Policy"]} for user in data]
                    self.logger.error("Failed to retrieve users: %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving users: %s", str(e))

        return []
    
    async def get_all_library_items(self):
        """
        Retrieves all items from the specified libraries or all libraries if no specific IDs are provided.
        :return: A dictionary of items organized by library name.
        """
        results_by_library = {}
        users = await self.get_all_users()
        admin_user = next((user for user in users if user.get('policy', {}).get('IsAdministrator')), None)
        libraries = self.libraries if self.libraries else await self.get_libraries()

        if not libraries:
            self.logger.error("No libraries found.")
            return None

        for library in libraries:
            library_id = library.get('id')
            library_name = library.get('name')
            library_type = ''

            params = {
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Series",
                "ParentID": library_id
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.api_url}/Items", headers=self.headers, params=params, timeout=REQUEST_TIMEOUT) as response:
                        if response.status == 200:
                            library_items = await response.json()
                            items = library_items.get('Items', [])
                            
                            for item in items:
                                item_id = item.get('Id')
                                library_type = 'tv' if item.get('Type') == 'Series' else 'movie'
                                if item_id:
                                    tmdb_id = await self.get_item_provider_id(admin_user['id'], item_id, provider='Tmdb')
                                    item['tmdb_id'] = tmdb_id
                                
                            results_by_library[library_type] = items
                            self.logger.info(f"Retrieved {len(items)} items in {library_name}")
                        else:
                            self.logger.error(
                                "Failed to get items for library %s: %d", library_name, response.status)
            except TypeError as e:
                self.logger.error(f"TypeError: {e}. Params: {params}, Timeout: {REQUEST_TIMEOUT}")
            except aiohttp.ClientError as e:
                self.logger.error(
                    "An error occurred while retrieving items for library %s: %s", library_name, str(e))
            except Exception as e:
                self.logger.error(e)

        return results_by_library if results_by_library else None


    async def get_recent_items(self, user):
        """
        Retrieves a list of recently played items for a given user from specific libraries asynchronously.
        :param user_id: The ID of the user whose recent items are to be retrieved.
        :return: A combined list of recent items from all specified libraries, organized by library.
        """
        results_by_library = {}
        seen_series = set()  # Track seen series to avoid duplicates

        url = f"{self.api_url}/Items"

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
                "ParentID": library_id
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=self.headers, params=params, timeout=REQUEST_TIMEOUT) as response:
                        if response.status == 200:
                            library_items = await response.json()
                            items = library_items.get('Items', [])

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

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        return await response.json()
                    self.logger.error(
                        "Failed to get libraries %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error(
                "An error occurred while retrieving libraries: %s", str(e))

    async def get_item_provider_id(self, user_id, item_id, provider='Tmdb'):
        """
        Retrieves the provider ID (e.g., TMDb or TVDb) for a specific media item asynchronously.
        :param user_id: The ID of the user.
        :param item_id: The ID of the media item.
        :param provider: The provider ID to retrieve (default is 'Tmdb').
        :return: The provider ID if found, otherwise None.
        """
        url = f"{self.api_url}/Users/{user_id}/Items/{item_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        item_data = await response.json()
                        return item_data.get('ProviderIds', {}).get(provider)

                    self.logger.error("Failed to retrieve ID for item %s: %d", item_id, response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving ID for item %s: %s", item_id, str(e))

        return None
