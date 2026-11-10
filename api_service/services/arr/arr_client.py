"""Read and add the titles Radarr and Sonarr manage (monitored or not)."""
from api_service.services.http.base_client import BaseHTTPClient
from api_service.utils.ssrf_guard import normalize_base_url

# service -> (list endpoint, SuggestArr media type)
SERVICES = {'radarr': ('movie', 'movie'), 'sonarr': ('series', 'tv')}
# Radarr and Sonarr answer 400 with these validator codes when the title is already added.
_EXISTS_CODES = ('MovieExistsValidator', 'SeriesExistsValidator')


class ArrClient(BaseHTTPClient):
    """Minimal Radarr/Sonarr v3 API client: library listing, options and adding titles."""

    REQUEST_TIMEOUT = 30  # a full library listing can be large

    def __init__(self, service, api_url, api_key):
        """
        :param service: 'radarr' or 'sonarr'.
        :param api_url: Base URL of the instance.
        :param api_key: The instance's API key.
        """
        super().__init__()
        if service not in SERVICES:
            raise ValueError(f'Unsupported service: {service}')
        self.service = service
        self.api_url = normalize_base_url(api_url)
        self.api_key = api_key
        self.guard_outbound = True
        self.private_urls = self.allowed_urls = (self.api_url,)

    async def _request(self, method, path, **kwargs):
        """Call the API and return ``(status, decoded JSON or None)``; never raises on HTTP status."""
        session = await self._get_session()
        async with session.request(method, f'{self.api_url}/api/v3/{path}',
                                   headers={'X-Api-Key': self.api_key}, **kwargs) as response:
            try:
                data = await response.json(content_type=None)
            except ValueError:
                data = None
            return response.status, data

    async def _get(self, path, **kwargs):
        status, data = await self._request('GET', path, **kwargs)
        if status != 200:
            raise RuntimeError(f'{self.service.capitalize()} answered HTTP {status} for {path}')
        return data

    async def test_connection(self):
        """Raise if the instance is unreachable or rejects the API key."""
        await self._get('system/status')

    async def get_tmdb_ids(self):
        """Return the TMDB IDs of every title in the instance, whether monitored or not.

        shortcut: Sonarr entries without ``tmdbId`` (Sonarr v3) are skipped; map
        from ``tvdbId`` if v3 support is ever needed.

        :return: Set of TMDB ID strings.
        """
        endpoint, _ = SERVICES[self.service]
        items = await self._get(endpoint)
        ids = {str(item['tmdbId']) for item in items if isinstance(item, dict) and item.get('tmdbId')}
        if items and not ids:
            self.logger.warning('%s returned titles without tmdbId: update to a version that exposes it '
                                '(Sonarr v4) or its titles cannot be excluded.', self.service.capitalize())
        return ids

    async def get_options(self):
        """Return the quality profiles, root folders and tags the instance offers (no secrets)."""
        profiles = await self._get('qualityprofile')
        folders = await self._get('rootfolder')
        tags = await self._get('tag')
        return {
            'profiles': [{'id': p['id'], 'name': p.get('name')} for p in profiles if isinstance(p, dict) and 'id' in p],
            'rootFolders': [{'path': f['path']} for f in folders if isinstance(f, dict) and f.get('path')],
            'tags': [{'id': t['id'], 'label': t.get('label')} for t in tags if isinstance(t, dict) and 'id' in t],
        }

    async def add(self, payload):
        """Add the title described by a queued request payload.

        :param payload: Queue payload: ``mediaType``, ``mediaId`` (TMDB ID), ``profileId``,
            ``rootFolder``, optional ``tags``, ``seasons`` (TV) and ``_is_anime``.
        :return: True when the title was added or was already in the instance.
        :raises RuntimeError: When the instance rejects the request.
        """
        endpoint, _ = SERVICES[self.service]
        tmdb_id = int(payload['mediaId'])
        found = await self._get(f'{endpoint}/lookup', params={'term': f'tmdb:{tmdb_id}'})
        item = next((i for i in found if isinstance(i, dict) and i.get('tmdbId') == tmdb_id), None) \
            if isinstance(found, list) else None
        if item is None:
            raise RuntimeError(f'{self.service.capitalize()} could not find tmdb:{tmdb_id}')

        item.update(qualityProfileId=payload['profileId'], rootFolderPath=payload['rootFolder'],
                    tags=list(payload.get('tags') or []), monitored=True)
        if self.service == 'radarr':
            item.update(minimumAvailability='released', addOptions={'searchForMovie': True})
        else:
            wanted = payload.get('seasons', 'all')
            for season in item.get('seasons') or []:
                number = season.get('seasonNumber')
                season['monitored'] = number != 0 and (wanted == 'all' or number in wanted)
            item.update(seasonFolder=True, seriesType='anime' if payload.get('_is_anime') else 'standard',
                        addOptions={'searchForMissingEpisodes': True})

        status, data = await self._request('POST', endpoint, json=item)
        if status in (200, 201):
            return True
        if status == 409:
            return True  # already added (conflict): delivery is idempotent
        if status == 400 and isinstance(data, list) and any(
                isinstance(e, dict) and e.get('errorCode') in _EXISTS_CODES for e in data):
            return True  # already added: delivery is idempotent
        raise RuntimeError(f'{self.service.capitalize()} rejected tmdb:{tmdb_id} (HTTP {status})')
