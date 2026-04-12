"""Client for WeatherIndex NOAA Weather Radio station feeds."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

WEATHERINDEX_API_URL = "https://api.wxindex.org/v1/stations/{call_sign}"
DEFAULT_CACHE_TTL = 1800
DEFAULT_TIMEOUT = 10


class WeatherIndexClient:
    """Resolve live stream URLs for a known NOAA radio call sign."""

    def __init__(
        self,
        api_url_template: str = WEATHERINDEX_API_URL,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        """Configure API URL template, cache TTL, timeout, and optional session."""
        self._api_url_template = api_url_template
        self._cache_ttl = cache_ttl
        self._timeout = timeout
        self._session = session or requests.Session()
        self._cache: dict[str, tuple[list[str], float]] = {}

    def get_stream_urls(self, call_sign: str) -> list[str]:
        """Return live stream URLs for a call sign, or an empty list on failure."""
        normalized = call_sign.upper().strip()
        if not normalized:
            return []

        cached_urls = self._get_cached(normalized)
        if cached_urls is not None:
            return list(cached_urls)

        try:
            payload = self._fetch(normalized)
            urls = self._parse(payload)
            self._cache[normalized] = (urls, time.monotonic())
            return list(urls)
        except Exception:
            logger.warning("Failed to fetch WeatherIndex feeds for %s", normalized)
            return []

    def _get_cached(self, call_sign: str) -> list[str] | None:
        cached = self._cache.get(call_sign)
        if cached is None:
            return None

        urls, cache_time = cached
        if (time.monotonic() - cache_time) < self._cache_ttl:
            return urls

        return None

    def _fetch(self, call_sign: str) -> dict[str, Any]:
        response = self._session.get(
            self._api_url_template.format(call_sign=call_sign),
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def _parse(self, payload: dict[str, Any]) -> list[str]:
        station_data = payload.get("station") if isinstance(payload, dict) else None
        if isinstance(station_data, dict):
            feeds = station_data.get("feeds", [])
        elif isinstance(payload, dict):
            feeds = payload.get("feeds", [])
        else:
            return []

        if not isinstance(feeds, list):
            return []

        urls: list[str] = []
        for feed in feeds:
            if not isinstance(feed, dict):
                continue
            stream_url = feed.get("stream_url")
            if not isinstance(stream_url, str):
                continue
            normalized = stream_url.strip()
            if normalized and normalized not in urls:
                urls.append(normalized)

        return urls
