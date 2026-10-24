"""Public-list URL validation and bounded HTTP reads shared by list providers."""
import asyncio
import re
from urllib.parse import urlsplit

import aiohttp


class PublicListError(ValueError):
    """A safe, user-facing error without provider bodies or credentials."""


def parse_list_url(provider, url):
    if provider not in ('trakt', 'mdblist') or not isinstance(url, str):
        raise PublicListError('Select MDBList or Trakt and enter a public list URL.')
    host = 'trakt.tv' if provider == 'trakt' else 'mdblist.com'
    try:
        parsed = urlsplit(url.strip())
        if provider == 'trakt':
            pattern = r'/users/([A-Za-z0-9_-]+)/lists/([A-Za-z0-9_-]+)/?'
        else:
            # Official lists live at /lists/official/<movies|shows>/<slug>; the owner is returned as 'official/<media>'.
            pattern = r'/lists/(official/(?:movies|shows)|[A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)/?'
        match = re.fullmatch(pattern, parsed.path)
        valid = (parsed.scheme == 'https' and parsed.hostname in (host, f'www.{host}')
                 and parsed.port in (None, 443) and not parsed.username and not parsed.password
                 and not parsed.query and not parsed.fragment and match)
    except ValueError:
        valid = False
    if not valid:
        raise PublicListError(f'Enter an HTTPS public list URL from {host}, without query parameters or credentials.')
    user, slug = match.groups()
    return user, slug


async def read_list_json(client, path, *, params=None, headers=None):
    """Never follow redirects or include a provider body/URL in exceptions."""
    for attempt in range(2):
        try:
            session = await client._get_session()
            async with session.get(client.BASE_URL + path, params=params, headers=headers,
                                   allow_redirects=False, timeout=client.REQUEST_TIMEOUT) as response:
                if response.status == 429 and attempt == 0:
                    try:
                        delay = max(0, int(response.headers.get('Retry-After', '1')))
                    except ValueError:
                        delay = 1
                    if delay <= 5:
                        await asyncio.sleep(delay)
                        continue
                if response.status in (401, 403, 404):
                    raise PublicListError('List unavailable: check the URL, public visibility and configured app credentials.')
                if response.status == 429:
                    raise PublicListError('List provider rate limit reached. Try again later.')
                if response.status != 200:
                    raise PublicListError('List provider returned an unexpected response.')
                return await response.json(), response.headers
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            if isinstance(exc, PublicListError):
                raise
            raise PublicListError('Could not read the list: provider timeout or invalid response.') from None


def normalize_list_item(raw):
    if not isinstance(raw, dict):
        return None
    kind = raw.get('type') or raw.get('mediatype') or raw.get('media_type')
    if kind not in ('movie', 'show', 'tv'):
        return None
    item = raw.get(kind, raw)
    if not isinstance(item, dict):
        return None
    ids = item.get('ids') or {}
    tmdb_id = ids.get('tmdb') if isinstance(ids, dict) else None
    tmdb_id = tmdb_id or item.get('tmdb_id')
    if isinstance(tmdb_id, bool) or not re.fullmatch(r'[1-9][0-9]*', str(tmdb_id)):
        return None
    return {'tmdb_id': str(tmdb_id), 'media_type': 'tv' if kind in ('show', 'tv') else 'movie',
            'title': item.get('title') or item.get('name') or ''}


def build_list_client(filters, config):
    if not isinstance(filters, dict):
        raise PublicListError('List source must be an object.')
    provider = filters.get('list_provider')
    parse_list_url(provider, filters.get('list_url'))
    if provider == 'trakt':
        from api_service.services.trakt.trakt_client import TraktClient
        key = config.get('TRAKT_CLIENT_ID')
        if not key:
            raise PublicListError('Configure the Trakt Client ID in Connections first.')
        return TraktClient(key)
    from api_service.services.mdblist.mdblist_client import MDBListClient
    key = config.get('MDBLIST_API_KEY')
    if not key:
        raise PublicListError('Configure the MDBList API key in Connections first.')
    return MDBListClient(key)
