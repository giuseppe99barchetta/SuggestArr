"""Read-only native watch-state adapters. Runtime is never treated as watch time.

The annual recap counts plays; the watch sync links plays to requested titles for the hit rate.
"""
import asyncio
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from api_service.db.recap_repository import utc_datetime, watch_provider
from api_service.services.http.base_client import BaseHTTPClient
from api_service.services.plex.plex_client import normalize_guid_provider_id
from api_service.utils.ssrf_guard import normalize_base_url

PAGE_SIZE = 500
MAX_PAGES = 10
MAX_PROFILES = 50


class YearWatchActivity(BaseHTTPClient):
    async def load(self, data, profiles, env):
        provider = data['provider']
        prefix = (provider or '').upper()
        url, token = env.get(f'{prefix}_API_URL'), env.get(f'{prefix}_TOKEN')
        if provider not in ('plex', 'jellyfin') or not url or not token:
            return {'watchStatus': 'not_configured', 'watchNote': 'Configure Plex or Jellyfin to load watch activity.'}
        ids = sorted({str(p['external_user_id']) for p in profiles if p.get('provider') == provider})
        if data['scope'] == 'personal' and not ids:
            return {'watchStatus': 'no_profiles', 'watchNote': f'Link your {data["providerLabel"]} account in My profile to load personal watch activity.'}
        try:
            url = normalize_base_url(url)
            self.guard_outbound = True
            self.private_urls = self.allowed_urls = (url,)
            async with asyncio.timeout(25):
                return await self._load(data, ids, url.rstrip('/'), token)
        except Exception as exc:
            # Credentials, server addresses and provider responses never enter API errors or logs;
            # only the failure type and HTTP status are logged to make the cause diagnosable.
            status = getattr(exc, 'status', None)
            self.logger.warning('Annual watch activity could not be loaded from %s: %s%s', provider,
                                type(exc).__name__, f' (HTTP {status})' if status else '')
            return {'watchStatus': 'unavailable', 'watchNote': 'Watch activity is unavailable. Check the connection and try again. Your recorded discoveries are still available.'}
        finally:
            await self.close()

    async def _json(self, url, headers, params=None):
        session = await self._get_session()
        async with session.get(url, headers=headers, params=params, timeout=self.REQUEST_TIMEOUT,
                               allow_redirects=False) as response:
            response.raise_for_status()
            return await response.json()

    def _headers(self, plex, token):
        headers = {'X-Plex-Token' if plex else 'X-Emby-Token': token, 'Accept': 'application/json'}
        if not plex:
            # Newer Jellyfin releases expect the MediaBrowser scheme, matching JellyfinClient.
            headers['Authorization'] = f'MediaBrowser Token="{token}"'
        return headers

    async def _scan(self, plex, ids, url, headers, start, end, server=False):
        """Read played movies and episodes between ``start`` (inclusive) and ``end`` (exclusive).

        :param plex: ``True`` for Plex history, ``False`` for the Jellyfin last-played snapshot.
        :param ids: Account IDs to read; ignored when ``server`` is set.
        :param server: Read every account on the server.
        :return: Tuple ``(entries, truncated)``. Each entry has ``account``, ``kind``, ``id``,
            ``series_id``, ``date`` and ``tmdb`` (when the provider reports it inline).
        """
        if server:
            ids = [None] if plex else [str(user['Id']) for user in await self._json(f'{url}/Users', headers)]
        truncated = len(ids) > MAX_PROFILES
        entries = []
        for user_id in ids[:MAX_PROFILES]:
            seen_pages = set()
            offset = 0
            for page in range(MAX_PAGES):
                if plex:
                    params = {'sort': 'viewedAt:desc', 'X-Plex-Container-Start': offset,
                              'X-Plex-Container-Size': PAGE_SIZE}
                    if user_id is not None:
                        params['accountID'] = user_id
                    payload = await self._json(f'{url}/status/sessions/history/all', headers, params)
                    container = payload.get('MediaContainer', {})
                    items = container.get('Metadata', [])
                    total = container.get('totalSize')
                else:
                    params = {'Recursive': 'true', 'IncludeItemTypes': 'Movie,Episode', 'IsPlayed': 'true',
                              'SortBy': 'DatePlayed', 'SortOrder': 'Descending', 'EnableUserData': 'true',
                              'Fields': 'ProviderIds,SeriesProviderIds',
                              'StartIndex': offset, 'Limit': PAGE_SIZE, 'EnableImages': 'false'}
                    payload = await self._json(f'{url}/Users/{quote(user_id, safe="")}/Items', headers, params)
                    items, total = payload.get('Items', []), payload.get('TotalRecordCount')
                signature = tuple((str(item.get('historyKey', item.get('ratingKey', item.get('Id')))),
                                   str(item.get('viewedAt', item.get('UserData', {}).get('LastPlayedDate')))) for item in items)
                if signature in seen_pages:
                    truncated = True  # Some servers ignore pagination; never loop/count indefinitely.
                    break
                seen_pages.add(signature)
                dates = []
                for item in items:
                    try:
                        date = (datetime.fromtimestamp(float(item['viewedAt']), timezone.utc) if plex else
                                utc_datetime(item.get('UserData', {}).get('LastPlayedDate')))
                    except (TypeError, ValueError, KeyError, OverflowError, OSError):
                        continue
                    if date is None:
                        continue
                    dates.append(date)
                    account = str(item.get('accountID', '')) if plex else user_id
                    # Defence in depth against a provider ignoring its accountID filter.
                    if plex and user_id is not None and account != user_id:
                        continue
                    if not start <= date < end:
                        continue
                    kind = item.get('type' if plex else 'Type', '').lower()
                    item_id = item.get('ratingKey' if plex else 'Id')
                    if not item_id or kind not in ('movie', 'episode'):
                        continue
                    provider_ids = {} if plex else item.get('ProviderIds' if kind == 'movie' else 'SeriesProviderIds') or {}
                    entries.append({'account': account, 'kind': kind, 'id': str(item_id),
                                    'series_id': item.get('grandparentRatingKey' if plex else 'SeriesId'),
                                    'date': date, 'tmdb': provider_ids.get('Tmdb')})
                if not items or (dates and max(dates) < start):
                    break
                offset += len(items)
                if total is not None and offset >= int(total):
                    break
                if total is None and len(items) < PAGE_SIZE:
                    break
                if page == MAX_PAGES - 1:
                    truncated = True
        return entries, truncated

    async def _load(self, data, ids, url, token):
        plex = data['provider'] == 'plex'
        start = datetime(data['year'], 1, 1, tzinfo=timezone.utc)
        end = min(datetime(data['year'] + 1, 1, 1, tzinfo=timezone.utc), utc_datetime(data['generatedAt']))
        entries, truncated = await self._scan(plex, ids, url, self._headers(plex, token), start, end,
                                              server=data['scope'] == 'server')
        movies, episodes, series, users = set(), set(), set(), set()
        for entry in entries:
            account = entry['account']
            users.add(account)
            (movies if entry['kind'] == 'movie' else episodes).add((account, entry['id']))
            if entry['kind'] == 'episode' and entry['series_id']:
                series.add((account, str(entry['series_id'])))
        source = ('Retained Plex history; unique movies and episodes per account, excluding replays.' if plex else
                  'Jellyfin last-played snapshot, including items marked as played. Earlier plays and removed items may be missing.')
        return {'watched': {'movies': len(movies), 'episodes': len(episodes), 'series': len(series)},
                'activeUsers': len(users), 'watchStatus': 'partial',
                'watchNote': source + (' Scan limit reached; counts are partial.' if truncated else '') +
                ' Actual watch time is unavailable; media runtime is not used as watch time.'}


SYNC_INTERVAL = timedelta(minutes=10)
RESOLVE_BATCH = 50
_last_sync = {}
_sync_lock = threading.Lock()


def match_plays(pending, entries):
    """Pair unwatched ledger titles with plays by their recipient at or after the request.

    :param pending: ``(media_type, tmdb_id, user_id, requested_at)`` rows from the ledger.
    :param entries: Scan entries with a resolved ``tmdb``.
    :return: List of ``(watched_at, media_type, tmdb_id)`` using the earliest qualifying play.
    """
    plays = {}
    for entry in entries:
        if entry['tmdb']:
            media_type = 'movie' if entry['kind'] == 'movie' else 'tv'
            plays.setdefault((media_type, str(entry['tmdb'])), []).append((entry['account'], entry['date']))
    matches = []
    for media_type, tmdb_id, user_id, requested_at in pending:
        # A title with no recorded recipient counts for any account on the server.
        dates = [date for account, date in plays.get((media_type, tmdb_id), [])
                 if (user_id is None or str(account) == str(user_id)) and date >= requested_at]
        if dates:
            matches.append((min(dates), media_type, tmdb_id))
    return matches


class RecapWatchSync(YearWatchActivity):
    """Mark requested titles as watched when their recipient played them after the request.

    Only the first observed play date is stored in the ledger; no viewing history is persisted.
    """

    async def sync(self, repo, user, env, now=None):
        """Scan watch history for the caller's recap scope and update the ledger.

        :param repo: ``RecapRepository`` bound to the application database.
        :param user: Authenticated user; the scope follows the same rules as the recap itself.
        :param env: Runtime configuration with the media server credentials.
        :param now: Reference instant, for tests.
        :return: ``{'status', 'matched'}`` where status is ``ok``, ``partial``, ``skipped``,
            ``not_configured``, ``no_profiles`` or ``unavailable``.
        """
        now = now or datetime.now(timezone.utc)
        provider = watch_provider(env)
        if not provider:
            return {'status': 'not_configured', 'matched': 0}
        scope, _ids = repo._scope(user, env)
        ids = None
        if scope == 'personal':
            ids = sorted({str(p['external_user_id']) for p in repo.db.get_user_media_profiles(int(user['id']))
                          if p.get('provider') == provider})
            if not ids:
                return {'status': 'no_profiles', 'matched': 0}
        key = (scope, tuple(ids or ()))
        with _sync_lock:
            # Home visits, tabs and the annual recap share one bounded scan per scope.
            if key in _last_sync and now - _last_sync[key] < SYNC_INTERVAL:
                return {'status': 'skipped', 'matched': 0}
            _last_sync[key] = now
        pending = repo.pending_watch(ids)
        if not pending:
            return {'status': 'ok', 'matched': 0}
        prefix = provider.upper()
        url, token = env[f'{prefix}_API_URL'].rstrip('/'), env[f'{prefix}_TOKEN']
        plex = provider == 'plex'
        headers = self._headers(plex, token)
        try:
            async with asyncio.timeout(40):
                # Plays before the oldest unwatched request can never match, so the scan stops there.
                entries, truncated = await self._scan(plex, ids, url, headers, min(row[3] for row in pending), now,
                                                      server=ids is None)
                await self._resolve(plex, url, headers, entries)
        except Exception as exc:
            with _sync_lock:
                _last_sync.pop(key, None)
            status = getattr(exc, 'status', None)
            self.logger.warning('Recap watch sync failed for %s: %s%s', provider, type(exc).__name__,
                                f' (HTTP {status})' if status else '')
            return {'status': 'unavailable', 'matched': 0}
        finally:
            await self.close()
        matched = repo.mark_watched(match_plays(pending, entries))
        return {'status': 'partial' if truncated else 'ok', 'matched': matched}

    async def _resolve(self, plex, url, headers, entries):
        """Fill each entry's missing ``tmdb`` from the movie itself or the episode's series."""
        def lookup(entry):
            return str(entry['id'] if entry['kind'] == 'movie' else entry['series_id'])

        keys = sorted({lookup(entry) for entry in entries
                       if not entry['tmdb'] and (entry['kind'] == 'movie' or entry['series_id'])})
        resolved = {}
        for i in range(0, len(keys), RESOLVE_BATCH):
            batch = keys[i:i + RESOLVE_BATCH]
            try:
                if plex:
                    payload = await self._json(f'{url}/library/metadata/{",".join(quote(key, safe="") for key in batch)}',
                                               headers, {'includeGuids': 1})
                    for item in payload.get('MediaContainer', {}).get('Metadata', []):
                        tmdb = next((value for value in (normalize_guid_provider_id(guid.get('id', ''), 'tmdb')
                                                         for guid in item.get('Guid', [])) if value), None)
                        if tmdb:
                            resolved[str(item.get('ratingKey'))] = tmdb
                else:
                    payload = await self._json(f'{url}/Items', headers, {'Ids': ','.join(batch), 'Fields': 'ProviderIds'})
                    for item in payload.get('Items', []):
                        tmdb = (item.get('ProviderIds') or {}).get('Tmdb')
                        if tmdb:
                            resolved[str(item.get('Id'))] = tmdb
            except Exception as exc:
                # Removed library items cannot be resolved; keep what the other batches found.
                self.logger.debug('Recap watch sync could not resolve a metadata batch: %s', type(exc).__name__)
        for entry in entries:
            if not entry['tmdb']:
                entry['tmdb'] = resolved.get(lookup(entry))
