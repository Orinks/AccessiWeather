"""
Simple AccessiWeather package.

This package provides a simplified, async-first implementation of AccessiWeather
using BeeWare/Toga best practices, replacing the complex service layer architecture
with straightforward, direct API calls and simple data models.
"""

try:
    from .app import AccessiWeatherApp, main
except (ImportError, ModuleNotFoundError):
    # wx may not be available in test/headless environments
    AccessiWeatherApp = None  # type: ignore[assignment, misc]
    main = None  # type: ignore[assignment]
from .config import ConfigManager
from .display import WeatherPresenter
from .formatters import WeatherFormatter
from .location_manager import LocationManager
from .models import (
    AppConfig,
    AppSettings,
    CurrentConditions,
    EnvironmentalConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    TrendInsight,
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
from .weather_history import (
    HistoricalWeatherData,
    WeatherComparison,
    WeatherHistoryService,
)


# Package version: try _version.py (generated for builds), then metadata, then pyproject.toml
def _get_version() -> str:
    """Get version from available sources."""
    # 1. Try generated _build_meta.py (works in PyInstaller builds)
    try:
        from ._build_meta import __version__ as v

        return v
    except ImportError:
        pass

    # 1b. Legacy: try _version.py for backwards compatibility
    try:
        from ._version import __version__ as v

        return v
    except ImportError:
        pass

    # 2. Try importlib.metadata (works when pip-installed)
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("accessiweather")
    except (ImportError, PackageNotFoundError):
        pass

    # 3. Try reading pyproject.toml (works in dev environment)
    try:
        from pathlib import Path

        import tomllib

        root = Path(__file__).resolve().parents[2]
        py = root / "pyproject.toml"
        if py.exists():
            with py.open("rb") as f:
                data = tomllib.load(f)
            v = data.get("project", {}).get("version")
            if v:
                return v
    except Exception:
        pass

    return "0.0.0"


__version__ = _get_version()


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
