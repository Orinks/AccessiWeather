"""Weather data models for AccessiWeather."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from .alerts import WeatherAlerts


@dataclass
class Location:
    """Simple location data."""

    name: str
    latitude: float
    longitude: float
    timezone: str | None = None
    country_code: str | None = None

    def __str__(self) -> str:
        return self.name

    def __post_init__(self) -> None:
        if self.country_code:
            self.country_code = self.country_code.upper()


@dataclass
class CurrentConditions:
    """Current weather conditions."""

    temperature: float | None = None
    temperature_f: float | None = None
    temperature_c: float | None = None
    condition: str | None = None
    humidity: int | None = None
    wind_speed: float | None = None
    dewpoint_f: float | None = None
    dewpoint_c: float | None = None
    wind_speed_mph: float | None = None
    wind_speed_kph: float | None = None
    wind_direction: str | None = None
    pressure: float | None = None
    pressure_in: float | None = None
    pressure_mb: float | None = None
    feels_like_f: float | None = None
    feels_like_c: float | None = None
    visibility_miles: float | None = None
    visibility_km: float | None = None
    uv_index: float | None = None
    sunrise_time: datetime | None = None
    sunset_time: datetime | None = None
    moon_phase: str | None = None
    moonrise_time: datetime | None = None
    moonset_time: datetime | None = None
    last_updated: datetime | None = None

    def has_data(self) -> bool:
        """Check if we have any meaningful weather data."""
        return any(
            [
                self.temperature is not None,
                self.temperature_f is not None,
                self.temperature_c is not None,
                self.condition is not None,
            ]
        )

    def __post_init__(self) -> None:
        """Backfill unit-agnostic fields when only unit-specific data is provided."""
        if self.temperature is None:
            if self.temperature_f is not None:
                self.temperature = self.temperature_f
            elif self.temperature_c is not None:
                self.temperature = self.temperature_c

        if self.wind_speed is None:
            if self.wind_speed_mph is not None:
                self.wind_speed = self.wind_speed_mph
            elif self.wind_speed_kph is not None:
                self.wind_speed = self.wind_speed_kph

        if self.pressure is None:
            if self.pressure_in is not None:
                self.pressure = self.pressure_in
            elif self.pressure_mb is not None:
                self.pressure = self.pressure_mb


@dataclass
class ForecastPeriod:
    """Single forecast period."""

    name: str
    temperature: float | None = None
    temperature_unit: str = "F"
    short_forecast: str | None = None
    detailed_forecast: str | None = None
    wind_speed: str | None = None
    wind_direction: str | None = None
    icon: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


@dataclass
class Forecast:
    """Weather forecast data."""

    periods: list[ForecastPeriod]
    generated_at: datetime | None = None

    def has_data(self) -> bool:
        """Check if we have any forecast data."""
        return len(self.periods) > 0


@dataclass
class HourlyForecastPeriod:
    """Single hourly forecast period."""

    start_time: datetime
    temperature: float | None = None
    temperature_unit: str = "F"
    short_forecast: str | None = None
    wind_speed: str | None = None
    wind_direction: str | None = None
    icon: str | None = None
    end_time: datetime | None = None
    pressure_mb: float | None = None
    pressure_in: float | None = None

    def has_data(self) -> bool:
        """Check if we have any meaningful hourly forecast data."""
        return any(
            [
                self.temperature is not None,
                self.short_forecast is not None,
                self.wind_speed is not None,
                self.pressure_mb is not None,
            ]
        )


@dataclass
class HourlyForecast:
    """Hourly weather forecast data."""

    periods: list[HourlyForecastPeriod]
    generated_at: datetime | None = None

    def has_data(self) -> bool:
        """Check if we have any hourly forecast data."""
        return len(self.periods) > 0

    def get_next_hours(self, count: int = 6) -> list[HourlyForecastPeriod]:
        """
        Get the next N hours of forecast data.

        Args:
        ----
            count: Number of hours to return (default: 6)

        Returns:
        -------
            List of hourly forecast periods, up to the requested count

        """
        if not self.periods:
            return []

        def _to_timestamp(dt: datetime | None, *, as_utc: bool) -> float | None:
            if dt is None:
                return None
            if as_utc:
                dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
                return dt.timestamp()
            if dt.tzinfo is not None:
                dt = dt.astimezone()
            return dt.timestamp()

        has_aware_times = any(
            p.start_time and p.start_time.tzinfo is not None for p in self.periods
        )
        now_reference = datetime.now(UTC) if has_aware_times else datetime.now()
        now_ts = now_reference.timestamp()
        tolerance = timedelta(hours=1)
        tolerance_seconds = tolerance.total_seconds()

        sortable_periods: list[tuple[HourlyForecastPeriod, float]] = []
        unordered_periods: list[HourlyForecastPeriod] = []
        for period in self.periods:
            ts = _to_timestamp(period.start_time, as_utc=has_aware_times)
            if ts is None:
                unordered_periods.append(period)
            else:
                sortable_periods.append((period, ts))

        sortable_periods.sort(key=lambda item: item[1])

        upcoming: list[HourlyForecastPeriod] = []
        for period, ts in sortable_periods:
            if ts >= now_ts - tolerance_seconds:
                upcoming.append(period)
                if len(upcoming) == count:
                    break

        if upcoming:
            return upcoming[:count]

        fallback = [period for period, _ in sortable_periods] + unordered_periods
        return fallback[:count]


@dataclass
class TrendInsight:
    """Summary of a metric trend over a timeframe."""

    metric: str
    direction: str
    change: float | None = None
    unit: str | None = None
    timeframe_hours: int = 24
    summary: str | None = None
    sparkline: str | None = None


@dataclass
class HourlyAirQuality:
    """Single hour of air quality forecast data."""

    timestamp: datetime
    aqi: int
    category: str
    pm2_5: float | None = None
    pm10: float | None = None
    ozone: float | None = None
    nitrogen_dioxide: float | None = None
    sulphur_dioxide: float | None = None
    carbon_monoxide: float | None = None


@dataclass
class EnvironmentalConditions:
    """Air quality and pollen conditions."""

    air_quality_index: float | None = None
    air_quality_category: str | None = None
    air_quality_pollutant: str | None = None
    hourly_air_quality: list[HourlyAirQuality] = field(default_factory=list)
    pollen_index: float | None = None
    pollen_category: str | None = None
    pollen_tree_index: float | None = None
    pollen_grass_index: float | None = None
    pollen_weed_index: float | None = None
    pollen_primary_allergen: str | None = None
    updated_at: datetime | None = None
    sources: list[str] = field(default_factory=list)

    def has_data(self) -> bool:
        return any(
            [
                self.air_quality_index is not None,
                self.pollen_index is not None,
                self.pollen_tree_index is not None,
                self.pollen_grass_index is not None,
                self.pollen_weed_index is not None,
                len(self.hourly_air_quality) > 0,
            ]
        )


@dataclass
class AviationData:
    """Aviation specific forecast and advisory data."""

    raw_taf: str | None = None
    decoded_taf: str | None = None
    station_id: str | None = None
    airport_name: str | None = None
    active_sigmets: list[dict] = field(default_factory=list)
    active_cwas: list[dict] = field(default_factory=list)

    def has_taf(self) -> bool:
        """Return ``True`` when a TAF is available."""
        return any(
            [
                bool(self.raw_taf and self.raw_taf.strip()),
                bool(self.decoded_taf and self.decoded_taf.strip()),
            ]
        )


@dataclass
class WeatherData:
    """Complete weather data for a location."""

    location: Location
    current: CurrentConditions | None = None
    forecast: Forecast | None = None
    hourly_forecast: HourlyForecast | None = None
    discussion: str | None = None
    alerts: WeatherAlerts | None = None
    last_updated: datetime | None = None
    environmental: EnvironmentalConditions | None = None
    aviation: AviationData | None = None
    trend_insights: list[TrendInsight] = field(default_factory=list)
    stale: bool = False
    stale_since: datetime | None = None
    stale_reason: str | None = None
    pending_enrichments: dict[str, asyncio.Task[Any]] | None = field(default=None, repr=False)

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
                self.alerts and self.alerts.has_alerts(),
                self.environmental and self.environmental.has_data(),
                self.aviation and self.aviation.has_taf(),
            ]
        )
