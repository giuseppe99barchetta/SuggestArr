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
        self._library = None  # tmdb id -> title, read once per client by find_owned
        self._tags_loaded = False
        self._options = None  # (quality profile ids, root folder paths), read once per client by add

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

    async def _get_list(self, path, **kwargs):
        """GET an endpoint that answers a JSON list.

        Anything else (an empty body, a proxy's HTML page) raises instead of passing for an
        empty library, which would make every title look gone.
        """
        data = await self._get(path, **kwargs)
        if not isinstance(data, list):
            raise RuntimeError(f'{self.service.capitalize()} answered {path} without a list')
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
        items = await self._get_list(endpoint)
        ids = {str(item['tmdbId']) for item in items if isinstance(item, dict) and item.get('tmdbId')}
        if items and not ids:
            self.logger.warning('%s returned titles without tmdbId: update to a version that exposes it '
                                '(Sonarr v4) or its titles cannot be excluded.', self.service.capitalize())
        return ids

    async def queue_busy(self):
        """Whether the download queue holds anything (stalled or failed items included).

        :raises RuntimeError: When the queue cannot be read.
        """
        queue = await self._get('queue', params={'page': 1, 'pageSize': 1})
        return isinstance(queue, dict) and (queue.get('totalRecords') or 0) > 0

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
        for item in await self._get_list(endpoint):
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
        profiles = await self._get_list('qualityprofile')
        folders = await self._get_list('rootfolder')
        tags = await self._get_list('tag')
        return {
            'profiles': [{'id': p['id'], 'name': p.get('name')} for p in profiles if isinstance(p, dict) and 'id' in p],
            'rootFolders': [{'path': f['path']} for f in folders if isinstance(f, dict) and f.get('path')],
            'tags': [{'id': t['id'], 'label': t.get('label')} for t in tags if isinstance(t, dict) and 'id' in t],
        }

    async def _load_tags(self):
        """Cache the id of every tag the instance has, by lowercase label.

        Marked as loaded only after a successful read, so a failed read is retried by the next
        caller instead of leaving an empty cache that makes every title look untagged.
        """
        tags = await self._get_list('tag')
        for tag in tags:
            if isinstance(tag, dict) and 'id' in tag and isinstance(tag.get('label'), str):
                self._tag_ids.setdefault(tag['label'].lower(), tag['id'])
        self._tags_loaded = True

    async def _tag_ids_for(self, labels):
        """Return the ids of the tags with these labels, creating the missing ones.

        :raises RuntimeError: When the tags cannot be read or created.
        """
        if any(label not in self._tag_ids for label in labels):
            await self._load_tags()
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
        # The profile may come from a job or an approval saved while another backend was active:
        # only send what this instance really offers (a root folder is a path on its host).
        if self._options is None:
            self._options = ({item.get('id') for item in await self._get_list('qualityprofile') if isinstance(item, dict)},
                             {item.get('path') for item in await self._get_list('rootfolder') if isinstance(item, dict)})
        profiles, folders = self._options
        # _tag_ids holds every tag of the instance (read in full on the first lookup) plus the ones created.
        if payload.get('profileId') not in profiles or payload.get('rootFolder') not in folders \
                or not set(payload.get('tags') or []) <= set(self._tag_ids.values()):
            raise RuntimeError(f'{self.service.capitalize()} does not offer the quality profile, root folder '
                               f'or tags chosen for tmdb:{tmdb_id}; choose them again')
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

    async def find_owned(self, tmdb_id):
        """Find a title and tell whether SuggestArr added it (it carries the ``suggestarr`` tag).

        The library and the tags are read once per client. The tag is never created here.

        :return: ``(status, item)``: ``'ok'``, ``'not_tagged'`` or ``'not_found'`` (item None).
        """
        endpoint, _ = SERVICES[self.service]
        if self._library is None:
            self._library = {str(item['tmdbId']): item for item in await self._get_list(endpoint)
                             if isinstance(item, dict) and item.get('tmdbId') and 'id' in item}
        item = self._library.get(str(tmdb_id))
        if item is None:
            return 'not_found', None
        if not self._tags_loaded:
            await self._load_tags()
        tag_id = self._tag_ids.get(SUGGESTARR_TAG)
        if tag_id is None or tag_id not in (item.get('tags') or []):
            return 'not_tagged', item
        return 'ok', item

    async def delete(self, tmdb_id):
        """Delete a title and its files, only if SuggestArr added it.

        A title without the ``suggestarr`` tag was added by someone else and is never deleted.

        :return: ``'deleted'``, ``'not_tagged'`` or ``'not_found'``.
        :raises RuntimeError: When the instance refuses the deletion.
        """
        status, item = await self.find_owned(tmdb_id)
        if status != 'ok':
            return status
        endpoint, _ = SERVICES[self.service]
        code, _ = await self._request('DELETE', f"{endpoint}/{int(item['id'])}", params={'deleteFiles': 'true'})
        if code not in (200, 202, 204):
            raise RuntimeError(f'{self.service.capitalize()} refused to delete tmdb:{tmdb_id} (HTTP {code})')
        self._library.pop(str(tmdb_id), None)
        return 'deleted'
