"""Weather data models for AccessiWeather."""

from __future__ import annotations

from .alerts import WeatherAlerts
from .weather_conditions import AviationData, CurrentConditions, EnvironmentalConditions
from .weather_core import (
    DataConflict,
    Location,
    Season,
    SourceAttribution,
    get_hemisphere,
    get_season,
)
from .weather_data import SourceData, WeatherData
from .weather_forecast import (
    Forecast,
    ForecastPeriod,
    HourlyAirQuality,
    HourlyForecast,
    HourlyForecastPeriod,
    HourlyUVIndex,
    MarineForecast,
    MarineForecastPeriod,
    MinutelyPrecipitationForecast,
    MinutelyPrecipitationPoint,
    TrendInsight,
)

__all__ = [
    "AviationData",
    "CurrentConditions",
    "DataConflict",
    "EnvironmentalConditions",
    "Forecast",
    "ForecastPeriod",
    "HourlyAirQuality",
    "HourlyForecast",
    "HourlyForecastPeriod",
    "HourlyUVIndex",
    "Location",
    "MarineForecast",
    "MarineForecastPeriod",
    "MinutelyPrecipitationForecast",
    "MinutelyPrecipitationPoint",
    "Season",
    "SourceAttribution",
    "SourceData",
    "TrendInsight",
    "WeatherData",
    "WeatherAlerts",
    "get_hemisphere",
    "get_season",
]
