from services.jellyfin.jellyfin_client import JellyfinClient
from services.jellyseer.seer_client import SeerClient
from services.plex.plex_client import PlexClient

def get_client(service_type, api_url, api_key, **kwargs):
    """
    Return the appropriate client based on the service type.
    :param service_type: The type of service ('jellyfin', 'seer', 'plex')
    :param api_url: The API URL for the service
    :param api_key: The API key or token
    :param kwargs: Additional parameters like user credentials
    :return: Initialized client for the specified service
    """
    if service_type == 'jellyfin':
        return JellyfinClient(api_url=api_url, token=api_key)
    elif service_type == 'seer':
        return SeerClient(api_url=api_url, api_key=api_key, **kwargs)
    elif service_type == 'plex':
        return PlexClient(api_url=api_url, token=api_key)
    else:
        raise ValueError(f"Unknown service type: {service_type}")
