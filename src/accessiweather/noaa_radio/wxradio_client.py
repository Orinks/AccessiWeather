"""Client for wxradio.org Icecast JSON API for dynamic NOAA stream discovery."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Default API endpoint
WXRADIO_API_URL = "https://wxradio.org/status-json.xsl"

# Default cache TTL in seconds (30 minutes)
DEFAULT_CACHE_TTL = 1800

# Default request timeout in seconds
DEFAULT_TIMEOUT = 10

# Regex to extract call sign from mount name (last segment after final hyphen)
_CALL_SIGN_RE = re.compile(r"-([A-Z]{2,3}\d{2,4}(?:-[Aa]lt\d*|-ALT\d*|-[A-Z])?)$", re.IGNORECASE)


def _extract_call_sign(mount: str) -> str | None:
    """
    Extract a station call sign from an Icecast mount name.

    Examples:
        /FL-Tallahassee-KIH24 -> KIH24
        /MI-MountPleasant-KZZ33-alt2 -> KZZ33
        /NE-Omaha-KIH61-A -> KIH61

    Args:
        mount: The mount point string (e.g. "/FL-Tallahassee-KIH24").

    Returns:
        The call sign string, or None if not parseable.

    """
    # Strip leading slash
    name = mount.lstrip("/")
    if not name:
        return None

    # Split by hyphens; call sign is typically the 3rd segment
    # Format: STATE-City-CALLSIGN or STATE-City-CALLSIGN-altN
    parts = name.split("-")
    if len(parts) < 3:
        return None

    # The call sign is the part that matches typical NWR call sign patterns
    # (letters followed by digits, e.g. KIH24, WXK85, WNG553, XLF339)
    call_sign_pattern = re.compile(r"^[A-Z]{2,4}\d{2,4}$", re.IGNORECASE)
    for part in parts[2:]:  # Skip state and city
        if call_sign_pattern.match(part):
            return part.upper()

    return None


class WxRadioClient:
    """
    Client that fetches and caches live stream data from wxradio.org.

    Queries the Icecast JSON status API to discover currently active
    NOAA Weather Radio streams, extracts call signs from mount names,
    and caches results with a configurable TTL.
    """

    def __init__(
        self,
        api_url: str = WXRADIO_API_URL,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        """
        Initialize the wxradio.org client.

        Args:
            api_url: URL of the Icecast JSON status endpoint.
            cache_ttl: Cache time-to-live in seconds.
            timeout: HTTP request timeout in seconds.
            session: Optional requests.Session for connection pooling/testing.

        """
        self._api_url = api_url
        self._cache_ttl = cache_ttl
        self._timeout = timeout
        self._session = session or requests.Session()
        self._cache: dict[str, list[str]] | None = None
        self._cache_time: float = 0.0

    @property
    def cache_ttl(self) -> int:
        """Return the cache TTL in seconds."""
        return self._cache_ttl

    def _is_cache_valid(self) -> bool:
        """Check whether the cached data is still fresh."""
        return self._cache is not None and (time.monotonic() - self._cache_time) < self._cache_ttl

    def get_streams(self) -> dict[str, list[str]]:
        """
        Get a mapping of call signs to stream URLs.

        Returns cached data if still fresh, otherwise fetches from the API.
        On error, returns cached data (even if stale) or an empty dict.

        Returns:
            Dictionary mapping uppercase call signs to lists of HTTPS stream URLs.

        """
        if self._is_cache_valid():
            return dict(self._cache)  # type: ignore[arg-type]

        try:
            data = self._fetch()
            streams = self._parse(data)
            self._cache = streams
            self._cache_time = time.monotonic()
            return dict(streams)
        except Exception:
            logger.warning("Failed to fetch wxradio.org streams, using cached/empty data")
            if self._cache is not None:
                return dict(self._cache)
            return {}

    def _fetch(self) -> dict[str, Any]:
        """
        Fetch the Icecast JSON status from wxradio.org.

        Returns:
            The parsed JSON response as a dictionary.

        Raises:
            requests.RequestException: On network or HTTP errors.
            ValueError: On malformed JSON.

        """
        response = self._session.get(self._api_url, timeout=self._timeout)
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def _parse(self, data: dict[str, Any]) -> dict[str, list[str]]:
        """
        Parse the Icecast JSON response into a call sign -> URLs mapping.

        Args:
            data: The parsed JSON response from the Icecast server.

        Returns:
            Dictionary mapping call signs to lists of stream URLs.

        """
        streams: dict[str, list[str]] = {}

        try:
            icestats = data.get("icestats", {})
            sources = icestats.get("source", [])
        except (AttributeError, TypeError):
            logger.warning("Malformed wxradio.org response: missing icestats/source")
            return streams

        # Icecast returns a single dict if only one source, list otherwise
        if isinstance(sources, dict):
            sources = [sources]

        if not isinstance(sources, list):
            return streams

        for source in sources:
            if not isinstance(source, dict):
                continue

            listenurl = source.get("listenurl", "")
            server_name = source.get("server_name", "")

            # Extract mount from listenurl or use server_name
            mount = ""
            if isinstance(listenurl, str) and listenurl:
                # listenurl is like http://wxradio.org:8000/FL-Tallahassee-KIH24
                parts = listenurl.rsplit("/", 1)
                if len(parts) == 2:
                    mount = "/" + parts[1]

            if not mount and isinstance(server_name, str):
                mount = "/" + server_name

            if not mount:
                continue

            call_sign = _extract_call_sign(mount)
            if not call_sign:
                continue

            # Build HTTPS URL
            mount_path = mount.lstrip("/")
            url = f"https://wxradio.org/{mount_path}"

            if call_sign not in streams:
                streams[call_sign] = []
            if url not in streams[call_sign]:
                streams[call_sign].append(url)

        return streams

    def invalidate_cache(self) -> None:
        """Force the cache to be invalidated."""
        self._cache = None
        self._cache_time = 0.0
