"""httpx transport that only talks to public addresses, and only to the address it just checked.

Used for AI providers whose address a person chose: a preflight check alone leaves a gap between the
check and the connection (DNS can answer differently the second time), so the check happens here, on
the very addresses the connection then uses.
"""
import asyncio
import socket

import httpx

from api_service.utils.ssrf_guard import validate_address


class PublicOnlyTransport(httpx.AsyncBaseTransport):
    """Resolve the host, refuse unless every address is public, then connect to the first one."""

    def __init__(self, inner: httpx.AsyncBaseTransport = None):
        self._inner = inner or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
            addresses = [info[4][0] for info in infos]
            if not addresses:
                raise ValueError("Destination did not resolve")
            for address in addresses:
                validate_address(address)
        except (OSError, ValueError, UnicodeError):
            raise httpx.ConnectError("Destination address is not allowed", request=request) from None
        extensions = dict(request.extensions)
        if request.url.scheme == "https":
            extensions["sni_hostname"] = host  # the certificate is still checked against the real name
        pinned = httpx.Request(
            request.method, request.url.copy_with(host=addresses[0]),
            headers=request.headers, stream=request.stream, extensions=extensions,
        )
        return await self._inner.handle_async_request(pinned)

    async def aclose(self) -> None:
        await self._inner.aclose()
