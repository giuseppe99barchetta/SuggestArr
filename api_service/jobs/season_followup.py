"""Next-season follow-up: request season S+1 when the media server's users near the end of S.

Reads the play history of every account on the selected media server, keeps the furthest
episode watched per show, and requests the next season through Seer or straight from Sonarr.
A show whose next season does not exist yet stays tracked, so it is requested once TMDb lists it.
"""
import asyncio
import hashlib
import time
from datetime import datetime, timedelta, timezone

from api_service.config.config import ARR_INSTANCES, arr_default_profile, get_request_backend
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
# Shared with request expiry and replacements, so the automations never overlap.
from api_service.jobs import queue_worker
from api_service.jobs.request_expiry import _run_lock
from api_service.services.arr.arr_client import ArrClient
from api_service.services.config_service import ConfigService
from api_service.services.seer.seer_client import SeerClient
from api_service.services.tmdb.tmdb_client import TMDbClient
from api_service.services.year_recap import RecapWatchSync
from api_service.utils.asyncio_loop import run_coroutine_sync
from api_service.utils.ssrf_guard import normalize_base_url

logger = LoggerManager.get_logger('SeasonFollowup')

SCAN_MAX_PAGES = 100  # 50,000 plays per account; the default scan stops at 5,000
SCAN_TIMEOUT = 600
WATERMARK_OVERLAP = timedelta(days=1)  # Jellyfin keeps only the last play per item: re-read a day back


def server_key(provider, url):
    """Stable key of one media server: a new provider or URL starts a fresh history scan."""
    return hashlib.sha256(f'{provider}|{url}'.encode()).hexdigest()


class SeasonPlays(RecapWatchSync):
    """Episode plays of every account on the media server, with their TMDb show ids."""

    async def read(self, plex, url, token, start, end):
        """Scan the server and resolve each episode's show.

        :return: Tuple ``(entries, truncated, cutoff)``: resolved episode entries older than
            ``cutoff``, and ``cutoff`` = the date of the first play whose show could not be
            resolved because of a transient error (None when every play was handled).
        """
        self.guard_outbound = True
        self.private_urls = self.allowed_urls = (url,)
        url = url.rstrip('/')
        headers = self._headers(plex, token)
        try:
            async with asyncio.timeout(SCAN_TIMEOUT):
                entries, truncated = await self._scan(plex, [], url, headers, start, end, server=True,
                                                      max_pages=SCAN_MAX_PAGES)
                entries = [entry for entry in entries if entry['kind'] == 'episode']
                await self._resolve(plex, url, headers, entries)
        finally:
            await self.close()
        # Only a transient lookup failure holds the watermark back. A play whose show has no TMDb id
        # (or no series at all) stays unresolvable, and waiting for it would stop the scan for good;
        # it is counted once the show gets an id and is played again.
        cutoff = min((entry['date'] for entry in entries if entry.get('unresolved')), default=None)
        if cutoff:
            entries = [entry for entry in entries if entry['date'] < cutoff]
        return entries, truncated, cutoff


def furthest_positions(entries):
    """Reduce episode plays to one row per show: furthest ``(season, episode)`` and newest play.

    Plays without a show id are ignored. Specials (season 0) and plays without numbers only
    count for the newest play; ``season``/``episode`` stay None when a show has no regular episode.
    """
    shows = {}
    for entry in entries:
        try:
            tmdb_id = int(entry['tmdb'])
        except (TypeError, ValueError, KeyError):
            continue
        row = shows.setdefault(tmdb_id, {'tmdb_id': tmdb_id, 'season': None, 'episode': None,
                                         'watched_at': entry['date']})
        row['watched_at'] = max(row['watched_at'], entry['date'])
        try:
            position = (int(entry['season']), int(entry['episode']))
        except (TypeError, ValueError, KeyError):
            continue
        if position[0] >= 1 and (row['season'] is None or position > (row['season'], row['episode'])):
            row['season'], row['episode'] = position
    return list(shows.values())


def next_season(show, seasons, episodes_before_end):
    """Season to request for a tracked show, or None.

    :param show: ``{season, episode, requested_season}`` from ``season_followups``.
    :param seasons: ``{season_number: episode_count}`` from TMDb.
    :param episodes_before_end: Request once at most this many episodes of the season remain.
    """
    count = seasons.get(show['season'])
    if not count or count <= 0:
        return None  # TMDb does not know the length of the season yet
    target = show['season'] + 1
    if target not in seasons or show['episode'] < count - episodes_before_end:
        return None
    if show['requested_season'] is not None and show['requested_season'] >= target:
        return None
    return target


def _tmdb_client(env):
    return TMDbClient(env.get('TMDB_API_KEY'), 10, 0, 0, True, 0, [], [], None, [])


async def _deliver(env, backend, tmdb_id, tvdb_id, season, clients):
    """Send one season to the configured backend; True only once it is accepted."""
    if backend == 'arr':
        url_key, token_key, _ = ARR_INSTANCES['sonarr']
        url, token = env.get(url_key), env.get(token_key)
        profile = arr_default_profile(env, 'tv')
        if not url or not token or profile is None:
            logger.warning("Season follow-up: no Sonarr instance or default TV profile; tmdb:%s skipped.", tmdb_id)
            return False
        if 'sonarr' not in clients:
            clients['sonarr'] = ArrClient('sonarr', url, token)
        return await clients['sonarr'].request_season(tmdb_id, season, profile)
    if 'seer' not in clients:
        clients['seer'] = SeerClient(env.get('SEER_API_URL', ''), env.get('SEER_TOKEN', ''),
                                     seer_user_name=env.get('SEER_USER_NAME'),
                                     seer_password=env.get('SEER_USER_PSW'),
                                     session_token=env.get('SEER_SESSION_TOKEN'),
                                     exclude_downloaded=False, exclude_watched=False)
    # Same pacing as the queue worker (issue #118: bursts make Seer drop notifications).
    delay = queue_worker._seer_request_delay(env)
    if delay and queue_worker._last_seer_send is not None:
        wait = delay - (time.monotonic() - queue_worker._last_seer_send)
        if wait > 0:
            await asyncio.sleep(wait)
    try:
        return await clients['seer'].request_seasons(tmdb_id, tvdb_id, [season])
    finally:
        queue_worker._last_seer_send = time.monotonic()


async def execute_season_followup(now=None):
    """Run one follow-up pass; manual and scheduled runs share the lock and the enabled gate.

    :param now: Current aware UTC time (tests).
    :return: Summary ``{status, shows, requested, skipped, errors, truncated}``.
    """
    if not _run_lock.acquire(blocking=False):
        return {'status': 'already_running'}
    try:
        env = ConfigService.get_runtime_config()
        result = dict(status='ok', shows=0, requested=0, skipped=0, errors=0, truncated=False)
        if env.get('SEASON_FOLLOWUP_ENABLED') is not True:
            return {**result, 'status': 'disabled'}
        provider = str(env.get('SELECTED_SERVICE') or '').lower()
        prefix = 'JELLYFIN' if provider == 'emby' else provider.upper()  # Emby uses the Jellyfin keys
        url, token = env.get(f'{prefix}_API_URL'), env.get(f'{prefix}_TOKEN')
        if provider not in ('plex', 'jellyfin', 'emby') or not url or not token or not env.get('TMDB_API_KEY'):
            return {**result, 'status': 'not_configured'}
        url = normalize_base_url(url)
        key = server_key(provider, url)
        now = now or datetime.now(timezone.utc)
        window_start = now - timedelta(days=env.get('SEASON_FOLLOWUP_WINDOW_DAYS', 180))
        db = DatabaseManager()
        watermark = db.get_scan_watermark(key)
        start = max(window_start, watermark - WATERMARK_OVERLAP) if watermark else window_start

        entries, truncated, cutoff = await SeasonPlays().read(provider == 'plex', url, token, start, now)
        if truncated:
            result['truncated'] = True
            logger.warning("Season follow-up: the history scan hit its limit; older plays in the window may be missed.")
        # Progress first, watermark second: a crash in between only causes a rescan.
        db.record_season_progress(key, furthest_positions(entries))
        db.set_scan_watermark(key, cutoff or now)

        backend = get_request_backend(env)
        only_suggestarr = env.get('SEASON_FOLLOWUP_ONLY_SUGGESTARR') is True
        episodes_before_end = env.get('SEASON_FOLLOWUP_EPISODES_BEFORE_END', 2)
        shows = db.season_followup_candidates(key, window_start)
        # Requests imported from Seer are in the same table; only SuggestArr's own count here.
        suggestarr_requests = db.get_requested_media_keys() if only_suggestarr else set()
        result['shows'] = len(shows)
        tmdb, clients = _tmdb_client(env), {}
        try:
            for show in shows:
                try:
                    if only_suggestarr and ('tv', str(show['tmdb_id'])) not in suggestarr_requests:
                        continue
                    details = await tmdb.get_tv_seasons(show['tmdb_id'])
                    target = next_season(show, details['seasons'], episodes_before_end) if details else None
                    if target is None:
                        continue
                    if await _deliver(env, backend, show['tmdb_id'], details['tvdb_id'], target, clients):
                        db.mark_season_requested(key, show['tmdb_id'], target)
                        result['requested'] += 1
                        logger.info("Season follow-up: requested season %s of tmdb:%s.", target, show['tmdb_id'])
                    else:
                        result['skipped'] += 1
                except Exception:
                    result['errors'] += 1
                    logger.warning("Season follow-up failed for tmdb:%s; retrying next run.",
                                   show['tmdb_id'], exc_info=True)
        finally:
            await tmdb.close()
            for client in clients.values():
                await client.close()
        return result
    finally:
        _run_lock.release()


def run_season_followup():
    """Scheduler entry point."""
    try:
        run_coroutine_sync(execute_season_followup(), logger)
    except Exception:
        logger.error('Scheduled season follow-up failed', exc_info=True)
