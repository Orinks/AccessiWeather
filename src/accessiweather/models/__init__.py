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
    EnvironmentalConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
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
    "TrendInsight",
    "EnvironmentalConditions",
    "AviationData",
    "WeatherAlert",
    "WeatherAlerts",
    "WeatherData",
    "ApiError",
    "AppSettings",
    "AppConfig",
]
