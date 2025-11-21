"""Compatibility facade for the refactored WeatherClient implementation."""

from __future__ import annotations

from . import (
    weather_client_nws as nws_client,  # noqa: F401
    weather_client_openmeteo as openmeteo_client,  # noqa: F401
    weather_client_parsers as parsers,  # noqa: F401
    weather_client_trends as trends,  # noqa: F401
    weather_client_visualcrossing as vc_alerts,  # noqa: F401
)
from .weather_client_base import WeatherClient

__all__ = ["WeatherClient"]
