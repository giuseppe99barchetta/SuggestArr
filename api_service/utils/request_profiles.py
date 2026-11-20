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
PROFILE_KEYS = ('serverId', 'profileId', 'rootFolder', 'is4k', 'languageProfileId', 'tags')
# A profile with serverId names a Seer server (Seer shape); without it, it is applied straight
# by Radarr/Sonarr with direct delivery (Arr shape: profileId, rootFolder, tags).
SEER_ONLY_KEYS = ('serverId', 'is4k', 'languageProfileId')


def is_seer_profile(profile):
    """Whether a per-media-type profile is in Seer shape (it names a Seer server)."""
    return isinstance(profile, dict) and profile.get('serverId') is not None


class UnknownSeerProfileError(ValueError):
    """A server, quality profile or root folder Jellyseerr does not offer; safe to show."""


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
        if profile.get('tags') is not None and (not isinstance(profile['tags'], list) or any(
                type(tag) is not int for tag in profile['tags'])):
            raise ValueError('tags must be a list of integers')
        # A quality profile id only means something together with the server it
        # belongs to, and Radarr refuses an item without a root folder — so the
        # three are all-or-nothing (the two, for a profile applied straight by Radarr/Sonarr).
        if is_seer_profile(profile):
            if profile.get('tags') is not None:
                raise ValueError('tags are only set on Radarr/Sonarr profiles')
            required = ('serverId', 'profileId', 'rootFolder')
        else:
            if any(profile.get(key) is not None for key in SEER_ONLY_KEYS):
                raise ValueError('is4k and languageProfileId need a Seer server')
            required = ('profileId', 'rootFolder')
        present = [profile.get(key) is not None for key in required]
        if any(present) and not all(present):
            raise ValueError(', '.join(required) + ' must be selected together')
        if profile.get('tags') and not all(present):
            raise ValueError('tags need a quality profile and a root folder')
    return value


def validate_request_profiles_with_arr(profiles, env):
    """
    Check Radarr/Sonarr-shape profiles against what the instance serving each type offers.

    Seer-shape profiles are skipped (they are ignored with direct delivery).

    Args:
        profiles: Output of validate_request_profiles().
        env: Runtime configuration with the RADARR_* / SONARR_* settings.

    Raises:
        ValueError: When an id is unknown, or the instance cannot be asked.
    """
    from api_service.config.config import ARR_INSTANCES
    from api_service.services.arr.arr_client import ArrClient

    wanted = {media_type: profile for media_type, profile in (profiles or {}).items()
              if profile and not is_seer_profile(profile) and profile.get('profileId') is not None}
    if not wanted:
        return

    async def check():
        for service, (url_key, token_key, media_type) in ARR_INSTANCES.items():
            profile = wanted.get(media_type)
            if profile is None:
                continue
            name = service.capitalize()
            if not env.get(url_key) or not env.get(token_key):
                raise UnknownSeerProfileError(f"{name} is not configured")
            async with ArrClient(service, env[url_key], env[token_key]) as client:
                options = await client.get_options()
            if profile['profileId'] not in {item['id'] for item in options['profiles']}:
                raise UnknownSeerProfileError(f"Unknown {name} quality profile")
            if profile['rootFolder'] not in {item['path'] for item in options['rootFolders']}:
                raise UnknownSeerProfileError(f"Unknown {name} root folder")
            if not set(profile.get('tags') or []) <= {item['id'] for item in options['tags']}:
                raise UnknownSeerProfileError(f"Unknown {name} tag")

    try:
        _run_async(check())
    except UnknownSeerProfileError:
        raise
    except Exception:
        logger.warning('Could not verify request profiles with Radarr/Sonarr', exc_info=True)
        raise ValueError('Could not verify request profiles with Radarr/Sonarr') from None


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
                    raise UnknownSeerProfileError(f"Unknown {media_type} server")
                if profile.get('profileId') not in {item.get('id') for item in server.get('profiles', [])}:
                    raise UnknownSeerProfileError(f"Unknown {media_type} quality profile")
                if profile.get('rootFolder') not in {item.get('path') for item in server.get('rootFolders', [])}:
                    raise UnknownSeerProfileError(f"Unknown {media_type} root folder")

    try:
        _run_async(check())
    except UnknownSeerProfileError:
        raise
    except ValueError:
        # Client errors (e.g. aiohttp.InvalidURL) carry the Seer address; callers show the message.
        logger.warning('Could not verify request profiles with Seer', exc_info=True)
        raise ValueError('Could not verify request profiles with Seer') from None
