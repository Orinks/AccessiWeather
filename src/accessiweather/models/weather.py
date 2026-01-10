"""Weather data models for AccessiWeather."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from .alerts import WeatherAlerts

# Note: CurrentConditions, Forecast, HourlyForecast are defined later in this file
# and used in SourceData via forward references (string annotations)


class Season(Enum):
    """Enumeration of seasons."""

    WINTER = "winter"
    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"


def get_hemisphere(latitude: float) -> str:
    """
    Determine hemisphere based on latitude.

    Args:
        latitude: Location latitude (-90 to 90)

    Returns:
        "northern" for positive latitudes, "southern" for negative

    """
    return "northern" if latitude >= 0 else "southern"


def get_season(date: datetime, latitude: float) -> Season:
    """
    Determine the season based on date and hemisphere.

    Args:
        date: The current date
        latitude: Location latitude (determines hemisphere)

    Returns:
        The current season

    """
    hemisphere = get_hemisphere(latitude)
    month = date.month

    # Determine base season from month (Northern Hemisphere)
    if month in (12, 1, 2):
        base_season = Season.WINTER
    elif month in (3, 4, 5):
        base_season = Season.SPRING
    elif month in (6, 7, 8):
        base_season = Season.SUMMER
    else:  # 9, 10, 11
        base_season = Season.FALL

    # Flip season for Southern Hemisphere
    if hemisphere == "southern":
        season_flip = {
            Season.WINTER: Season.SUMMER,
            Season.SPRING: Season.FALL,
            Season.SUMMER: Season.WINTER,
            Season.FALL: Season.SPRING,
        }
        return season_flip[base_season]

    return base_season


@dataclass
class DataConflict:
    """Records a conflict between sources during data fusion."""

    field_name: str
    values: dict[str, Any]  # source -> value
    selected_source: str
    selected_value: Any


@dataclass
class SourceAttribution:
    """Tracks source attribution for merged data."""

    # Field name -> source name
    field_sources: dict[str, str] = field(default_factory=dict)

    # Conflicts detected during merge
    conflicts: list[DataConflict] = field(default_factory=list)

    # Sources that contributed to this data
    contributing_sources: set[str] = field(default_factory=set)

    # Sources that failed
    failed_sources: set[str] = field(default_factory=set)


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

    # Seasonal fields - Winter
    snow_depth_in: float | None = None  # Snow depth on ground (inches)
    snow_depth_cm: float | None = None  # Snow depth on ground (cm)
    snowfall_rate_in: float | None = None  # Current snowfall rate (in/hr)
    wind_chill_f: float | None = None  # Wind chill (Fahrenheit)
    wind_chill_c: float | None = None  # Wind chill (Celsius)
    freezing_level_ft: float | None = None  # Freezing level (feet)
    freezing_level_m: float | None = None  # Freezing level (meters)

    # Seasonal fields - Summer
    heat_index_f: float | None = None  # Heat index (Fahrenheit)
    heat_index_c: float | None = None  # Heat index (Celsius)

    # Seasonal fields - Spring/Fall
    frost_risk: str | None = None  # "None", "Low", "Moderate", "High"

    # Seasonal fields - Year-round
    precipitation_type: list[str] | None = None  # ["rain", "snow", "ice", etc.]
    severe_weather_risk: int | None = None  # 0-100 scale

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
    precipitation_probability: float | None = None
    snowfall: float | None = None
    uv_index: float | None = None

    # Seasonal fields - Winter
    snow_depth: float | None = None  # Expected snow accumulation (inches)
    wind_chill_min_f: float | None = None  # Minimum wind chill for the period
    wind_chill_max_f: float | None = None  # Maximum wind chill for the period
    freezing_level_ft: float | None = None  # Freezing level (feet)
    ice_risk: str | None = None  # "None", "Low", "Moderate", "High"

    # Seasonal fields - Summer
    heat_index_max_f: float | None = None  # Maximum heat index for the period
    heat_index_min_f: float | None = None  # Minimum heat index for the period
    uv_index_max: float | None = None  # Maximum UV index for the period
    air_quality_forecast: int | None = None  # Forecasted AQI

    # Seasonal fields - Spring/Fall
    frost_risk: str | None = None  # "None", "Low", "Moderate", "High"
    pollen_forecast: str | None = None  # "Low", "Moderate", "High", "Very High"

    # Seasonal fields - Year-round
    precipitation_type: list[str] | None = None  # ["rain", "snow", "ice"]
    severe_weather_risk: int | None = None  # 0-100 scale
    feels_like_high: float | None = None  # High "feels like" (heat index or temp)
    feels_like_low: float | None = None  # Low "feels like" (wind chill or temp)


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
    precipitation_probability: float | None = None
    snowfall: float | None = None
    uv_index: float | None = None

    # Seasonal fields - Winter
    snow_depth: float | None = None  # Snow depth at this hour (inches)
    freezing_level_ft: float | None = None  # Freezing level (feet)
    wind_chill_f: float | None = None  # Wind chill at this hour

    # Seasonal fields - Summer
    heat_index_f: float | None = None  # Heat index at this hour
    air_quality_index: int | None = None  # AQI at this hour

    # Seasonal fields - Spring/Fall
    frost_risk: bool | None = None  # Frost expected this hour
    pollen_level: str | None = None  # Pollen level this hour

    # Seasonal fields - Year-round
    precipitation_type: list[str] | None = None  # ["rain", "snow", "ice"]
    feels_like: float | None = None  # Feels like (wind chill or heat index)
    visibility_miles: float | None = None  # Visibility forecast

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
class HourlyUVIndex:
    """Single hour of UV index forecast data."""

    timestamp: datetime
    uv_index: float
    category: str


@dataclass
class EnvironmentalConditions:
    """Air quality and pollen conditions."""

    air_quality_index: float | None = None
    air_quality_category: str | None = None
    air_quality_pollutant: str | None = None
    hourly_air_quality: list[HourlyAirQuality] = field(default_factory=list)
    uv_index: float | None = None
    uv_category: str | None = None
    hourly_uv_index: list[HourlyUVIndex] = field(default_factory=list)
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
    daily_history: list[ForecastPeriod] = field(default_factory=list)
    discussion: str | None = None
    alerts: WeatherAlerts | None = None
    environmental: EnvironmentalConditions | None = None
    aviation: AviationData | None = None
    trend_insights: list[TrendInsight] = field(default_factory=list)
    stale: bool = False
    stale_since: datetime | None = None
    stale_reason: str | None = None
    pending_enrichments: dict[str, asyncio.Task[Any]] | None = field(default=None, repr=False)

    # Smart auto source fields
    source_attribution: SourceAttribution | None = None
    incomplete_sections: set[str] = field(default_factory=set)

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
