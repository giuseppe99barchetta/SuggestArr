"""Follow requested titles through Seer (or Radarr/Sonarr with direct delivery): requested, processing, available.

Runs on a schedule, reads the media list once and stores only what changed.
A title that becomes available fires the ``request.available`` webhook.
"""
import threading
from urllib.parse import urlsplit

from api_service.config.config import ARR_INSTANCES, get_request_backend
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.arr.arr_client import ArrClient
from api_service.services.config_service import ConfigService
from api_service.services.seer.seer_client import SeerClient, normalize_seer_url
from api_service.utils.asyncio_loop import run_coroutine_sync

logger = LoggerManager.get_logger('AvailabilitySync')
_run_lock = threading.Lock()

# Requested but not (yet) known to Seer, or known without a media status.
REQUESTED = 'requested'


def external_media_url(url, external_base):
    """
    Point Seer's play link at the browser-facing media server address.

    Seer builds Jellyfin/Emby links from its own server address, often an internal
    Docker name; everything before the ``/web/`` app path is swapped for the base.

    Args:
        url: Seer's play link, or None.
        external_base: Configured external URL, or empty.

    Returns:
        The rewritten link, or ``url`` unchanged when there is nothing to rewrite.
    """
    if not url or not external_base:
        return url
    parts = urlsplit(url)
    start = parts.path.find('/web/')
    if start < 0:
        return url
    rewritten = external_base.rstrip('/') + url[len(f'{parts.scheme}://{parts.netloc}') + start:]
    # Longer would not fit the stored column.
    return rewritten if len(rewritten) <= 500 else url


def plan_availability_changes(requested, known, statuses):
    """
    Work out which stored states change and which titles just became available.

    Args:
        requested: Set of ``(media_type, tmdb_id)`` SuggestArr requested.
        known: Dict of stored ``{'status', 'url'}`` from the previous sync.
        statuses: Dict of current Seer ``{'status', 'url'}`` (titles Seer does not list are absent).

    Returns:
        Tuple ``(changes, newly_available)``: changes maps keys to the new state
        (None removes a title no longer requested); newly_available lists keys that
        reached 'available' since a previous sync saw them in another state. The
        very first sync only records the current state, so a library full of old
        requests does not send a burst of notifications.
    """
    changes = {}
    newly_available = []
    first_sync = not known
    for key in requested:
        state = statuses.get(key) or {'status': REQUESTED, 'url': None}
        previous = known.get(key) or {}
        if state == {'status': previous.get('status'), 'url': previous.get('url')}:
            continue
        changes[key] = state
        if state['status'] == 'available' and not first_sync and previous.get('status') != 'available':
            newly_available.append(key)
    for key in known.keys() - requested:
        changes[key] = None
    return changes, newly_available


def notify_owners(db, env, media_type, tmdb_id, play_url=None):
    """
    Tell each account a title was requested for that it is ready, on their own destination.

    Args:
        db: DatabaseManager.
        env: Runtime config (for SELECTED_SERVICE).
        media_type: 'movie' or 'tv'.
        tmdb_id: TMDb id of the title.
        play_url: Link to play it on the media server, when Seer knows one.

    Returns:
        Number of personal notifications queued.
    """
    sent = 0
    try:
        owners = db.get_title_owner_ids(media_type, tmdb_id, env.get('SELECTED_SERVICE'))
        if not owners:
            return 0
        title = (db.get_metadata(str(tmdb_id), media_type) or {}).get('title') or f"{media_type} {tmdb_id}"
        text = f"Your request is ready to watch: {title}" + (f"\n{play_url}" if play_url else "")
        for owner_id in owners:
            sent += bool(db.enqueue_personal_notification(owner_id, 'request.available', text))
    except Exception as exc:
        # A personal message is a courtesy; it must never stop the sync.
        logger.error("Unable to queue personal availability notifications: %s", exc)
    return sent


async def _arr_media_statuses(instances):
    """Merge the statuses of every configured Radarr/Sonarr, or None when any of them cannot be read."""
    statuses = {}
    for service, url, token, _ in instances:
        try:
            async with ArrClient(service, url, token) as client:
                statuses.update(await client.get_media_statuses())
        except Exception as exc:
            logger.warning("Could not read %s's library; availability not updated: %s", service.capitalize(), exc)
            return None
    return statuses


async def sync_availability():
    """
    Update the stored status of every requested title, from Seer or, with direct
    delivery, from Radarr/Sonarr.

    Returns:
        Dict with 'status' ('ok', 'not_configured', 'unavailable' or 'already_running'),
        'changed' and 'available' counts.
    """
    if not _run_lock.acquire(blocking=False):
        return {'status': 'already_running'}
    try:
        env = ConfigService.get_runtime_config()
        if get_request_backend(env) == 'arr':
            instances = [(service, env[url_key], env[token_key], media_type)
                         for service, (url_key, token_key, media_type) in ARR_INSTANCES.items()
                         if env.get(url_key) and env.get(token_key)]
            if not instances:
                return {'status': 'not_configured', 'changed': 0, 'available': 0}
        else:
            try:
                url = normalize_seer_url(env.get('SEER_API_URL', ''))
            except (ValueError, AttributeError):
                url = None
            token = env.get('SEER_TOKEN')
            if not url or not token:
                return {'status': 'not_configured', 'changed': 0, 'available': 0}
        db = DatabaseManager()
        requested = db.get_requested_media_keys()
        if not requested:
            return {'status': 'ok', 'changed': 0, 'available': 0}
        known = db.get_media_availability()
        if get_request_backend(env) == 'arr':
            statuses = await _arr_media_statuses(instances)
            # A type without an instance is left alone: its stored states are neither reset nor removed.
            served = {media_type for *_, media_type in instances}
            requested = {key for key in requested if key[0] in served}
            known = {key: value for key, value in known.items() if key[0] in served}
        else:
            async with SeerClient(url, token) as seer:
                statuses = await seer.get_media_statuses()
        if statuses is None:
            return {'status': 'unavailable', 'changed': 0, 'available': 0}
        if env.get('SELECTED_SERVICE') in ('jellyfin', 'emby'):
            for state in statuses.values():
                state['url'] = external_media_url(state['url'], env.get('JELLYFIN_EXTERNAL_URL'))

        changes, newly_available = plan_availability_changes(requested, known, statuses)
        db.save_media_availability(changes)
        for media_type, tmdb_id in newly_available:
            try:
                db.enqueue_webhook_event('request.available', {'tmdb_id': tmdb_id, 'media_type': media_type})
            except Exception as exc:
                logger.error("Unable to queue request.available webhook: %s", exc)
            notify_owners(db, env, media_type, tmdb_id, (statuses.get((media_type, tmdb_id)) or {}).get('url'))
        if changes:
            logger.info("Availability sync: %d status changes, %d newly available.", len(changes), len(newly_available))
        return {'status': 'ok', 'changed': len(changes), 'available': len(newly_available)}
    finally:
        _run_lock.release()


def run_availability_sync():
    """Scheduler entry point; errors are logged so the schedule keeps running."""
    try:
        run_coroutine_sync(sync_availability(), logger)
    except Exception as exc:
        logger.error("Availability sync failed: %s", exc, exc_info=True)
