"""Simple data models for AccessiWeather.

This module provides simple dataclasses for weather information,
replacing the complex service layer architecture with straightforward data structures.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


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
    # Optional pressure fields for trend computation
    pressure_mb: float | None = None
    pressure_in: float | None = None

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
    id: str | None = None  # NWS alert ID for unique identification

    def __post_init__(self):
        if self.areas is None:
            self.areas = []

    def get_unique_id(self) -> str:
        """Get a unique identifier for this alert.

        Uses the NWS alert ID if available, otherwise generates one from key fields.
        """
        if self.id:
            return self.id

        # Generate ID from key fields if NWS ID not available
        key_parts = [
            self.event or "unknown",
            self.severity or "unknown",
            self.headline or self.title or "unknown",
        ]
        return "-".join(part.lower().replace(" ", "_") for part in key_parts)

    def get_content_hash(self) -> str:
        """Generate a hash of key content fields for change detection.

        This helps detect when an alert has been updated with new information.
        """
        import hashlib

        # Include key fields that would indicate a meaningful change
        content_parts = [
            self.title or "",
            self.description or "",
            self.severity or "",
            self.urgency or "",
            self.headline or "",
            self.instruction or "",
        ]

        content_string = "|".join(content_parts)
        return hashlib.md5(content_string.encode(), usedforsecurity=False).hexdigest()

    def is_expired(self) -> bool:
        """Check if this alert has expired."""
        if self.expires is None:
            return False

        now = datetime.now(UTC)
        alert_expires = self.expires

        # Ensure both datetimes are timezone-aware for comparison
        if alert_expires.tzinfo is None:
            # If alert expires time is naive, assume it's UTC
            alert_expires = alert_expires.replace(tzinfo=UTC)

        return now > alert_expires

    def get_severity_priority(self) -> int:
        """Get numeric priority for severity level (higher = more severe)."""
        severity_map = {"extreme": 5, "severe": 4, "moderate": 3, "minor": 2, "unknown": 1}
        return severity_map.get(self.severity.lower(), 1)


@dataclass
class WeatherAlerts:
    """Collection of weather alerts."""

    alerts: list[WeatherAlert]

    def has_alerts(self) -> bool:
        """Check if we have any active alerts."""
        return len(self.alerts) > 0

    def get_active_alerts(self) -> list[WeatherAlert]:
        """Get alerts that haven't expired."""
        now = datetime.now(UTC)
        active = []

        for alert in self.alerts:
            if alert.expires is None:
                active.append(alert)
            else:
                # Ensure both datetimes are timezone-aware for comparison
                alert_expires = alert.expires
                if alert_expires.tzinfo is None:
                    # If alert expires time is naive, assume it's UTC
                    alert_expires = alert_expires.replace(tzinfo=UTC)

                if alert_expires > now:
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
    minimize_to_tray: bool = False
    data_source: str = "auto"  # "nws", "openmeteo", "visualcrossing", or "auto"

    # API Keys
    visual_crossing_api_key: str = ""

    # Update system settings
    auto_update_enabled: bool = True
    update_channel: str = "stable"  # GitHub release channel: "stable", "beta", or "dev"
    update_check_interval_hours: int = 24

    debug_mode: bool = False

    # Sound settings
    sound_enabled: bool = True
    sound_pack: str = "default"

    # GitHub backend settings
    github_backend_url: str = ""

    # Alert notification settings
    alert_notifications_enabled: bool = True
    alert_notify_extreme: bool = True
    alert_notify_severe: bool = True
    alert_notify_moderate: bool = True
    alert_notify_minor: bool = False
    alert_notify_unknown: bool = False
    alert_global_cooldown_minutes: int = 5
    alert_per_alert_cooldown_minutes: int = 60
    alert_escalation_cooldown_minutes: int = 15
    alert_max_notifications_per_hour: int = 10
    alert_ignored_categories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "temperature_unit": self.temperature_unit,
            "update_interval_minutes": self.update_interval_minutes,
            "show_detailed_forecast": self.show_detailed_forecast,
            "enable_alerts": self.enable_alerts,
            "minimize_to_tray": self.minimize_to_tray,
            "data_source": self.data_source,
            "visual_crossing_api_key": self.visual_crossing_api_key,
            "auto_update_enabled": self.auto_update_enabled,
            "update_channel": self.update_channel,
            "update_check_interval_hours": self.update_check_interval_hours,
            "debug_mode": self.debug_mode,
            "sound_enabled": self.sound_enabled,
            "sound_pack": self.sound_pack,
            "github_backend_url": self.github_backend_url,
            "alert_notifications_enabled": self.alert_notifications_enabled,
            "alert_notify_extreme": self.alert_notify_extreme,
            "alert_notify_severe": self.alert_notify_severe,
            "alert_notify_moderate": self.alert_notify_moderate,
            "alert_notify_minor": self.alert_notify_minor,
            "alert_notify_unknown": self.alert_notify_unknown,
            "alert_global_cooldown_minutes": self.alert_global_cooldown_minutes,
            "alert_per_alert_cooldown_minutes": self.alert_per_alert_cooldown_minutes,
            "alert_escalation_cooldown_minutes": self.alert_escalation_cooldown_minutes,
            "alert_max_notifications_per_hour": self.alert_max_notifications_per_hour,
            "alert_ignored_categories": self.alert_ignored_categories,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        """Create from dictionary."""
        return cls(
            temperature_unit=data.get("temperature_unit", "both"),
            update_interval_minutes=data.get("update_interval_minutes", 10),
            show_detailed_forecast=data.get("show_detailed_forecast", True),
            enable_alerts=data.get("enable_alerts", True),
            minimize_to_tray=data.get("minimize_to_tray", False),
            data_source=data.get("data_source", "auto"),
            visual_crossing_api_key=data.get("visual_crossing_api_key", ""),
            auto_update_enabled=data.get("auto_update_enabled", True),
            update_channel=data.get("update_channel", "stable"),
            update_check_interval_hours=data.get("update_check_interval_hours", 24),
            debug_mode=data.get("debug_mode", False),
            sound_enabled=data.get("sound_enabled", True),
            sound_pack=data.get("sound_pack", "default"),
            github_backend_url=data.get("github_backend_url", ""),
            alert_notifications_enabled=data.get("alert_notifications_enabled", True),
            alert_notify_extreme=data.get("alert_notify_extreme", True),
            alert_notify_severe=data.get("alert_notify_severe", True),
            alert_notify_moderate=data.get("alert_notify_moderate", True),
            alert_notify_minor=data.get("alert_notify_minor", False),
            alert_notify_unknown=data.get("alert_notify_unknown", False),
            alert_global_cooldown_minutes=data.get("alert_global_cooldown_minutes", 5),
            alert_per_alert_cooldown_minutes=data.get("alert_per_alert_cooldown_minutes", 60),
            alert_escalation_cooldown_minutes=data.get("alert_escalation_cooldown_minutes", 15),
            alert_max_notifications_per_hour=data.get("alert_max_notifications_per_hour", 10),
            alert_ignored_categories=data.get("alert_ignored_categories", []),
        )

    def to_alert_settings(self):
        """Convert to AlertSettings for the alert management system."""
        from .alert_manager import AlertSettings

        settings = AlertSettings()
        settings.notifications_enabled = self.alert_notifications_enabled
        settings.sound_enabled = self.sound_enabled
        settings.global_cooldown = self.alert_global_cooldown_minutes
        settings.per_alert_cooldown = self.alert_per_alert_cooldown_minutes
        settings.escalation_cooldown = self.alert_escalation_cooldown_minutes
        settings.max_notifications_per_hour = self.alert_max_notifications_per_hour
        settings.ignored_categories = set(self.alert_ignored_categories)

        # Map severity preferences to minimum priority
        if self.alert_notify_unknown:
            settings.min_severity_priority = 1
        elif self.alert_notify_minor:
            settings.min_severity_priority = 2
        elif self.alert_notify_moderate:
            settings.min_severity_priority = 3
        elif self.alert_notify_severe:
            settings.min_severity_priority = 4
        elif self.alert_notify_extreme:
            settings.min_severity_priority = 5
        else:
            settings.min_severity_priority = 6  # Effectively disable notifications

        return settings


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
