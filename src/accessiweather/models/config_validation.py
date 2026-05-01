"""Validation helpers for application settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..sound_events import DEFAULT_MUTED_SOUND_EVENTS, normalize_known_muted_sound_events
from .config_constants import NON_CRITICAL_SETTINGS

if TYPE_CHECKING:
    from .config_settings import AppSettings


class AppSettingsValidationMixin:
    """Deferred validation helpers for non-critical application settings."""

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
        if isinstance(value, int | float):
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
        settings = cast("AppSettings", self)
        if not hasattr(settings, setting_name):
            return False

        value = getattr(settings, setting_name)

        # Validation rules for specific settings
        if setting_name == "ai_explanation_style":
            valid_styles = {"brief", "standard", "detailed"}
            if value not in valid_styles:
                setattr(settings, setting_name, "standard")

        elif setting_name == "update_channel":
            valid_channels = {"stable", "beta", "dev"}
            if value not in valid_channels:
                setattr(settings, setting_name, "stable")

        elif setting_name == "time_display_mode":
            valid_modes = {"local", "utc", "both"}
            if value not in valid_modes:
                setattr(settings, setting_name, "local")

        elif setting_name == "forecast_time_reference":
            valid_references = {"location", "user_local"}
            if value not in valid_references:
                setattr(settings, setting_name, "location")

        elif setting_name == "forecast_duration_days":
            if not isinstance(value, int) or value < 3 or value > 16:
                setattr(settings, setting_name, 7)

        elif setting_name == "sound_pack":
            # Ensure sound_pack is a non-empty string
            if not isinstance(value, str) or not value.strip():
                setattr(settings, setting_name, "default")

        elif setting_name == "muted_sound_events":
            if not isinstance(value, list):
                setattr(settings, setting_name, list(DEFAULT_MUTED_SOUND_EVENTS))
            else:
                normalized = normalize_known_muted_sound_events(value)
                setattr(settings, setting_name, normalized)

        elif setting_name == "taskbar_icon_text_format":
            # Ensure format string is valid
            if not isinstance(value, str) or not value.strip():
                setattr(settings, setting_name, "{temp} {condition}")

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
                setattr(settings, setting_name, defaults.get(setting_name, 5))

        elif setting_name == "alert_max_notifications_per_hour":
            # Ensure positive integer
            if not isinstance(value, int) or value < 1:
                setattr(settings, setting_name, 10)

        elif setting_name == "trend_hours":
            # Ensure reasonable range for trend hours (1-168 hours = 1 week)
            if not isinstance(value, int) or value < 1 or value > 168:
                setattr(settings, setting_name, 24)

        elif setting_name == "ai_cache_ttl":
            # Ensure non-negative integer for cache TTL
            if not isinstance(value, int) or value < 0:
                setattr(settings, setting_name, 300)

        elif setting_name == "update_check_interval_hours":
            # Ensure positive integer for update interval
            if not isinstance(value, int) or value < 1:
                setattr(settings, setting_name, 24)

        elif setting_name == "offline_cache_max_age_minutes":
            # Ensure positive integer for cache age
            if not isinstance(value, int) or value < 1:
                setattr(settings, setting_name, 180)

        elif setting_name == "precipitation_sensitivity":
            valid_levels = {"light", "moderate", "heavy"}
            if value not in valid_levels:
                setattr(settings, setting_name, "light")

        elif setting_name == "alert_radius_type":
            valid_types = {"county", "point", "zone", "state"}
            if value not in valid_types:
                setattr(settings, setting_name, "county")

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
                setattr(settings, setting_name, "best_match")

        elif setting_name == "station_selection_strategy":
            valid_strategies = {
                "nearest",
                "major_airport_preferred",
                "freshest_observation",
                "hybrid_default",
            }
            if value not in valid_strategies:
                setattr(settings, setting_name, "hybrid_default")

        elif setting_name == "auto_mode_api_budget":
            valid_budgets = {"economy", "balanced", "max_coverage"}
            if value not in valid_budgets:
                setattr(settings, setting_name, "max_coverage")

        elif setting_name == "alert_display_style":
            valid_styles = {"separate", "combined"}
            if value not in valid_styles:
                setattr(settings, setting_name, "separate")

        elif setting_name == "date_format":
            valid_formats = {"iso", "us_short", "us_long", "eu"}
            if value not in valid_formats:
                setattr(settings, setting_name, "iso")

        elif setting_name in {
            "source_priority_us",
            "source_priority_international",
            "auto_sources_us",
            "auto_sources_international",
        }:
            # Ensure valid list of source names
            valid_sources = {"nws", "openmeteo", "visualcrossing", "pirateweather"}
            us_default = ["nws", "openmeteo", "visualcrossing", "pirateweather"]
            intl_default = ["openmeteo", "pirateweather", "visualcrossing"]
            is_us_setting = setting_name in {"source_priority_us", "auto_sources_us"}
            if not isinstance(value, list):
                setattr(settings, setting_name, us_default if is_us_setting else intl_default)
            else:
                # Filter to only valid sources
                filtered = [s for s in value if s in valid_sources]
                if not filtered:
                    setattr(settings, setting_name, us_default if is_us_setting else intl_default)
                elif filtered != value:
                    setattr(settings, setting_name, filtered)

        elif setting_name == "alert_ignored_categories":
            # Ensure it's a list
            if not isinstance(value, list):
                setattr(settings, setting_name, [])

        # Boolean settings are validated by _as_bool during from_dict,
        # but we can still ensure they're actually booleans
        elif setting_name in NON_CRITICAL_SETTINGS:
            # Get the default value for this setting from a fresh instance
            default_settings = settings.__class__()
            default_value = getattr(default_settings, setting_name, None)
            if isinstance(default_value, bool) and not isinstance(value, bool):
                setattr(settings, setting_name, settings._as_bool(value, default_value))

        return True
