"""AccessiWeather package metadata and lazy top-level compatibility exports."""

from __future__ import annotations

from typing import Any


def _get_version() -> str:
    """Get version from available sources."""
    try:
        from ._build_meta import __version__ as version  # pragma: no cover - build artifact

        return version  # pragma: no cover - build artifact
    except ImportError:
        pass

    try:
        from ._version import __version__ as version  # pragma: no cover - legacy build artifact

        return version  # pragma: no cover - legacy build artifact
    except ImportError:
        pass

    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("accessiweather")
    except (ImportError, PackageNotFoundError):
        pass

    try:
        import tomllib
        from pathlib import Path

        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"  # pragma: no cover
        if pyproject.exists():  # pragma: no cover - source tree fallback
            with pyproject.open("rb") as f:  # pragma: no cover - source tree fallback
                data = tomllib.load(f)  # pragma: no cover - source tree fallback
            project_version = data.get("project", {}).get("version")  # pragma: no cover
            if project_version:  # pragma: no cover - source tree fallback
                return project_version  # pragma: no cover - source tree fallback
    except Exception:
        pass

    return "0.0.0"


__version__ = _get_version()


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "AccessiWeatherApp": ("accessiweather.app", "AccessiWeatherApp"),
    "main": ("accessiweather.app", "main"),
    "ConfigManager": ("accessiweather.config", "ConfigManager"),
    "WeatherClient": ("accessiweather.weather_client", "WeatherClient"),
    "LocationManager": ("accessiweather.location_manager", "LocationManager"),
    "WeatherFormatter": ("accessiweather.formatters", "WeatherFormatter"),
    "WeatherPresenter": ("accessiweather.display", "WeatherPresenter"),
    "TemperatureUnit": ("accessiweather.utils", "TemperatureUnit"),
    "format_temperature": ("accessiweather.utils", "format_temperature"),
    "format_wind_speed": ("accessiweather.utils", "format_wind_speed"),
    "format_pressure": ("accessiweather.utils", "format_pressure"),
    "convert_wind_direction_to_cardinal": (
        "accessiweather.utils",
        "convert_wind_direction_to_cardinal",
    ),
    "HistoricalWeatherData": ("accessiweather.weather_history", "HistoricalWeatherData"),
    "WeatherHistoryService": ("accessiweather.weather_history", "WeatherHistoryService"),
    "WeatherComparison": ("accessiweather.weather_history", "WeatherComparison"),
}

for _model_name in (
    "AppConfig",
    "AppSettings",
    "CurrentConditions",
    "EnvironmentalConditions",
    "Forecast",
    "ForecastPeriod",
    "HourlyForecast",
    "HourlyForecastPeriod",
    "Location",
    "TrendInsight",
    "WeatherAlert",
    "WeatherAlerts",
    "WeatherData",
):
    _LAZY_EXPORTS[_model_name] = ("accessiweather.models", _model_name)


def __getattr__(name: str) -> Any:
    """Load legacy top-level exports only when explicitly requested."""
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    import importlib

    module_name, attr_name = _LAZY_EXPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


__all__ = ["__version__", *_LAZY_EXPORTS]
