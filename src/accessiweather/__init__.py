"""Simple AccessiWeather package.

This package provides a simplified, async-first implementation of AccessiWeather
using BeeWare/Toga best practices, replacing the complex service layer architecture
with straightforward, direct API calls and simple data models.
"""

from .display import WxStyleWeatherFormatter
from .formatters import WeatherFormatter
from .location_manager import LocationManager
from .models import (
    AppConfig,
    AppSettings,
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)
from .simple_config import ConfigManager
from .toga_app import AccessiWeatherApp, main
from .utils import (
    TemperatureUnit,
    convert_wind_direction_to_cardinal,
    format_pressure,
    format_temperature,
    format_wind_speed,
)
from .weather_client import WeatherClient

__all__ = [
    # Main app
    "AccessiWeatherApp",
    "main",
    # Core components
    "ConfigManager",
    "WeatherClient",
    "LocationManager",
    "WeatherFormatter",
    "WxStyleWeatherFormatter",
    # Data models
    "Location",
    "CurrentConditions",
    "ForecastPeriod",
    "Forecast",
    "HourlyForecastPeriod",
    "HourlyForecast",
    "WeatherAlert",
    "WeatherAlerts",
    "WeatherData",
    "AppSettings",
    "AppConfig",
    # Utilities
    "TemperatureUnit",
    "format_temperature",
    "format_wind_speed",
    "format_pressure",
    "convert_wind_direction_to_cardinal",
]
