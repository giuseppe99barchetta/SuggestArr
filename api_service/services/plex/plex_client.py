"""
This module provides the PlexClient class for interacting with the Plex API.
The client can retrieve users, recent items, and libraries.

Classes:
    - PlexClient: A class that handles communication with the Plex API.
"""
import asyncio
import json
import aiohttp
from api_service.config.logger_manager import LoggerManager
from api_service.exceptions.api_exceptions import PlexConnectionError, PlexClientError

# Constants
REQUEST_TIMEOUT = 10  # Timeout in seconds for HTTP requests


class PlexClient:
    """
    A client to interact with the Plex API, allowing the retrieval of users, recent items,
    and libraries.
    """

    def __init__(self, token, api_url=None, max_content=10, library_ids=None, client_id=None, user_ids=None):
        """
        Initializes the PlexClient with the provided API URL and token.
        :param api_url: The base URL for the Plex API.
        :param token: The authentication token for Plex.
        :param max_content: Maximum number of recent items to fetch.
        """
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.max_content_fetch = max_content
        self.api_url = api_url
        self.library_ids = library_ids
        self.user_ids = user_ids
        self.base_url = 'https://plex.tv/api/v2'
        self.headers = {
            "X-Plex-Token": token, 
            "Accept": 'application/json'
        }
        
        if client_id:
            self.headers['X-Plex-Client-Identifier'] = client_id

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

    async def _safe_json_decode(self, response):
        """
        Safely decode JSON response with fallback encoding support
        :param response: aiohttp response object
        :return: decoded JSON data
        :raises: PlexClientError if decoding fails
        """
        try:
            text = await response.text()
            return json.loads(text)
        except UnicodeDecodeError:
            try:
                content = await response.read()
                text = content.decode('latin-1')
                return json.loads(text)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                self.logger.error("Failed to decode response content: %s", str(e))
                raise PlexClientError(f"Failed to decode Plex response: {str(e)}")

    async def get_all_users(self):
        """
        Retrieves a combined list of all users (both friends and local accounts) from the Plex server asynchronously.
        Only includes 'id' and 'name' for each user.
        :return: A list of users with 'id' and 'name' if successful, otherwise an empty list.
        """
        self.logger.info("Fetching all users from Plex server")
        friends_url = f"{self.base_url}/friends"
        accounts_url = f"{self.api_url}/accounts"
        users = []

        try:
            session = await self._get_session()
            # Request for friends
            self.logger.debug(f"Fetching friends from: {friends_url}")
            async with session.get(friends_url, headers=self.headers, timeout=REQUEST_TIMEOUT) as friends_response:
                if friends_response.status == 200:
                    friends = await self._safe_json_decode(friends_response)
                    self.logger.debug(f"Retrieved {len(friends)} friends from Plex")
                    # Extract 'id' and 'name' from each friend (skip users without username)
                    users.extend({'id': friend['id'], 'name': friend['title']} for friend in friends if friend.get('username'))
                else:
                    self.logger.error("Failed to retrieve friends: HTTP %d", friends_response.status)

            # Request for local accounts
            self.logger.debug(f"Fetching local accounts from: {accounts_url}")
            async with session.get(accounts_url, headers=self.headers, timeout=REQUEST_TIMEOUT) as accounts_response:
                if accounts_response.status == 200:
                    accounts_data = await self._safe_json_decode(accounts_response)
                    accounts = accounts_data.get('MediaContainer', {}).get('Account', [])
                    self.logger.debug(f"Retrieved {len(accounts)} local accounts from Plex")
                    # Extract 'id' and 'name' from each local account (skip users without username)
                    users.extend({'id': account['id'], 'name': account['name']} for account in accounts if account.get('name'))
                else:
                    self.logger.error("Failed to retrieve local accounts: HTTP %d", accounts_response.status)

            unique_users = {user['id']: user for user in users}.values()
            sorted_users = sorted(unique_users, key=lambda x: x['id'])
            self.logger.info(f"Successfully retrieved {len(sorted_users)} unique users from Plex")

        except aiohttp.ClientError as e:
            self.logger.error("Network error occurred while retrieving users: %s", str(e))
            raise PlexConnectionError(f"Failed to connect to Plex server: {str(e)}")
        except Exception as e:
            self.logger.error("Unexpected error occurred while retrieving users: %s", str(e))
            raise PlexClientError(f"Unexpected error while retrieving users: {str(e)}")

        return list(sorted_users)

    async def get_recent_items(self):
        """
        Retrieves a list of recently viewed items asynchronously.
        :return: A list of recent items in JSON format if successful, otherwise an empty list.
        """
        all_filtered_items = []
        user_ids = self.user_ids if self.user_ids else [None]  # Use None if no specific user is selected

        for user_id in user_ids:
            url = f"{self.api_url}/status/sessions/history/all"
            params = {
                "sort": "viewedAt:desc",
            }

            # If a specific user is selected, add the accountID parameter
            # Handle both dict format {id: 'xxx', name: 'yyy'} and plain string 'xxx'
            if user_id:
                account_id = user_id.get('id') if isinstance(user_id, dict) else user_id
                params["accountID"] = account_id
    
            # Add library filtering if libraries are specified
            if self.library_ids:
                # Handle both dict format {id: 'xxx', name: 'yyy'} and plain string 'xxx'
                library_id_list = [str(lib.get('id')) if isinstance(lib, dict) else str(lib) for lib in self.library_ids]
                params["librarySectionIDs"] = ','.join(library_id_list)
    
            try:
                session = await self._get_session()
                async with session.get(url, headers=self.headers, params=params, timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        data = await self._safe_json_decode(response)
                        metadata = data.get('MediaContainer', {}).get('Metadata', [])

                        # Filter items for this specific user (or all users) and add to the combined list
                        filtered_items = await self.filter_recent_items(metadata)
                        all_filtered_items.extend(filtered_items)
                        if user_id:
                            # Get user identifier for logging (handle both dict and string formats)
                            user_identifier = user_id.get('id') if isinstance(user_id, dict) else user_id
                            self.logger.info(f"User {user_identifier}: Returning {len(filtered_items)} filtered recent items.")
                        else:
                            self.logger.info(f"All users: Returning {len(filtered_items)} filtered recent items.")
                    else:
                        user_identifier = user_id.get('id') if isinstance(user_id, dict) else user_id if user_id else "all"
                        self.logger.error("Failed to retrieve recent items for user %s: %d", user_identifier, response.status)
            except aiohttp.ClientError as e:
                user_identifier = user_id.get('id') if isinstance(user_id, dict) else user_id if user_id else "all"
                self.logger.error("An error occurred while retrieving recent items for user %s: %s", user_identifier, str(e))
                raise PlexConnectionError(f"Failed to retrieve recent items from Plex: {str(e)}")
            except Exception as e:
                user_identifier = user_id.get('id') if isinstance(user_id, dict) else user_id if user_id else "all"
                self.logger.error("Unexpected error occurred while retrieving recent items for user %s: %s", user_identifier, str(e))
                raise PlexClientError(f"Unexpected error while retrieving recent items: {str(e)}")
    
        self.logger.info(f"Total filtered items across all users: {len(all_filtered_items)}")
        
        return all_filtered_items


    async def filter_recent_items(self, metadata):
        """
        Filters recent items to avoid duplicates and respects the max content fetch limit.
        :param metadata: List of items to filter.
        :return: Filtered list of items.
        """
        seen_series = set()
        filtered_items = []
        total_items = 0  # Counter for total filtered items
        
        # Pre-calculate a list of target library IDs as strings
        target_library_ids = []
        if self.library_ids:
            target_library_ids = [str(lib.get('id')) if isinstance(lib, dict) else str(lib) for lib in self.library_ids]
    
        for item in metadata:
            # Check if the item's librarySectionID is in the selected libraries
            if target_library_ids:
                item_lib_id = str(item.get('librarySectionID', ''))
                if item_lib_id not in target_library_ids:
                    continue  # Skip items not in the selected libraries
            
            # Check if we've reached the max content fetch limit
            if total_items >= int(self.max_content_fetch):
                break
            
            if item['type'] == 'episode':
                # Check if the series has already been counted
                series_title = item['grandparentTitle']
                if series_title not in seen_series:
                    seen_series.add(series_title)
                    filtered_items.append(item)
                    total_items += 1  # Increment total_items for series
            else:
                filtered_items.append(item)
                total_items += 1  # Increment total_items for movies
    
            # Allow fetching more content if we've only seen episodes from one series
            if total_items < int(self.max_content_fetch) and len(seen_series) == 1:
                continue  # Keep looking for more items
            
        return filtered_items

    async def get_libraries(self):
        """
        Retrieves a list of libraries (sections) from the Plex server asynchronously.
        :return: A list of libraries in JSON format if successful, otherwise an empty list.
        """
        self.logger.info("Fetching libraries from Plex.")

        url = f"{self.api_url}/library/sections"

        try:
            session = await self._get_session()
            async with session.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    data = await self._safe_json_decode(response)
                    return data.get('MediaContainer', {}).get('Directory', [])
                self.logger.error("Failed to retrieve libraries: %d", response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving libraries: %s", str(e))

        return []

    async def get_metadata_provider_id(self, item_id, provider='tmdb'):
        """
        Retrieves the TMDB ID (or other provider ID) for a specific media item asynchronously.
        :param item_id: The ID of the media item.
        :param provider: The provider ID to retrieve (default is 'themoviedb').
        :return: The TMDB ID if found, otherwise None.
        """
        url = f"{self.api_url}{item_id}"
        try:
            session = await self._get_session()
            async with session.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    item_data = await self._safe_json_decode(response)
                    guids = item_data.get('MediaContainer', {}).get('Metadata', [])[0].get('Guid', [])

                    for guid in guids:
                        guid_id = guid.get('id', '')
                        if guid_id.startswith(f'{provider}://'):
                            tmdb_id = guid_id.split(f'{provider}://')[-1]
                            return tmdb_id

                    self.logger.debug("No %s GUID found for item %s (available GUIDs: %s)", provider, item_id, [g.get('id') for g in guids])
                else:
                    self.logger.error("Failed to retrieve metadata for item %s: %d", item_id, response.status)
        except aiohttp.ClientError as e:
            self.logger.error("An error occurred while retrieving metadata for item %s: %s", item_id, str(e))

        return None
    
    async def get_servers(self):
        """
        obtain available Plex server for current user
        :return: Lista di server Plex se trovati, altrimenti None.
        """
        url = f"{self.base_url}/resources"
        try:
            session = await self._get_session()
            async with session.get(url, headers=self.headers, timeout=10) as response:
                if response.status == 200:
                    servers = await self._safe_json_decode(response)
                    return servers
                else:
                    print(f"Errore durante il recupero dei server Plex: {response.status}")
                    return None
        except aiohttp.ClientError as e:
            print(f"Errore durante il recupero dei server Plex: {str(e)}")
            return None
        
    async def init_existing_content(self):
        self.logger.info('Searching all content in Plex')
        self.existing_content = await self.get_all_library_items()
        
    async def get_all_library_items(self):
        """
        Retrieves all items from the specified libraries or all libraries if no specific IDs are provided.
        :return: A dictionary of items organized by library name.
        """
        results_by_library = {}
        
        if self.library_ids:
            # Handle both dict format {id: 'xxx', name: 'yyy'} and plain string 'xxx'
            libraries = []
            for index, lib in enumerate(self.library_ids):
                if isinstance(lib, dict):
                    # Already in dict format with 'id' and 'name'
                    libraries.append({'key': lib.get('id'), 'title': lib.get('name', f'Library {index}')})
                else:
                    # Plain string format
                    libraries.append({'key': lib, 'title': f'Library {index}'})
        else:
            libraries = await self.get_libraries()
    
        if not libraries:
            self.logger.error("No libraries found.")
            return None
    
        session = await self._get_session()
        tasks = [
            self._fetch_library_items(session, library, results_by_library)
            for library in libraries
        ]
        await asyncio.gather(*tasks)
    
        return results_by_library if results_by_library else None
    
    async def _fetch_library_items(self, session, library, results_by_library):
        """
        Fetch items for a single library and update results_by_library.
        """
        library_id = library.get('key')
        library_name = library.get('title')
    
        if not isinstance(library_id, str) or not isinstance(library_name, str):
            self.logger.error(f"Invalid library data - ID: {library_id}, Name: {library_name}")
            return
    
        url = f"{self.api_url}/library/sections/{library_id}/all"

        try:
            safe_headers = {k: '***' if k == 'X-Plex-Token' else v for k, v in self.headers.items()}
            self.logger.debug(f"Requesting URL: {url} with headers: {safe_headers} and timeout: {REQUEST_TIMEOUT}")
            async with session.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    library_items = await self._safe_json_decode(response)
                    items = library_items.get('MediaContainer', {}).get('Metadata', [])

                    if isinstance(items, list):
                        # Extract TMDB ID for each element in list
                        processed_items = []
                        library_type = None
                        for item in items:
                            library_type = 'tv' if item.get('type') == 'show' else 'movie'
                            item_id = item.get('key').replace('/children', '')
                            tmdb_id = await self.get_metadata_provider_id(item_id)
                            if tmdb_id:
                                item['tmdb_id'] = tmdb_id
                            processed_items.append(item)

                        if library_type:
                            results_by_library.setdefault(library_type, []).extend(processed_items)
                        self.logger.info(f"Retrieved {len(processed_items)} items in {library_type} with TMDB IDs")

                    else:
                        self.logger.error(f"Expected list for items, got {type(items)}")
                else:
                    self.logger.error("Failed to get items for library %s: %d", library_name, response.status)

        except aiohttp.ClientError as e:
            self.logger.error(f"Client error for library {library_name}: {e}")
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout error for library {library_name}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred for library {library_name}: {e}")