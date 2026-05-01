"""Application settings dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..sound_events import DEFAULT_MUTED_SOUND_EVENTS
from .config_serialization import AppSettingsSerializationMixin
from .config_validation import AppSettingsValidationMixin


@dataclass
class AppSettings(AppSettingsValidationMixin, AppSettingsSerializationMixin):
    """Application settings."""

    temperature_unit: str = "both"
    update_interval_minutes: int = 10
    enable_alerts: bool = True
    minimize_to_tray: bool = False
    minimize_on_startup: bool = False
    startup_enabled: bool = False
    data_source: str = "auto"
    pirate_weather_api_key: str = ""
    auto_update_enabled: bool = True
    update_channel: str = "stable"
    update_check_interval_hours: int = 24
    sound_enabled: bool = True
    sound_pack: str = "default"
    muted_sound_events: list[str] = field(default_factory=lambda: list(DEFAULT_MUTED_SOUND_EVENTS))
    # Nationwide location visibility
    show_nationwide_location: bool = True
    # Event-based notifications
    notify_discussion_update: bool = True
    notify_hwo_update: bool = True
    notify_sps_issued: bool = True
    notify_severe_risk_change: bool = False
    notify_minutely_precipitation_start: bool = True
    notify_minutely_precipitation_stop: bool = True
    minutely_precipitation_fast_polling: bool = False
    # Minimum intensity level required to count as precipitation ("light", "moderate", "heavy")
    precipitation_sensitivity: str = "light"
    notify_precipitation_likelihood: bool = False
    precipitation_likelihood_threshold: float = 0.5
    github_backend_url: str = ""
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_app_installation_id: str = ""
    alert_radius_type: str = "county"  # "county", "point", "zone", or "state"
    alert_notifications_enabled: bool = True
    alert_notify_extreme: bool = True
    alert_notify_severe: bool = True
    alert_notify_moderate: bool = True
    alert_notify_minor: bool = False
    alert_notify_unknown: bool = False
    immediate_alert_details_popups: bool = False
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
    forecast_duration_days: int = 7
    hourly_forecast_hours: int = 6
    forecast_time_reference: str = "location"
    time_display_mode: str = "local"
    time_format_12hour: bool = True
    show_timezone_suffix: bool = False
    # Alert dialog display style
    alert_display_style: str = "separate"  # "separate" | "combined"
    # Place Add/Edit/Remove Location buttons on the location row instead of the
    # bottom button panel.  Takes effect on app restart.
    location_buttons_on_top: bool = False
    # Date format preset for rendered dates
    date_format: str = "iso"  # "iso" | "us_short" | "us_long" | "eu"
    # Taskbar icon text options
    taskbar_icon_text_enabled: bool = False
    taskbar_icon_dynamic_enabled: bool = True
    taskbar_icon_text_format: str = "{temp} {condition}"
    # Source priority settings for smart auto mode
    source_priority_us: list[str] = field(
        default_factory=lambda: ["nws", "openmeteo", "pirateweather"]
    )
    source_priority_international: list[str] = field(
        default_factory=lambda: ["openmeteo", "pirateweather"]
    )
    # Open-Meteo weather model selection
    openmeteo_weather_model: str = "best_match"
    # NWS station selection behavior for current conditions
    station_selection_strategy: str = "hybrid_default"
    # AVWX API key for international aviation weather
    avwx_api_key: str = ""
    # AI Explanation Settings
    openrouter_api_key: str = ""
    ai_model_preference: str = "openrouter/free"  # free auto-router (default)
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
    severe_weather_override: bool = False
    # Startup UX guidance flags
    onboarding_wizard_shown: bool = False
    portable_missing_api_keys_hint_shown: bool = False
    # Display precision
    round_values: bool = False
    # Impact summaries (Outdoor, Driving, Allergy) — opt-in, off by default
    show_impact_summaries: bool = False
    # Parallel fetch timeout for smart auto mode (seconds)
    parallel_fetch_timeout: float = 5.0
    # Auto mode source selection — which sources participate in auto mode
    auto_mode_api_budget: str = "max_coverage"
    auto_sources_us: list[str] = field(
        default_factory=lambda: ["nws", "openmeteo", "pirateweather"]
    )
    auto_sources_international: list[str] = field(
        default_factory=lambda: ["openmeteo", "pirateweather"]
    )
