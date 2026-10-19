"""Read-only native watch-state adapters. Runtime is never treated as watch time."""
import asyncio
from datetime import datetime, timezone
from urllib.parse import quote

from api_service.db.recap_repository import utc_datetime
from api_service.services.http.base_client import BaseHTTPClient
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

    async def _load(self, data, ids, url, token):
        plex = data['provider'] == 'plex'
        headers = {'X-Plex-Token' if plex else 'X-Emby-Token': token, 'Accept': 'application/json'}
        if not plex:
            # Newer Jellyfin releases expect the MediaBrowser scheme, matching JellyfinClient.
            headers['Authorization'] = f'MediaBrowser Token="{token}"'
        if data['scope'] == 'server':
            ids = [None] if plex else [str(user['Id']) for user in await self._json(f'{url}/Users', headers)]
        truncated = len(ids) > MAX_PROFILES
        start = datetime(data['year'], 1, 1, tzinfo=timezone.utc)
        end = min(datetime(data['year'] + 1, 1, 1, tzinfo=timezone.utc), utc_datetime(data['generatedAt']))
        movies, episodes, series, users = set(), set(), set(), set()
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
                    users.add(account)
                    (movies if kind == 'movie' else episodes).add((account, str(item_id)))
                    series_id = item.get('grandparentRatingKey' if plex else 'SeriesId')
                    if kind == 'episode' and series_id:
                        series.add((account, str(series_id)))
                if not items or (dates and max(dates) < start):
                    break
                offset += len(items)
                if total is not None and offset >= int(total):
                    break
                if total is None and len(items) < PAGE_SIZE:
                    break
                if page == MAX_PAGES - 1:
                    truncated = True
        source = ('Retained Plex history; unique movies and episodes per account, excluding replays.' if plex else
                  'Jellyfin last-played snapshot, including items marked as played. Earlier plays and removed items may be missing.')
        return {'watched': {'movies': len(movies), 'episodes': len(episodes), 'series': len(series)},
                'activeUsers': len(users), 'watchStatus': 'partial',
                'watchNote': source + (' Scan limit reached; counts are partial.' if truncated else '') +
                ' Actual watch time is unavailable; media runtime is not used as watch time.'}
