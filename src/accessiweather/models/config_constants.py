"""Configuration setting groups for startup and deferred validation."""

from __future__ import annotations

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
    "alert_radius_type",
    "alert_notifications_enabled",
    "alert_notify_extreme",
    "alert_notify_severe",
    "alert_notify_moderate",
    "alert_notify_minor",
    "alert_notify_unknown",
    "immediate_alert_details_popups",
    "alert_global_cooldown_minutes",
    "alert_per_alert_cooldown_minutes",
    "alert_escalation_cooldown_minutes",
    "alert_freshness_window_minutes",
    "alert_max_notifications_per_hour",
    "alert_ignored_categories",
    # Sound settings
    "sound_enabled",
    "sound_pack",
    "muted_sound_events",
    "show_nationwide_location",
    # Event notifications
    "notify_discussion_update",
    "notify_hwo_update",
    "notify_sps_issued",
    "notify_severe_risk_change",
    "notify_minutely_precipitation_start",
    "notify_minutely_precipitation_stop",
    "minutely_precipitation_fast_polling",
    "precipitation_sensitivity",
    "notify_precipitation_likelihood",
    "precipitation_likelihood_threshold",
    # GitHub settings
    "github_backend_url",
    "github_app_id",
    "github_app_private_key",
    "github_app_installation_id",
    # AI explanation settings
    "openrouter_api_key",
    "avwx_api_key",
    "ai_model_preference",
    "ai_explanation_style",
    "ai_cache_ttl",
    "custom_system_prompt",
    "custom_instructions",
    # API key settings (loaded lazily via keyring)
    "pirate_weather_api_key",
    # Display preferences
    "round_values",
    "enable_alerts",
    "minimize_to_tray",
    "minimize_on_startup",
    "startup_enabled",
    "auto_update_enabled",
    "update_channel",
    "update_check_interval_hours",
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
    "forecast_duration_days",
    "forecast_time_reference",
    "time_display_mode",
    "time_format_12hour",
    "show_timezone_suffix",
    "alert_display_style",
    "date_format",
    "taskbar_icon_text_enabled",
    "taskbar_icon_dynamic_enabled",
    "taskbar_icon_text_format",
    "source_priority_us",
    "source_priority_international",
    "auto_sources_us",
    "auto_sources_international",
    "auto_mode_api_budget",
    "openmeteo_weather_model",
    "station_selection_strategy",
    "show_impact_summaries",
}
