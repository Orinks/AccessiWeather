"""
Data models for AccessiWeather.

This package provides dataclasses for weather information, alerts, and configuration.
"""

# Weather data models
# Alert models
from .alerts import WeatherAlert, WeatherAlerts

# Configuration models
from .config import AppConfig, AppSettings

# Error models
from .errors import ApiError
from .weather import (
    AviationData,
    CurrentConditions,
    DataConflict,
    EnvironmentalConditions,
    Forecast,
    ForecastPeriod,
    HourlyAirQuality,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    SourceAttribution,
    SourceData,
    TrendInsight,
    WeatherData,
)

__all__ = [
    "Location",
    "CurrentConditions",
    "ForecastPeriod",
    "Forecast",
    "HourlyForecastPeriod",
    "HourlyForecast",
    "HourlyAirQuality",
    "TrendInsight",
    "EnvironmentalConditions",
    "AviationData",
    "WeatherAlert",
    "WeatherAlerts",
    "WeatherData",
    "ApiError",
    "AppSettings",
    "AppConfig",
    "SourceData",
    "SourceAttribution",
    "DataConflict",
]
