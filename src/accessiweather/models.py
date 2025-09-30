"""Simple data models for AccessiWeather.

This module provides simple dataclasses for weather information,
replacing the complex service layer architecture with straightforward data structures.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


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
    dewpoint_f: float | None = None
    dewpoint_c: float | None = None
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
        """Get the next N hours of forecast data.

        Args:
            count: Number of hours to return (default: 6)

        Returns:
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
            # Treat naive times as local clock values
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

        # If there are no future periods, fall back to the earliest ordered data (including
        # any periods without start times) to avoid returning an empty list.
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
class EnvironmentalConditions:
    """Supplemental environmental metrics such as air quality and pollen."""

    air_quality_index: float | None = None
    air_quality_category: str | None = None
    air_quality_pollutant: str | None = None
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
            ]
        )


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
    source: str | None = None

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
        if self.source:
            key_parts.append(self.source)
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
    environmental: EnvironmentalConditions | None = None
    trend_insights: list[TrendInsight] = field(default_factory=list)
    stale: bool = False
    stale_since: datetime | None = None
    stale_reason: str | None = None

    def has_any_data(self) -> bool:
        """Check if we have any weather data."""
        return any(
            [
                self.current and self.current.has_data(),
                self.forecast and self.forecast.has_data(),
                self.hourly_forecast and self.hourly_forecast.has_data(),
                self.alerts and self.alerts.has_alerts(),
                self.environmental and self.environmental.has_data(),
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
    startup_enabled: bool = False
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
    # Advanced alert audio options
    alert_sound_overrides: dict[str, str] = field(default_factory=dict)
    alert_tts_enabled: bool = False
    alert_tts_voice: str = ""
    alert_tts_rate: int = 0

    # International alert integration
    international_alerts_enabled: bool = True
    international_alerts_provider: str = "meteosalarm"

    # Trend insight configuration
    trend_insights_enabled: bool = True
    trend_hours: int = 24

    # Environmental metrics
    air_quality_enabled: bool = True
    pollen_enabled: bool = True
    air_quality_notify_threshold: int = 3

    # Offline cache
    offline_cache_enabled: bool = True
    offline_cache_max_age_minutes: int = 180

    @staticmethod
    def _as_bool(value, default: bool) -> bool:
        """Normalize common truthy/falsey representations to bool."""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        return default

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "temperature_unit": self.temperature_unit,
            "update_interval_minutes": self.update_interval_minutes,
            "show_detailed_forecast": self.show_detailed_forecast,
            "enable_alerts": self.enable_alerts,
            "minimize_to_tray": self.minimize_to_tray,
            "startup_enabled": self.startup_enabled,
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
            "alert_sound_overrides": self.alert_sound_overrides,
            "alert_tts_enabled": self.alert_tts_enabled,
            "alert_tts_voice": self.alert_tts_voice,
            "alert_tts_rate": self.alert_tts_rate,
            "international_alerts_enabled": self.international_alerts_enabled,
            "international_alerts_provider": self.international_alerts_provider,
            "trend_insights_enabled": self.trend_insights_enabled,
            "trend_hours": self.trend_hours,
            "air_quality_enabled": self.air_quality_enabled,
            "pollen_enabled": self.pollen_enabled,
            "air_quality_notify_threshold": self.air_quality_notify_threshold,
            "offline_cache_enabled": self.offline_cache_enabled,
            "offline_cache_max_age_minutes": self.offline_cache_max_age_minutes,
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
            startup_enabled=cls._as_bool(data.get("startup_enabled"), False),
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
            alert_sound_overrides=data.get("alert_sound_overrides", {}),
            alert_tts_enabled=data.get("alert_tts_enabled", False),
            alert_tts_voice=data.get("alert_tts_voice", ""),
            alert_tts_rate=data.get("alert_tts_rate", 0),
            international_alerts_enabled=data.get("international_alerts_enabled", True),
            international_alerts_provider=data.get("international_alerts_provider", "meteosalarm"),
            trend_insights_enabled=data.get("trend_insights_enabled", True),
            trend_hours=data.get("trend_hours", 24),
            air_quality_enabled=data.get("air_quality_enabled", True),
            pollen_enabled=data.get("pollen_enabled", True),
            air_quality_notify_threshold=data.get("air_quality_notify_threshold", 3),
            offline_cache_enabled=data.get("offline_cache_enabled", True),
            offline_cache_max_age_minutes=data.get("offline_cache_max_age_minutes", 180),
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

    def to_alert_audio_settings(self) -> "AlertAudioSettings":
        """Convert to audio-specific alert preferences."""
        return AlertAudioSettings(
            sound_overrides=dict(self.alert_sound_overrides or {}),
            tts_enabled=bool(self.alert_tts_enabled),
            tts_voice=self.alert_tts_voice or None,
            tts_rate=self.alert_tts_rate or None,
        )


@dataclass
class AlertAudioSettings:
    """Audio preferences for alert notifications."""

    sound_overrides: dict[str, str] = field(default_factory=dict)
    tts_enabled: bool = False
    tts_voice: str | None = None
    tts_rate: int | None = None


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
