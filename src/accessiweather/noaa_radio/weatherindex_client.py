"""Client for WeatherIndex NOAA Weather Radio station feeds."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

WEATHERINDEX_API_URL = "https://api.wxindex.org/v1/stations/{call_sign}"
DEFAULT_CACHE_TTL = 1800
DEFAULT_TIMEOUT = 10


@dataclass(frozen=True)
class WeatherIndexServedCounty:
    """County coverage metadata advertised for a NOAA Weather Radio station."""

    county: str
    same_code: str
    state: str
    area: str | None = None


@dataclass(frozen=True)
class WeatherIndexStationMetadata:
    """Coverage metadata from the WeatherIndex station detail endpoint."""

    call_sign: str
    wfo: str | None
    latitude: float | None
    longitude: float | None
    served_counties: tuple[WeatherIndexServedCounty, ...]


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
        self._metadata_cache: dict[str, tuple[WeatherIndexStationMetadata | None, float]] = {}

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

    def get_station_metadata(self, call_sign: str) -> WeatherIndexStationMetadata | None:
        """Return station coverage metadata, or None when unavailable."""
        normalized = call_sign.upper().strip()
        if not normalized:
            return None

        cached_metadata = self._get_cached_metadata(normalized)
        if cached_metadata is not _CACHE_MISS:
            return cached_metadata

        try:
            payload = self._fetch(normalized)
            metadata = self._parse_metadata(payload, normalized)
            self._metadata_cache[normalized] = (metadata, time.monotonic())
            return metadata
        except Exception:
            logger.warning("Failed to fetch WeatherIndex metadata for %s", normalized)
            return None

    def _get_cached(self, call_sign: str) -> list[str] | None:
        cached = self._cache.get(call_sign)
        if cached is None:
            return None

        urls, cache_time = cached
        if (time.monotonic() - cache_time) < self._cache_ttl:
            return urls

        return None

    def _get_cached_metadata(self, call_sign: str) -> WeatherIndexStationMetadata | None | object:
        cached = self._metadata_cache.get(call_sign)
        if cached is None:
            return _CACHE_MISS

        metadata, cache_time = cached
        if (time.monotonic() - cache_time) < self._cache_ttl:
            return metadata

        return _CACHE_MISS

    def _fetch(self, call_sign: str) -> dict[str, Any]:
        response = self._session.get(
            self._api_url_template.format(call_sign=call_sign),
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def _parse(self, payload: dict[str, Any]) -> list[str]:
        station_data = self._station_payload(payload)
        if not station_data:
            return []
        feeds = station_data.get("feeds", [])

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

    def _parse_metadata(
        self, payload: dict[str, Any], requested_call_sign: str
    ) -> WeatherIndexStationMetadata | None:
        station_data = self._station_payload(payload)
        if not station_data:
            return None

        served_counties_raw = station_data.get("served_counties")
        if not isinstance(served_counties_raw, list):
            served_counties_raw = []

        served_counties: list[WeatherIndexServedCounty] = []
        for county_data in served_counties_raw:
            if not isinstance(county_data, dict):
                continue
            same_code = self._normalize_same_code(county_data.get("same_code"))
            state = county_data.get("state")
            county = county_data.get("county")
            if not same_code or not isinstance(state, str) or not isinstance(county, str):
                continue
            area = county_data.get("area")
            served_counties.append(
                WeatherIndexServedCounty(
                    county=county.strip(),
                    same_code=same_code,
                    state=state.strip().upper(),
                    area=area.strip() if isinstance(area, str) and area.strip() else None,
                )
            )

        call_sign = station_data.get("callsign") or station_data.get("call_sign")
        wfo = station_data.get("wfo")
        return WeatherIndexStationMetadata(
            call_sign=str(call_sign or requested_call_sign).strip().upper(),
            wfo=wfo.strip() if isinstance(wfo, str) and wfo.strip() else None,
            latitude=self._as_float(station_data.get("latitude")),
            longitude=self._as_float(station_data.get("longitude")),
            served_counties=tuple(served_counties),
        )

    @staticmethod
    def _station_payload(payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        station_data = payload.get("station")
        if isinstance(station_data, dict):
            return station_data
        return payload

    @staticmethod
    def _normalize_same_code(value: object) -> str | None:
        if isinstance(value, int):
            return f"{value:06d}"
        if not isinstance(value, str):
            return None
        digits = "".join(ch for ch in value.strip() if ch.isdigit())
        if not digits:
            return None
        return digits.zfill(6)

    @staticmethod
    def _as_float(value: object) -> float | None:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None


_CACHE_MISS = object()
