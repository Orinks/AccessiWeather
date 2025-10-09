"""Configuration models for AccessiWeather."""

from __future__ import annotations

from dataclasses import dataclass, field

from .weather import Location


@dataclass
class AppSettings:
    """Application settings."""

    temperature_unit: str = "both"
    update_interval_minutes: int = 10
    show_detailed_forecast: bool = True
    enable_alerts: bool = True
    minimize_to_tray: bool = False
    startup_enabled: bool = False
    data_source: str = "auto"
    visual_crossing_api_key: str = ""
    auto_update_enabled: bool = True
    update_channel: str = "stable"
    update_check_interval_hours: int = 24
    debug_mode: bool = False
    sound_enabled: bool = True
    sound_pack: str = "default"
    github_backend_url: str = ""
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
    alert_sound_overrides: dict[str, str] = field(default_factory=dict)
    alert_tts_enabled: bool = False
    alert_tts_voice: str = ""
    alert_tts_rate: int = 0
    international_alerts_enabled: bool = True
    international_alerts_provider: str = "meteosalarm"
    trend_insights_enabled: bool = True
    trend_hours: int = 24
    air_quality_enabled: bool = True
    pollen_enabled: bool = True
    air_quality_notify_threshold: int = 3
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
    def from_dict(cls, data: dict) -> AppSettings:
        """Create from dictionary."""
        return cls(
            temperature_unit=data.get("temperature_unit", "both"),
            update_interval_minutes=data.get("update_interval_minutes", 10),
            show_detailed_forecast=cls._as_bool(data.get("show_detailed_forecast"), True),
            enable_alerts=cls._as_bool(data.get("enable_alerts"), True),
            minimize_to_tray=cls._as_bool(data.get("minimize_to_tray"), False),
            startup_enabled=cls._as_bool(data.get("startup_enabled"), False),
            data_source=data.get("data_source", "auto"),
            visual_crossing_api_key=data.get("visual_crossing_api_key", ""),
            auto_update_enabled=cls._as_bool(data.get("auto_update_enabled"), True),
            update_channel=data.get("update_channel", "stable"),
            update_check_interval_hours=data.get("update_check_interval_hours", 24),
            debug_mode=cls._as_bool(data.get("debug_mode"), False),
            sound_enabled=cls._as_bool(data.get("sound_enabled"), True),
            sound_pack=data.get("sound_pack", "default"),
            github_backend_url=data.get("github_backend_url", ""),
            alert_notifications_enabled=cls._as_bool(data.get("alert_notifications_enabled"), True),
            alert_notify_extreme=cls._as_bool(data.get("alert_notify_extreme"), True),
            alert_notify_severe=cls._as_bool(data.get("alert_notify_severe"), True),
            alert_notify_moderate=cls._as_bool(data.get("alert_notify_moderate"), True),
            alert_notify_minor=cls._as_bool(data.get("alert_notify_minor"), False),
            alert_notify_unknown=cls._as_bool(data.get("alert_notify_unknown"), False),
            alert_global_cooldown_minutes=data.get("alert_global_cooldown_minutes", 5),
            alert_per_alert_cooldown_minutes=data.get("alert_per_alert_cooldown_minutes", 60),
            alert_escalation_cooldown_minutes=data.get("alert_escalation_cooldown_minutes", 15),
            alert_max_notifications_per_hour=data.get("alert_max_notifications_per_hour", 10),
            alert_ignored_categories=data.get("alert_ignored_categories", []),
            alert_sound_overrides=data.get("alert_sound_overrides", {}),
            alert_tts_enabled=cls._as_bool(data.get("alert_tts_enabled"), False),
            alert_tts_voice=data.get("alert_tts_voice", ""),
            alert_tts_rate=data.get("alert_tts_rate", 0),
            international_alerts_enabled=cls._as_bool(
                data.get("international_alerts_enabled"), True
            ),
            international_alerts_provider=data.get("international_alerts_provider", "meteosalarm"),
            trend_insights_enabled=cls._as_bool(data.get("trend_insights_enabled"), True),
            trend_hours=data.get("trend_hours", 24),
            air_quality_enabled=cls._as_bool(data.get("air_quality_enabled"), True),
            pollen_enabled=cls._as_bool(data.get("pollen_enabled"), True),
            air_quality_notify_threshold=data.get("air_quality_notify_threshold", 3),
            offline_cache_enabled=cls._as_bool(data.get("offline_cache_enabled"), True),
            offline_cache_max_age_minutes=data.get("offline_cache_max_age_minutes", 180),
        )

    def to_alert_settings(self):
        """Convert to AlertSettings for the alert management system."""
        from accessiweather.alert_manager import AlertSettings

        settings = AlertSettings()
        settings.notifications_enabled = self.alert_notifications_enabled
        settings.sound_enabled = self.sound_enabled
        settings.global_cooldown = self.alert_global_cooldown_minutes
        settings.per_alert_cooldown = self.alert_per_alert_cooldown_minutes
        settings.escalation_cooldown = self.alert_escalation_cooldown_minutes
        settings.max_notifications_per_hour = self.alert_max_notifications_per_hour
        settings.ignored_categories = set(self.alert_ignored_categories)

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
            settings.min_severity_priority = 6

        return settings

    def to_alert_audio_settings(self) -> AlertAudioSettings:
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
    def from_dict(cls, data: dict) -> AppConfig:
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
    def default(cls) -> AppConfig:
        """Create default configuration."""
        return cls(
            settings=AppSettings(),
            locations=[],
            current_location=None,
        )
