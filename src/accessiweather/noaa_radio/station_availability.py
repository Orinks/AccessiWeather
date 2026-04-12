"""Helpers for filtering NOAA radio stations by current availability."""

from __future__ import annotations

from dataclasses import dataclass

from accessiweather.noaa_radio.availability_cache import StationAvailabilityCache
from accessiweather.noaa_radio.stations import Station
from accessiweather.noaa_radio.weatherindex_client import WeatherIndexClient

TEMPORARILY_UNAVAILABLE = "temporarily unavailable"


@dataclass(frozen=True)
class StationAvailabilityEntry:
    """UI-ready station availability metadata."""

    station: Station
    available: bool
    label: str
    unavailable_reason: str | None = None


class StationAvailabilityService:
    """Build station entries using WeatherIndex and local suppression state."""

    def __init__(
        self,
        *,
        weatherindex_client: WeatherIndexClient,
        availability_cache: StationAvailabilityCache,
    ) -> None:
        """Initialize the service with WeatherIndex and local suppression state."""
        self._weatherindex_client = weatherindex_client
        self._availability_cache = availability_cache

    def build_entries(
        self,
        stations: list[Station],
        *,
        show_unavailable: bool = False,
    ) -> list[StationAvailabilityEntry]:
        entries: list[StationAvailabilityEntry] = []
        for station in stations:
            if not self._weatherindex_client.get_stream_urls(station.call_sign):
                continue

            label = self._base_label(station)
            if self._availability_cache.is_suppressed(station.call_sign):
                if not show_unavailable:
                    continue
                entries.append(
                    StationAvailabilityEntry(
                        station=station,
                        available=False,
                        label=f"{label} - {TEMPORARILY_UNAVAILABLE}",
                        unavailable_reason=TEMPORARILY_UNAVAILABLE,
                    )
                )
                continue

            entries.append(
                StationAvailabilityEntry(
                    station=station,
                    available=True,
                    label=label,
                )
            )
        return entries

    @staticmethod
    def _base_label(station: Station) -> str:
        return f"{station.call_sign} - {station.name} ({station.frequency} MHz)"
