"""URL validation utilities to prevent SSRF attacks."""

import ipaddress
import socket
from urllib.parse import urlparse


class SSRFError(ValueError):
    """Raised when a URL fails SSRF validation."""


def validate_backend_url(url: str) -> str:
    """
    Validate a backend URL to prevent SSRF attacks.

    Args:
        url: The URL to validate.

    Returns:
        The validated URL (stripped).

    Raises:
        SSRFError: If the URL fails validation.

    """
    url = url.strip()
    if not url:
        raise SSRFError("URL must not be empty")

    parsed = urlparse(url)

    # Enforce HTTPS only
    if parsed.scheme != "https":
        raise SSRFError(f"Only HTTPS URLs are allowed, got scheme: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL must have a valid hostname")

    # Reject localhost variants
    _lower = hostname.lower()
    if _lower in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise SSRFError(f"Localhost URLs are not allowed: {hostname!r}")

    # Check if hostname is an IP address and reject private/internal ranges
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise SSRFError(f"Private/internal IP addresses are not allowed: {hostname!r}")
    except ValueError:
        # Not an IP literal — resolve the hostname and check all addresses
        try:
            infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for _family, _type, _proto, _canonname, sockaddr in infos:
                ip_str = sockaddr[0]
                addr = ipaddress.ip_address(ip_str)
                if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                    raise SSRFError(
                        f"Hostname {hostname!r} resolves to private/internal address {ip_str}"
                    )
        except socket.gaierror:
            # Can't resolve — allow it (will fail at request time anyway)
            pass

    return url
