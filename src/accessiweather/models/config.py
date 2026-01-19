"""Configuration models for AccessiWeather."""

from __future__ import annotations

from dataclasses import dataclass, field

from .weather import Location

# Critical settings needed for app initialization (load synchronously)
# These are essential for the app to start and display basic functionality
CRITICAL_SETTINGS: set[str] = {
    "temperature_unit",  # Display formatting
    "data_source",  # Weather client selection
    "update_interval_minutes",  # Background task timing
}

# Non-critical settings (defer validation until first access)
# These can be loaded lazily without blocking startup
NON_CRITICAL_SETTINGS: set[str] = {
    # Alert notification settings
    "alert_notifications_enabled",
    "alert_notify_extreme",
    "alert_notify_severe",
    "alert_notify_moderate",
    "alert_notify_minor",
    "alert_notify_unknown",
    "alert_global_cooldown_minutes",
    "alert_per_alert_cooldown_minutes",
    "alert_escalation_cooldown_minutes",
    "alert_freshness_window_minutes",
    "alert_max_notifications_per_hour",
    "alert_ignored_categories",
    # Sound settings
    "sound_enabled",
    "sound_pack",
    # GitHub settings
    "github_backend_url",
    "github_app_id",
    "github_app_private_key",
    "github_app_installation_id",
    # AI explanation settings
    "openrouter_api_key",
    "ai_model_preference",
    "ai_explanation_style",
    "ai_cache_ttl",
    "custom_system_prompt",
    "custom_instructions",
    # API key settings (loaded lazily via keyring)
    "visual_crossing_api_key",
    # Display preferences
    "show_detailed_forecast",
    "enable_alerts",
    "minimize_to_tray",
    "startup_enabled",
    "auto_update_enabled",
    "update_channel",
    "update_check_interval_hours",
    "debug_mode",
    "trend_insights_enabled",
    "trend_hours",
    "show_dewpoint",
    "show_pressure_trend",
    "show_visibility",
    "show_uv_index",
    "show_seasonal_data",
    "air_quality_enabled",
    "pollen_enabled",
    "offline_cache_enabled",
    "offline_cache_max_age_minutes",
    "weather_history_enabled",
    "time_display_mode",
    "time_format_12hour",
    "show_timezone_suffix",
    "taskbar_icon_text_enabled",
    "taskbar_icon_dynamic_enabled",
    "taskbar_icon_text_format",
    "source_priority_us",
    "source_priority_international",
    "openmeteo_weather_model",
}


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
    trend_insights_enabled: bool = True
    trend_hours: int = 24
    show_dewpoint: bool = True
    show_pressure_trend: bool = True
    show_visibility: bool = True
    show_uv_index: bool = True
    show_seasonal_data: bool = True
    air_quality_enabled: bool = True
    pollen_enabled: bool = True
    offline_cache_enabled: bool = True
    offline_cache_max_age_minutes: int = 180
    weather_history_enabled: bool = True
    time_display_mode: str = "local"
    time_format_12hour: bool = True
    show_timezone_suffix: bool = False
    # Taskbar icon text options
    taskbar_icon_text_enabled: bool = False
    taskbar_icon_dynamic_enabled: bool = True
    taskbar_icon_text_format: str = "{temp} {condition}"
    # Source priority settings for smart auto mode
    source_priority_us: list[str] = field(
        default_factory=lambda: ["nws", "openmeteo", "visualcrossing"]
    )
    source_priority_international: list[str] = field(
        default_factory=lambda: ["openmeteo", "visualcrossing"]
    )
    # Open-Meteo weather model selection
    openmeteo_weather_model: str = "best_match"
    # AI Explanation Settings
    openrouter_api_key: str = ""
    ai_model_preference: str = (
        "meta-llama/llama-3.3-70b-instruct:free"  # free model or "auto" for paid
    )
    ai_explanation_style: str = "standard"  # "brief", "standard", "detailed"
    ai_cache_ttl: int = 300  # 5 minutes in seconds
    # AI Prompt Customization Settings
    custom_system_prompt: str | None = None  # None means use default
    custom_instructions: str | None = None  # Appended to user prompt
    # Priority ordering settings
    verbosity_level: str = "standard"  # "minimal", "standard", "detailed"
    category_order: list[str] = field(
        default_factory=lambda: [
            "temperature",
            "precipitation",
            "wind",
            "humidity_pressure",
            "visibility_clouds",
            "uv_index",
        ]
    )
    severe_weather_override: bool = True

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

    def validate_on_access(self, setting_name: str) -> bool:
        """
        Validate a non-critical setting on first access.

        This method performs deferred validation for settings that are not
        critical for app startup. It validates the current value and corrects
        it to a default if invalid.

        Args:
            setting_name: The name of the setting to validate.

        Returns:
            True if the setting is valid (or was corrected), False if
            the setting name is unknown.

        """
        if not hasattr(self, setting_name):
            return False

        value = getattr(self, setting_name)

        # Validation rules for specific settings
        if setting_name == "ai_explanation_style":
            valid_styles = {"brief", "standard", "detailed"}
            if value not in valid_styles:
                setattr(self, setting_name, "standard")

        elif setting_name == "update_channel":
            valid_channels = {"stable", "beta", "dev"}
            if value not in valid_channels:
                setattr(self, setting_name, "stable")

        elif setting_name == "time_display_mode":
            valid_modes = {"local", "utc", "both"}
            if value not in valid_modes:
                setattr(self, setting_name, "local")

        elif setting_name == "sound_pack":
            # Ensure sound_pack is a non-empty string
            if not isinstance(value, str) or not value.strip():
                setattr(self, setting_name, "default")

        elif setting_name == "taskbar_icon_text_format":
            # Ensure format string is valid
            if not isinstance(value, str) or not value.strip():
                setattr(self, setting_name, "{temp} {condition}")

        elif setting_name in {
            "alert_global_cooldown_minutes",
            "alert_per_alert_cooldown_minutes",
            "alert_escalation_cooldown_minutes",
            "alert_freshness_window_minutes",
        }:
            # Ensure positive integer for cooldown settings
            if not isinstance(value, int) or value < 0:
                defaults = {
                    "alert_global_cooldown_minutes": 5,
                    "alert_per_alert_cooldown_minutes": 60,
                    "alert_escalation_cooldown_minutes": 15,
                    "alert_freshness_window_minutes": 15,
                }
                setattr(self, setting_name, defaults.get(setting_name, 5))

        elif setting_name == "alert_max_notifications_per_hour":
            # Ensure positive integer
            if not isinstance(value, int) or value < 1:
                setattr(self, setting_name, 10)

        elif setting_name == "trend_hours":
            # Ensure reasonable range for trend hours (1-168 hours = 1 week)
            if not isinstance(value, int) or value < 1 or value > 168:
                setattr(self, setting_name, 24)

        elif setting_name == "ai_cache_ttl":
            # Ensure non-negative integer for cache TTL
            if not isinstance(value, int) or value < 0:
                setattr(self, setting_name, 300)

        elif setting_name == "update_check_interval_hours":
            # Ensure positive integer for update interval
            if not isinstance(value, int) or value < 1:
                setattr(self, setting_name, 24)

        elif setting_name == "offline_cache_max_age_minutes":
            # Ensure positive integer for cache age
            if not isinstance(value, int) or value < 1:
                setattr(self, setting_name, 180)

        elif setting_name == "openmeteo_weather_model":
            valid_models = {
                "best_match",
                "icon_seamless",
                "icon_global",
                "icon_eu",
                "icon_d2",
                "gfs_seamless",
                "gfs_global",
                "ecmwf_ifs04",
                "meteofrance_seamless",
                "gem_seamless",
                "jma_seamless",
            }
            if value not in valid_models:
                setattr(self, setting_name, "best_match")

        elif setting_name in {"source_priority_us", "source_priority_international"}:
            # Ensure valid list of source names
            valid_sources = {"nws", "openmeteo", "visualcrossing"}
            if not isinstance(value, list):
                if setting_name == "source_priority_us":
                    setattr(self, setting_name, ["nws", "openmeteo", "visualcrossing"])
                else:
                    setattr(self, setting_name, ["openmeteo", "visualcrossing"])
            else:
                # Filter to only valid sources
                filtered = [s for s in value if s in valid_sources]
                if not filtered:
                    if setting_name == "source_priority_us":
                        setattr(self, setting_name, ["nws", "openmeteo", "visualcrossing"])
                    else:
                        setattr(self, setting_name, ["openmeteo", "visualcrossing"])
                elif filtered != value:
                    setattr(self, setting_name, filtered)

        elif setting_name == "alert_ignored_categories":
            # Ensure it's a list
            if not isinstance(value, list):
                setattr(self, setting_name, [])

        # Boolean settings are validated by _as_bool during from_dict,
        # but we can still ensure they're actually booleans
        elif setting_name in NON_CRITICAL_SETTINGS:
            # Get the default value for this setting from a fresh instance
            default_settings = AppSettings()
            default_value = getattr(default_settings, setting_name, None)
            if isinstance(default_value, bool) and not isinstance(value, bool):
                setattr(self, setting_name, self._as_bool(value, default_value))

        return True

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
            "trend_insights_enabled": self.trend_insights_enabled,
            "trend_hours": self.trend_hours,
            "show_dewpoint": self.show_dewpoint,
            "show_pressure_trend": self.show_pressure_trend,
            "show_visibility": self.show_visibility,
            "show_uv_index": self.show_uv_index,
            "show_seasonal_data": self.show_seasonal_data,
            "air_quality_enabled": self.air_quality_enabled,
            "pollen_enabled": self.pollen_enabled,
            "offline_cache_enabled": self.offline_cache_enabled,
            "offline_cache_max_age_minutes": self.offline_cache_max_age_minutes,
            "weather_history_enabled": self.weather_history_enabled,
            "time_display_mode": self.time_display_mode,
            "time_format_12hour": self.time_format_12hour,
            "show_timezone_suffix": self.show_timezone_suffix,
            "taskbar_icon_text_enabled": self.taskbar_icon_text_enabled,
            "taskbar_icon_dynamic_enabled": self.taskbar_icon_dynamic_enabled,
            "taskbar_icon_text_format": self.taskbar_icon_text_format,
            "source_priority_us": self.source_priority_us,
            "source_priority_international": self.source_priority_international,
            "openmeteo_weather_model": self.openmeteo_weather_model,
            # AI settings (API key stored in secure storage, not here)
            "ai_model_preference": self.ai_model_preference,
            "ai_explanation_style": self.ai_explanation_style,
            "ai_cache_ttl": self.ai_cache_ttl,
            # AI Prompt Customization
            "custom_system_prompt": self.custom_system_prompt,
            "custom_instructions": self.custom_instructions,
            # Priority ordering settings
            "verbosity_level": self.verbosity_level,
            "category_order": self.category_order,
            "severe_weather_override": self.severe_weather_override,
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
            trend_insights_enabled=cls._as_bool(data.get("trend_insights_enabled"), True),
            trend_hours=data.get("trend_hours", 24),
            show_dewpoint=cls._as_bool(data.get("show_dewpoint"), True),
            show_pressure_trend=cls._as_bool(data.get("show_pressure_trend"), True),
            show_visibility=cls._as_bool(data.get("show_visibility"), True),
            show_uv_index=cls._as_bool(data.get("show_uv_index"), True),
            show_seasonal_data=cls._as_bool(data.get("show_seasonal_data"), True),
            air_quality_enabled=cls._as_bool(data.get("air_quality_enabled"), True),
            pollen_enabled=cls._as_bool(data.get("pollen_enabled"), True),
            offline_cache_enabled=cls._as_bool(data.get("offline_cache_enabled"), True),
            offline_cache_max_age_minutes=data.get("offline_cache_max_age_minutes", 180),
            weather_history_enabled=cls._as_bool(data.get("weather_history_enabled"), True),
            time_display_mode=data.get("time_display_mode", "local"),
            time_format_12hour=cls._as_bool(data.get("time_format_12hour"), True),
            show_timezone_suffix=cls._as_bool(data.get("show_timezone_suffix"), False),
            taskbar_icon_text_enabled=cls._as_bool(data.get("taskbar_icon_text_enabled"), False),
            taskbar_icon_dynamic_enabled=cls._as_bool(
                data.get("taskbar_icon_dynamic_enabled"), True
            ),
            taskbar_icon_text_format=data.get("taskbar_icon_text_format", "{temp} {condition}"),
            source_priority_us=data.get(
                "source_priority_us", ["nws", "openmeteo", "visualcrossing"]
            ),
            source_priority_international=data.get(
                "source_priority_international", ["openmeteo", "visualcrossing"]
            ),
            openmeteo_weather_model=data.get("openmeteo_weather_model", "best_match"),
            # AI settings
            openrouter_api_key=data.get("openrouter_api_key", ""),
            ai_model_preference=data.get(
                "ai_model_preference", "meta-llama/llama-3.3-70b-instruct:free"
            ),
            ai_explanation_style=data.get("ai_explanation_style", "standard"),
            ai_cache_ttl=data.get("ai_cache_ttl", 300),
            # AI Prompt Customization
            custom_system_prompt=data.get("custom_system_prompt"),
            custom_instructions=data.get("custom_instructions"),
            # Priority ordering settings
            verbosity_level=data.get("verbosity_level", "standard"),
            category_order=data.get(
                "category_order",
                [
                    "temperature",
                    "precipitation",
                    "wind",
                    "humidity_pressure",
                    "visibility_clouds",
                    "uv_index",
                ],
            ),
            severe_weather_override=cls._as_bool(data.get("severe_weather_override"), True),
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
