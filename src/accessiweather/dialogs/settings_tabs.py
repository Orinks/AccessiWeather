"""Tab builder helpers for the settings dialog UI."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

logger = logging.getLogger(__name__)


def create_general_tab(dialog):
    """Build the General tab for the provided settings dialog."""
    general_box = toga.Box(style=Pack(direction=COLUMN, margin=10))
    dialog.general_tab = general_box

    general_box.add(toga.Label("Temperature Display:", style=Pack(margin_bottom=5)))

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

    general_box.add(dialog.temperature_unit_selection)

    general_box.add(toga.Label("Update Interval (minutes):", style=Pack(margin_bottom=5)))
    dialog.update_interval_input = toga.NumberInput(
        value=dialog.current_settings.update_interval_minutes,
        style=Pack(margin_bottom=15),
    )
    general_box.add(dialog.update_interval_input)

    dialog.show_detailed_forecast_switch = toga.Switch(
        "Show detailed forecast information",
        value=dialog.current_settings.show_detailed_forecast,
        style=Pack(margin_bottom=10),
        id="show_detailed_forecast_switch",
    )
    general_box.add(dialog.show_detailed_forecast_switch)

    dialog.enable_alerts_switch = toga.Switch(
        "Enable weather alerts",
        value=dialog.current_settings.enable_alerts,
        style=Pack(margin_bottom=10),
        id="enable_alerts_switch",
    )
    general_box.add(dialog.enable_alerts_switch)

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
    general_box.add(dialog.air_quality_threshold_input)

    dialog.option_container.content.append("General", general_box)


def create_data_sources_tab(dialog):
    """Build the Data Sources tab for the provided settings dialog."""
    data_sources_box = toga.Box(style=Pack(direction=COLUMN, margin=10))
    dialog.data_sources_container = data_sources_box
    dialog.data_sources_tab = data_sources_box

    data_sources_box.add(toga.Label("Weather Data Source:", style=Pack(margin_bottom=5)))

    data_source_options = [
        "Automatic (NWS for US, Open-Meteo for non-US)",
        "National Weather Service (NWS)",
        "Open-Meteo (International)",
        "Visual Crossing (Global, requires API key)",
    ]
    dialog.data_source_display_to_value = {
        "Automatic (NWS for US, Open-Meteo for non-US)": "auto",
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

    dialog._update_visual_crossing_visibility()

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
        "Beta (Pre-release testing)",
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
    if current_channel == "dev":
        dialog.update_channel_selection.value = "Development (Latest features, may be unstable)"
    elif current_channel == "beta":
        dialog.update_channel_selection.value = "Beta (Pre-release testing)"
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
