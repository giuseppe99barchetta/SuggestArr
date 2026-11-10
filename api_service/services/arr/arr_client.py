"""Read and add the titles Radarr and Sonarr manage (monitored or not)."""
import re

from api_service.services.http.base_client import BaseHTTPClient
from api_service.utils.ssrf_guard import normalize_base_url

# service -> (list endpoint, SuggestArr media type)
SERVICES = {'radarr': ('movie', 'movie'), 'sonarr': ('series', 'tv')}
# Radarr and Sonarr answer 400 with these validator codes when the title is already added.
_EXISTS_CODES = ('MovieExistsValidator', 'SeriesExistsValidator')
# Tag put on every title SuggestArr adds; cleanup only ever deletes titles carrying it.
SUGGESTARR_TAG = 'suggestarr'


def arr_tag_label(text):
    """Turn free text into a Radarr/Sonarr tag label (only ``a-z``, ``0-9`` and ``-`` are accepted).

    :return: The label, or '' when nothing usable is left.
    """
    return re.sub(r'[^a-z0-9]+', '-', str(text or '').lower()).strip('-')


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
        self._tag_ids = {}  # label -> id, cached for this client's lifetime

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

    async def get_media_statuses(self):
        """Where each title of the instance stands, in the shape of ``SeerClient.get_media_statuses``.

        Radarr: a downloaded file means available, otherwise the title is being fetched.
        Sonarr: files for every monitored aired episode mean available, some files partial.
        There is no play link, so ``url`` is always None.

        :return: Dict ``{(media_type, tmdb_id): {'status', 'url'}}``.
        :raises RuntimeError: When the library cannot be read (a partial read must not
            make titles look as if they had left the instance).
        """
        endpoint, media_type = SERVICES[self.service]
        statuses = {}
        for item in await self._get(endpoint) or []:
            if not isinstance(item, dict) or not item.get('tmdbId'):
                continue
            if self.service == 'radarr':
                status = 'available' if item.get('hasFile') else 'processing'
            else:
                stats = item.get('statistics') or {}
                files, wanted = stats.get('episodeFileCount') or 0, stats.get('episodeCount') or 0
                status = 'available' if files and files >= wanted else 'partial' if files else 'processing'
            statuses[(media_type, str(item['tmdbId']))] = {'status': status, 'url': None}
        return statuses

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

    async def _tag_ids_for(self, labels):
        """Return the ids of the tags with these labels, creating the missing ones.

        :raises RuntimeError: When the tags cannot be read or created.
        """
        missing = [label for label in labels if label not in self._tag_ids]
        if missing:
            for tag in await self._get('tag') or []:
                if isinstance(tag, dict) and 'id' in tag and isinstance(tag.get('label'), str):
                    self._tag_ids.setdefault(tag['label'].lower(), tag['id'])
        for label in labels:
            if label not in self._tag_ids:
                status, data = await self._request('POST', 'tag', json={'label': label})
                if status not in (200, 201) or not isinstance(data, dict) or 'id' not in data:
                    raise RuntimeError(f'{self.service.capitalize()} could not create the tag {label} (HTTP {status})')
                self._tag_ids[label] = data['id']
        return [self._tag_ids[label] for label in labels]

    async def add(self, payload, extra_labels=()):
        """Add the title described by a queued request payload, tagged ``suggestarr``.

        :param payload: Queue payload: ``mediaType``, ``mediaId`` (TMDB ID), ``profileId``,
            ``rootFolder``, optional ``tags``, ``seasons`` (TV) and ``_is_anime``.
        :param extra_labels: Further tag labels to put on the title (already normalized).
        :return: True when the title was added or was already in the instance.
        :raises RuntimeError: When the instance rejects the request or the tags cannot be set
            (an untagged title could never be cleaned up, so the delivery is retried instead).
        """
        endpoint, _ = SERVICES[self.service]
        tmdb_id = int(payload['mediaId'])
        tag_ids = await self._tag_ids_for([SUGGESTARR_TAG, *extra_labels])
        found = await self._get(f'{endpoint}/lookup', params={'term': f'tmdb:{tmdb_id}'})
        item = next((i for i in found if isinstance(i, dict) and i.get('tmdbId') == tmdb_id), None) \
            if isinstance(found, list) else None
        if item is None:
            raise RuntimeError(f'{self.service.capitalize()} could not find tmdb:{tmdb_id}')

        item.update(qualityProfileId=payload['profileId'], rootFolderPath=payload['rootFolder'],
                    tags=list(dict.fromkeys([*(payload.get('tags') or []), *tag_ids])), monitored=True)
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
