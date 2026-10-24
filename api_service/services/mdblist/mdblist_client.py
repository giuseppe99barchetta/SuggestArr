"""Read public MDBList lists through the official API."""
from api_service.services.http.base_client import BaseHTTPClient
from api_service.services.public_lists import PublicListError, parse_list_url, read_list_json


class MDBListClient(BaseHTTPClient):
    BASE_URL = 'https://api.mdblist.com'

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    async def test_connection(self):
        data, _ = await read_list_json(self, '/user', params={'apikey': self.api_key})
        if not isinstance(data, dict) or not data or data.get('error'):
            raise PublicListError('MDBList API key could not be validated.')

    @staticmethod
    def _list_ref(url):
        """Split an MDBList URL into API owner, slug and optional media filter.

        :param url: Public MDBList list URL.
        :return: Tuple (user, slug, mediatype) where mediatype is 'movie', 'show' or None.
        """
        owner, slug = parse_list_url('mdblist', url)
        user, _, media = owner.partition('/')
        return user, slug, {'movies': 'movie', 'shows': 'show'}.get(media)

    async def public_list_info(self, url):
        user, slug, _ = self._list_ref(url)
        data, _ = await read_list_json(self, f'/lists/{user}/{slug}', params={'apikey': self.api_key})
        lists = data if isinstance(data, list) else [data]
        if not lists or any(not isinstance(item, dict) or not (
                item.get('privacy') == 'public' or
                ('private' in item and item['private'] in (False, 0))) for item in lists):
            raise PublicListError('Only explicitly public MDBList lists are supported.')
        return {'name': lists[0].get('name') or slug, 'provider': 'mdblist'}

    async def public_list_page(self, url, offset, limit=100):
        user, slug, media = self._list_ref(url)
        params = {'apikey': self.api_key, 'limit': limit, 'offset': offset, 'unified': 'true'}
        if media:
            params['mediatype'] = media
        data, headers = await read_list_json(self, f'/lists/{user}/{slug}/items', params=params)
        if isinstance(data, dict) and isinstance(data.get('movies'), list) and isinstance(data.get('shows'), list):
            data = ([{**item, 'mediatype': 'movie'} for item in data['movies']]
                    + [{**item, 'mediatype': 'show'} for item in data['shows']])
            data.sort(key=lambda item: item.get('rank', 0))
        if not isinstance(data, list) or len(data) > limit:
            raise PublicListError('MDBList returned an invalid list page.')
        more = str(headers.get('X-Has-More', '')).lower()
        return data, more == 'true' if more else len(data) == limit
