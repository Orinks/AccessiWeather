"""Simple data models for AccessiWeather.

This module provides simple dataclasses for weather information,
replacing the complex service layer architecture with straightforward data structures.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Location:
    """Simple location data."""

    name: str
    latitude: float
    longitude: float

    def __str__(self) -> str:
        return self.name


@dataclass
class CurrentConditions:
    """Current weather conditions."""

    temperature_f: float | None = None
    temperature_c: float | None = None
    condition: str | None = None
    humidity: int | None = None
    wind_speed_mph: float | None = None
    wind_speed_kph: float | None = None
    wind_direction: str | None = None
    pressure_in: float | None = None
    pressure_mb: float | None = None
    feels_like_f: float | None = None
    feels_like_c: float | None = None
    visibility_miles: float | None = None
    visibility_km: float | None = None
    uv_index: float | None = None
    last_updated: datetime | None = None

    def has_data(self) -> bool:
        """Check if we have any meaningful weather data."""
        return any(
            [
                self.temperature_f is not None,
                self.temperature_c is not None,
                self.condition is not None,
            ]
        )


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

    def has_data(self) -> bool:
        """Check if we have any meaningful hourly forecast data."""
        return any(
            [
                self.temperature is not None,
                self.short_forecast is not None,
                self.wind_speed is not None,
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
        """Get the next N hours of forecast data.

        Args:
            count: Number of hours to return (default: 6)

        Returns:
            List of hourly forecast periods, up to the requested count

        """
        return self.periods[:count]


@dataclass
class WeatherAlert:
    """Weather alert/warning."""

    title: str
    description: str
    severity: str = "Unknown"
    urgency: str = "Unknown"
    certainty: str = "Unknown"
    event: str | None = None
    headline: str | None = None
    instruction: str | None = None
    onset: datetime | None = None
    expires: datetime | None = None
    areas: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.areas is None:
            self.areas = []


@dataclass
class WeatherAlerts:
    """Collection of weather alerts."""

    alerts: list[WeatherAlert]

    def has_alerts(self) -> bool:
        """Check if we have any active alerts."""
        return len(self.alerts) > 0

    def get_active_alerts(self) -> list[WeatherAlert]:
        """Get alerts that haven't expired."""
        now = datetime.now()
        active = []

        for alert in self.alerts:
            if alert.expires is None or alert.expires > now:
                active.append(alert)

        return active


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

    def has_any_data(self) -> bool:
        """Check if we have any weather data."""
        return any(
            [
                self.current and self.current.has_data(),
                self.forecast and self.forecast.has_data(),
                self.hourly_forecast and self.hourly_forecast.has_data(),
                self.alerts and self.alerts.has_alerts(),
            ]
        )


@dataclass
class ApiError:
    """API error information."""

    message: str
    code: str | None = None
    details: str | None = None
    timestamp: datetime | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


# Configuration data structures
@dataclass
class AppSettings:
    """Application settings."""

    temperature_unit: str = "both"  # "f", "c", or "both"
    update_interval_minutes: int = 10
    show_detailed_forecast: bool = True
    enable_alerts: bool = True
    minimize_to_tray: bool = True
    data_source: str = "auto"  # "nws", "openmeteo", or "auto"

    # Update system settings
    auto_update_enabled: bool = True
    update_channel: str = "stable"  # "stable" or "dev"
    update_check_interval_hours: int = 24
    debug_mode: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "temperature_unit": self.temperature_unit,
            "update_interval_minutes": self.update_interval_minutes,
            "show_detailed_forecast": self.show_detailed_forecast,
            "enable_alerts": self.enable_alerts,
            "minimize_to_tray": self.minimize_to_tray,
            "data_source": self.data_source,
            "auto_update_enabled": self.auto_update_enabled,
            "update_channel": self.update_channel,
            "update_check_interval_hours": self.update_check_interval_hours,
            "debug_mode": self.debug_mode,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        """Create from dictionary."""
        return cls(
            temperature_unit=data.get("temperature_unit", "both"),
            update_interval_minutes=data.get("update_interval_minutes", 10),
            show_detailed_forecast=data.get("show_detailed_forecast", True),
            enable_alerts=data.get("enable_alerts", True),
            minimize_to_tray=data.get("minimize_to_tray", True),
            data_source=data.get("data_source", "auto"),
            auto_update_enabled=data.get("auto_update_enabled", True),
            update_channel=data.get("update_channel", "stable"),
            update_check_interval_hours=data.get("update_check_interval_hours", 24),
            debug_mode=data.get("debug_mode", False),
        )


@dataclass
class AppConfig:
    """Application configuration."""

    settings: AppSettings
    locations: list[Location]
    current_location: Location | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "settings": self.settings.to_dict(),
            "locations": [
                {
                    "name": loc.name,
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                }
                for loc in self.locations
            ],
            "current_location": {
                "name": self.current_location.name,
                "latitude": self.current_location.latitude,
                "longitude": self.current_location.longitude,
            }
            if self.current_location
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """Create from dictionary."""
        settings = AppSettings.from_dict(data.get("settings", {}))

        locations = []
        for loc_data in data.get("locations", []):
            locations.append(
                Location(
                    name=loc_data["name"],
                    latitude=loc_data["latitude"],
                    longitude=loc_data["longitude"],
                )
            )

        current_location = None
        if data.get("current_location"):
            loc_data = data["current_location"]
            current_location = Location(
                name=loc_data["name"],
                latitude=loc_data["latitude"],
                longitude=loc_data["longitude"],
            )

        return cls(
            settings=settings,
            locations=locations,
            current_location=current_location,
        )

    @classmethod
    def default(cls) -> "AppConfig":
        """Create default configuration."""
        return cls(
            settings=AppSettings(),
            locations=[],
            current_location=None,
        )
