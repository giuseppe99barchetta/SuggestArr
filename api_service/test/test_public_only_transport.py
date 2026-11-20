"""The connection itself refuses private destinations and uses the address it validated."""
import asyncio
from unittest.mock import patch

import httpx
import pytest

from api_service.services.http.public_only_transport import PublicOnlyTransport


class Recorder(httpx.AsyncBaseTransport):
    def __init__(self):
        self.requests = []

    async def handle_async_request(self, request):
        self.requests.append(request)
        return httpx.Response(200, json={'ok': True})


def resolving(*addresses):
    async def getaddrinfo(self, host, port, **kwargs):
        return [(2, 1, 6, '', (address, port)) for address in addresses]
    return patch('asyncio.base_events.BaseEventLoop.getaddrinfo', getaddrinfo)


def send(url, *addresses):
    recorder = Recorder()

    async def run():
        async with httpx.AsyncClient(transport=PublicOnlyTransport(recorder), follow_redirects=False) as client:
            return await client.get(url)

    with resolving(*addresses):
        return recorder, asyncio.run(run())


def test_a_public_destination_is_reached_at_the_validated_address_with_the_real_name():
    recorder, response = send('https://api.example.com/v1/models', '93.184.216.34')
    sent = recorder.requests[0]
    assert response.status_code == 200
    assert sent.url.host == '93.184.216.34' and sent.headers['host'] == 'api.example.com'
    assert sent.extensions['sni_hostname'] == 'api.example.com'


@pytest.mark.parametrize('addresses', [('127.0.0.1',), ('10.0.0.5',), ('169.254.169.254',), ('::1',),
                                       ('93.184.216.34', '192.168.1.10')])  # one private record is enough to refuse
def test_a_private_or_mixed_answer_is_refused_before_connecting(addresses):
    recorder = Recorder()
    with pytest.raises(httpx.ConnectError):
        asyncio.run(_refused(recorder, addresses))
    assert recorder.requests == []


async def _refused(recorder, addresses):
    with resolving(*addresses):
        async with httpx.AsyncClient(transport=PublicOnlyTransport(recorder)) as client:
            await client.get('http://rebind.example.com/v1')
