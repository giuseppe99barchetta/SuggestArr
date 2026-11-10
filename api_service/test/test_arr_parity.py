"""Seer-only features carried over to direct Radarr/Sonarr delivery (REQUEST_BACKEND=arr).

Every ArrClient call here goes through a fake ``_request``: no test ever reaches a real
Radarr/Sonarr (the operator's config holds real credentials).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api_service.services.arr.arr_client import ArrClient, arr_tag_label
from api_service.services.arr.arr_request_client import ArrRequestClient

RADARR = {'RADARR_API_URL': 'http://radarr:7878', 'RADARR_TOKEN': 'k'}
SONARR = {'SONARR_API_URL': 'http://sonarr:8989', 'SONARR_TOKEN': 'k'}
PROFILES = {'default_movie': {'profileId': 4, 'rootFolder': '/movies', 'tags': [1]},
            'default_tv': {'profileId': 6, 'rootFolder': '/tv'}}
ARR_ENV = {**RADARR, **SONARR, 'ARR_PROFILE_CONFIG': PROFILES, 'REQUEST_BACKEND': 'arr'}


@pytest.fixture(autouse=True)
def no_real_arr(monkeypatch):
    """Fail loudly if a test forgot to fake the Radarr/Sonarr API."""
    async def refuse(self, method, path, **kwargs):
        raise AssertionError(f'unexpected real {method} {path} to {self.api_url}')
    monkeypatch.setattr(ArrClient, '_request', refuse)


class FakeArr:
    """Answers ArrClient._request from a ``{(method, path): (status, data)}`` table and records calls."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    async def __call__(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        answer = self.routes[(method, path)]
        return answer(kwargs) if callable(answer) else answer

    def paths(self, method):
        return [path for m, path, _ in self.calls if m == method]


def _client(service, routes):
    client = ArrClient(service, 'http://arr.test/', 'k')
    client._request = FakeArr(routes)
    return client


LOOKUP = [{'title': 'Inception', 'tmdbId': 27205}]
PAYLOAD = {'mediaType': 'movie', 'mediaId': 27205, 'profileId': 4, 'rootFolder': '/movies', 'tags': [1, 9]}


def _posted_tags(client):
    return next(kwargs['json']['tags'] for m, path, kwargs in client._request.calls if (m, path) == ('POST', 'movie'))


# --- 1. suggestarr tag ---------------------------------------------------------

def test_an_existing_suggestarr_tag_is_reused_and_merged_without_duplicates():
    client = _client('radarr', {('GET', 'tag'): (200, [{'id': 9, 'label': 'SuggestArr'}]),
                                ('GET', 'movie/lookup'): (200, LOOKUP), ('POST', 'movie'): (201, {})})
    assert asyncio.run(client.add(PAYLOAD)) is True
    assert client._request.paths('POST') == ['movie']  # no tag created
    assert _posted_tags(client) == [1, 9]


def test_a_missing_tag_is_created_once_per_client():
    client = _client('radarr', {('GET', 'tag'): (200, []), ('POST', 'tag'): lambda kw: (201, {'id': 12, **kw['json']}),
                                ('GET', 'movie/lookup'): (200, LOOKUP), ('POST', 'movie'): (201, {})})
    asyncio.run(client.add(PAYLOAD, ['suggestarr-user-mario']))
    asyncio.run(client.add(PAYLOAD, ['suggestarr-user-mario']))
    labels = [kw['json']['label'] for m, path, kw in client._request.calls if (m, path) == ('POST', 'tag')]
    assert labels == ['suggestarr', 'suggestarr-user-mario']  # created once, then cached
    assert client._request.paths('GET').count('tag') == 1
    assert _posted_tags(client) == [1, 9, 12]


def test_a_tag_that_cannot_be_created_fails_the_delivery():
    client = _client('radarr', {('GET', 'tag'): (200, []), ('POST', 'tag'): (500, None)})
    with pytest.raises(RuntimeError, match='tag'):
        asyncio.run(client.add(PAYLOAD))
    assert 'movie' not in client._request.paths('POST')


@pytest.mark.parametrize('text,label', [('Mario Rossi!', 'mario-rossi'), ('ÉLodie_99', 'lodie-99'),
                                        ('__', ''), (None, ''), ('a--b', 'a-b')])
def test_tag_labels_only_keep_lowercase_letters_digits_and_dashes(text, label):
    assert arr_tag_label(text) == label


@pytest.mark.parametrize('enabled,name,expected', [
    (True, 'Mario Rossi', ['suggestarr-user-mario-rossi']),
    (True, None, []),       # name unknown: only the suggestarr tag
    (True, '!!', []),       # nothing usable after normalization
    (False, 'Mario Rossi', []),
])
def test_the_per_user_tag_follows_the_setting_and_the_known_name(enabled, name, expected):
    client = ArrRequestClient({**ARR_ENV, 'ARR_TAG_BY_USER': enabled})
    fake = MagicMock()
    fake.add = AsyncMock(return_value=True)
    with patch('api_service.services.arr.arr_request_client.DatabaseManager') as db, \
            patch('api_service.services.arr.arr_request_client.ArrClient', return_value=fake):
        db.return_value.get_media_user_name.return_value = name
        assert asyncio.run(client.submit_queued_request({'mediaType': 'movie', 'mediaId': 1, '_user_id': 'u1'})) is True
    assert fake.add.await_args.args[1] == expected


def test_the_request_client_reuses_one_arr_client_per_instance_and_closes_it():
    client = ArrRequestClient(ARR_ENV)
    fake = MagicMock()
    fake.add = AsyncMock(return_value=True)
    fake.close = AsyncMock()
    with patch('api_service.services.arr.arr_request_client.ArrClient', return_value=fake) as factory:
        async def deliver_twice():
            async with client:
                await client.submit_queued_request({'mediaType': 'movie', 'mediaId': 1})
                await client.submit_queued_request({'mediaType': 'movie', 'mediaId': 2})
        asyncio.run(deliver_twice())
    factory.assert_called_once_with('radarr', 'http://radarr:7878', 'k')
    fake.close.assert_awaited_once()
