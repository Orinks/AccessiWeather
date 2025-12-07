"""Tab builder helpers for the settings dialog UI."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

logger = logging.getLogger(__name__)


def _on_taskbar_icon_enabled_changed(dialog, widget):
    """Handle taskbar icon text enabled switch change."""
    enabled = getattr(widget, "value", False)
    if getattr(dialog, "taskbar_icon_dynamic_enabled_switch", None) is not None:
        dialog.taskbar_icon_dynamic_enabled_switch.enabled = enabled
    if getattr(dialog, "taskbar_icon_text_format_input", None) is not None:
        dialog.taskbar_icon_text_format_input.enabled = enabled


def create_general_tab(dialog):
    """Build the General tab for the provided settings dialog."""
    general_box = toga.Box(style=Pack(direction=COLUMN, margin=10))
    dialog.general_tab = general_box

    general_box.add(toga.Label("Update Interval (minutes):", style=Pack(margin_bottom=5)))
    dialog.update_interval_input = toga.NumberInput(
        value=dialog.current_settings.update_interval_minutes,
        style=Pack(margin_bottom=15),
    )
    dialog.update_interval_input.aria_label = "Update interval"
    dialog.update_interval_input.aria_description = (
        "Set how often the app should refresh weather data in minutes."
    )
    general_box.add(dialog.update_interval_input)

    aq_default = getattr(dialog.current_settings, "air_quality_notify_threshold", 3)
    try:
        aq_default = int(aq_default)
    except Exception:  # pragma: no cover - fallback path
        aq_default = 3

    general_box.add(
        toga.Label("Air Quality alert threshold (US AQI):", style=Pack(margin_bottom=5))
    )
    dialog.air_quality_threshold_input = toga.NumberInput(
        value=aq_default,
        style=Pack(margin_bottom=15),
        id="air_quality_threshold_input",
    )
    dialog.air_quality_threshold_input.aria_label = "Air quality threshold"
    dialog.air_quality_threshold_input.aria_description = (
        "Set the US AQI level at which air quality alerts should be triggered."
    )
    general_box.add(dialog.air_quality_threshold_input)

    dialog.option_container.content.append("General", general_box)


def create_display_tab(dialog):
    """Build the Display tab for visual presentation settings."""
    display_box = toga.Box(style=Pack(direction=COLUMN, margin=10))
    dialog.display_tab = display_box

    display_box.add(toga.Label("Temperature Display:", style=Pack(margin_bottom=5)))

    temp_unit_options = [
        "Fahrenheit only",
        "Celsius only",
        "Both (Fahrenheit and Celsius)",
    ]
    dialog.temperature_display_to_value = {
        "Fahrenheit only": "f",
        "Celsius only": "c",
        "Both (Fahrenheit and Celsius)": "both",
    }
    dialog.temperature_value_to_display = {
        value: key for key, value in dialog.temperature_display_to_value.items()
    }

    dialog.temperature_unit_selection = toga.Selection(
        items=temp_unit_options,
        style=Pack(margin_bottom=15),
        id="temperature_unit_selection",
    )
    dialog.temperature_unit_selection.aria_label = "Temperature unit selection"
    dialog.temperature_unit_selection.aria_description = (
        "Choose Fahrenheit, Celsius, or both for weather displays."
    )

    try:
        current_temp_unit = getattr(dialog.current_settings, "temperature_unit", "both")
        display_value = dialog.temperature_value_to_display.get(
            current_temp_unit,
            "Both (Fahrenheit and Celsius)",
        )
        dialog.temperature_unit_selection.value = display_value
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to set temperature unit selection: %s", exc)
        dialog.temperature_unit_selection.value = "Both (Fahrenheit and Celsius)"

    display_box.add(dialog.temperature_unit_selection)

    display_box.add(
        toga.Label(
            "Metric Visibility:",
            style=Pack(margin_bottom=8, font_weight="bold"),
        )
    )
    display_box.add(
        toga.Label(
            "Select which weather metrics to display:",
            style=Pack(margin_bottom=10, font_size=9),
        )
    )

    dialog.show_dewpoint_switch = toga.Switch(
        "Show dewpoint",
        value=getattr(dialog.current_settings, "show_dewpoint", True),
        style=Pack(margin_bottom=8),
        id="show_dewpoint_switch",
    )
    dialog.show_dewpoint_switch.aria_label = "Toggle dewpoint metric"
    dialog.show_dewpoint_switch.aria_description = (
        "Include the dewpoint measurement in the current conditions overview."
    )
    display_box.add(dialog.show_dewpoint_switch)

    dialog.show_visibility_switch = toga.Switch(
        "Show visibility",
        value=getattr(dialog.current_settings, "show_visibility", True),
        style=Pack(margin_bottom=8),
        id="show_visibility_switch",
    )
    dialog.show_visibility_switch.aria_label = "Toggle visibility metric"
    dialog.show_visibility_switch.aria_description = (
        "Include the horizontal visibility reading in the current conditions overview."
    )
    display_box.add(dialog.show_visibility_switch)

    dialog.show_uv_index_switch = toga.Switch(
        "Show UV index",
        value=getattr(dialog.current_settings, "show_uv_index", True),
        style=Pack(margin_bottom=8),
        id="show_uv_index_switch",
    )
    dialog.show_uv_index_switch.aria_label = "Toggle UV index metric"
    dialog.show_uv_index_switch.aria_description = (
        "Include the ultraviolet index rating in the current conditions overview."
    )
    display_box.add(dialog.show_uv_index_switch)

    dialog.show_pressure_trend_switch = toga.Switch(
        "Show pressure trend",
        value=getattr(dialog.current_settings, "show_pressure_trend", True),
        style=Pack(margin_bottom=15),
        id="show_pressure_trend_switch",
    )
    dialog.show_pressure_trend_switch.aria_label = "Toggle pressure trend metric"
    dialog.show_pressure_trend_switch.aria_description = (
        "Include the barometric pressure trend analysis in the current conditions overview."
    )
    display_box.add(dialog.show_pressure_trend_switch)

    dialog.show_detailed_forecast_switch = toga.Switch(
        "Show detailed forecast information",
        value=dialog.current_settings.show_detailed_forecast,
        style=Pack(margin_bottom=10),
        id="show_detailed_forecast_switch",
    )
    dialog.show_detailed_forecast_switch.aria_label = "Toggle detailed forecast"
    dialog.show_detailed_forecast_switch.aria_description = "Show extended details in weather forecasts including wind, precipitation, and other metrics."
    display_box.add(dialog.show_detailed_forecast_switch)

    # Time & Date Display Settings
    display_box.add(
        toga.Label(
            "Time & Date Display:",
            style=Pack(margin_top=10, margin_bottom=8, font_weight="bold"),
        )
    )
    display_box.add(
        toga.Label(
            "Configure how times are displayed in forecasts:",
            style=Pack(margin_bottom=10, font_size=9),
        )
    )

    # Time display mode selection
    display_box.add(toga.Label("Time zone display:", style=Pack(margin_bottom=5)))

    time_display_options = [
        "Local time only",
        "UTC time only",
        "Both (Local and UTC)",
    ]
    dialog.time_display_display_to_value = {
        "Local time only": "local",
        "UTC time only": "utc",
        "Both (Local and UTC)": "both",
    }
    dialog.time_display_value_to_display = {
        value: key for key, value in dialog.time_display_display_to_value.items()
    }

    dialog.time_display_mode_selection = toga.Selection(
        items=time_display_options,
        style=Pack(margin_bottom=12),
        id="time_display_mode_selection",
    )
    dialog.time_display_mode_selection.aria_label = "Time zone display selection"
    dialog.time_display_mode_selection.aria_description = (
        "Choose whether to display times in your local timezone, UTC, or both."
    )

    try:
        current_time_mode = getattr(dialog.current_settings, "time_display_mode", "local")
        display_value = dialog.time_display_value_to_display.get(
            current_time_mode,
            "Local time only",
        )
        dialog.time_display_mode_selection.value = display_value
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to set time display mode selection: %s", exc)
        dialog.time_display_mode_selection.value = "Local time only"

    display_box.add(dialog.time_display_mode_selection)

    # Time format switch (12-hour vs 24-hour)
    dialog.time_format_12hour_switch = toga.Switch(
        "Use 12-hour time format (e.g., 3:00 PM)",
        value=getattr(dialog.current_settings, "time_format_12hour", True),
        style=Pack(margin_bottom=10),
        id="time_format_12hour_switch",
    )
    dialog.time_format_12hour_switch.aria_label = "Toggle 12-hour time format"
    dialog.time_format_12hour_switch.aria_description = (
        "Enable to use 12-hour time format with AM/PM. Disable to use 24-hour format."
    )
    display_box.add(dialog.time_format_12hour_switch)

    # Show timezone suffix switch
    dialog.show_timezone_suffix_switch = toga.Switch(
        "Show timezone abbreviations (e.g., EST, UTC)",
        value=getattr(dialog.current_settings, "show_timezone_suffix", False),
        style=Pack(margin_bottom=15),
        id="show_timezone_suffix_switch",
    )
    dialog.show_timezone_suffix_switch.aria_label = "Toggle timezone abbreviations"
    dialog.show_timezone_suffix_switch.aria_description = (
        "Enable to append timezone abbreviations like EST or UTC to displayed times."
    )
    display_box.add(dialog.show_timezone_suffix_switch)

    # HTML Rendering Settings
    display_box.add(
        toga.Label(
            "Weather Display Rendering:",
            style=Pack(margin_top=10, margin_bottom=8, font_weight="bold"),
        )
    )
    display_box.add(
        toga.Label(
            "HTML rendering provides better screen reader navigation with headings.",
            style=Pack(margin_bottom=10, font_size=9),
        )
    )

    dialog.html_render_current_conditions_switch = toga.Switch(
        "Use HTML for current conditions (requires app restart)",
        value=getattr(dialog.current_settings, "html_render_current_conditions", True),
        style=Pack(margin_bottom=8),
        id="html_render_current_conditions_switch",
    )
    dialog.html_render_current_conditions_switch.aria_label = (
        "Toggle HTML rendering for current conditions"
    )
    dialog.html_render_current_conditions_switch.aria_description = (
        "Enable HTML rendering for better accessibility. "
        "Disable to use plain text display. Requires app restart."
    )
    display_box.add(dialog.html_render_current_conditions_switch)

    dialog.html_render_forecast_switch = toga.Switch(
        "Use HTML for forecast (requires app restart)",
        value=getattr(dialog.current_settings, "html_render_forecast", True),
        style=Pack(margin_bottom=8),
        id="html_render_forecast_switch",
    )
    dialog.html_render_forecast_switch.aria_label = "Toggle HTML rendering for forecast"
    dialog.html_render_forecast_switch.aria_description = (
        "Enable HTML rendering with semantic headings for screen reader navigation. "
        "Disable to use plain text display. Requires app restart."
    )
    display_box.add(dialog.html_render_forecast_switch)

    display_box.add(
        toga.Label(
            "Note: Changes to rendering settings require an app restart.",
            style=Pack(margin_top=5, margin_bottom=10, font_size=9, font_style="italic"),
        )
    )

    # Taskbar Icon Text Settings
    display_box.add(
        toga.Label(
            "Taskbar Icon Text:",
            style=Pack(margin_top=10, margin_bottom=8, font_weight="bold"),
        )
    )
    display_box.add(
        toga.Label(
            "Customize the text shown in the system tray icon tooltip.",
            style=Pack(margin_bottom=10, font_size=9),
        )
    )

    dialog.taskbar_icon_text_enabled_switch = toga.Switch(
        "Enable taskbar icon text",
        value=getattr(dialog.current_settings, "taskbar_icon_text_enabled", False),
        style=Pack(margin_bottom=8),
        id="taskbar_icon_text_enabled_switch",
        on_change=lambda w: _on_taskbar_icon_enabled_changed(dialog, w),
    )
    dialog.taskbar_icon_text_enabled_switch.aria_label = "Toggle taskbar icon text"
    dialog.taskbar_icon_text_enabled_switch.aria_description = (
        "Enable to show weather information in the system tray icon tooltip."
    )
    display_box.add(dialog.taskbar_icon_text_enabled_switch)

    dialog.taskbar_icon_dynamic_enabled_switch = toga.Switch(
        "Enable dynamic format switching",
        value=getattr(dialog.current_settings, "taskbar_icon_dynamic_enabled", True),
        style=Pack(margin_bottom=8),
        id="taskbar_icon_dynamic_enabled_switch",
    )
    dialog.taskbar_icon_dynamic_enabled_switch.aria_label = "Toggle dynamic format switching"
    dialog.taskbar_icon_dynamic_enabled_switch.aria_description = (
        "Enable to automatically adjust the format based on available weather data."
    )
    dialog.taskbar_icon_dynamic_enabled_switch.enabled = getattr(
        dialog.current_settings, "taskbar_icon_text_enabled", False
    )
    display_box.add(dialog.taskbar_icon_dynamic_enabled_switch)

    display_box.add(toga.Label("Custom format string:", style=Pack(margin_bottom=5)))
    dialog.taskbar_icon_text_format_input = toga.TextInput(
        value=getattr(dialog.current_settings, "taskbar_icon_text_format", "{temp} {condition}"),
        placeholder="{temp} {condition}",
        style=Pack(margin_bottom=5, width=300),
        id="taskbar_icon_text_format_input",
    )
    dialog.taskbar_icon_text_format_input.aria_label = "Taskbar icon format string"
    dialog.taskbar_icon_text_format_input.aria_description = (
        "Enter a custom format string for the taskbar icon tooltip. "
        "Use placeholders like {temp}, {condition}, {humidity}, etc."
    )
    dialog.taskbar_icon_text_format_input.enabled = getattr(
        dialog.current_settings, "taskbar_icon_text_enabled", False
    )
    display_box.add(dialog.taskbar_icon_text_format_input)

    dialog.taskbar_format_validation_label = toga.Label(
        "",
        style=Pack(margin_bottom=5, font_size=9),
    )
    display_box.add(dialog.taskbar_format_validation_label)

    display_box.add(
        toga.Label(
            "Available variables: {temp}, {condition}, {humidity}, {wind}, {wind_speed}, "
            "{wind_dir}, {feels_like}, {pressure}, {uv}, {visibility}, {precip}, {precip_chance}",
            style=Pack(margin_bottom=5, font_size=9, font_style="italic"),
        )
    )
    display_box.add(
        toga.Label(
            "Example: '{temp} {condition}' shows '72F Partly Cloudy'",
            style=Pack(margin_bottom=10, font_size=9, font_style="italic"),
        )
    )

    dialog.option_container.content.append("Display", display_box)


def create_data_sources_tab(dialog):
    """Build the Data Sources tab for the provided settings dialog."""
    data_sources_box = toga.Box(style=Pack(direction=COLUMN, margin=10))
    dialog.data_sources_container = data_sources_box
    dialog.data_sources_tab = data_sources_box

    data_sources_box.add(toga.Label("Weather Data Source:", style=Pack(margin_bottom=5)))

    data_source_options = [
        "Automatic (merges all available sources)",
        "National Weather Service (NWS)",
        "Open-Meteo (International)",
        "Visual Crossing (Global, requires API key)",
    ]
    dialog.data_source_display_to_value = {
        "Automatic (merges all available sources)": "auto",
        "National Weather Service (NWS)": "nws",
        "Open-Meteo (International)": "openmeteo",
        "Visual Crossing (Global, requires API key)": "visualcrossing",
    }
    dialog.data_source_value_to_display = {
        value: key for key, value in dialog.data_source_display_to_value.items()
    }

    dialog.data_source_selection = toga.Selection(
        items=data_source_options,
        style=Pack(margin_bottom=15),
        id="data_source_selection",
        on_change=dialog._on_data_source_changed,
    )
    dialog.data_source_selection.aria_label = "Weather data source selection"
    dialog.data_source_selection.aria_description = (
        "Select the provider used for fetching weather data."
    )
    data_sources_box.add(dialog.data_source_selection)

    try:
        current_data_source = getattr(dialog.current_settings, "data_source", "auto")
        display_value = dialog.data_source_value_to_display.get(
            current_data_source,
            data_source_options[0],
        )
        dialog.data_source_selection.value = display_value
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to set data source selection: %s", exc)
        dialog.data_source_selection.value = data_source_options[0]

    dialog.visual_crossing_config_box = toga.Box(style=Pack(direction=COLUMN))

    dialog.visual_crossing_config_box.add(
        toga.Label(
            "Visual Crossing API Configuration:",
            style=Pack(margin_top=15, margin_bottom=5, font_weight="bold"),
        )
    )

    dialog.visual_crossing_config_box.add(toga.Label("API Key:", style=Pack(margin_bottom=5)))
    dialog.visual_crossing_api_key_input = toga.PasswordInput(
        value=getattr(dialog.current_settings, "visual_crossing_api_key", ""),
        placeholder="Enter your Visual Crossing API key",
        style=Pack(margin_bottom=10),
        id="visual_crossing_api_key_input",
        # Reminder: never log or echo this API key; the widget masks the value intentionally.
    )
    dialog.visual_crossing_api_key_input.aria_label = "Visual Crossing API key input"
    dialog.visual_crossing_api_key_input.aria_description = (
        "Enter the Visual Crossing API key to enable that weather data source."
    )
    dialog.visual_crossing_config_box.add(dialog.visual_crossing_api_key_input)

    api_key_buttons_row = toga.Box(style=Pack(direction=ROW, margin_bottom=15))

    dialog.get_api_key_button = toga.Button(
        "Get Free API Key",
        on_press=dialog._on_get_visual_crossing_api_key,
        style=Pack(margin_right=10, width=150),
        id="get_visual_crossing_api_key_button",
    )
    api_key_buttons_row.add(dialog.get_api_key_button)

    dialog.validate_api_key_button = toga.Button(
        "Validate API Key",
        on_press=dialog._on_validate_visual_crossing_api_key,
        style=Pack(width=150),
        id="validate_visual_crossing_api_key_button",
    )
    api_key_buttons_row.add(dialog.validate_api_key_button)

    dialog.visual_crossing_config_box.add(api_key_buttons_row)

    data_sources_box.add(dialog.visual_crossing_config_box)

    # Source Priority Configuration (for Auto mode) - wrapped in a container for visibility control
    dialog.source_priority_config_box = toga.Box(style=Pack(direction=COLUMN))

    dialog.source_priority_config_box.add(
        toga.Label(
            "Source Priority (Auto Mode):",
            style=Pack(margin_top=20, margin_bottom=5, font_weight="bold"),
        )
    )
    dialog.source_priority_config_box.add(
        toga.Label(
            "When using Auto mode, data is merged from multiple sources in priority order.",
            style=Pack(margin_bottom=10, font_size=9),
        )
    )

    # US locations priority
    dialog.source_priority_config_box.add(
        toga.Label("US Locations Priority:", style=Pack(margin_bottom=5))
    )

    us_priority_options = [
        "NWS → Open-Meteo → Visual Crossing (Default)",
        "NWS → Visual Crossing → Open-Meteo",
        "Open-Meteo → NWS → Visual Crossing",
    ]
    dialog.us_priority_display_to_value = {
        "NWS → Open-Meteo → Visual Crossing (Default)": ["nws", "openmeteo", "visualcrossing"],
        "NWS → Visual Crossing → Open-Meteo": ["nws", "visualcrossing", "openmeteo"],
        "Open-Meteo → NWS → Visual Crossing": ["openmeteo", "nws", "visualcrossing"],
    }
    dialog.us_priority_value_to_display = {
        tuple(v): k for k, v in dialog.us_priority_display_to_value.items()
    }

    dialog.us_priority_selection = toga.Selection(
        items=us_priority_options,
        style=Pack(margin_bottom=10),
        id="us_priority_selection",
    )
    dialog.us_priority_selection.aria_label = "US locations source priority"
    dialog.us_priority_selection.aria_description = (
        "Select the order in which weather sources are prioritized for US locations. "
        "Higher priority sources are used first when merging data."
    )

    # Set current value
    try:
        current_us_priority = getattr(
            dialog.current_settings, "source_priority_us", ["nws", "openmeteo", "visualcrossing"]
        )
        display_value = dialog.us_priority_value_to_display.get(
            tuple(current_us_priority), us_priority_options[0]
        )
        dialog.us_priority_selection.value = display_value
    except Exception as exc:
        logger.warning("Failed to set US priority selection: %s", exc)
        dialog.us_priority_selection.value = us_priority_options[0]

    dialog.source_priority_config_box.add(dialog.us_priority_selection)

    # International locations priority
    dialog.source_priority_config_box.add(
        toga.Label("International Locations Priority:", style=Pack(margin_bottom=5))
    )

    intl_priority_options = [
        "Open-Meteo → Visual Crossing (Default)",
        "Visual Crossing → Open-Meteo",
    ]
    dialog.intl_priority_display_to_value = {
        "Open-Meteo → Visual Crossing (Default)": ["openmeteo", "visualcrossing"],
        "Visual Crossing → Open-Meteo": ["visualcrossing", "openmeteo"],
    }
    dialog.intl_priority_value_to_display = {
        tuple(v): k for k, v in dialog.intl_priority_display_to_value.items()
    }

    dialog.intl_priority_selection = toga.Selection(
        items=intl_priority_options,
        style=Pack(margin_bottom=10),
        id="intl_priority_selection",
    )
    dialog.intl_priority_selection.aria_label = "International locations source priority"
    dialog.intl_priority_selection.aria_description = (
        "Select the order in which weather sources are prioritized for international locations. "
        "NWS is not available outside the US."
    )

    # Set current value
    try:
        current_intl_priority = getattr(
            dialog.current_settings,
            "source_priority_international",
            ["openmeteo", "visualcrossing"],
        )
        display_value = dialog.intl_priority_value_to_display.get(
            tuple(current_intl_priority), intl_priority_options[0]
        )
        dialog.intl_priority_selection.value = display_value
    except Exception as exc:
        logger.warning("Failed to set international priority selection: %s", exc)
        dialog.intl_priority_selection.value = intl_priority_options[0]

    dialog.source_priority_config_box.add(dialog.intl_priority_selection)

    dialog.source_priority_config_box.add(
        toga.Label(
            "Note: Higher priority sources provide the primary data. Lower priority sources "
            "fill in missing fields and provide additional details.",
            style=Pack(margin_top=5, margin_bottom=10, font_size=9, font_style="italic"),
        )
    )

    # Add the priority config box to the main container
    data_sources_box.add(dialog.source_priority_config_box)

    # Update visibility based on selected data source
    dialog._update_visual_crossing_config_visibility()
    dialog._update_priority_settings_visibility()

    dialog.option_container.content.append("Data Sources", data_sources_box)


def create_audio_tab(dialog):
    """Build the Audio tab for the provided settings dialog."""
    audio_box = toga.Box(style=Pack(direction=COLUMN, margin=10))
    dialog.audio_tab = audio_box

    audio_box.add(toga.Label("Sound Notifications:", style=Pack(font_weight="bold")))

    dialog.sound_enabled_switch = toga.Switch(
        "Enable Sounds",
        value=getattr(dialog.current_settings, "sound_enabled", True),
        style=Pack(margin_top=10, margin_bottom=10),
        id="sound_enabled_switch",
        on_change=dialog._on_sound_enabled_changed,
    )
    audio_box.add(dialog.sound_enabled_switch)

    load_sound_packs(dialog)
    audio_box.add(toga.Label("Active sound pack:", style=Pack(margin_bottom=5)))

    dialog.sound_pack_selection = toga.Selection(
        items=dialog.sound_pack_options,
        style=Pack(margin_bottom=10, width=200),
        id="sound_pack_selection",
    )
    dialog.sound_pack_selection.aria_label = "Sound pack selection"
    dialog.sound_pack_selection.aria_description = (
        "Choose the notification sound pack used for alerts."
    )
    dialog.sound_pack_selection.enabled = bool(dialog.sound_enabled_switch.value)

    current_pack = getattr(dialog.current_settings, "sound_pack", "default")
    display_value = next(
        (name for name, pack_id in dialog.sound_pack_map.items() if pack_id == current_pack),
        dialog.sound_pack_options[0] if dialog.sound_pack_options else "Default",
    )
    if dialog.sound_pack_options:
        dialog.sound_pack_selection.value = display_value
    audio_box.add(dialog.sound_pack_selection)

    dialog.manage_soundpacks_button = toga.Button(
        "Manage Sound Packs...",
        on_press=dialog._on_manage_soundpacks,
        style=Pack(margin_bottom=10, width=180),
    )
    audio_box.add(dialog.manage_soundpacks_button)

    dialog.option_container.content.append("Audio", audio_box)


def create_updates_tab(dialog):
    """Build the Updates tab for the provided settings dialog."""
    updates_box = toga.Box(style=Pack(direction=COLUMN, margin=10))
    dialog.updates_tab = updates_box

    dialog.auto_update_switch = toga.Switch(
        "Check for updates automatically",
        value=getattr(dialog.current_settings, "auto_update_enabled", True),
        style=Pack(margin_bottom=10),
        id="auto_update_switch",
    )
    dialog.auto_update_switch.aria_label = "Automatic update checks toggle"
    dialog.auto_update_switch.aria_description = (
        "Enable to allow AccessiWeather to check for updates in the background."
    )
    updates_box.add(dialog.auto_update_switch)

    updates_box.add(toga.Label("Update Channel:", style=Pack(margin_bottom=5)))

    update_channel_options = [
        "Stable (Production releases only)",
        "Development (Latest features, may be unstable)",
    ]
    dialog.update_channel_selection = toga.Selection(
        items=update_channel_options,
        style=Pack(margin_bottom=10),
        id="update_channel_selection",
        on_change=dialog._on_update_channel_changed,
    )
    dialog.update_channel_selection.aria_label = "Update channel selection"
    dialog.update_channel_selection.aria_description = (
        "Choose which release channel to follow for application updates."
    )

    current_channel = getattr(dialog.current_settings, "update_channel", "stable")
    if current_channel == "dev" or current_channel == "beta":
        dialog.update_channel_selection.value = "Development (Latest features, may be unstable)"
    else:
        dialog.update_channel_selection.value = "Stable (Production releases only)"

    updates_box.add(dialog.update_channel_selection)

    dialog.channel_description_label = toga.Label(
        "",
        style=Pack(margin_bottom=15, font_size=11, font_style="italic"),
    )
    updates_box.add(dialog.channel_description_label)

    dialog._update_channel_description()

    updates_box.add(toga.Label("Check Interval (hours):", style=Pack(margin_bottom=5)))
    dialog.update_check_interval_input = toga.NumberInput(
        value=getattr(dialog.current_settings, "update_check_interval_hours", 24),
        style=Pack(margin_bottom=15),
        id="update_check_interval_input",
    )
    updates_box.add(dialog.update_check_interval_input)

    dialog.check_updates_button = toga.Button(
        "Check for Updates Now",
        on_press=dialog._on_check_updates,
        style=Pack(margin_bottom=10),
        id="check_updates_button",
    )
    updates_box.add(dialog.check_updates_button)

    dialog.update_status_label = toga.Label(
        "Ready to check for updates",
        style=Pack(margin_bottom=10, font_style="italic"),
    )
    updates_box.add(dialog.update_status_label)

    dialog.last_check_label = toga.Label(
        "Never checked for updates",
        style=Pack(font_size=11, margin_bottom=10),
    )
    updates_box.add(dialog.last_check_label)

    dialog.option_container.content.append("Updates", updates_box)


def create_advanced_tab(dialog):
    """Build the Advanced tab for the provided settings dialog."""
    advanced_box = toga.Box(style=Pack(direction=COLUMN, margin=10))
    dialog.advanced_tab = advanced_box

    dialog.minimize_to_tray_switch = toga.Switch(
        "Minimize to notification area when closing",
        value=dialog.current_settings.minimize_to_tray,
        style=Pack(margin_bottom=10),
        id="minimize_to_tray_switch",
    )
    advanced_box.add(dialog.minimize_to_tray_switch)

    dialog.startup_enabled_switch = toga.Switch(
        "Launch automatically at startup",
        value=getattr(dialog.current_settings, "startup_enabled", False),
        style=Pack(margin_bottom=10),
        id="startup_enabled_switch",
    )
    advanced_box.add(dialog.startup_enabled_switch)

    dialog.weather_history_enabled_switch = toga.Switch(
        "Enable weather history comparisons",
        value=getattr(dialog.current_settings, "weather_history_enabled", True),
        style=Pack(margin_bottom=10),
        id="weather_history_enabled_switch",
    )
    dialog.weather_history_enabled_switch.aria_label = "Weather history comparisons toggle"
    dialog.weather_history_enabled_switch.aria_description = "Enable or disable comparing current weather with historical data from Open-Meteo archive API"
    advanced_box.add(dialog.weather_history_enabled_switch)

    dialog.debug_mode_switch = toga.Switch(
        "Enable Debug Mode",
        value=getattr(dialog.current_settings, "debug_mode", False),
        style=Pack(margin_bottom=10),
        id="debug_mode_switch",
    )
    advanced_box.add(dialog.debug_mode_switch)

    advanced_box.add(
        toga.Label(
            "Reset Configuration",
            style=Pack(margin_top=20, font_weight="bold"),
        )
    )
    advanced_box.add(
        toga.Label(
            "Restore all settings to their default values.",
            style=Pack(margin_top=5, margin_bottom=5, font_style="italic"),
        )
    )
    dialog.reset_defaults_button = toga.Button(
        "Reset all settings to defaults",
        on_press=dialog._on_reset_to_defaults,
        style=Pack(margin_top=5, width=240),
        id="reset_defaults_button",
    )
    advanced_box.add(dialog.reset_defaults_button)

    advanced_box.add(toga.Label("Full Data Reset", style=Pack(margin_top=20, font_weight="bold")))
    advanced_box.add(
        toga.Label(
            "Reset all application data: settings, locations, caches, and alert state.",
            style=Pack(margin_top=5, margin_bottom=5, font_style="italic"),
        )
    )
    dialog.full_reset_button = toga.Button(
        "Reset all app data (settings, locations, caches)",
        on_press=dialog._on_full_reset,
        style=Pack(margin_top=5, width=340),
        id="full_reset_button",
    )
    advanced_box.add(dialog.full_reset_button)

    advanced_box.add(
        toga.Label("Configuration Files", style=Pack(margin_top=20, font_weight="bold"))
    )
    advanced_box.add(
        toga.Label(
            "Open the configuration directory in your file explorer.",
            style=Pack(margin_top=5, margin_bottom=5, font_style="italic"),
        )
    )
    dialog.open_config_dir_button = toga.Button(
        "Open config directory",
        on_press=dialog._on_open_config_dir,
        style=Pack(margin_top=5, width=240),
        id="open_config_dir_button",
    )
    advanced_box.add(dialog.open_config_dir_button)

    advanced_box.add(toga.Label("Sound Pack Files", style=Pack(margin_top=20, font_weight="bold")))
    advanced_box.add(
        toga.Label(
            "Open the folder where your sound packs are stored.",
            style=Pack(margin_top=5, margin_bottom=5, font_style="italic"),
        )
    )
    dialog.open_soundpacks_dir_button = toga.Button(
        "Open sound packs folder",
        on_press=dialog._on_open_soundpacks_dir,
        style=Pack(margin_top=5, width=260),
        id="open_soundpacks_dir_button",
    )
    advanced_box.add(dialog.open_soundpacks_dir_button)

    dialog.option_container.content.append("Advanced", advanced_box)


def load_sound_packs(dialog):
    """Load available sound packs and attach them to the dialog."""
    dialog.sound_pack_options = []
    dialog.sound_pack_map = {}

    soundpacks_dir = Path(__file__).parent.parent / "soundpacks"

    try:
        if soundpacks_dir.exists():
            for pack_dir in soundpacks_dir.iterdir():
                if pack_dir.is_dir() and (pack_dir / "pack.json").exists():
                    try:
                        with open(pack_dir / "pack.json", encoding="utf-8") as handle:
                            meta = json.load(handle)
                    except Exception as exc:  # pragma: no cover - invalid pack data
                        logger.warning("Failed to load sound pack at %s: %s", pack_dir, exc)
                        continue

                    display_name = meta.get("name", pack_dir.name)
                    dialog.sound_pack_options.append(display_name)
                    dialog.sound_pack_map[display_name] = pack_dir.name
    except Exception as exc:  # pragma: no cover - filesystem failure
        logger.warning("Error scanning soundpacks: %s", exc)

    if not dialog.sound_pack_options:
        dialog.sound_pack_options = ["Default"]
        dialog.sound_pack_map = {"Default": "default"}


def create_notifications_tab(dialog):
    """Build the Notifications tab for alert configuration."""
    notifications_box = toga.Box(style=Pack(direction=COLUMN, margin=10))
    dialog.notifications_tab = notifications_box

    # Title and description
    notifications_box.add(
        toga.Label(
            "Alert Notification Settings",
            style=Pack(margin_bottom=5, font_weight="bold", font_size=12),
        )
    )
    notifications_box.add(
        toga.Label(
            "Configure which weather alerts trigger notifications based on severity.",
            style=Pack(margin_bottom=15, font_size=9),
        )
    )

    # Master enable alerts switch
    dialog.enable_alerts_switch = toga.Switch(
        "Enable weather alerts",
        value=dialog.current_settings.enable_alerts,
        style=Pack(margin_bottom=10),
        id="enable_alerts_switch",
    )
    dialog.enable_alerts_switch.aria_label = "Toggle weather alerts"
    dialog.enable_alerts_switch.aria_description = (
        "Master control to enable or disable all weather alert functionality."
    )
    notifications_box.add(dialog.enable_alerts_switch)

    # Alert notifications enabled master switch
    dialog.alert_notifications_enabled_switch = toga.Switch(
        "Enable alert notifications",
        value=getattr(dialog.current_settings, "alert_notifications_enabled", True),
        style=Pack(margin_bottom=15),
        id="alert_notifications_enabled_switch",
    )
    dialog.alert_notifications_enabled_switch.aria_label = "Toggle alert notifications"
    dialog.alert_notifications_enabled_switch.aria_description = (
        "Master control to enable or disable all weather alert notifications."
    )
    notifications_box.add(dialog.alert_notifications_enabled_switch)

    # Severity level section
    notifications_box.add(
        toga.Label(
            "Alert Severity Levels:",
            style=Pack(margin_bottom=8, font_weight="bold"),
        )
    )
    notifications_box.add(
        toga.Label(
            "Select which severity levels should trigger notifications:",
            style=Pack(margin_bottom=10, font_size=9),
        )
    )

    # Extreme severity switch
    dialog.alert_notify_extreme_switch = toga.Switch(
        "Extreme - Life-threatening events (e.g., Tornado Warning)",
        value=getattr(dialog.current_settings, "alert_notify_extreme", True),
        style=Pack(margin_bottom=8),
        id="alert_notify_extreme_switch",
    )
    dialog.alert_notify_extreme_switch.aria_label = "Notify for extreme severity alerts"
    dialog.alert_notify_extreme_switch.aria_description = "Receive notifications for extreme severity weather events that pose life-threatening danger."
    notifications_box.add(dialog.alert_notify_extreme_switch)

    # Severe severity switch
    dialog.alert_notify_severe_switch = toga.Switch(
        "Severe - Significant hazards (e.g., Severe Thunderstorm Warning)",
        value=getattr(dialog.current_settings, "alert_notify_severe", True),
        style=Pack(margin_bottom=8),
        id="alert_notify_severe_switch",
    )
    dialog.alert_notify_severe_switch.aria_label = "Notify for severe severity alerts"
    dialog.alert_notify_severe_switch.aria_description = (
        "Receive notifications for severe weather events that pose significant hazards."
    )
    notifications_box.add(dialog.alert_notify_severe_switch)

    # Moderate severity switch
    dialog.alert_notify_moderate_switch = toga.Switch(
        "Moderate - Potentially hazardous (e.g., Winter Weather Advisory)",
        value=getattr(dialog.current_settings, "alert_notify_moderate", True),
        style=Pack(margin_bottom=8),
        id="alert_notify_moderate_switch",
    )
    dialog.alert_notify_moderate_switch.aria_label = "Notify for moderate severity alerts"
    dialog.alert_notify_moderate_switch.aria_description = (
        "Receive notifications for moderate severity weather events that may be hazardous."
    )
    notifications_box.add(dialog.alert_notify_moderate_switch)

    # Minor severity switch
    dialog.alert_notify_minor_switch = toga.Switch(
        "Minor - Low impact events (e.g., Frost Advisory, Fog Advisory)",
        value=getattr(dialog.current_settings, "alert_notify_minor", False),
        style=Pack(margin_bottom=8),
        id="alert_notify_minor_switch",
    )
    dialog.alert_notify_minor_switch.aria_label = "Notify for minor severity alerts"
    dialog.alert_notify_minor_switch.aria_description = (
        "Receive notifications for minor severity weather events with low impact."
    )
    notifications_box.add(dialog.alert_notify_minor_switch)

    # Unknown severity switch
    dialog.alert_notify_unknown_switch = toga.Switch(
        "Unknown - Uncategorized alerts",
        value=getattr(dialog.current_settings, "alert_notify_unknown", False),
        style=Pack(margin_bottom=15),
        id="alert_notify_unknown_switch",
    )
    dialog.alert_notify_unknown_switch.aria_label = "Notify for unknown severity alerts"
    dialog.alert_notify_unknown_switch.aria_description = (
        "Receive notifications for alerts without a defined severity level."
    )
    notifications_box.add(dialog.alert_notify_unknown_switch)

    # Cooldown and rate limiting section
    notifications_box.add(
        toga.Label(
            "Rate Limiting:",
            style=Pack(margin_bottom=8, margin_top=10, font_weight="bold"),
        )
    )
    notifications_box.add(
        toga.Label(
            "Prevent notification spam by setting cooldown periods:",
            style=Pack(margin_bottom=10, font_size=9),
        )
    )

    # Global cooldown
    notifications_box.add(
        toga.Label(
            "Global cooldown (minutes):",
            style=Pack(margin_bottom=5),
        )
    )
    notifications_box.add(
        toga.Label(
            "Minimum time between any notifications",
            style=Pack(margin_bottom=5, font_size=9),
        )
    )
    dialog.alert_global_cooldown_input = toga.NumberInput(
        value=getattr(dialog.current_settings, "alert_global_cooldown_minutes", 5),
        min=0,
        max=60,
        style=Pack(margin_bottom=12),
        id="alert_global_cooldown_input",
    )
    dialog.alert_global_cooldown_input.aria_label = "Global notification cooldown"
    dialog.alert_global_cooldown_input.aria_description = (
        "Set the minimum number of minutes to wait between any alert notifications, "
        "from 0 to 60 minutes. This prevents notification spam across all alerts."
    )
    notifications_box.add(dialog.alert_global_cooldown_input)

    # Per-alert cooldown
    notifications_box.add(
        toga.Label(
            "Per-alert cooldown (minutes):",
            style=Pack(margin_bottom=5),
        )
    )
    notifications_box.add(
        toga.Label(
            "Minimum time between notifications for the same alert",
            style=Pack(margin_bottom=5, font_size=9),
        )
    )
    dialog.alert_per_alert_cooldown_input = toga.NumberInput(
        value=getattr(dialog.current_settings, "alert_per_alert_cooldown_minutes", 60),
        min=0,
        max=1440,
        style=Pack(margin_bottom=12),
        id="alert_per_alert_cooldown_input",
    )
    dialog.alert_per_alert_cooldown_input.aria_label = "Per-alert notification cooldown"
    dialog.alert_per_alert_cooldown_input.aria_description = (
        "Set the minimum number of minutes to wait before notifying about the same alert again, "
        "from 0 to 1440 minutes (24 hours). This prevents repeated notifications for unchanged alerts."
    )
    notifications_box.add(dialog.alert_per_alert_cooldown_input)

    # Alert freshness window
    notifications_box.add(
        toga.Label(
            "Alert freshness window (minutes):",
            style=Pack(margin_bottom=5),
        )
    )
    notifications_box.add(
        toga.Label(
            "Bypass per-alert cooldown for alerts issued within this window",
            style=Pack(margin_bottom=5, font_size=9),
        )
    )
    dialog.alert_freshness_window_input = toga.NumberInput(
        value=getattr(dialog.current_settings, "alert_freshness_window_minutes", 15),
        min=0,
        max=120,
        style=Pack(margin_bottom=12),
        id="alert_freshness_window_input",
    )
    dialog.alert_freshness_window_input.aria_label = "Alert freshness window"
    dialog.alert_freshness_window_input.aria_description = (
        "Set the time window in minutes for treating alerts as fresh. Alerts issued within this "
        "window will bypass per-alert cooldown if never notified before. Range: 0 to 120 minutes. "
        "Recommended: 15-30 minutes for time-sensitive alerts."
    )
    notifications_box.add(dialog.alert_freshness_window_input)

    # Max notifications per hour
    notifications_box.add(
        toga.Label(
            "Maximum notifications per hour:",
            style=Pack(margin_bottom=5),
        )
    )
    notifications_box.add(
        toga.Label(
            "Total notification limit per hour",
            style=Pack(margin_bottom=5, font_size=9),
        )
    )
    dialog.alert_max_notifications_input = toga.NumberInput(
        value=getattr(dialog.current_settings, "alert_max_notifications_per_hour", 10),
        min=1,
        max=100,
        style=Pack(margin_bottom=15),
        id="alert_max_notifications_input",
    )
    dialog.alert_max_notifications_input.aria_label = "Maximum notifications per hour"
    dialog.alert_max_notifications_input.aria_description = (
        "Set the total number of alert notifications allowed per hour, from 1 to 100. "
        "Uses token bucket rate limiting to prevent notification storms while allowing bursts."
    )
    notifications_box.add(dialog.alert_max_notifications_input)

    # Add the tab to the option container
    dialog.option_container.content.append("Notifications", notifications_box)
