"""Enforce URL/address policy on the addresses actually handed to aiohttp."""
from contextlib import asynccontextmanager

import aiohttp

from api_service.utils.ssrf_guard import parse_http_url, url_origin, validate_address


class OutboundHTTPError(aiohttp.ClientError):
    """A destination or redirect violated the outbound HTTP policy."""


class GuardedConnector(aiohttp.TCPConnector):
    def __init__(self, *, private_origins=(), allow_private=False, **kwargs):
        self._private_hosts = {(origin[1], origin[2]) for origin in private_origins}
        self._allow_private = allow_private
        super().__init__(**kwargs)

    async def _resolve_host(self, host, port, traces=None):
        results = await super()._resolve_host(host, port, traces)
        if not results:
            raise OutboundHTTPError('Destination did not resolve')
        try:
            for result in results:
                validate_address(result['host'], self._allow_private or (host.lower(), port) in self._private_hosts)
        except ValueError:
            raise OutboundHTTPError('Destination address is not allowed') from None
        return results


class GuardedSession:
    """Small session facade: no redirect, proxy, cookie or DNS-policy bypass."""
    def __init__(self, *, private_urls=(), allowed_urls=(), allow_private=False, **kwargs):
        self._allowed = {url_origin(url) for url in allowed_urls}
        private = {url_origin(url) for url in private_urls}
        self._session = aiohttp.ClientSession(
            connector=GuardedConnector(private_origins=private, allow_private=allow_private),
            cookie_jar=aiohttp.DummyCookieJar(), trust_env=False, **kwargs,
        )

    @property
    def closed(self):
        return self._session.closed

    async def close(self):
        await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    @asynccontextmanager
    async def request(self, method, url, **kwargs):
        try:
            parse_http_url(url)
            if self._allowed and url_origin(url) not in self._allowed:
                raise ValueError
            if kwargs.get('proxy'):
                raise ValueError
        except ValueError:
            raise OutboundHTTPError('Destination URL is not allowed') from None
        kwargs['allow_redirects'] = False
        try:
            async with self._session.request(method, url, **kwargs) as response:
                if 300 <= response.status < 400:
                    raise OutboundHTTPError('Outbound redirects are not allowed')
                yield response
        except OutboundHTTPError:
            raise
        except aiohttp.ClientError:
            raise OutboundHTTPError('Outbound HTTP request failed') from None

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def post(self, url, **kwargs):
        return self.request('POST', url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request('DELETE', url, **kwargs)


async def send_bytes(method, url, *, allow_private=False, **kwargs):
    """Return buffered data only, so sync bridges never retain live responses."""
    async with GuardedSession(allowed_urls=(url,), allow_private=allow_private,
                              timeout=aiohttp.ClientTimeout(total=10)) as session:
        async with session.request(method, url, **kwargs) as response:
            return response.status, await response.read()
