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

# Text product models (NWS AFD / HWO / SPS)
from .text_product import TextProduct
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
    HourlyUVIndex,
    Location,
    MarineForecast,
    MarineForecastPeriod,
    MinutelyPrecipitationForecast,
    MinutelyPrecipitationPoint,
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
    "HourlyUVIndex",
    "MarineForecastPeriod",
    "MarineForecast",
    "MinutelyPrecipitationPoint",
    "MinutelyPrecipitationForecast",
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
    "TextProduct",
]
