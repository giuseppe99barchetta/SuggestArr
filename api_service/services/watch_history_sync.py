"""Read a media-server user's play history into ``watched_media``.

Shared by the Ratings page (on demand) and the rating-prompt job (scheduled).
"""
from datetime import timedelta, timezone

from api_service.services.config_service import ConfigService
from api_service.services.year_recap import PlayedTitles
from api_service.utils.asyncio_loop import run_coroutine_sync

# Jellyfin only keeps the last play per item, so re-read a day back to catch replays.
SYNC_OVERLAP = timedelta(days=1)
SUPPORTED_PROVIDERS = {'jellyfin', 'emby', 'plex'}


def selected_provider() -> str:
    """The configured media server (``jellyfin``, ``emby``, ``plex``) or an empty string."""
    return str(ConfigService.get_runtime_config().get('SELECTED_SERVICE') or '').lower()


def identity_for_user(db, user_id: int, provider: str, verified_only: bool = False):
    """Media identity of a SuggestArr account for the given server, or None when not linked.

    Args:
        db: DatabaseManager.
        user_id: SuggestArr account id.
        provider: ``jellyfin``, ``emby`` or ``plex``.
        verified_only: Ignore profile links an administrator has not verified.
    """
    if provider not in SUPPORTED_PROVIDERS:
        return None
    for profile in db.get_user_media_profiles(user_id):
        if profile.get('provider') == provider and (profile.get('verified') or not verified_only):
            return db.upsert_media_user_identity(
                provider, str(profile['external_user_id']), profile.get('external_username'))
    return None


def sync_identity_history(db, provider: str, identity: dict, logger):
    """Store plays newer than the last sync for one identity.

    Returns:
        ``None`` when the media server is not configured, otherwise
        ``(played, truncated, added)``: the titles read, whether the scan was cut short,
        and how many titles were new. Raises when the server cannot be read.
    """
    latest = db.latest_server_play(identity['id'])
    since = latest.replace(tzinfo=timezone.utc) - SYNC_OVERLAP if latest else None
    result = run_coroutine_sync(PlayedTitles().titles(
        provider, identity['external_user_id'], ConfigService.get_runtime_config(), since=since), logger)
    if result is None:
        return None
    played, truncated = result
    return played, truncated, db.record_server_plays(identity['id'], played)
