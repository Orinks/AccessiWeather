"""Current, environmental, and aviation condition dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .weather_forecast import HourlyAirQuality, HourlyUVIndex


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
    cloud_cover: float | None = None  # Cloud cover percentage (0-100)
    wind_gust_mph: float | None = None  # Wind gust speed (mph)
    wind_gust_kph: float | None = None  # Wind gust speed (kph)
    precipitation_in: float | None = None  # Precipitation amount (inches)
    precipitation_mm: float | None = None  # Precipitation amount (mm)
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
                self.uv_index is not None,
                len(self.hourly_uv_index) > 0,
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
