from api_service.config.config import get_request_backend
from api_service.services.arr.arr_request_client import ArrRequestClient
from api_service.services.jellyfin.jellyfin_client import JellyfinClient
from api_service.services.seer.seer_client import SeerClient
from api_service.services.plex.plex_client import PlexClient

def build_request_client(env_vars, number_of_seasons, exclude_downloaded, exclude_requested,
                         request_first_season_only, queue_context=None):
    """Return the client requests are enqueued with, per ``REQUEST_BACKEND``.

    ``seer`` and ``both`` use Seer (Radarr/Sonarr then only feed the library check);
    ``arr`` delivers straight to Radarr/Sonarr.
    """
    if get_request_backend(env_vars) == 'arr':
        return ArrRequestClient(env_vars, number_of_seasons, exclude_downloaded, exclude_requested,
                                request_first_season_only, queue_context=queue_context)
    anime_profile_config = env_vars.get('SEER_ANIME_PROFILE_CONFIG')
    return SeerClient(
        env_vars['SEER_API_URL'], env_vars['SEER_TOKEN'], env_vars['SEER_USER_NAME'],
        env_vars['SEER_USER_PSW'], env_vars['SEER_SESSION_TOKEN'], number_of_seasons,
        exclude_downloaded, exclude_requested,
        anime_profile_config if isinstance(anime_profile_config, dict) else {},
        request_first_season_only, queue_context=queue_context,
    )


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
