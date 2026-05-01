"""Forecast-oriented weather dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


@dataclass
class ForecastPeriod:
    """Single forecast period."""

    name: str
    temperature: float | None = None  # High temperature (or single temp for the period)
    temperature_low: float | None = None  # Low temperature for the period
    temperature_unit: str = "F"
    short_forecast: str | None = None
    detailed_forecast: str | None = None
    wind_speed: str | None = None
    wind_speed_mph: float | None = None  # Numeric mph value for unit-correct display
    wind_direction: str | None = None
    icon: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    precipitation_probability: float | None = None
    snowfall: float | None = None
    uv_index: float | None = None
    cloud_cover: float | None = None  # Cloud cover percentage (0-100)
    wind_gust: str | None = None  # Wind gust speed as string (e.g. "25 mph")
    precipitation_amount: float | None = None  # Precipitation amount (inches)

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
    summary: str | None = None

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
    humidity: int | None = None
    dewpoint_f: float | None = None
    dewpoint_c: float | None = None
    pressure_mb: float | None = None
    pressure_in: float | None = None
    precipitation_probability: float | None = None
    snowfall: float | None = None
    uv_index: float | None = None
    cloud_cover: float | None = None  # Cloud cover percentage (0-100)
    wind_speed_mph: float | None = None  # Wind speed as numeric mph (for unit-correct display)
    wind_gust_mph: float | None = None  # Wind gust speed (mph)
    precipitation_amount: float | None = None  # Precipitation amount (inches)

    # Seasonal fields - Winter
    snow_depth: float | None = None  # Snow depth at this hour (inches)
    freezing_level_ft: float | None = None  # Freezing level (feet)
    wind_chill_f: float | None = None  # Wind chill at this hour (Fahrenheit)
    wind_chill_c: float | None = None  # Wind chill at this hour (Celsius)

    # Seasonal fields - Summer
    heat_index_f: float | None = None  # Heat index at this hour (Fahrenheit)
    heat_index_c: float | None = None  # Heat index at this hour (Celsius)
    air_quality_index: int | None = None  # AQI at this hour

    # Seasonal fields - Spring/Fall
    frost_risk: bool | None = None  # Frost expected this hour
    pollen_level: str | None = None  # Pollen level this hour

    # Seasonal fields - Year-round
    precipitation_type: list[str] | None = None  # ["rain", "snow", "ice"]
    feels_like: float | None = None  # Feels like (wind chill or heat index)
    visibility_miles: float | None = None  # Visibility forecast (miles)
    visibility_km: float | None = None  # Visibility forecast (kilometers)

    def has_data(self) -> bool:
        """Check if we have any meaningful hourly forecast data."""
        return any(
            [
                self.temperature is not None,
                self.short_forecast is not None,
                self.wind_speed is not None,
                self.humidity is not None,
                self.dewpoint_f is not None,
                self.dewpoint_c is not None,
                self.pressure_mb is not None,
            ]
        )


@dataclass
class HourlyForecast:
    """Hourly weather forecast data."""

    periods: list[HourlyForecastPeriod]
    generated_at: datetime | None = None
    summary: str | None = None

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
class MinutelyPrecipitationPoint:
    """A single minute of precipitation guidance."""

    time: datetime
    precipitation_intensity: float | None = None
    precipitation_probability: float | None = None
    precipitation_type: str | None = None
    precipitation_intensity_unit: str = "mm/hr"
    precipitation_intensity_error: float | None = None
    precipitation_intensity_error_unit: str = "mm/hr"


@dataclass
class MinutelyPrecipitationForecast:
    """Short-range precipitation guidance from a minutely provider."""

    summary: str | None = None
    icon: str | None = None
    points: list[MinutelyPrecipitationPoint] = field(default_factory=list)

    def has_data(self) -> bool:
        """Return True when at least one minutely point is available."""
        return len(self.points) > 0


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
class MarineForecastPeriod:
    """Single marine forecast period from an NWS marine zone product."""

    name: str
    summary: str


@dataclass
class MarineForecast:
    """Marine zone essentials for a coastal location."""

    zone_id: str | None = None
    zone_name: str | None = None
    forecast_summary: str | None = None
    issued_at: datetime | None = None
    periods: list[MarineForecastPeriod] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)

    def has_data(self) -> bool:
        """Return True when any marine essentials are available."""
        return bool(self.forecast_summary or self.zone_name or self.periods or self.highlights)
