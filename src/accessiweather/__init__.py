"""Simple AccessiWeather package.

This package provides a simplified, async-first implementation of AccessiWeather
using BeeWare/Toga best practices, replacing the complex service layer architecture
with straightforward, direct API calls and simple data models.
"""

from .app import AccessiWeatherApp, main
from .config import ConfigManager
from .display import DetailedWeatherFormatter
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
from .utils import (
    TemperatureUnit,
    convert_wind_direction_to_cardinal,
    format_pressure,
    format_temperature,
    format_wind_speed,
)
from .weather_client import WeatherClient

# Package version is sourced from installed metadata, with fallback to pyproject.toml
try:
    from importlib.metadata import (
        PackageNotFoundError,
        version as _pkg_version,
    )

    try:
        _v = _pkg_version("accessiweather")
    except PackageNotFoundError:
        _v = None
except Exception:
    _v = None


def _read_pyproject_version() -> str | None:
    try:
        import tomllib
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        py = root / "pyproject.toml"
        if not py.exists():
            return None
        with py.open("rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version") or data.get("tool", {}).get(
            "briefcase", {}
        ).get("version")
    except Exception:
        return None


__version__ = _v or _read_pyproject_version() or "0.0.0"


__all__ = [
    # Main app
    "AccessiWeatherApp",
    "main",
    # Core components
    "ConfigManager",
    "WeatherClient",
    "LocationManager",
    "WeatherFormatter",
    "DetailedWeatherFormatter",
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
