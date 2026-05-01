"""Composite weather data dataclasses."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .alerts import WeatherAlerts
from .weather_conditions import AviationData, CurrentConditions, EnvironmentalConditions
from .weather_core import Location, SourceAttribution
from .weather_forecast import (
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    MarineForecast,
    MinutelyPrecipitationForecast,
    TrendInsight,
)

if TYPE_CHECKING:
    from accessiweather.alert_lifecycle import AlertLifecycleDiff
    from accessiweather.forecast_confidence import ForecastConfidence
    from accessiweather.weather_anomaly import AnomalyCallout


@dataclass
class SourceData:
    """Container for data from a single source."""

    source: str  # "nws", "openmeteo", "visualcrossing"
    current: CurrentConditions | None = None
    forecast: Forecast | None = None
    hourly_forecast: HourlyForecast | None = None
    alerts: WeatherAlerts | None = None
    fetch_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    success: bool = True
    error: str | None = None


@dataclass
class WeatherData:
    """Complete weather data for a location."""

    location: Location
    current: CurrentConditions | None = None
    forecast: Forecast | None = None
    hourly_forecast: HourlyForecast | None = None
    daily_history: list[ForecastPeriod] = field(default_factory=list)
    discussion: str | None = None
    discussion_issuance_time: datetime | None = None  # NWS AFD issuance time for update detection
    minutely_precipitation: MinutelyPrecipitationForecast | None = None
    alerts: WeatherAlerts | None = None
    environmental: EnvironmentalConditions | None = None
    aviation: AviationData | None = None
    marine: MarineForecast | None = None
    trend_insights: list[TrendInsight] = field(default_factory=list)
    stale: bool = False
    stale_since: datetime | None = None
    stale_reason: str | None = None
    pending_enrichments: dict[str, asyncio.Task[Any]] | None = field(default=None, repr=False)

    # Smart auto source fields
    source_attribution: SourceAttribution | None = None
    incomplete_sections: set[str] = field(default_factory=set)

    # Alert lifecycle diff (computed per-fetch from cached previous alerts)
    alert_lifecycle_diff: AlertLifecycleDiff | None = None
    # Cross-source forecast confidence (only set for multi-source fetches)
    forecast_confidence: ForecastConfidence | None = None
    # Historical anomaly callout (computed on demand, optional)
    anomaly_callout: AnomalyCallout | None = None

    @property
    def current_conditions(self) -> CurrentConditions | None:
        """Backward-compatible accessor for current conditions."""
        return self.current

    @current_conditions.setter
    def current_conditions(self, value: CurrentConditions | None) -> None:
        self.current = value

    def has_any_data(self) -> bool:
        """Check if we have any weather data."""
        return any(
            [
                self.current and self.current.has_data(),
                self.forecast and self.forecast.has_data(),
                self.hourly_forecast and self.hourly_forecast.has_data(),
                self.minutely_precipitation and self.minutely_precipitation.has_data(),
                self.alerts and self.alerts.has_alerts(),
                self.environmental and self.environmental.has_data(),
                self.aviation and self.aviation.has_taf(),
                self.marine and self.marine.has_data(),
            ]
        )
