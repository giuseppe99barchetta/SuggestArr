"""SSRF policies and transport enforcement without external DNS or HTTP."""
import asyncio
import socket
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from api_service.utils.ssrf_guard import normalize_base_url, validate_address, validate_url
from api_service.services.http.guarded_session import GuardedConnector, GuardedSession, OutboundHTTPError


@pytest.mark.parametrize('ip', [
    '100.64.0.1', '127.0.0.1', '10.0.0.1', '169.254.169.254', '0.0.0.0', '224.0.0.1',
    '::1', 'fc00::1', 'fe80::1', 'ff02::1', '::ffff:127.0.0.1',
    '2002:c0a8:0101::', '2002:7f00:0001::', '2002:a9fe:a9fe::',
    '64:ff9b::c0a8:0101', '64:ff9b::7f00:0001', '64:ff9b::a9fe:a9fe',
    '64:ff9b:1::1', '2001:0000:4136:e378:8000:63bf:3fff:fdd2',
])
def test_non_public_and_transition_addresses(ip):
    with pytest.raises(ValueError):
        validate_address(ip)
    validate_address(ip, allow_private=True)


@pytest.mark.parametrize('ip', ['8.8.8.8', '2606:4700:4700::1111', '::ffff:8.8.8.8'])
def test_public_addresses(ip):
    validate_address(ip)


@pytest.mark.parametrize('url', [
    'file:///etc/passwd', 'http://user:password@server', 'http://server?q=x',
    'http://server#fragment', 'http://server?', 'http://server#', 'http://server:0',
    'http://server:65536', 'http://server:', 'http://[invalid]', 'http://server\\@evil',
    'http://server\n', 'http://[fe80::1%25eth0]', 'http://', None,
])
def test_invalid_base_urls(url):
    with pytest.raises(ValueError):
        normalize_base_url(url)


def test_reverse_proxy_paths_and_ipv6_are_preserved():
    assert normalize_base_url('https://MEDIA:443/jellyfin/') == 'https://media/jellyfin'
    assert normalize_base_url('http://[::1]:8096/emby/') == 'http://[::1]:8096/emby'


def test_dns_mixed_empty_and_failure_fail_closed():
    answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 80)) for ip in ('8.8.8.8', '10.0.0.1')]
    with patch('socket.getaddrinfo', return_value=answers):
        with pytest.raises(ValueError):
            validate_url('https://media.test/hook?token=opaque')
        validate_url('https://media.test/hook?token=opaque', allow_private=True)
    with patch('socket.getaddrinfo', return_value=[]):
        with pytest.raises(ValueError):
            validate_url('http://media.test')
    with patch('socket.getaddrinfo', side_effect=socket.gaierror):
        with pytest.raises(ValueError):
            validate_url('http://media.test')


@pytest.mark.asyncio
async def test_connector_rechecks_dns_after_preflight_rebinding():
    answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]
    with patch('socket.getaddrinfo', return_value=answer):
        validate_url('https://attacker.test')
    connector = GuardedConnector()
    try:
        with patch.object(aiohttp.TCPConnector, '_resolve_host', AsyncMock(return_value=[{'host': '127.0.0.1'}])):
            with pytest.raises(OutboundHTTPError):
                await connector._resolve_host('attacker.test', 443)
    finally:
        await connector.close()


@pytest.mark.asyncio
async def test_literal_ip_and_cached_resolutions_are_also_checked():
    connector = GuardedConnector()
    try:
        with pytest.raises(OutboundHTTPError):
            await connector._resolve_host('127.0.0.1', 80)
        with patch.object(aiohttp.TCPConnector, '_resolve_host', AsyncMock(side_effect=[
            [{'host': '8.8.8.8'}], [{'host': '10.0.0.1'}], [],
        ])) as resolver:
            assert (await connector._resolve_host('public.test', 443))[0]['host'] == '8.8.8.8'
            for _ in range(2):
                with pytest.raises(OutboundHTTPError):
                    await connector._resolve_host('public.test', 443)
            assert resolver.await_count == 3
    finally:
        await connector.close()


@pytest.mark.asyncio
async def test_authorized_lan_connector_uses_the_validated_answers():
    connector = GuardedConnector(private_origins=(('http', 'media', 8096),))
    answers = [{'host': '192.168.1.3'}, {'host': '::1'}]
    try:
        with patch.object(aiohttp.TCPConnector, '_resolve_host', AsyncMock(return_value=answers)) as resolver:
            assert await connector._resolve_host('media', 8096) is answers
            resolver.assert_awaited_once()
            with pytest.raises(OutboundHTTPError):
                await connector._resolve_host('unapproved', 8096)
    finally:
        await connector.close()


@pytest.mark.asyncio
async def test_session_blocks_redirects_and_foreign_credential_destinations():
    @asynccontextmanager
    async def reply(*args, **kwargs):
        yield MagicMock(status=302)

    async with GuardedSession(private_urls=('https://media.test/base',),
                              allowed_urls=('https://media.test/base',)) as session:
        with patch.object(session._session, 'request', side_effect=reply) as request:
            with pytest.raises(OutboundHTTPError, match='redirect'):
                async with session.get('https://media.test/base/users', headers={'X-Api-Key': 'test-only'}):
                    pass
            args, kwargs = request.call_args
            assert args == ('GET', 'https://media.test/base/users')  # Host and TLS hostname stay intact.
            assert kwargs['allow_redirects'] is False
            assert 'ssl' not in kwargs and 'server_hostname' not in kwargs
            for url in ('https://evil.test/users', 'https://user:password@media.test/users'):
                with pytest.raises(OutboundHTTPError):
                    async with session.get(url, headers={'X-Api-Key': 'test-only'}):
                        pass
            assert request.call_count == 1
        assert session._session.trust_env is False
        assert isinstance(session._session.cookie_jar, aiohttp.DummyCookieJar)


@pytest.mark.asyncio
@pytest.mark.parametrize('destination,blocked', [('127.0.0.1', True), ('8.8.8.8', False)])
async def test_real_connector_path_blocks_before_socket_and_preserves_tls(destination, blocked):
    import ssl
    answer = [{'hostname': 'guard.example', 'host': destination, 'port': 443,
               'family': socket.AF_INET, 'proto': socket.IPPROTO_TCP, 'flags': socket.AI_NUMERICHOST}]
    async with GuardedSession(allowed_urls=('https://guard.example',)) as session:
        connector = session._session.connector
        with patch.object(connector._resolver, 'resolve', AsyncMock(return_value=answer)), \
             patch.object(connector, '_wrap_create_connection', AsyncMock(side_effect=RuntimeError('stop before socket'))) as connect:
            if blocked:
                with pytest.raises(OutboundHTTPError):
                    async with session.get('https://guard.example/users'):
                        pass
                connect.assert_not_awaited()
            else:
                with pytest.raises(RuntimeError, match='stop before socket'):
                    async with session.get('https://guard.example/users'):
                        pass
                options = connect.call_args.kwargs
                assert options['addr_infos'][0][4][0] == destination
                assert options['server_hostname'] == 'guard.example'
                assert options['ssl'].verify_mode == ssl.CERT_REQUIRED
                assert options['ssl'].check_hostname is True
                assert options['req'].headers['Host'] == 'guard.example'
