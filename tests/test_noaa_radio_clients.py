"""Tests for the WeatherIndex-backed NOAA radio station database."""

from __future__ import annotations

from unittest.mock import MagicMock

from accessiweather.noaa_radio.clients import directory_stations, load_station_database
from accessiweather.noaa_radio.weatherindex_client import WeatherIndexDirectoryStation


def _entry(call_sign, lat=30.0, lon=-97.0):
    return WeatherIndexDirectoryStation(
        call_sign=call_sign,
        city="Austin",
        state="TX",
        frequency=162.4,
        latitude=lat,
        longitude=lon,
        status="NORMAL",
        stream_urls=("https://example.com/live",),
    )


def test_directory_stations_drops_entries_without_coordinates():
    client = MagicMock()
    client.get_all_stations.return_value = [_entry("WXK27"), _entry("NOPOS", lat=None)]

    assert [station.call_sign for station in directory_stations(client)] == ["WXK27"]


def test_load_station_database_uses_weatherindex_directory():
    client = MagicMock()
    client.get_all_stations.return_value = [_entry("ZZZ99")]

    db = load_station_database(client)

    assert [station.call_sign for station in db.get_all_stations()] == ["ZZZ99"]


def test_load_station_database_falls_back_to_builtin_list():
    client = MagicMock()
    client.get_all_stations.return_value = []

    db = load_station_database(client)

    assert db.get_stations_by_call_signs(["WXK27"])
