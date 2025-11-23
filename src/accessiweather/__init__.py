"""Simple AccessiWeather package."""

from __future__ import annotations

import importlib
from importlib import metadata

_EXPORT_MAP = {
    # Main app
    "AccessiWeatherApp": "accessiweather.app",
    "main": "accessiweather.app",
    # Core components
    "ConfigManager": "accessiweather.config",
    "WeatherClient": "accessiweather.weather_client",
    "LocationManager": "accessiweather.location_manager",
    "WeatherFormatter": "accessiweather.formatters",
    "WeatherPresenter": "accessiweather.display",
    # Data models
    "Location": "accessiweather.models",
    "CurrentConditions": "accessiweather.models",
    "ForecastPeriod": "accessiweather.models",
    "Forecast": "accessiweather.models",
    "HourlyForecastPeriod": "accessiweather.models",
    "HourlyForecast": "accessiweather.models",
    "EnvironmentalConditions": "accessiweather.models",
    "TrendInsight": "accessiweather.models",
    "WeatherAlert": "accessiweather.models",
    "WeatherAlerts": "accessiweather.models",
    "WeatherData": "accessiweather.models",
    "AppSettings": "accessiweather.models",
    "AppConfig": "accessiweather.models",
    # Weather History
    "HistoricalWeatherData": "accessiweather.weather_history",
    "WeatherHistoryService": "accessiweather.weather_history",
    "WeatherComparison": "accessiweather.weather_history",
    # Utilities
    "TemperatureUnit": "accessiweather.utils",
    "format_temperature": "accessiweather.utils",
    "format_wind_speed": "accessiweather.utils",
    "format_pressure": "accessiweather.utils",
    "convert_wind_direction_to_cardinal": "accessiweather.utils",
}

try:
    _v = metadata.version("accessiweather")
except metadata.PackageNotFoundError:
    _v = None
except Exception:
    _v = None


def _read_pyproject_version() -> str | None:
    """Read version from pyproject.toml (project.version is the single source of truth)."""
    try:
        from pathlib import Path

        import tomllib

        root = Path(__file__).resolve().parents[2]
        py = root / "pyproject.toml"
        if not py.exists():
            return None
        with py.open("rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version")
    except Exception:
        return None


__version__ = _v or _read_pyproject_version() or "0.0.0"


def __getattr__(name: str):
    module_path = _EXPORT_MAP.get(name)
    if module_path is None:
        raise AttributeError(f"module 'accessiweather' has no attribute '{name}'")
    module = importlib.import_module(module_path)
    return getattr(module, name)


def __dir__():  # pragma: no cover - trivial listing helper
    return sorted(set(__all__))


__all__ = [
    # Main app
    "AccessiWeatherApp",
    "main",
    # Core components
    "ConfigManager",
    "WeatherClient",
    "LocationManager",
    "WeatherFormatter",
    "WeatherPresenter",
    # Data models
    "Location",
    "CurrentConditions",
    "ForecastPeriod",
    "Forecast",
    "HourlyForecastPeriod",
    "HourlyForecast",
    "EnvironmentalConditions",
    "TrendInsight",
    "WeatherAlert",
    "WeatherAlerts",
    "WeatherData",
    "AppSettings",
    "AppConfig",
    # Weather History
    "HistoricalWeatherData",
    "WeatherHistoryService",
    "WeatherComparison",
    # Utilities
    "TemperatureUnit",
    "format_temperature",
    "format_wind_speed",
    "format_pressure",
    "convert_wind_direction_to_cardinal",
]
