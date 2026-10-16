"""Shared NOAA radio dialog client cache."""

from __future__ import annotations

from accessiweather.noaa_radio.clients import get_weatherindex_client, get_wxradio_client
from accessiweather.noaa_radio.weatherindex_client import WeatherIndexClient
from accessiweather.noaa_radio.wxradio_client import WxRadioClient


def get_clients() -> tuple[WxRadioClient, WeatherIndexClient]:
    """Get or create cached client instances for dialog reuse."""
    return get_wxradio_client(), get_weatherindex_client()
