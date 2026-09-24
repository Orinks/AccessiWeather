"""Client for WeatherIndex NOAA Weather Radio station feeds."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from accessiweather.noaa_radio.stations import Station

logger = logging.getLogger(__name__)

WEATHERINDEX_API_URL = "https://api.wxindex.org/v1/stations/{call_sign}"
WEATHERINDEX_DIRECTORY_URL = "https://api.wxindex.org/v1/stations/all"
DEFAULT_CACHE_TTL = 1800
DEFAULT_TIMEOUT = 10
# How long to wait before re-trying the directory download after a failure.
_DIRECTORY_RETRY_DELAY = 300

OUT_OF_SERVICE_STATUS = "OUT OF SERVICE"


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


@dataclass(frozen=True)
class WeatherIndexDirectoryStation:
    """A station with live feeds from the WeatherIndex station directory."""

    call_sign: str
    city: str
    state: str
    frequency: float | None
    latitude: float | None
    longitude: float | None
    status: str
    stream_urls: tuple[str, ...]

    def to_station(self) -> Station | None:
        """Convert to the player's ``Station`` model, or None when coordinates are missing."""
        if self.latitude is None or self.longitude is None:
            return None
        name = self.city
        if self.state and not name.upper().endswith(f", {self.state}"):
            name = f"{name}, {self.state}" if name else self.state
        return Station(
            call_sign=self.call_sign,
            frequency=self.frequency if self.frequency is not None else 0.0,
            name=name,
            lat=self.latitude,
            lon=self.longitude,
            state=self.state,
            status=self.status,
        )


class WeatherIndexClient:
    """Resolve live stream URLs for a known NOAA radio call sign."""

    def __init__(
        self,
        api_url_template: str = WEATHERINDEX_API_URL,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
        *,
        directory_url: str = WEATHERINDEX_DIRECTORY_URL,
        directory_cache_path: Path | str | None = None,
    ) -> None:
        """Configure API URL template, cache TTL, timeout, and optional session."""
        self._api_url_template = api_url_template
        self._directory_url = directory_url
        self._directory_cache_path = (
            Path(directory_cache_path) if directory_cache_path is not None else None
        )
        self._cache_ttl = cache_ttl
        self._timeout = timeout
        self._session = session or requests.Session()
        self._cache: dict[str, tuple[list[str], float]] = {}
        self._metadata_cache: dict[str, tuple[WeatherIndexStationMetadata | None, float]] = {}
        self._directory: tuple[list[WeatherIndexDirectoryStation], float] | None = None

    def get_all_stations(self) -> list[WeatherIndexDirectoryStation]:
        """
        Return every station WeatherIndex currently lists with a live feed.

        The directory is fetched in one request and cached for ``cache_ttl``
        seconds. When the download fails, the previous in-memory copy is used,
        then the on-disk copy from an earlier run, then an empty list.
        """
        cached = self._get_cached_directory()
        if cached is not None:
            return list(cached)

        try:
            response = self._session.get(self._directory_url, timeout=self._timeout)
            response.raise_for_status()
            payload = response.json()
            stations = self._parse_directory(payload)
            if not stations:
                raise ValueError("WeatherIndex station directory is empty")
        except Exception:
            logger.warning("Failed to fetch WeatherIndex station directory")
            fallback = self._directory[0] if self._directory is not None else None
            if fallback is None:
                fallback = self._load_directory_from_disk()
            retry_at = time.monotonic() - self._cache_ttl + _DIRECTORY_RETRY_DELAY
            self._directory = (fallback or [], retry_at)
            return list(fallback or [])

        self._directory = (stations, time.monotonic())
        self._save_directory_to_disk(payload)
        return list(stations)

    def has_station_directory(self) -> bool:
        """Return True once a station directory (live or cached) has been loaded."""
        return self._directory is not None and bool(self._directory[0])

    def get_stream_urls(self, call_sign: str) -> list[str]:
        """Return live stream URLs for a call sign, or an empty list on failure."""
        normalized = call_sign.upper().strip()
        if not normalized:
            return []

        directory_urls = self._directory_stream_urls(normalized)
        if directory_urls is not None:
            return directory_urls

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

    def _get_cached_directory(self) -> list[WeatherIndexDirectoryStation] | None:
        if self._directory is None:
            return None
        stations, cache_time = self._directory
        if (time.monotonic() - cache_time) < self._cache_ttl:
            return stations
        return None

    def _directory_stream_urls(self, call_sign: str) -> list[str] | None:
        """Return feeds from the loaded directory, or None when it does not list the station."""
        if not self.has_station_directory():
            return None
        stations = self._directory[0] if self._directory is not None else []
        for station in stations:
            if station.call_sign == call_sign:
                return list(station.stream_urls)
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

    def _parse_directory(self, payload: object) -> list[WeatherIndexDirectoryStation]:
        entries = payload
        if isinstance(entries, dict):
            entries = entries.get("stations")
        if not isinstance(entries, list):
            return []

        stations: list[WeatherIndexDirectoryStation] = []
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            call_sign = entry.get("callsign") or entry.get("call_sign")
            if not isinstance(call_sign, str) or not call_sign.strip():
                continue
            normalized = call_sign.strip().upper()
            if normalized in seen:
                continue
            urls = self._parse(entry)
            if not urls:
                continue
            seen.add(normalized)
            city = entry.get("city")
            state = entry.get("state_slug") or entry.get("state")
            status = entry.get("status")
            stations.append(
                WeatherIndexDirectoryStation(
                    call_sign=normalized,
                    city=city.strip() if isinstance(city, str) else "",
                    state=state.strip().upper() if isinstance(state, str) else "",
                    frequency=self._as_float(entry.get("frequency")),
                    latitude=self._as_float(entry.get("latitude")),
                    longitude=self._as_float(entry.get("longitude")),
                    status=status.strip().upper() if isinstance(status, str) else "",
                    stream_urls=tuple(urls),
                )
            )
        return stations

    def _load_directory_from_disk(self) -> list[WeatherIndexDirectoryStation] | None:
        if self._directory_cache_path is None or not self._directory_cache_path.exists():
            return None
        try:
            payload = json.loads(self._directory_cache_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load cached WeatherIndex station directory: %s", exc)
            return None
        stations = self._parse_directory(payload)
        return stations or None

    def _save_directory_to_disk(self, payload: object) -> None:
        if self._directory_cache_path is None:
            return
        try:
            self._directory_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._directory_cache_path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to save WeatherIndex station directory cache: %s", exc)

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
