"""App-wide NOAA radio HTTP clients and the WeatherIndex-backed station database."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from accessiweather.noaa_radio.station_db import StationDatabase
from accessiweather.noaa_radio.stations import Station
from accessiweather.noaa_radio.weatherindex_client import WeatherIndexClient
from accessiweather.noaa_radio.wxradio_client import WxRadioClient
from accessiweather.paths import resolve_default_runtime_storage

logger = logging.getLogger(__name__)

_wxradio_client: WxRadioClient | None = None
_weatherindex_client: WeatherIndexClient | None = None
_client_lock = threading.Lock()


def _directory_cache_path() -> Path | None:
    try:
        return resolve_default_runtime_storage().noaa_radio_station_directory_file
    except Exception:
        logger.debug("Could not resolve NOAA radio station directory cache path", exc_info=True)
        return None


def get_weatherindex_client() -> WeatherIndexClient:
    """Return the shared WeatherIndex client so every radio entry point shares one cache."""
    global _weatherindex_client
    with _client_lock:
        if _weatherindex_client is None:
            _weatherindex_client = WeatherIndexClient(directory_cache_path=_directory_cache_path())
            logger.debug("Created cached WeatherIndexClient instance")
        return _weatherindex_client


def get_wxradio_client() -> WxRadioClient:
    """Return the shared wxradio.org client."""
    global _wxradio_client
    with _client_lock:
        if _wxradio_client is None:
            _wxradio_client = WxRadioClient()
            logger.debug("Created cached WxRadioClient instance")
        return _wxradio_client


def directory_stations(weatherindex_client: WeatherIndexClient) -> list[Station]:
    """Return WeatherIndex directory stations as ``Station`` records (empty on failure)."""
    try:
        entries = weatherindex_client.get_all_stations()
    except Exception:
        logger.warning("Could not load WeatherIndex station directory", exc_info=True)
        return []
    if not isinstance(entries, list):
        return []
    stations: list[Station] = []
    for entry in entries:
        station = entry.to_station()
        if station is not None:
            stations.append(station)
    return stations


def load_station_database(weatherindex_client: WeatherIndexClient) -> StationDatabase:
    """
    Build the station database from the WeatherIndex directory.

    WeatherIndex is the source of truth for which transmitters currently have
    a live stream, so its directory replaces the built-in list whenever it can
    be loaded. The built-in list is only a last resort when neither the API nor
    the on-disk copy of the directory is available.
    """
    stations = directory_stations(weatherindex_client)
    if stations:
        return StationDatabase(stations)
    logger.warning("Using built-in NOAA radio station list; WeatherIndex directory unavailable")
    return StationDatabase()
