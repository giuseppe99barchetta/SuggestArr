"""Resolve profile images using explicit account links, keeping credentials server-side."""

import asyncio
import json
from urllib.parse import quote, urljoin, urlsplit
from xml.etree import ElementTree

import aiohttp

from api_service.services.http.base_client import BaseHTTPClient
from api_service.utils.ssrf_guard import validate_url

MAX_IMAGE_BYTES = 2 * 1024 * 1024
IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/avif'}


class UserAvatarService(BaseHTTPClient):
    """Try Seer, then the linked account on the active media server."""

    REQUEST_TIMEOUT = 4

    async def _read(self, url, headers=None):
        session = await self._get_session()
        async with session.get(url, headers=headers, allow_redirects=False) as response:
            if response.status != 200:
                return None
            if response.content_length and response.content_length > MAX_IMAGE_BYTES:
                return None
            data = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                data.extend(chunk)
                if len(data) > MAX_IMAGE_BYTES:
                    return None
            return bytes(data), response.content_type

    async def _json(self, url, headers):
        result = await self._read(url, headers)
        return json.loads(result[0]) if result else None

    async def _image(self, url, headers=None):
        result = await self._read(url, headers)
        return result if result and result[0] and result[1] in IMAGE_TYPES else None

    async def _remote_image(self, value, base_url, headers):
        if not isinstance(value, str) or not value.strip():
            return None
        url = urljoin(base_url.rstrip('/') + '/', value)
        parsed, base = urlsplit(url), urlsplit(base_url)
        if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
            return None
        def origin(parts):
            return parts.scheme, parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80)

        same_origin = origin(parsed) == origin(base)
        # Only the configured server may be private. Never forward its API key
        # to a provider's CDN or follow an unchecked redirect.
        if not same_origin:
            validate_url(url)
        return await self._image(url, headers if same_origin else None)

    async def _seer(self, config, seer_user_id):
        base = (config.get('SEER_API_URL') or '').rstrip('/')
        token = config.get('SEER_TOKEN')
        if not base or not token or not seer_user_id:
            return None
        headers = {'X-Api-Key': token}
        user = await self._json(f'{base}/api/v1/user/{int(seer_user_id)}', headers)
        return await self._remote_image(user.get('avatar') if isinstance(user, dict) else None, base, headers)

    async def _jellyfin(self, config, external_id):
        base = (config.get('JELLYFIN_API_URL') or '').rstrip('/')
        token = config.get('JELLYFIN_TOKEN')
        if not base or not token:
            return None
        user_id = quote(str(external_id), safe='')
        return await self._image(
            f'{base}/Users/{user_id}/Images/Primary?maxWidth=128&maxHeight=128',
            {'X-Emby-Token': token},
        )

    async def _plex(self, config, external_id):
        token = config.get('PLEX_TOKEN')
        if not token:
            return None
        base = 'https://plex.tv'
        headers = {'X-Plex-Token': token, 'Accept': 'application/json',
                   'X-Plex-Client-Identifier': 'SuggestArr'}
        user = await self._json(f'{base}/api/v2/user', headers)
        if isinstance(user, dict) and str(user.get('id')) == str(external_id):
            return await self._remote_image(user.get('thumb'), base, headers)
        # Plex's XML directory includes shared and managed users. Match the
        # linked Plex account ID, never a display name or local server ID.
        result = await self._read(f'{base}/api/users/', {**headers, 'Accept': 'application/xml'})
        if result and b'<!DOCTYPE' not in result[0].upper():
            for entry in ElementTree.fromstring(result[0]).iter('User'):
                if entry.get('id') == str(external_id):
                    return await self._remote_image(entry.get('thumb'), base, headers)
        return None

    async def resolve(self, config, user, links):
        """Return (bytes, MIME type, provider), or None when no image is available."""
        candidates = []
        if user.get('seer_user_id'):
            candidates.append(('seer', lambda: self._seer(config, user['seer_user_id'])))
        provider = (config.get('SELECTED_SERVICE') or '').lower()
        for link in links:
            if link.get('provider') != provider or not link.get('verified') or not link.get('external_user_id'):
                continue
            external_id = link['external_user_id']
            if provider in ('jellyfin', 'emby'):
                candidates.append((provider, lambda: self._jellyfin(config, external_id)))
            elif provider == 'plex':
                candidates.append((provider, lambda: self._plex(config, external_id)))
            break
        for source, fetch in candidates:
            try:
                result = await fetch()
                if result:
                    return *result, source
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError, ElementTree.ParseError):
                # A missing image, offline provider or invalid response is normal.
                # Do not log upstream URLs/errors, which can contain credentials.
                self.logger.debug('Profile image unavailable from %s', source)
        return None
