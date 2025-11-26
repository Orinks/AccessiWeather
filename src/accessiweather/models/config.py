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
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_app_installation_id: str = ""
    alert_notifications_enabled: bool = True
    alert_notify_extreme: bool = True
    alert_notify_severe: bool = True
    alert_notify_moderate: bool = True
    alert_notify_minor: bool = False
    alert_notify_unknown: bool = False
    alert_global_cooldown_minutes: int = 5
    alert_per_alert_cooldown_minutes: int = 60
    alert_escalation_cooldown_minutes: int = 15
    alert_freshness_window_minutes: int = 15
    alert_max_notifications_per_hour: int = 10
    alert_ignored_categories: list[str] = field(default_factory=list)
    international_alerts_enabled: bool = True
    international_alerts_provider: str = "meteosalarm"
    trend_insights_enabled: bool = True
    trend_hours: int = 24
    show_dewpoint: bool = True
    show_pressure_trend: bool = True
    show_visibility: bool = True
    show_uv_index: bool = True
    air_quality_enabled: bool = True
    pollen_enabled: bool = True
    air_quality_notify_threshold: int = 3
    offline_cache_enabled: bool = True
    offline_cache_max_age_minutes: int = 180
    weather_history_enabled: bool = True
    time_display_mode: str = "local"
    time_format_12hour: bool = True
    show_timezone_suffix: bool = False
    # HTML rendering options - when True, use WebView with HTML; when False, use MultilineTextInput
    html_render_current_conditions: bool = True
    html_render_forecast: bool = True

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
            # visual_crossing_api_key and github_app_* are stored in secure keyring, not JSON
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
            "alert_freshness_window_minutes": self.alert_freshness_window_minutes,
            "alert_max_notifications_per_hour": self.alert_max_notifications_per_hour,
            "alert_ignored_categories": self.alert_ignored_categories,
            "international_alerts_enabled": self.international_alerts_enabled,
            "international_alerts_provider": self.international_alerts_provider,
            "trend_insights_enabled": self.trend_insights_enabled,
            "trend_hours": self.trend_hours,
            "show_dewpoint": self.show_dewpoint,
            "show_pressure_trend": self.show_pressure_trend,
            "show_visibility": self.show_visibility,
            "show_uv_index": self.show_uv_index,
            "air_quality_enabled": self.air_quality_enabled,
            "pollen_enabled": self.pollen_enabled,
            "air_quality_notify_threshold": self.air_quality_notify_threshold,
            "offline_cache_enabled": self.offline_cache_enabled,
            "offline_cache_max_age_minutes": self.offline_cache_max_age_minutes,
            "weather_history_enabled": self.weather_history_enabled,
            "time_display_mode": self.time_display_mode,
            "time_format_12hour": self.time_format_12hour,
            "show_timezone_suffix": self.show_timezone_suffix,
            "html_render_current_conditions": self.html_render_current_conditions,
            "html_render_forecast": self.html_render_forecast,
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
            alert_freshness_window_minutes=data.get("alert_freshness_window_minutes", 15),
            alert_max_notifications_per_hour=data.get("alert_max_notifications_per_hour", 10),
            alert_ignored_categories=data.get("alert_ignored_categories", []),
            international_alerts_enabled=cls._as_bool(
                data.get("international_alerts_enabled"), True
            ),
            international_alerts_provider=data.get("international_alerts_provider", "meteosalarm"),
            trend_insights_enabled=cls._as_bool(data.get("trend_insights_enabled"), True),
            trend_hours=data.get("trend_hours", 24),
            show_dewpoint=cls._as_bool(data.get("show_dewpoint"), True),
            show_pressure_trend=cls._as_bool(data.get("show_pressure_trend"), True),
            show_visibility=cls._as_bool(data.get("show_visibility"), True),
            show_uv_index=cls._as_bool(data.get("show_uv_index"), True),
            air_quality_enabled=cls._as_bool(data.get("air_quality_enabled"), True),
            pollen_enabled=cls._as_bool(data.get("pollen_enabled"), True),
            air_quality_notify_threshold=data.get("air_quality_notify_threshold", 3),
            offline_cache_enabled=cls._as_bool(data.get("offline_cache_enabled"), True),
            offline_cache_max_age_minutes=data.get("offline_cache_max_age_minutes", 180),
            weather_history_enabled=cls._as_bool(data.get("weather_history_enabled"), True),
            time_display_mode=data.get("time_display_mode", "local"),
            time_format_12hour=cls._as_bool(data.get("time_format_12hour"), True),
            show_timezone_suffix=cls._as_bool(data.get("show_timezone_suffix"), False),
            html_render_current_conditions=cls._as_bool(
                data.get("html_render_current_conditions"), True
            ),
            html_render_forecast=cls._as_bool(data.get("html_render_forecast"), True),
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
        settings.freshness_window_minutes = self.alert_freshness_window_minutes
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
                    **({"country_code": loc.country_code} if loc.country_code else {}),
                }
                for loc in self.locations
            ],
            "current_location": {
                "name": self.current_location.name,
                "latitude": self.current_location.latitude,
                "longitude": self.current_location.longitude,
                **(
                    {"country_code": self.current_location.country_code}
                    if self.current_location.country_code
                    else {}
                ),
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
                    country_code=loc_data.get("country_code"),
                )
            )

        current_location = None
        if data.get("current_location"):
            loc_data = data["current_location"]
            current_location = Location(
                name=loc_data["name"],
                latitude=loc_data["latitude"],
                longitude=loc_data["longitude"],
                country_code=loc_data.get("country_code"),
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
