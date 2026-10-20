"""URL syntax and address policy shared by preflight and HTTP transport checks."""
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit


def parse_http_url(url: str):
    """Validate syntax without DNS or disclosing a credential-bearing URL."""
    if not isinstance(url, str) or not url or any(ord(c) <= 32 or ord(c) == 127 for c in url) or '\\' in url:
        raise ValueError('Invalid HTTP URL')
    try:
        parsed = urlsplit(url)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or '#' in url or '%' in parsed.hostname):
            raise ValueError
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError
        if parsed.netloc.endswith(':'):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('Invalid HTTP URL') from None
    return parsed


def normalize_base_url(url: str) -> str:
    """Canonical integration base; preserve legitimate reverse-proxy paths."""
    parsed = parse_http_url(url)
    if '?' in url:
        raise ValueError('Integration base URLs cannot contain a query or fragment')
    host = parsed.hostname.lower()
    if ':' in host:
        host = f'[{host}]'
    if parsed.port and parsed.port != (443 if parsed.scheme == 'https' else 80):
        host += f':{parsed.port}'
    return urlunsplit((parsed.scheme, host, parsed.path.rstrip('/'), '', ''))


def url_origin(url: str) -> tuple[str, str, int]:
    parsed = parse_http_url(url)
    return parsed.scheme, parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == 'https' else 80)


def validate_address(value: str, allow_private: bool = False) -> None:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        raise ValueError('Invalid destination address') from None
    if allow_private:
        return
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        elif (ip.sixtofour is not None or ip.teredo is not None
              or ip in ipaddress.ip_network('64:ff9b::/96')
              or ip in ipaddress.ip_network('64:ff9b:1::/48')):
            raise ValueError('IPv6 transition destinations are not allowed')
    if (not ip.is_global or ip.is_multicast or ip.is_reserved
            or ip.is_unspecified or ip.is_loopback or ip.is_link_local
            or getattr(ip, 'is_site_local', False)):
        raise ValueError('Connections to non-public addresses are not allowed')


def validate_url(url: str, allow_private: bool = False) -> None:
    """Preflight check; transport MUST also validate its own DNS results."""
    parsed = parse_http_url(url)
    try:
        results = socket.getaddrinfo(parsed.hostname, parsed.port, type=socket.SOCK_STREAM)
    except (UnicodeError, OSError):
        raise ValueError('Could not resolve destination hostname') from None
    if not results:
        raise ValueError('Could not resolve destination hostname')
    for result in results:
        validate_address(result[4][0], allow_private)


def validate_base_url(url: str, allow_private: bool = True) -> str:
    normalized = normalize_base_url(url)
    validate_url(normalized, allow_private=allow_private)
    return normalized
