"""Tests for NOAA radio station availability filtering."""

from __future__ import annotations

from unittest.mock import MagicMock

from accessiweather.noaa_radio import Station
from accessiweather.noaa_radio.station_availability import StationAvailabilityService


def test_filters_out_station_without_weatherindex_feeds():
    weatherindex = MagicMock()
    weatherindex.get_stream_urls.side_effect = lambda call_sign: (
        [] if call_sign == "NOFEED" else ["https://example.com/live"]
    )
    cache = MagicMock()
    cache.is_suppressed.return_value = False

    service = StationAvailabilityService(
        weatherindex_client=weatherindex,
        availability_cache=cache,
    )
    stations = [
        Station("NOFEED", 162.4, "No Feed", 0.0, 0.0, "TX"),
        Station("WXK27", 162.4, "Austin", 0.0, 0.0, "TX"),
    ]

    entries = service.build_entries(stations)

    assert [entry.station.call_sign for entry in entries] == ["WXK27"]
    assert entries[0].label == "WXK27 - Austin (162.4 MHz)"
    assert entries[0].available is True


def test_hides_suppressed_station_by_default():
    weatherindex = MagicMock()
    weatherindex.get_stream_urls.return_value = ["https://example.com/live"]
    cache = MagicMock()
    cache.is_suppressed.side_effect = lambda call_sign: call_sign == "WXK27"

    service = StationAvailabilityService(
        weatherindex_client=weatherindex,
        availability_cache=cache,
    )
    stations = [Station("WXK27", 162.4, "Austin", 0.0, 0.0, "TX")]

    assert service.build_entries(stations) == []


def test_includes_suppressed_station_when_show_unavailable_enabled():
    weatherindex = MagicMock()
    weatherindex.get_stream_urls.return_value = ["https://example.com/live"]
    cache = MagicMock()
    cache.is_suppressed.return_value = True

    service = StationAvailabilityService(
        weatherindex_client=weatherindex,
        availability_cache=cache,
    )
    stations = [Station("WXK27", 162.4, "Austin", 0.0, 0.0, "TX")]

    entries = service.build_entries(stations, show_unavailable=True)

    assert len(entries) == 1
    assert entries[0].available is False
    assert entries[0].unavailable_reason == "temporarily unavailable"
    assert entries[0].label == "WXK27 - Austin (162.4 MHz) - temporarily unavailable"
