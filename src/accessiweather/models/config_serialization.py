"""Serialization helpers for application settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..sound_events import DEFAULT_MUTED_SOUND_EVENTS

if TYPE_CHECKING:
    from .config_settings import AppSettings


class AppSettingsSerializationMixin:
    """JSON conversion helpers for application settings."""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        settings = cast("AppSettings", self)
        return {
            "temperature_unit": settings.temperature_unit,
            "update_interval_minutes": settings.update_interval_minutes,
            "enable_alerts": settings.enable_alerts,
            "minimize_to_tray": settings.minimize_to_tray,
            "minimize_on_startup": settings.minimize_on_startup,
            "startup_enabled": settings.startup_enabled,
            "data_source": settings.data_source,
            # weather provider API keys and github_app_* are stored in secure keyring, not JSON
            "auto_update_enabled": settings.auto_update_enabled,
            "update_channel": settings.update_channel,
            "update_check_interval_hours": settings.update_check_interval_hours,
            "sound_enabled": settings.sound_enabled,
            "sound_pack": settings.sound_pack,
            "muted_sound_events": settings.muted_sound_events,
            "show_nationwide_location": settings.show_nationwide_location,
            "notify_discussion_update": settings.notify_discussion_update,
            "notify_hwo_update": settings.notify_hwo_update,
            "notify_sps_issued": settings.notify_sps_issued,
            "notify_severe_risk_change": settings.notify_severe_risk_change,
            "notify_minutely_precipitation_start": settings.notify_minutely_precipitation_start,
            "notify_minutely_precipitation_stop": settings.notify_minutely_precipitation_stop,
            "minutely_precipitation_fast_polling": settings.minutely_precipitation_fast_polling,
            "precipitation_sensitivity": settings.precipitation_sensitivity,
            "notify_precipitation_likelihood": settings.notify_precipitation_likelihood,
            "precipitation_likelihood_threshold": settings.precipitation_likelihood_threshold,
            "github_backend_url": settings.github_backend_url,
            "alert_radius_type": settings.alert_radius_type,
            "alert_notifications_enabled": settings.alert_notifications_enabled,
            "alert_notify_extreme": settings.alert_notify_extreme,
            "alert_notify_severe": settings.alert_notify_severe,
            "alert_notify_moderate": settings.alert_notify_moderate,
            "alert_notify_minor": settings.alert_notify_minor,
            "alert_notify_unknown": settings.alert_notify_unknown,
            "immediate_alert_details_popups": settings.immediate_alert_details_popups,
            "alert_global_cooldown_minutes": settings.alert_global_cooldown_minutes,
            "alert_per_alert_cooldown_minutes": settings.alert_per_alert_cooldown_minutes,
            "alert_escalation_cooldown_minutes": settings.alert_escalation_cooldown_minutes,
            "alert_freshness_window_minutes": settings.alert_freshness_window_minutes,
            "alert_max_notifications_per_hour": settings.alert_max_notifications_per_hour,
            "alert_ignored_categories": settings.alert_ignored_categories,
            "trend_insights_enabled": settings.trend_insights_enabled,
            "trend_hours": settings.trend_hours,
            "show_dewpoint": settings.show_dewpoint,
            "show_pressure_trend": settings.show_pressure_trend,
            "show_visibility": settings.show_visibility,
            "show_uv_index": settings.show_uv_index,
            "show_seasonal_data": settings.show_seasonal_data,
            "air_quality_enabled": settings.air_quality_enabled,
            "pollen_enabled": settings.pollen_enabled,
            "offline_cache_enabled": settings.offline_cache_enabled,
            "offline_cache_max_age_minutes": settings.offline_cache_max_age_minutes,
            "weather_history_enabled": settings.weather_history_enabled,
            "forecast_duration_days": settings.forecast_duration_days,
            "hourly_forecast_hours": settings.hourly_forecast_hours,
            "forecast_time_reference": settings.forecast_time_reference,
            "time_display_mode": settings.time_display_mode,
            "time_format_12hour": settings.time_format_12hour,
            "show_timezone_suffix": settings.show_timezone_suffix,
            "alert_display_style": settings.alert_display_style,
            "location_buttons_on_top": settings.location_buttons_on_top,
            "date_format": settings.date_format,
            "taskbar_icon_text_enabled": settings.taskbar_icon_text_enabled,
            "taskbar_icon_dynamic_enabled": settings.taskbar_icon_dynamic_enabled,
            "taskbar_icon_text_format": settings.taskbar_icon_text_format,
            "source_priority_us": settings.source_priority_us,
            "source_priority_international": settings.source_priority_international,
            "auto_mode_api_budget": settings.auto_mode_api_budget,
            "auto_sources_us": settings.auto_sources_us,
            "auto_sources_international": settings.auto_sources_international,
            "openmeteo_weather_model": settings.openmeteo_weather_model,
            "station_selection_strategy": settings.station_selection_strategy,
            # AI settings and AVWX key stored in secure storage, not here
            "ai_model_preference": settings.ai_model_preference,
            "ai_explanation_style": settings.ai_explanation_style,
            "ai_cache_ttl": settings.ai_cache_ttl,
            # AI Prompt Customization
            "custom_system_prompt": settings.custom_system_prompt,
            "custom_instructions": settings.custom_instructions,
            # Priority ordering settings
            "verbosity_level": settings.verbosity_level,
            "category_order": settings.category_order,
            "severe_weather_override": settings.severe_weather_override,
            "onboarding_wizard_shown": settings.onboarding_wizard_shown,
            "portable_missing_api_keys_hint_shown": settings.portable_missing_api_keys_hint_shown,
            "round_values": settings.round_values,
            "show_impact_summaries": settings.show_impact_summaries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AppSettings:
        """Create from dictionary."""
        settings_cls = cast("type[AppSettings]", cls)
        settings = settings_cls(
            temperature_unit=data.get("temperature_unit", "both"),
            update_interval_minutes=data.get("update_interval_minutes", 10),
            enable_alerts=settings_cls._as_bool(data.get("enable_alerts"), True),
            minimize_to_tray=settings_cls._as_bool(data.get("minimize_to_tray"), False),
            minimize_on_startup=settings_cls._as_bool(data.get("minimize_on_startup"), False),
            startup_enabled=settings_cls._as_bool(data.get("startup_enabled"), False),
            data_source=data.get("data_source", "auto"),
            pirate_weather_api_key=data.get("pirate_weather_api_key", ""),
            auto_update_enabled=settings_cls._as_bool(data.get("auto_update_enabled"), True),
            update_channel=data.get("update_channel", "stable"),
            update_check_interval_hours=data.get("update_check_interval_hours", 24),
            sound_enabled=settings_cls._as_bool(data.get("sound_enabled"), True),
            sound_pack=data.get("sound_pack", "default"),
            muted_sound_events=data.get("muted_sound_events", list(DEFAULT_MUTED_SOUND_EVENTS)),
            show_nationwide_location=settings_cls._as_bool(
                data.get("show_nationwide_location"), True
            ),
            notify_discussion_update=settings_cls._as_bool(
                data.get("notify_discussion_update"), True
            ),
            notify_hwo_update=settings_cls._as_bool(data.get("notify_hwo_update"), True),
            notify_sps_issued=settings_cls._as_bool(data.get("notify_sps_issued"), True),
            notify_severe_risk_change=settings_cls._as_bool(
                data.get("notify_severe_risk_change"), False
            ),
            notify_minutely_precipitation_start=settings_cls._as_bool(
                data.get("notify_minutely_precipitation_start"), True
            ),
            notify_minutely_precipitation_stop=settings_cls._as_bool(
                data.get("notify_minutely_precipitation_stop"), True
            ),
            minutely_precipitation_fast_polling=settings_cls._as_bool(
                data.get("minutely_precipitation_fast_polling"), False
            ),
            precipitation_sensitivity=data.get("precipitation_sensitivity", "light"),
            notify_precipitation_likelihood=settings_cls._as_bool(
                data.get("notify_precipitation_likelihood"), False
            ),
            precipitation_likelihood_threshold=float(
                data.get("precipitation_likelihood_threshold", 0.5)
            ),
            github_backend_url=data.get("github_backend_url", ""),
            alert_radius_type=data.get("alert_radius_type", "county"),
            alert_notifications_enabled=settings_cls._as_bool(
                data.get("alert_notifications_enabled"), True
            ),
            alert_notify_extreme=settings_cls._as_bool(data.get("alert_notify_extreme"), True),
            alert_notify_severe=settings_cls._as_bool(data.get("alert_notify_severe"), True),
            alert_notify_moderate=settings_cls._as_bool(data.get("alert_notify_moderate"), True),
            alert_notify_minor=settings_cls._as_bool(data.get("alert_notify_minor"), False),
            alert_notify_unknown=settings_cls._as_bool(data.get("alert_notify_unknown"), False),
            immediate_alert_details_popups=settings_cls._as_bool(
                data.get("immediate_alert_details_popups"), False
            ),
            alert_global_cooldown_minutes=data.get("alert_global_cooldown_minutes", 5),
            alert_per_alert_cooldown_minutes=data.get("alert_per_alert_cooldown_minutes", 60),
            alert_escalation_cooldown_minutes=data.get("alert_escalation_cooldown_minutes", 15),
            alert_freshness_window_minutes=data.get("alert_freshness_window_minutes", 15),
            alert_max_notifications_per_hour=data.get("alert_max_notifications_per_hour", 10),
            alert_ignored_categories=data.get("alert_ignored_categories", []),
            trend_insights_enabled=settings_cls._as_bool(data.get("trend_insights_enabled"), True),
            trend_hours=data.get("trend_hours", 24),
            show_dewpoint=settings_cls._as_bool(data.get("show_dewpoint"), True),
            show_pressure_trend=settings_cls._as_bool(data.get("show_pressure_trend"), True),
            show_visibility=settings_cls._as_bool(data.get("show_visibility"), True),
            show_uv_index=settings_cls._as_bool(data.get("show_uv_index"), True),
            show_seasonal_data=settings_cls._as_bool(data.get("show_seasonal_data"), True),
            air_quality_enabled=settings_cls._as_bool(data.get("air_quality_enabled"), True),
            pollen_enabled=settings_cls._as_bool(data.get("pollen_enabled"), True),
            offline_cache_enabled=settings_cls._as_bool(data.get("offline_cache_enabled"), True),
            offline_cache_max_age_minutes=data.get("offline_cache_max_age_minutes", 180),
            weather_history_enabled=settings_cls._as_bool(
                data.get("weather_history_enabled"), True
            ),
            forecast_duration_days=data.get("forecast_duration_days", 7),
            hourly_forecast_hours=data.get("hourly_forecast_hours", 6),
            forecast_time_reference=data.get("forecast_time_reference", "location"),
            time_display_mode=data.get("time_display_mode", "local"),
            time_format_12hour=settings_cls._as_bool(data.get("time_format_12hour"), True),
            show_timezone_suffix=settings_cls._as_bool(data.get("show_timezone_suffix"), False),
            alert_display_style=data.get("alert_display_style", "separate"),
            location_buttons_on_top=settings_cls._as_bool(
                data.get("location_buttons_on_top"), False
            ),
            date_format=data.get("date_format", "iso"),
            taskbar_icon_text_enabled=settings_cls._as_bool(
                data.get("taskbar_icon_text_enabled"), False
            ),
            taskbar_icon_dynamic_enabled=settings_cls._as_bool(
                data.get("taskbar_icon_dynamic_enabled"), True
            ),
            taskbar_icon_text_format=data.get("taskbar_icon_text_format", "{temp} {condition}"),
            source_priority_us=data.get(
                "source_priority_us", ["nws", "openmeteo", "pirateweather"]
            ),
            source_priority_international=data.get(
                "source_priority_international", ["openmeteo", "pirateweather"]
            ),
            auto_mode_api_budget=data.get("auto_mode_api_budget", "max_coverage"),
            auto_sources_us=data.get("auto_sources_us", ["nws", "openmeteo", "pirateweather"]),
            auto_sources_international=data.get(
                "auto_sources_international", ["openmeteo", "pirateweather"]
            ),
            openmeteo_weather_model=data.get("openmeteo_weather_model", "best_match"),
            station_selection_strategy=data.get("station_selection_strategy", "hybrid_default"),
            # AVWX and AI settings (stored in secure storage)
            avwx_api_key=data.get("avwx_api_key", ""),
            openrouter_api_key=data.get("openrouter_api_key", ""),
            ai_model_preference=data.get("ai_model_preference", "openrouter/free"),
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
            severe_weather_override=settings_cls._as_bool(
                data.get("severe_weather_override"), False
            ),
            onboarding_wizard_shown=settings_cls._as_bool(
                data.get("onboarding_wizard_shown"), False
            ),
            portable_missing_api_keys_hint_shown=settings_cls._as_bool(
                data.get("portable_missing_api_keys_hint_shown"), False
            ),
            round_values=settings_cls._as_bool(data.get("round_values"), False),
            show_impact_summaries=settings_cls._as_bool(data.get("show_impact_summaries"), False),
        )
        settings.validate_on_access("auto_mode_api_budget")
        settings.validate_on_access("alert_display_style")
        settings.validate_on_access("date_format")
        settings.validate_on_access("source_priority_us")
        settings.validate_on_access("source_priority_international")
        settings.validate_on_access("auto_sources_us")
        settings.validate_on_access("auto_sources_international")
        if settings.data_source not in {"auto", "nws", "openmeteo", "pirateweather"}:
            settings.data_source = "auto"
        return settings

    def to_alert_settings(self):
        """Convert to AlertSettings for the alert management system."""
        app_settings = cast("AppSettings", self)
        from accessiweather.alert_manager import AlertSettings

        settings = AlertSettings()
        settings.notifications_enabled = app_settings.alert_notifications_enabled
        settings.sound_enabled = app_settings.sound_enabled
        settings.global_cooldown = app_settings.alert_global_cooldown_minutes
        settings.per_alert_cooldown = app_settings.alert_per_alert_cooldown_minutes
        settings.escalation_cooldown = app_settings.alert_escalation_cooldown_minutes
        settings.freshness_window_minutes = app_settings.alert_freshness_window_minutes
        settings.max_notifications_per_hour = app_settings.alert_max_notifications_per_hour
        settings.ignored_categories = set(app_settings.alert_ignored_categories)

        if app_settings.alert_notify_unknown:
            settings.min_severity_priority = 1
        elif app_settings.alert_notify_minor:
            settings.min_severity_priority = 2
        elif app_settings.alert_notify_moderate:
            settings.min_severity_priority = 3
        elif app_settings.alert_notify_severe:
            settings.min_severity_priority = 4
        elif app_settings.alert_notify_extreme:
            settings.min_severity_priority = 5
        else:
            settings.min_severity_priority = 6

        return settings
