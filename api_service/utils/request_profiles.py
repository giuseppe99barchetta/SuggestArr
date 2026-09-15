"""Validation for per-media-type request profiles.

A request profile pins how an item reaches Radarr/Sonarr: which server, which
quality profile, which root folder.  Jobs carry one as a default for everything
they suggest; an approval can carry one for the items being approved right now.

Both callers need the same two checks — the shape, and whether Jellyseerr
actually knows the ids — so they live here rather than in one blueprint that
the other has to import from.
"""
from api_service.config.logger_manager import LoggerManager
from api_service.services.config_service import ConfigService
from api_service.services.seer.seer_client import SeerClient
from api_service.utils.asyncio_loop import run_coroutine_sync

logger = LoggerManager.get_logger("RequestProfiles")

MEDIA_TYPES = ('movie', 'tv')
PROFILE_KEYS = ('serverId', 'profileId', 'rootFolder', 'is4k', 'languageProfileId')


def _run_async(coro):
    """Run an async coroutine synchronously on a per-invocation event loop."""
    return run_coroutine_sync(coro, logger)


def validate_request_profiles(value):
    """
    Validate the shape of a per-media-type request profile mapping.

    Args:
        value: ``{'movie': {...}, 'tv': {...}}`` with any subset of
               PROFILE_KEYS per entry, or None.

    Returns:
        dict: The mapping, unchanged, or ``{}`` when None was given.

    Raises:
        ValueError: On any unexpected key, wrong type, or a partial
                    server/profile/root-folder triple.
    """
    if value is None:
        return {}
    if not isinstance(value, dict) or any(key not in MEDIA_TYPES for key in value):
        raise ValueError('request_profiles must contain only movie and tv')
    for profile in value.values():
        if not isinstance(profile, dict) or any(key not in PROFILE_KEYS for key in profile):
            raise ValueError('Invalid request profile')
        if profile.get('serverId') is not None and not isinstance(profile['serverId'], int):
            raise ValueError('serverId must be an integer')
        if profile.get('profileId') is not None and not isinstance(profile['profileId'], int):
            raise ValueError('profileId must be an integer')
        if profile.get('rootFolder') is not None and not isinstance(profile['rootFolder'], str):
            raise ValueError('rootFolder must be a string')
        if profile.get('is4k') is not None and not isinstance(profile['is4k'], bool):
            raise ValueError('is4k must be a boolean')
        if profile.get('languageProfileId') is not None and not isinstance(profile['languageProfileId'], int):
            raise ValueError('languageProfileId must be an integer')
        # A quality profile id only means something together with the server it
        # belongs to, and Radarr refuses an item without a root folder — so the
        # three are all-or-nothing.
        present = [profile.get(key) is not None for key in ('serverId', 'profileId', 'rootFolder')]
        if any(present) and not all(present):
            raise ValueError('serverId, profileId and rootFolder must be selected together')
    return value


def validate_request_profiles_with_seer(profiles):
    """
    Check the ids against what Jellyseerr really offers.

    The shape check above cannot tell profile 7 from profile 70; both are
    integers.  A wrong one is accepted by Jellyseerr and then fetches the item
    with someone else's quality — so ask the server.

    Args:
        profiles: Output of validate_request_profiles().

    Raises:
        ValueError: When a server, quality profile or root folder is unknown.
    """
    if not any(profiles.values()):
        return
    env = ConfigService.get_runtime_config()

    async def check():
        async with SeerClient(env.get('SEER_API_URL', ''), env.get('SEER_TOKEN', ''),
                              session_token=env.get('SEER_SESSION_TOKEN')) as seer:
            for media_type, profile in profiles.items():
                if not profile or profile.get('serverId') is None:
                    continue
                servers = await (seer.get_radarr_servers() if media_type == 'movie'
                                 else seer.get_sonarr_servers())
                server = next((item for item in servers or [] if item.get('id') == profile['serverId']), None)
                if not server:
                    raise ValueError(f"Unknown {media_type} server")
                if profile.get('profileId') not in {item.get('id') for item in server.get('profiles', [])}:
                    raise ValueError(f"Unknown {media_type} quality profile")
                if profile.get('rootFolder') not in {item.get('path') for item in server.get('rootFolders', [])}:
                    raise ValueError(f"Unknown {media_type} root folder")

    _run_async(check())
