"""
SSRF protection: validate user-supplied URLs before making outbound requests.

Blocks loopback, private, link-local, and multicast addresses to prevent
Server-Side Request Forgery (SSRF) attacks.
"""
import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}

_BLOCKED_HOSTNAMES = {
    "localhost",
    "ip6-localhost",
    "ip6-loopback",
    "broadcasthost",
    "local",
}


def validate_url(url: str) -> None:
    """
    Validate a user-supplied URL against SSRF attack vectors.

    Checks that the URL uses an allowed scheme (http/https), has a resolvable
    hostname that does not point to a loopback, private, link-local, or
    multicast address.

    Args:
        url: The URL string to validate.

    Raises:
        ValueError: If the URL is invalid, uses a disallowed scheme, or
                    resolves to a blocked address.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError("Invalid URL")

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"URL scheme '{parsed.scheme}' is not allowed; use http or https"
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise ValueError("Connections to internal hosts are not allowed")

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"Could not resolve hostname: {hostname}")

    for addr_info in addr_infos:
        ip_str = addr_info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("Connections to internal/private addresses are not allowed")
