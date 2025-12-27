"""Handlers for applying and collecting settings in the dialog."""

from __future__ import annotations

import contextlib
import logging

from ..models import AppSettings

logger = logging.getLogger(__name__)
LOG_PREFIX = "SettingsHandlers"


def _apply_general_settings(dialog, settings):
    """Apply general/display settings to UI widgets."""
    if getattr(dialog, "temperature_unit_selection", None):
        dialog.temperature_unit_selection.value = dialog.temperature_value_to_display.get(
            getattr(settings, "temperature_unit", "both"),
            "Both (Fahrenheit and Celsius)",
        )

    if getattr(dialog, "update_interval_input", None):
        dialog.update_interval_input.value = getattr(settings, "update_interval_minutes", 10)

    if getattr(dialog, "show_dewpoint_switch", None):
        dialog.show_dewpoint_switch.value = getattr(settings, "show_dewpoint", True)

    if getattr(dialog, "show_visibility_switch", None):
        dialog.show_visibility_switch.value = getattr(settings, "show_visibility", True)

    if getattr(dialog, "show_uv_index_switch", None):
        dialog.show_uv_index_switch.value = getattr(settings, "show_uv_index", True)

    if getattr(dialog, "show_pressure_trend_switch", None):
        dialog.show_pressure_trend_switch.value = getattr(settings, "show_pressure_trend", True)

    if getattr(dialog, "show_detailed_forecast_switch", None):
        dialog.show_detailed_forecast_switch.value = getattr(
            settings, "show_detailed_forecast", True
        )

    if getattr(dialog, "enable_alerts_switch", None):
        dialog.enable_alerts_switch.value = getattr(settings, "enable_alerts", True)

    # Time display settings
    if getattr(dialog, "time_display_mode_selection", None):
        display = dialog.time_display_value_to_display.get(
            getattr(settings, "time_display_mode", "local"),
            "Local time only",
        )
        dialog.time_display_mode_selection.value = display

    if getattr(dialog, "time_format_12hour_switch", None):
        dialog.time_format_12hour_switch.value = getattr(settings, "time_format_12hour", True)

    if getattr(dialog, "show_timezone_suffix_switch", None):
        dialog.show_timezone_suffix_switch.value = getattr(settings, "show_timezone_suffix", False)

    # HTML rendering settings
    if getattr(dialog, "html_render_current_conditions_switch", None):
        dialog.html_render_current_conditions_switch.value = getattr(
            settings, "html_render_current_conditions", True
        )

    if getattr(dialog, "html_render_forecast_switch", None):
        dialog.html_render_forecast_switch.value = getattr(settings, "html_render_forecast", True)

    # Taskbar icon text settings
    if getattr(dialog, "taskbar_icon_text_enabled_switch", None):
        dialog.taskbar_icon_text_enabled_switch.value = getattr(
            settings, "taskbar_icon_text_enabled", False
        )

    if getattr(dialog, "taskbar_icon_dynamic_enabled_switch", None):
        dialog.taskbar_icon_dynamic_enabled_switch.value = getattr(
            settings, "taskbar_icon_dynamic_enabled", True
        )
        dialog.taskbar_icon_dynamic_enabled_switch.enabled = getattr(
            settings, "taskbar_icon_text_enabled", False
        )

    if getattr(dialog, "taskbar_icon_text_format_input", None):
        dialog.taskbar_icon_text_format_input.value = getattr(
            settings, "taskbar_icon_text_format", "{temp} {condition}"
        )
        dialog.taskbar_icon_text_format_input.enabled = getattr(
            settings, "taskbar_icon_text_enabled", False
        )


def _apply_data_source_settings(dialog, settings):
    """Apply data source and API settings to UI widgets."""
    if getattr(dialog, "data_source_selection", None):
        display = dialog.data_source_value_to_display.get(getattr(settings, "data_source", "auto"))
        if display:
            dialog.data_source_selection.value = display

    if getattr(dialog, "visual_crossing_api_key_input", None) is not None:
        dialog.visual_crossing_api_key_input.value = getattr(
            settings, "visual_crossing_api_key", ""
        )

    # Apply source priority settings
    if getattr(dialog, "us_priority_selection", None) is not None:
        try:
            current_us_priority = getattr(
                settings, "source_priority_us", ["nws", "openmeteo", "visualcrossing"]
            )
            display_value = dialog.us_priority_value_to_display.get(
                tuple(current_us_priority),
                "NWS → Open-Meteo → Visual Crossing (Default)",
            )
            dialog.us_priority_selection.value = display_value
        except Exception as exc:
            logger.warning("%s: Failed to apply US priority selection: %s", LOG_PREFIX, exc)

    if getattr(dialog, "intl_priority_selection", None) is not None:
        try:
            current_intl_priority = getattr(
                settings, "source_priority_international", ["openmeteo", "visualcrossing"]
            )
            display_value = dialog.intl_priority_value_to_display.get(
                tuple(current_intl_priority),
                "Open-Meteo → Visual Crossing (Default)",
            )
            dialog.intl_priority_selection.value = display_value
        except Exception as exc:
            logger.warning("%s: Failed to apply intl priority selection: %s", LOG_PREFIX, exc)

    with contextlib.suppress(Exception):
        dialog._update_visual_crossing_config_visibility()
        dialog._update_priority_settings_visibility()


def _apply_sound_settings(dialog, settings):
    """Apply sound pack settings to UI widgets."""
    if getattr(dialog, "sound_enabled_switch", None) is not None:
        dialog.sound_enabled_switch.value = getattr(settings, "sound_enabled", True)

    if getattr(dialog, "sound_pack_selection", None) is not None:
        target_pack = getattr(settings, "sound_pack", "default")
        display_name = None
        for name, pack_id in getattr(dialog, "sound_pack_map", {}).items():
            if pack_id == target_pack:
                display_name = name
                break

        if not display_name and getattr(dialog, "sound_pack_options", []):
            display_name = dialog.sound_pack_options[0]

        if display_name:
            dialog.sound_pack_selection.value = display_name

        dialog.sound_pack_selection.enabled = bool(dialog.sound_enabled_switch.value)


def _apply_update_settings(dialog, settings):
    """Apply update-related settings to UI widgets."""
    if getattr(dialog, "auto_update_switch", None) is not None:
        dialog.auto_update_switch.value = getattr(settings, "auto_update_enabled", True)

    if getattr(dialog, "update_channel_selection", None) is not None:
        channel = getattr(settings, "update_channel", "stable")
        if channel == "dev":
            dialog.update_channel_selection.value = "Development (Latest features, may be unstable)"
        elif channel == "beta":
            dialog.update_channel_selection.value = "Beta (Pre-release testing)"
        else:
            dialog.update_channel_selection.value = "Stable (Production releases only)"

        with contextlib.suppress(Exception):
            dialog._update_channel_description()

    if getattr(dialog, "update_check_interval_input", None) is not None:
        dialog.update_check_interval_input.value = getattr(
            settings, "update_check_interval_hours", 24
        )


def _apply_system_settings(dialog, settings):
    """Apply system/startup settings to UI widgets."""
    if getattr(dialog, "minimize_to_tray_switch", None) is not None:
        dialog.minimize_to_tray_switch.value = getattr(settings, "minimize_to_tray", False)

    if getattr(dialog, "startup_enabled_switch", None) is not None:
        try:
            actual_startup = dialog.config_manager.is_startup_enabled()
            dialog.startup_enabled_switch.value = actual_startup
        except Exception as exc:  # pragma: no cover - platform failures
            logger.warning("%s: Failed to sync startup state: %s", LOG_PREFIX, exc)
            dialog.startup_enabled_switch.value = getattr(settings, "startup_enabled", False)

    if getattr(dialog, "debug_mode_switch", None) is not None:
        dialog.debug_mode_switch.value = getattr(settings, "debug_mode", False)

    if getattr(dialog, "weather_history_enabled_switch", None) is not None:
        dialog.weather_history_enabled_switch.value = getattr(
            settings, "weather_history_enabled", True
        )


def _apply_alert_notification_settings(dialog, settings):
    """Apply alert notification settings to UI widgets."""
    if getattr(dialog, "alert_notifications_enabled_switch", None) is not None:
        dialog.alert_notifications_enabled_switch.value = getattr(
            settings, "alert_notifications_enabled", True
        )

    if getattr(dialog, "alert_notify_extreme_switch", None) is not None:
        dialog.alert_notify_extreme_switch.value = getattr(settings, "alert_notify_extreme", True)

    if getattr(dialog, "alert_notify_severe_switch", None) is not None:
        dialog.alert_notify_severe_switch.value = getattr(settings, "alert_notify_severe", True)

    if getattr(dialog, "alert_notify_moderate_switch", None) is not None:
        dialog.alert_notify_moderate_switch.value = getattr(settings, "alert_notify_moderate", True)

    if getattr(dialog, "alert_notify_minor_switch", None) is not None:
        dialog.alert_notify_minor_switch.value = getattr(settings, "alert_notify_minor", False)

    if getattr(dialog, "alert_notify_unknown_switch", None) is not None:
        dialog.alert_notify_unknown_switch.value = getattr(settings, "alert_notify_unknown", False)

    if getattr(dialog, "alert_global_cooldown_input", None) is not None:
        dialog.alert_global_cooldown_input.value = getattr(
            settings, "alert_global_cooldown_minutes", 5
        )

    if getattr(dialog, "alert_per_alert_cooldown_input", None) is not None:
        dialog.alert_per_alert_cooldown_input.value = getattr(
            settings, "alert_per_alert_cooldown_minutes", 60
        )

    if getattr(dialog, "alert_freshness_window_input", None) is not None:
        dialog.alert_freshness_window_input.value = getattr(
            settings, "alert_freshness_window_minutes", 15
        )

    if getattr(dialog, "alert_max_notifications_input", None) is not None:
        dialog.alert_max_notifications_input.value = getattr(
            settings, "alert_max_notifications_per_hour", 10
        )


def _apply_display_priority_settings(dialog, settings):
    """Apply display priority settings to UI widgets."""
    # Verbosity level
    if getattr(dialog, "verbosity_selection", None) is not None:
        verbosity = getattr(settings, "verbosity_level", "standard")
        if hasattr(dialog, "verbosity_value_to_display"):
            display_value = dialog.verbosity_value_to_display.get(
                verbosity, "Standard (recommended)"
            )
            try:
                dialog.verbosity_selection.value = display_value
            except Exception as exc:
                logger.debug("%s: Failed to set verbosity selection: %s", LOG_PREFIX, exc)

    # Category order
    if getattr(dialog, "category_order_list", None) is not None:
        category_order = getattr(
            settings,
            "category_order",
            [
                "temperature",
                "precipitation",
                "wind",
                "humidity_pressure",
                "visibility_clouds",
                "uv_index",
            ],
        )
        category_display_names = {
            "temperature": "Temperature",
            "precipitation": "Precipitation",
            "wind": "Wind",
            "humidity_pressure": "Humidity & Pressure",
            "visibility_clouds": "Visibility & Clouds",
            "uv_index": "UV Index",
        }
        display_items = [category_display_names.get(c, c) for c in category_order]
        try:
            dialog.category_order_list.items = display_items
            if display_items:
                dialog.category_order_list.value = display_items[0]
        except Exception as exc:
            logger.debug("%s: Failed to set category order list: %s", LOG_PREFIX, exc)

    # Severe weather override
    if getattr(dialog, "severe_weather_override_switch", None) is not None:
        dialog.severe_weather_override_switch.value = getattr(
            settings, "severe_weather_override", True
        )


def _apply_ai_settings(dialog, settings):
    """Apply AI explanation settings to UI widgets."""
    # OpenRouter API key
    if getattr(dialog, "openrouter_api_key_input", None) is not None:
        dialog.openrouter_api_key_input.value = getattr(settings, "openrouter_api_key", "") or ""

    # Model preference
    if getattr(dialog, "ai_model_selection", None) is not None:
        model_pref = getattr(
            settings, "ai_model_preference", "meta-llama/llama-3.3-70b-instruct:free"
        )
        if hasattr(dialog, "ai_model_value_to_display"):
            display_value = dialog.ai_model_value_to_display.get(model_pref, "Llama 3.3 70B (Free)")
            try:
                dialog.ai_model_selection.value = display_value
            except Exception as exc:
                logger.debug("%s: Failed to set AI model selection: %s", LOG_PREFIX, exc)
        # Label is static; selection widget shows the full option text
        # Update selected model label
        if hasattr(dialog, "selected_model_label"):
            dialog.selected_model_label.value = (
                model_pref
                if model_pref not in ("meta-llama/llama-3.3-70b-instruct:free", "auto")
                else ""
            )

    # Explanation style
    if getattr(dialog, "ai_style_selection", None) is not None:
        style = getattr(settings, "ai_explanation_style", "standard")
        if hasattr(dialog, "ai_style_value_to_display"):
            display_value = dialog.ai_style_value_to_display.get(style, "Standard (3-4 sentences)")
            try:
                dialog.ai_style_selection.value = display_value
            except Exception as exc:
                logger.debug("%s: Failed to set AI style selection: %s", LOG_PREFIX, exc)

    # Custom system prompt
    if getattr(dialog, "custom_system_prompt_input", None) is not None:
        custom_prompt = getattr(settings, "custom_system_prompt", None) or ""
        dialog.custom_system_prompt_input.value = custom_prompt

    # Custom instructions
    if getattr(dialog, "custom_instructions_input", None) is not None:
        custom_instructions = getattr(settings, "custom_instructions", None) or ""
        dialog.custom_instructions_input.value = custom_instructions


def apply_settings_to_ui(dialog):
    """Apply settings model to UI widgets in the dialog using helper functions."""
    try:
        settings = dialog.current_settings

        _apply_general_settings(dialog, settings)
        _apply_data_source_settings(dialog, settings)
        _apply_sound_settings(dialog, settings)
        _apply_update_settings(dialog, settings)
        _apply_system_settings(dialog, settings)
        _apply_alert_notification_settings(dialog, settings)
        _apply_display_priority_settings(dialog, settings)
        _apply_ai_settings(dialog, settings)

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("%s: Failed to apply settings to UI: %s", LOG_PREFIX, exc)


def map_channel_display_to_value(display: str) -> str:
    """Return the internal channel value for the provided display text."""
    if "Development" in display:
        return "dev"
    if "Beta" in display:
        return "beta"
    return "stable"


def _collect_display_settings(dialog, current_settings):
    """Collect general display settings from UI widgets."""

    def _switch_value(attr: str, default: bool) -> bool:
        widget = getattr(dialog, attr, None)
        if widget is None or not hasattr(widget, "value"):
            return default
        try:
            return bool(widget.value)
        except Exception:  # pragma: no cover - defensive fallback
            return default

    try:
        selected_display = str(dialog.temperature_unit_selection.value)
        temperature_unit = dialog.temperature_display_to_value.get(selected_display, "both")
    except Exception as exc:  # pragma: no cover
        logger.warning("%s: Failed to get temperature unit selection: %s", LOG_PREFIX, exc)
        temperature_unit = "both"

    try:
        update_interval = int(dialog.update_interval_input.value)
        update_interval = max(1, min(1440, update_interval))
    except (ValueError, TypeError):
        update_interval = 10

    # Time display settings
    try:
        selected_time_display = str(dialog.time_display_mode_selection.value)
        time_display_mode = dialog.time_display_display_to_value.get(selected_time_display, "local")
    except Exception as exc:  # pragma: no cover
        logger.warning("%s: Failed to get time display mode selection: %s", LOG_PREFIX, exc)
        time_display_mode = "local"

    time_format_12hour = _switch_value(
        "time_format_12hour_switch",
        getattr(current_settings, "time_format_12hour", True),
    )
    show_timezone_suffix = _switch_value(
        "show_timezone_suffix_switch",
        getattr(current_settings, "show_timezone_suffix", False),
    )

    show_dewpoint = _switch_value(
        "show_dewpoint_switch", getattr(current_settings, "show_dewpoint", True)
    )
    show_visibility = _switch_value(
        "show_visibility_switch", getattr(current_settings, "show_visibility", True)
    )
    show_uv_index = _switch_value(
        "show_uv_index_switch", getattr(current_settings, "show_uv_index", True)
    )
    show_pressure_trend = _switch_value(
        "show_pressure_trend_switch", getattr(current_settings, "show_pressure_trend", True)
    )
    show_detailed_forecast = _switch_value(
        "show_detailed_forecast_switch",
        getattr(current_settings, "show_detailed_forecast", True),
    )
    enable_alerts = _switch_value(
        "enable_alerts_switch", getattr(current_settings, "enable_alerts", True)
    )

    # HTML rendering settings
    html_render_current_conditions = _switch_value(
        "html_render_current_conditions_switch",
        getattr(current_settings, "html_render_current_conditions", True),
    )
    html_render_forecast = _switch_value(
        "html_render_forecast_switch",
        getattr(current_settings, "html_render_forecast", True),
    )

    # Taskbar icon text settings
    taskbar_icon_text_enabled = _switch_value(
        "taskbar_icon_text_enabled_switch",
        getattr(current_settings, "taskbar_icon_text_enabled", False),
    )
    taskbar_icon_dynamic_enabled = _switch_value(
        "taskbar_icon_dynamic_enabled_switch",
        getattr(current_settings, "taskbar_icon_dynamic_enabled", True),
    )
    taskbar_icon_text_format = getattr(
        current_settings, "taskbar_icon_text_format", "{temp} {condition}"
    )
    if getattr(dialog, "taskbar_icon_text_format_input", None) is not None:
        try:
            taskbar_icon_text_format = str(
                dialog.taskbar_icon_text_format_input.value or ""
            ).strip()
            if not taskbar_icon_text_format:
                taskbar_icon_text_format = "{temp} {condition}"
        except Exception:
            pass

    return {
        "temperature_unit": temperature_unit,
        "update_interval_minutes": update_interval,
        "show_detailed_forecast": show_detailed_forecast,
        "enable_alerts": enable_alerts,
        "show_dewpoint": show_dewpoint,
        "show_visibility": show_visibility,
        "show_uv_index": show_uv_index,
        "show_pressure_trend": show_pressure_trend,
        "time_display_mode": time_display_mode,
        "time_format_12hour": time_format_12hour,
        "show_timezone_suffix": show_timezone_suffix,
        "html_render_current_conditions": html_render_current_conditions,
        "html_render_forecast": html_render_forecast,
        "taskbar_icon_text_enabled": taskbar_icon_text_enabled,
        "taskbar_icon_dynamic_enabled": taskbar_icon_dynamic_enabled,
        "taskbar_icon_text_format": taskbar_icon_text_format,
    }


def _collect_data_source_settings(dialog, current_settings):
    """Collect data source and API settings from UI widgets."""
    try:
        selected_display = str(dialog.data_source_selection.value)
        data_source = dialog.data_source_display_to_value.get(selected_display, "auto")
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("%s: Failed to get data source selection: %s", LOG_PREFIX, exc)
        data_source = "auto"

    # Start with existing API key to preserve it across data source changes
    visual_crossing_api_key = getattr(current_settings, "visual_crossing_api_key", "") or ""

    # Read from input field if it exists and has a value
    # The input field is only visible when Visual Crossing is selected, but we should
    # still read from it if the user entered a key before switching sources
    if getattr(dialog, "visual_crossing_api_key_input", None):
        input_value = str(dialog.visual_crossing_api_key_input.value or "").strip()
        # Only update if the user entered something (don't clear existing key with empty input)
        if input_value:
            visual_crossing_api_key = input_value

    # Source priority settings
    source_priority_us = getattr(
        current_settings, "source_priority_us", ["nws", "openmeteo", "visualcrossing"]
    )
    source_priority_international = getattr(
        current_settings, "source_priority_international", ["openmeteo", "visualcrossing"]
    )

    if getattr(dialog, "us_priority_selection", None) is not None:
        try:
            selected_us = str(dialog.us_priority_selection.value)
            source_priority_us = dialog.us_priority_display_to_value.get(
                selected_us, ["nws", "openmeteo", "visualcrossing"]
            )
        except Exception as exc:
            logger.warning("%s: Failed to get US priority selection: %s", LOG_PREFIX, exc)

    if getattr(dialog, "intl_priority_selection", None) is not None:
        try:
            selected_intl = str(dialog.intl_priority_selection.value)
            source_priority_international = dialog.intl_priority_display_to_value.get(
                selected_intl, ["openmeteo", "visualcrossing"]
            )
        except Exception as exc:
            logger.warning("%s: Failed to get intl priority selection: %s", LOG_PREFIX, exc)

    return {
        "data_source": data_source,
        "visual_crossing_api_key": visual_crossing_api_key,
        "source_priority_us": source_priority_us,
        "source_priority_international": source_priority_international,
    }


def _collect_update_settings(dialog):
    """Collect update-related settings from UI widgets."""
    auto_update_enabled = getattr(dialog.auto_update_switch, "value", True)

    if getattr(dialog, "update_channel_selection", None) and hasattr(
        dialog.update_channel_selection, "value"
    ):
        channel_value = str(dialog.update_channel_selection.value)
        update_channel = map_channel_display_to_value(channel_value)
    else:
        update_channel = "stable"

    if getattr(dialog, "update_check_interval_input", None) and hasattr(
        dialog.update_check_interval_input, "value"
    ):
        try:
            update_check_interval_hours = int(dialog.update_check_interval_input.value)
            update_check_interval_hours = max(1, min(168, update_check_interval_hours))
        except (ValueError, TypeError):
            update_check_interval_hours = 24
    else:
        update_check_interval_hours = 24

    return {
        "auto_update_enabled": auto_update_enabled,
        "update_channel": update_channel,
        "update_check_interval_hours": update_check_interval_hours,
    }


def _collect_sound_settings(dialog):
    """Collect sound-related settings from UI widgets."""
    sound_enabled = getattr(dialog.sound_enabled_switch, "value", True)

    pack_display = None
    if getattr(dialog, "sound_pack_selection", None) and hasattr(
        dialog.sound_pack_selection, "value"
    ):
        pack_display = dialog.sound_pack_selection.value
    sound_pack = getattr(dialog, "sound_pack_map", {}).get(pack_display, "default")

    return {
        "sound_enabled": sound_enabled,
        "sound_pack": sound_pack,
    }


def _collect_system_settings(dialog, current_settings):
    """Collect system-related settings from UI widgets."""

    def _switch_value(attr: str, default: bool) -> bool:
        widget = getattr(dialog, attr, None)
        if widget is None or not hasattr(widget, "value"):
            return default
        try:
            return bool(widget.value)
        except Exception:  # pragma: no cover - defensive fallback
            return default

    startup_enabled = getattr(dialog.startup_enabled_switch, "value", False)
    minimize_to_tray = _switch_value(
        "minimize_to_tray_switch", getattr(current_settings, "minimize_to_tray", False)
    )
    debug_mode = _switch_value("debug_mode_switch", getattr(current_settings, "debug_mode", False))
    weather_history_enabled = _switch_value(
        "weather_history_enabled_switch",
        getattr(current_settings, "weather_history_enabled", True),
    )

    return {
        "startup_enabled": startup_enabled,
        "minimize_to_tray": minimize_to_tray,
        "debug_mode": debug_mode,
        "weather_history_enabled": weather_history_enabled,
    }


def _collect_alert_settings(dialog, current_settings):
    """Collect alert notification settings from UI widgets."""

    def _as_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    alerts_enabled = bool(
        getattr(
            getattr(dialog, "alert_notifications_enabled_switch", None),
            "value",
            getattr(current_settings, "alert_notifications_enabled", True),
        )
    )
    notify_extreme = bool(
        getattr(
            getattr(dialog, "alert_notify_extreme_switch", None),
            "value",
            getattr(current_settings, "alert_notify_extreme", True),
        )
    )
    notify_severe = bool(
        getattr(
            getattr(dialog, "alert_notify_severe_switch", None),
            "value",
            getattr(current_settings, "alert_notify_severe", True),
        )
    )
    notify_moderate = bool(
        getattr(
            getattr(dialog, "alert_notify_moderate_switch", None),
            "value",
            getattr(current_settings, "alert_notify_moderate", True),
        )
    )
    notify_minor = bool(
        getattr(
            getattr(dialog, "alert_notify_minor_switch", None),
            "value",
            getattr(current_settings, "alert_notify_minor", False),
        )
    )
    notify_unknown = bool(
        getattr(
            getattr(dialog, "alert_notify_unknown_switch", None),
            "value",
            getattr(current_settings, "alert_notify_unknown", False),
        )
    )

    global_cooldown = _as_int(
        getattr(getattr(dialog, "alert_global_cooldown_input", None), "value", None),
        getattr(current_settings, "alert_global_cooldown_minutes", 5),
    )
    per_alert_cooldown = _as_int(
        getattr(getattr(dialog, "alert_per_alert_cooldown_input", None), "value", None),
        getattr(current_settings, "alert_per_alert_cooldown_minutes", 60),
    )
    escalation_cooldown = _as_int(
        getattr(getattr(dialog, "alert_escalation_cooldown_input", None), "value", None),
        getattr(current_settings, "alert_escalation_cooldown_minutes", 15),
    )
    freshness_window = _as_int(
        getattr(getattr(dialog, "alert_freshness_window_input", None), "value", None),
        getattr(current_settings, "alert_freshness_window_minutes", 15),
    )
    max_per_hour = _as_int(
        getattr(getattr(dialog, "alert_max_notifications_input", None), "value", None),
        getattr(current_settings, "alert_max_notifications_per_hour", 10),
    )

    if hasattr(dialog, "_collect_ignored_categories"):
        try:
            ignored_categories = list(dialog._collect_ignored_categories())  # type: ignore[attr-defined]
        except Exception:
            ignored_categories = list(getattr(current_settings, "alert_ignored_categories", []))
    else:
        ignored_categories = list(getattr(current_settings, "alert_ignored_categories", []))

    return {
        "alert_notifications_enabled": alerts_enabled,
        "alert_notify_extreme": notify_extreme,
        "alert_notify_severe": notify_severe,
        "alert_notify_moderate": notify_moderate,
        "alert_notify_minor": notify_minor,
        "alert_notify_unknown": notify_unknown,
        "alert_global_cooldown_minutes": global_cooldown,
        "alert_per_alert_cooldown_minutes": per_alert_cooldown,
        "alert_escalation_cooldown_minutes": escalation_cooldown,
        "alert_freshness_window_minutes": freshness_window,
        "alert_max_notifications_per_hour": max_per_hour,
        "alert_ignored_categories": ignored_categories,
    }


def _collect_display_priority_settings(dialog, current_settings: AppSettings) -> dict:
    """Collect display priority settings from dialog widgets."""
    # Verbosity level
    verbosity_level = getattr(current_settings, "verbosity_level", "standard")
    if hasattr(dialog, "verbosity_selection"):
        display_value = getattr(dialog.verbosity_selection, "value", None)
        if display_value and hasattr(dialog, "verbosity_display_to_value"):
            verbosity_level = dialog.verbosity_display_to_value.get(display_value, verbosity_level)

    # Category order - convert display names back to internal names
    default_order = [
        "temperature",
        "precipitation",
        "wind",
        "humidity_pressure",
        "visibility_clouds",
        "uv_index",
    ]
    category_order = getattr(current_settings, "category_order", default_order)

    display_to_internal = {
        "Temperature": "temperature",
        "Precipitation": "precipitation",
        "Wind": "wind",
        "Humidity & Pressure": "humidity_pressure",
        "Visibility & Clouds": "visibility_clouds",
        "UV Index": "uv_index",
    }

    if hasattr(dialog, "category_order_list") and dialog.category_order_list is not None:
        try:
            # Get items from the ListSource
            display_items = [item.value for item in dialog.category_order_list.items]
            category_order = [display_to_internal.get(item, item) for item in display_items]
        except Exception as exc:
            logger.debug("Failed to get category order from list: %s", exc)

    # Severe weather override
    severe_weather_override = getattr(current_settings, "severe_weather_override", True)
    if hasattr(dialog, "severe_weather_override_switch"):
        severe_weather_override = bool(
            getattr(dialog.severe_weather_override_switch, "value", True)
        )

    return {
        "verbosity_level": verbosity_level,
        "category_order": category_order,
        "severe_weather_override": severe_weather_override,
    }


def _collect_ai_settings(dialog, current_settings: AppSettings) -> dict:
    """Collect AI explanation settings from dialog widgets."""
    # OpenRouter API key
    api_key = getattr(current_settings, "openrouter_api_key", "")
    if hasattr(dialog, "openrouter_api_key_input"):
        api_key = getattr(dialog.openrouter_api_key_input, "value", api_key) or ""

    # Model preference
    model_pref = getattr(current_settings, "ai_model_preference", "auto:free")
    if hasattr(dialog, "ai_model_selection"):
        display_value = getattr(dialog.ai_model_selection, "value", None)
        if display_value and hasattr(dialog, "ai_model_display_to_value"):
            model_pref = dialog.ai_model_display_to_value.get(display_value, model_pref)

    # Explanation style
    style = getattr(current_settings, "ai_explanation_style", "standard")
    if hasattr(dialog, "ai_style_selection"):
        display_value = getattr(dialog.ai_style_selection, "value", None)
        if display_value and hasattr(dialog, "ai_style_display_to_value"):
            style = dialog.ai_style_display_to_value.get(display_value, style)

    # Cache TTL (not exposed in UI, use default)
    cache_ttl = getattr(current_settings, "ai_cache_ttl", 300)

    # Custom system prompt
    custom_system_prompt = getattr(current_settings, "custom_system_prompt", None)
    if hasattr(dialog, "custom_system_prompt_input"):
        value = getattr(dialog.custom_system_prompt_input, "value", "") or ""
        custom_system_prompt = value.strip() if value.strip() else None

    # Custom instructions
    custom_instructions = getattr(current_settings, "custom_instructions", None)
    if hasattr(dialog, "custom_instructions_input"):
        value = getattr(dialog.custom_instructions_input, "value", "") or ""
        custom_instructions = value.strip() if value.strip() else None

    return {
        "openrouter_api_key": api_key,
        "ai_model_preference": model_pref,
        "ai_explanation_style": style,
        "ai_cache_ttl": cache_ttl,
        "custom_system_prompt": custom_system_prompt,
        "custom_instructions": custom_instructions,
    }


def collect_settings_from_ui(dialog) -> AppSettings:
    """Read current widget values and return an AppSettings instance using helper functions."""
    current_settings = getattr(dialog, "current_settings", AppSettings())

    # Collect settings from each category
    display = _collect_display_settings(dialog, current_settings)
    data_source = _collect_data_source_settings(dialog, current_settings)
    updates = _collect_update_settings(dialog)
    sound = _collect_sound_settings(dialog)
    system = _collect_system_settings(dialog, current_settings)
    alerts = _collect_alert_settings(dialog, current_settings)
    display_priority = _collect_display_priority_settings(dialog, current_settings)
    ai = _collect_ai_settings(dialog, current_settings)

    # Build and return AppSettings with collected values
    return AppSettings(
        # Display settings
        temperature_unit=display["temperature_unit"],
        update_interval_minutes=display["update_interval_minutes"],
        show_detailed_forecast=display["show_detailed_forecast"],
        enable_alerts=display["enable_alerts"],
        show_dewpoint=display["show_dewpoint"],
        show_visibility=display["show_visibility"],
        show_uv_index=display["show_uv_index"],
        show_pressure_trend=display["show_pressure_trend"],
        # Data source settings
        data_source=data_source["data_source"],
        visual_crossing_api_key=data_source["visual_crossing_api_key"],
        source_priority_us=data_source["source_priority_us"],
        source_priority_international=data_source["source_priority_international"],
        # Update settings
        auto_update_enabled=updates["auto_update_enabled"],
        update_channel=updates["update_channel"],
        update_check_interval_hours=updates["update_check_interval_hours"],
        # Sound settings
        sound_enabled=sound["sound_enabled"],
        sound_pack=sound["sound_pack"],
        # System settings
        startup_enabled=system["startup_enabled"],
        minimize_to_tray=system["minimize_to_tray"],
        debug_mode=system["debug_mode"],
        weather_history_enabled=system["weather_history_enabled"],
        # Alert settings
        alert_notifications_enabled=alerts["alert_notifications_enabled"],
        alert_notify_extreme=alerts["alert_notify_extreme"],
        alert_notify_severe=alerts["alert_notify_severe"],
        alert_notify_moderate=alerts["alert_notify_moderate"],
        alert_notify_minor=alerts["alert_notify_minor"],
        alert_notify_unknown=alerts["alert_notify_unknown"],
        alert_global_cooldown_minutes=alerts["alert_global_cooldown_minutes"],
        alert_per_alert_cooldown_minutes=alerts["alert_per_alert_cooldown_minutes"],
        alert_escalation_cooldown_minutes=alerts["alert_escalation_cooldown_minutes"],
        alert_freshness_window_minutes=alerts["alert_freshness_window_minutes"],
        alert_max_notifications_per_hour=alerts["alert_max_notifications_per_hour"],
        alert_ignored_categories=alerts["alert_ignored_categories"],
        # Settings without UI widgets (preserve from current_settings)
        github_backend_url="",
        trend_insights_enabled=getattr(current_settings, "trend_insights_enabled", True),
        trend_hours=getattr(current_settings, "trend_hours", 24),
        air_quality_enabled=getattr(current_settings, "air_quality_enabled", True),
        pollen_enabled=getattr(current_settings, "pollen_enabled", True),
        offline_cache_enabled=getattr(current_settings, "offline_cache_enabled", True),
        offline_cache_max_age_minutes=getattr(
            current_settings, "offline_cache_max_age_minutes", 180
        ),
        # Time display settings
        time_display_mode=display["time_display_mode"],
        time_format_12hour=display["time_format_12hour"],
        show_timezone_suffix=display["show_timezone_suffix"],
        # HTML rendering settings
        html_render_current_conditions=display["html_render_current_conditions"],
        html_render_forecast=display["html_render_forecast"],
        # Taskbar icon text settings
        taskbar_icon_text_enabled=display["taskbar_icon_text_enabled"],
        taskbar_icon_dynamic_enabled=display["taskbar_icon_dynamic_enabled"],
        taskbar_icon_text_format=display["taskbar_icon_text_format"],
        # Display priority settings
        verbosity_level=display_priority["verbosity_level"],
        category_order=display_priority["category_order"],
        severe_weather_override=display_priority["severe_weather_override"],
        # AI explanation settings
        openrouter_api_key=ai["openrouter_api_key"],
        ai_model_preference=ai["ai_model_preference"],
        ai_explanation_style=ai["ai_explanation_style"],
        ai_cache_ttl=ai["ai_cache_ttl"],
        # AI prompt customization
        custom_system_prompt=ai["custom_system_prompt"],
        custom_instructions=ai["custom_instructions"],
    )
