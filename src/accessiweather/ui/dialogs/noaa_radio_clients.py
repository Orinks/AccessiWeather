"""Shared NOAA radio dialog client cache."""

from __future__ import annotations

import logging
import threading

from accessiweather.noaa_radio.weatherindex_client import WeatherIndexClient
from accessiweather.noaa_radio.wxradio_client import WxRadioClient

logger = logging.getLogger(__name__)

_wxradio_client: WxRadioClient | None = None
_weatherindex_client: WeatherIndexClient | None = None
_client_lock = threading.Lock()


def get_clients() -> tuple[WxRadioClient, WeatherIndexClient]:
    """Get or create cached client instances for dialog reuse."""
    global _wxradio_client, _weatherindex_client
    with _client_lock:
        if _wxradio_client is None:
            _wxradio_client = WxRadioClient()
            logger.debug("Created cached WxRadioClient instance")
        if _weatherindex_client is None:
            _weatherindex_client = WeatherIndexClient()
            logger.debug("Created cached WeatherIndexClient instance")
        return _wxradio_client, _weatherindex_client
