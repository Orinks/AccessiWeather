"""Settings dialog for application configuration using wxPython."""

from __future__ import annotations

import json
import logging
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)

API_KEYS_TRANSFER_NOTE = (
    "API keys are not included here. API keys stay in this machine's secure keyring by "
    "default. To transfer them, use 'Export API keys (encrypted)' and then "
    "'Import API keys (encrypted)'."
)


class SettingsDialogSimple(wx.Dialog):
    """Comprehensive settings dialog matching Toga version functionality."""

    def __init__(self, parent, app: AccessiWeatherApp):
        """Initialize the settings dialog."""
        super().__init__(
            parent,
            title="Settings",
            size=(600, 550),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.app = app
        self.config_manager = app.config_manager
        self._controls = {}
        self._selected_specific_model: str | None = None

        self._create_ui()
        self._load_settings()
        self._setup_accessibility()

    def _create_ui(self):
        """Create the dialog UI."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Notebook for tabs
        self.notebook = wx.Notebook(self)

        # Create all tab panels
        self._create_general_tab()
        self._create_display_tab()
        self._create_data_sources_tab()
        self._create_notifications_tab()
        self._create_audio_tab()
        self._create_updates_tab()
        self._create_ai_tab()
        self._create_advanced_tab()

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        ok_btn = wx.Button(self, wx.ID_OK, "OK")
        ok_btn.Bind(wx.EVT_BUTTON, self._on_ok)

        button_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        button_sizer.Add(ok_btn, 0)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(main_sizer)

    def _create_general_tab(self):
        """Create the general settings tab."""
        panel = wx.ScrolledWindow(self.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Update interval
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(
            wx.StaticText(panel, label="Update Interval (minutes):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["update_interval"] = wx.SpinCtrl(panel, min=1, max=120, initial=10)
        row1.Add(self._controls["update_interval"], 0)
        sizer.Add(row1, 0, wx.ALL, 5)

        # Show Nationwide location (only available with Auto or NWS data source)
        self._controls["show_nationwide"] = wx.CheckBox(
            panel, label="Show Nationwide location (requires Auto or NWS data source)"
        )
        sizer.Add(self._controls["show_nationwide"], 0, wx.ALL, 5)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(wx.StaticText(panel, label="Taskbar icon text:"), 0, wx.LEFT | wx.TOP, 5)

        self._controls["taskbar_icon_text_enabled"] = wx.CheckBox(
            panel, label="Show weather text on tray icon"
        )
        self._controls["taskbar_icon_text_enabled"].Bind(
            wx.EVT_CHECKBOX,
            self._on_taskbar_icon_text_enabled_changed,
        )
        sizer.Add(self._controls["taskbar_icon_text_enabled"], 0, wx.ALL, 5)

        self._controls["taskbar_icon_dynamic_enabled"] = wx.CheckBox(
            panel, label="Update tray text dynamically"
        )
        sizer.Add(self._controls["taskbar_icon_dynamic_enabled"], 0, wx.LEFT | wx.BOTTOM, 15)

        row_taskbar_format = wx.BoxSizer(wx.HORIZONTAL)
        row_taskbar_format.Add(
            wx.StaticText(panel, label="Tray text format:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["taskbar_icon_text_format"] = wx.TextCtrl(panel, size=(280, -1))
        row_taskbar_format.Add(self._controls["taskbar_icon_text_format"], 1)
        sizer.Add(row_taskbar_format, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 15)

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "General")

    def _create_display_tab(self):
        """Create the display settings tab."""
        panel = wx.ScrolledWindow(self.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Temperature Display Section
        sizer.Add(
            wx.StaticText(panel, label="Temperature Display:"),
            0,
            wx.ALL | wx.EXPAND,
            5,
        )
        self._controls["temp_unit"] = wx.Choice(
            panel,
            choices=[
                "Fahrenheit only",
                "Celsius only",
                "Both (Fahrenheit and Celsius)",
            ],
        )
        sizer.Add(self._controls["temp_unit"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # Metric Visibility Section
        sizer.Add(
            wx.StaticText(panel, label="Metric Visibility:", style=wx.BOLD),
            0,
            wx.ALL,
            5,
        )
        sizer.Add(
            wx.StaticText(panel, label="Select which weather metrics to display:"),
            0,
            wx.LEFT | wx.BOTTOM,
            5,
        )

        self._controls["show_dewpoint"] = wx.CheckBox(panel, label="Show dewpoint")
        sizer.Add(self._controls["show_dewpoint"], 0, wx.LEFT, 10)

        self._controls["show_visibility"] = wx.CheckBox(panel, label="Show visibility")
        sizer.Add(self._controls["show_visibility"], 0, wx.LEFT, 10)

        self._controls["show_uv_index"] = wx.CheckBox(panel, label="Show UV index")
        sizer.Add(self._controls["show_uv_index"], 0, wx.LEFT, 10)

        self._controls["show_pressure_trend"] = wx.CheckBox(panel, label="Show pressure trend")
        sizer.Add(self._controls["show_pressure_trend"], 0, wx.LEFT, 10)

        self._controls["detailed_forecast"] = wx.CheckBox(
            panel, label="Show detailed forecast information"
        )
        sizer.Add(self._controls["detailed_forecast"], 0, wx.LEFT | wx.TOP, 10)

        row_forecast_duration = wx.BoxSizer(wx.HORIZONTAL)
        row_forecast_duration.Add(
            wx.StaticText(panel, label="Forecast duration:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["forecast_duration_days"] = wx.Choice(
            panel,
            choices=[
                "3 days",
                "5 days",
                "7 days (default)",
                "10 days",
                "14 days",
                "15 days",
            ],
        )
        row_forecast_duration.Add(self._controls["forecast_duration_days"], 0)
        sizer.Add(row_forecast_duration, 0, wx.LEFT | wx.TOP, 10)

        # Time & Date Display Section
        sizer.Add(
            wx.StaticText(panel, label="Time & Date Display:"),
            0,
            wx.ALL,
            5,
        )

        row_time_ref = wx.BoxSizer(wx.HORIZONTAL)
        row_time_ref.Add(
            wx.StaticText(panel, label="Forecast time display:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["forecast_time_reference"] = wx.Choice(
            panel,
            choices=["Location's timezone (default)", "My local timezone"],
        )
        row_time_ref.Add(self._controls["forecast_time_reference"], 0)
        sizer.Add(row_time_ref, 0, wx.LEFT, 10)

        row_tz = wx.BoxSizer(wx.HORIZONTAL)
        row_tz.Add(
            wx.StaticText(panel, label="Time zone display:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["time_display_mode"] = wx.Choice(
            panel,
            choices=["Local time only", "UTC time only", "Both (Local and UTC)"],
        )
        row_tz.Add(self._controls["time_display_mode"], 0)
        sizer.Add(row_tz, 0, wx.LEFT, 10)

        self._controls["time_format_12hour"] = wx.CheckBox(
            panel, label="Use 12-hour time format (e.g., 3:00 PM)"
        )
        sizer.Add(self._controls["time_format_12hour"], 0, wx.LEFT | wx.TOP, 10)

        self._controls["show_timezone_suffix"] = wx.CheckBox(
            panel, label="Show timezone abbreviations (e.g., EST, UTC)"
        )
        sizer.Add(self._controls["show_timezone_suffix"], 0, wx.LEFT, 10)

        # Verbosity Section
        sizer.Add(
            wx.StaticText(panel, label="Information Priority:"),
            0,
            wx.ALL,
            5,
        )

        row_verb = wx.BoxSizer(wx.HORIZONTAL)
        row_verb.Add(
            wx.StaticText(panel, label="Verbosity level:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["verbosity_level"] = wx.Choice(
            panel,
            choices=[
                "Minimal (essentials only)",
                "Standard (recommended)",
                "Detailed (all available info)",
            ],
        )
        row_verb.Add(self._controls["verbosity_level"], 0)
        sizer.Add(row_verb, 0, wx.LEFT, 10)

        # Severe Weather Override
        self._controls["severe_weather_override"] = wx.CheckBox(
            panel, label="Automatically prioritize severe weather info"
        )
        sizer.Add(self._controls["severe_weather_override"], 0, wx.ALL, 10)

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Display")

    def _create_data_sources_tab(self):
        """Create the data sources tab."""
        panel = wx.ScrolledWindow(self.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Data source selection
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(
            wx.StaticText(panel, label="Weather Data Source:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["data_source"] = wx.Choice(
            panel,
            choices=[
                "Automatic (merges all available sources)",
                "National Weather Service (US only, with alerts)",
                "Open-Meteo (International, no alerts)",
                "Visual Crossing (International with alerts, requires API key)",
            ],
        )
        row1.Add(self._controls["data_source"], 0)
        sizer.Add(row1, 0, wx.ALL, 5)

        # Visual Crossing Configuration
        sizer.Add(
            wx.StaticText(panel, label="Visual Crossing API Configuration:"),
            0,
            wx.ALL,
            5,
        )

        row_key = wx.BoxSizer(wx.HORIZONTAL)
        row_key.Add(
            wx.StaticText(panel, label="API Key:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["vc_key"] = wx.TextCtrl(panel, style=wx.TE_PASSWORD, size=(250, -1))
        row_key.Add(self._controls["vc_key"], 1)
        sizer.Add(row_key, 0, wx.LEFT | wx.EXPAND, 10)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        get_key_btn = wx.Button(panel, label="Get Free API Key")
        get_key_btn.Bind(wx.EVT_BUTTON, self._on_get_vc_api_key)
        btn_row.Add(get_key_btn, 0, wx.RIGHT, 10)

        validate_btn = wx.Button(panel, label="Validate API Key")
        validate_btn.Bind(wx.EVT_BUTTON, self._on_validate_vc_api_key)
        btn_row.Add(validate_btn, 0)
        sizer.Add(btn_row, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        # Source Priority (Auto Mode)
        sizer.Add(
            wx.StaticText(panel, label="Source Priority (Auto Mode):"),
            0,
            wx.ALL,
            5,
        )
        sizer.Add(
            wx.StaticText(
                panel,
                label="Station selection strategy applies to NWS current conditions. In Auto mode, it applies when NWS is selected or used as fallback.",
            ),
            0,
            wx.LEFT | wx.BOTTOM,
            5,
        )

        row_us = wx.BoxSizer(wx.HORIZONTAL)
        row_us.Add(
            wx.StaticText(panel, label="US Locations Priority:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["us_priority"] = wx.Choice(
            panel,
            choices=[
                "NWS → Open-Meteo → Visual Crossing (Default)",
                "NWS → Visual Crossing → Open-Meteo",
                "Open-Meteo → NWS → Visual Crossing",
            ],
        )
        row_us.Add(self._controls["us_priority"], 0)
        sizer.Add(row_us, 0, wx.LEFT, 10)

        row_intl = wx.BoxSizer(wx.HORIZONTAL)
        row_intl.Add(
            wx.StaticText(panel, label="International Locations Priority:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["intl_priority"] = wx.Choice(
            panel,
            choices=[
                "Open-Meteo → Visual Crossing (Default)",
                "Visual Crossing → Open-Meteo",
            ],
        )
        row_intl.Add(self._controls["intl_priority"], 0)
        sizer.Add(row_intl, 0, wx.LEFT | wx.TOP, 10)

        # Open-Meteo Weather Model
        sizer.Add(
            wx.StaticText(panel, label="Open-Meteo Weather Model:"),
            0,
            wx.ALL,
            5,
        )

        self._controls["openmeteo_model"] = wx.Choice(
            panel,
            choices=[
                "Best Match (Automatic)",
                "ICON Seamless (DWD, Europe/Global)",
                "ICON Global (DWD, 13km)",
                "ICON EU (DWD, 6.5km Europe)",
                "ICON D2 (DWD, 2km Germany)",
                "GFS Seamless (NOAA, Americas/Global)",
                "GFS Global (NOAA, 28km)",
                "ECMWF IFS (9km Global)",
                "Météo-France (Europe)",
                "GEM (Canadian, North America)",
                "JMA (Japan/Asia)",
            ],
        )
        sizer.Add(self._controls["openmeteo_model"], 0, wx.LEFT, 10)

        sizer.Add(
            wx.StaticText(panel, label="NWS Station Selection (Current Conditions):"),
            0,
            wx.ALL,
            5,
        )
        self._controls["station_selection_strategy"] = wx.Choice(
            panel,
            choices=[
                "Hybrid default (recommended: fresh + major station with distance guardrail)",
                "Nearest station (pure distance)",
                "Major airport preferred (within radius, else nearest)",
                "Freshest observation (among nearest stations)",
            ],
        )
        self._controls["station_selection_strategy"].SetToolTip(
            "Applies to NWS current conditions. In Auto mode, applies when NWS is selected or used as fallback."
        )
        sizer.Add(self._controls["station_selection_strategy"], 0, wx.LEFT, 10)

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Data Sources")

    def _create_notifications_tab(self):
        """Create the notifications tab."""
        panel = wx.ScrolledWindow(self.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Alert Settings Header
        sizer.Add(
            wx.StaticText(panel, label="Alert Notification Settings"),
            0,
            wx.ALL,
            5,
        )
        sizer.Add(
            wx.StaticText(
                panel,
                label="Configure which weather alerts trigger notifications based on severity.",
            ),
            0,
            wx.LEFT | wx.BOTTOM,
            5,
        )

        # Master switches
        self._controls["enable_alerts"] = wx.CheckBox(panel, label="Enable weather alerts")
        sizer.Add(self._controls["enable_alerts"], 0, wx.ALL, 5)

        self._controls["alert_notif"] = wx.CheckBox(panel, label="Enable alert notifications")
        sizer.Add(self._controls["alert_notif"], 0, wx.LEFT | wx.BOTTOM, 5)

        # Alert area setting
        row_area = wx.BoxSizer(wx.HORIZONTAL)
        row_area.Add(
            wx.StaticText(panel, label="Alert Area:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["alert_radius_type"] = wx.Choice(
            panel,
            choices=[
                "Point (recommended)",
                "Zone",
                "State",
            ],
        )
        row_area.Add(self._controls["alert_radius_type"], 0)
        sizer.Add(row_area, 0, wx.ALL, 5)

        # Severity levels
        sizer.Add(
            wx.StaticText(panel, label="Alert Severity Levels:"),
            0,
            wx.ALL,
            5,
        )

        self._controls["notify_extreme"] = wx.CheckBox(
            panel, label="Extreme - Life-threatening events (e.g., Tornado Warning)"
        )
        sizer.Add(self._controls["notify_extreme"], 0, wx.LEFT, 10)

        self._controls["notify_severe"] = wx.CheckBox(
            panel, label="Severe - Significant hazards (e.g., Severe Thunderstorm Warning)"
        )
        sizer.Add(self._controls["notify_severe"], 0, wx.LEFT, 10)

        self._controls["notify_moderate"] = wx.CheckBox(
            panel, label="Moderate - Potentially hazardous (e.g., Winter Weather Advisory)"
        )
        sizer.Add(self._controls["notify_moderate"], 0, wx.LEFT, 10)

        self._controls["notify_minor"] = wx.CheckBox(
            panel, label="Minor - Low impact events (e.g., Frost Advisory, Fog Advisory)"
        )
        sizer.Add(self._controls["notify_minor"], 0, wx.LEFT, 10)

        self._controls["notify_unknown"] = wx.CheckBox(
            panel, label="Unknown - Uncategorized alerts"
        )
        sizer.Add(self._controls["notify_unknown"], 0, wx.LEFT, 10)

        # Event-Based Notifications Section
        sizer.Add(
            wx.StaticText(panel, label="Event-Based Notifications:"),
            0,
            wx.ALL,
            5,
        )
        sizer.Add(
            wx.StaticText(
                panel,
                label="Get notified when specific weather events occur (disabled by default).",
            ),
            0,
            wx.LEFT | wx.BOTTOM,
            5,
        )

        self._controls["notify_discussion_update"] = wx.CheckBox(
            panel, label="Notify when Area Forecast Discussion is updated (NWS US only)"
        )
        sizer.Add(self._controls["notify_discussion_update"], 0, wx.LEFT, 10)

        self._controls["notify_severe_risk_change"] = wx.CheckBox(
            panel, label="Notify when severe weather risk level changes (Visual Crossing only)"
        )
        sizer.Add(self._controls["notify_severe_risk_change"], 0, wx.LEFT | wx.BOTTOM, 10)

        # Rate Limiting Section
        sizer.Add(
            wx.StaticText(panel, label="Rate Limiting:"),
            0,
            wx.ALL,
            5,
        )
        sizer.Add(
            wx.StaticText(panel, label="Prevent notification spam by setting cooldown periods:"),
            0,
            wx.LEFT | wx.BOTTOM,
            5,
        )

        # Global cooldown
        row_gc = wx.BoxSizer(wx.HORIZONTAL)
        row_gc.Add(
            wx.StaticText(panel, label="Global cooldown (minutes):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["global_cooldown"] = wx.SpinCtrl(panel, min=0, max=60, initial=5)
        row_gc.Add(self._controls["global_cooldown"], 0)
        sizer.Add(row_gc, 0, wx.LEFT, 10)

        # Per-alert cooldown
        row_pac = wx.BoxSizer(wx.HORIZONTAL)
        row_pac.Add(
            wx.StaticText(panel, label="Per-alert cooldown (minutes):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["per_alert_cooldown"] = wx.SpinCtrl(panel, min=0, max=1440, initial=60)
        row_pac.Add(self._controls["per_alert_cooldown"], 0)
        sizer.Add(row_pac, 0, wx.LEFT | wx.TOP, 10)

        # Alert freshness window
        row_fw = wx.BoxSizer(wx.HORIZONTAL)
        row_fw.Add(
            wx.StaticText(panel, label="Alert freshness window (minutes):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["freshness_window"] = wx.SpinCtrl(panel, min=0, max=120, initial=15)
        row_fw.Add(self._controls["freshness_window"], 0)
        sizer.Add(row_fw, 0, wx.LEFT | wx.TOP, 10)

        # Max notifications per hour
        row_max = wx.BoxSizer(wx.HORIZONTAL)
        row_max.Add(
            wx.StaticText(panel, label="Maximum notifications per hour:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["max_notifications"] = wx.SpinCtrl(panel, min=1, max=100, initial=10)
        row_max.Add(self._controls["max_notifications"], 0)
        sizer.Add(row_max, 0, wx.LEFT | wx.TOP, 10)

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Notifications")

    def _create_audio_tab(self):
        """Create the audio tab."""
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(panel, label="Sound Notifications:"),
            0,
            wx.ALL,
            5,
        )

        self._controls["sound_enabled"] = wx.CheckBox(panel, label="Enable Sounds")
        sizer.Add(self._controls["sound_enabled"], 0, wx.LEFT | wx.BOTTOM, 10)

        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(
            wx.StaticText(panel, label="Active sound pack:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )

        # Load available sound packs
        self._sound_pack_ids = ["default"]
        pack_names = ["Default"]
        try:
            from ...notifications.sound_player import get_available_sound_packs

            packs = get_available_sound_packs()
            self._sound_pack_ids = list(packs.keys())
            pack_names = [packs[pid].get("name", pid) for pid in self._sound_pack_ids]
        except Exception as e:
            logger.warning(f"Failed to load sound packs: {e}")

        self._controls["sound_pack"] = wx.Choice(panel, choices=pack_names)
        row1.Add(self._controls["sound_pack"], 0)
        sizer.Add(row1, 0, wx.LEFT, 10)

        # Test sound button
        test_btn = wx.Button(panel, label="Test Sound")
        test_btn.Bind(wx.EVT_BUTTON, self._on_test_sound)
        sizer.Add(test_btn, 0, wx.LEFT | wx.TOP, 10)

        manage_btn = wx.Button(panel, label="Manage Sound Packs...")
        manage_btn.Bind(wx.EVT_BUTTON, self._on_manage_soundpacks)
        sizer.Add(manage_btn, 0, wx.LEFT | wx.TOP, 10)

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Audio")

    def _create_updates_tab(self):
        """Create the updates tab."""
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self._controls["auto_update"] = wx.CheckBox(panel, label="Check for updates automatically")
        sizer.Add(self._controls["auto_update"], 0, wx.ALL, 5)

        # Update channel
        row_ch = wx.BoxSizer(wx.HORIZONTAL)
        row_ch.Add(
            wx.StaticText(panel, label="Update Channel:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["update_channel"] = wx.Choice(
            panel,
            choices=[
                "Stable (Production releases only)",
                "Development (Latest features, may be unstable)",
            ],
        )
        row_ch.Add(self._controls["update_channel"], 0)
        sizer.Add(row_ch, 0, wx.LEFT, 5)

        # Check interval
        row_int = wx.BoxSizer(wx.HORIZONTAL)
        row_int.Add(
            wx.StaticText(panel, label="Check Interval (hours):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["update_check_interval"] = wx.SpinCtrl(panel, min=1, max=168, initial=24)
        row_int.Add(self._controls["update_check_interval"], 0)
        sizer.Add(row_int, 0, wx.LEFT | wx.TOP, 5)

        # Check now button
        check_btn = wx.Button(panel, label="Check for Updates Now")
        check_btn.Bind(wx.EVT_BUTTON, self._on_check_updates)
        sizer.Add(check_btn, 0, wx.ALL, 10)

        self._controls["update_status"] = wx.StaticText(panel, label="Ready to check for updates")
        sizer.Add(self._controls["update_status"], 0, wx.LEFT, 10)

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Updates")

    def _create_ai_tab(self):
        """Create the AI explanations tab."""
        panel = wx.ScrolledWindow(self.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        sizer.Add(
            wx.StaticText(panel, label="AI Weather Explanations"),
            0,
            wx.ALL,
            5,
        )
        sizer.Add(
            wx.StaticText(
                panel,
                label="Get natural language explanations of weather conditions using AI.",
            ),
            0,
            wx.LEFT | wx.BOTTOM,
            5,
        )

        # OpenRouter API Key
        sizer.Add(
            wx.StaticText(panel, label="OpenRouter API Key:"),
            0,
            wx.ALL,
            5,
        )
        sizer.Add(
            wx.StaticText(
                panel, label="Required for all models. Get a free key at openrouter.ai/keys"
            ),
            0,
            wx.LEFT | wx.BOTTOM,
            5,
        )

        self._controls["openrouter_key"] = wx.TextCtrl(panel, style=wx.TE_PASSWORD, size=(300, -1))
        sizer.Add(self._controls["openrouter_key"], 0, wx.LEFT, 10)

        validate_btn = wx.Button(panel, label="Validate API Key")
        validate_btn.Bind(wx.EVT_BUTTON, self._on_validate_openrouter_key)
        sizer.Add(validate_btn, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        # Model Preference
        row_model = wx.BoxSizer(wx.HORIZONTAL)
        row_model.Add(
            wx.StaticText(panel, label="Model Preference:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["ai_model"] = wx.Choice(
            panel,
            choices=[
                "Free Router (Auto, Free)",
                "Llama 3.3 70B (Free)",
                "Auto Router (Paid)",
            ],
        )
        row_model.Add(self._controls["ai_model"], 0)
        sizer.Add(row_model, 0, wx.LEFT, 10)

        browse_btn = wx.Button(panel, label="Browse Models...")
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse_models)
        sizer.Add(browse_btn, 0, wx.LEFT | wx.TOP, 10)

        # Explanation Style
        row_style = wx.BoxSizer(wx.HORIZONTAL)
        row_style.Add(
            wx.StaticText(panel, label="Explanation Style:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._controls["ai_style"] = wx.Choice(
            panel,
            choices=[
                "Brief (1-2 sentences)",
                "Standard (3-4 sentences)",
                "Detailed (full paragraph)",
            ],
        )
        row_style.Add(self._controls["ai_style"], 0)
        sizer.Add(row_style, 0, wx.LEFT | wx.TOP, 10)

        # Custom System Prompt
        sizer.Add(
            wx.StaticText(panel, label="Custom System Prompt (optional):"),
            0,
            wx.LEFT | wx.TOP,
            10,
        )
        self._controls["custom_prompt"] = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(400, 60))
        sizer.Add(self._controls["custom_prompt"], 0, wx.LEFT | wx.EXPAND, 10)

        reset_prompt_btn = wx.Button(panel, label="Reset to Default")
        reset_prompt_btn.Bind(wx.EVT_BUTTON, self._on_reset_prompt)
        sizer.Add(reset_prompt_btn, 0, wx.LEFT | wx.TOP, 10)

        # Custom Instructions
        sizer.Add(
            wx.StaticText(panel, label="Custom Instructions (optional):"),
            0,
            wx.LEFT | wx.TOP,
            10,
        )
        self._controls["custom_instructions"] = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE, size=(400, 40)
        )
        self._controls["custom_instructions"].SetHint(
            "e.g., Focus on outdoor activities, Keep responses under 50 words"
        )
        sizer.Add(self._controls["custom_instructions"], 0, wx.LEFT | wx.EXPAND, 10)

        # Pricing info
        sizer.Add(
            wx.StaticText(panel, label="Cost Information:"),
            0,
            wx.LEFT | wx.TOP,
            10,
        )
        sizer.Add(
            wx.StaticText(panel, label="Free models: No cost, may have rate limits"),
            0,
            wx.LEFT,
            15,
        )
        sizer.Add(
            wx.StaticText(panel, label="Paid models: ~$0.001 per explanation (varies by model)"),
            0,
            wx.LEFT,
            15,
        )

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "AI")

    def _create_advanced_tab(self):
        """Create the advanced tab."""
        panel = wx.ScrolledWindow(self.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # System options
        self._controls["minimize_tray"] = wx.CheckBox(
            panel, label="Minimize to notification area when closing"
        )
        self._controls["minimize_tray"].Bind(wx.EVT_CHECKBOX, self._on_minimize_tray_changed)
        sizer.Add(self._controls["minimize_tray"], 0, wx.ALL, 5)

        self._controls["minimize_on_startup"] = wx.CheckBox(
            panel, label="Start minimized to notification area"
        )
        sizer.Add(self._controls["minimize_on_startup"], 0, wx.LEFT | wx.BOTTOM, 5)

        self._controls["startup"] = wx.CheckBox(panel, label="Launch automatically at startup")
        sizer.Add(self._controls["startup"], 0, wx.LEFT | wx.BOTTOM, 5)

        self._controls["weather_history"] = wx.CheckBox(
            panel, label="Enable weather history comparisons"
        )
        sizer.Add(self._controls["weather_history"], 0, wx.LEFT | wx.BOTTOM, 5)

        # Reset Configuration Section
        sizer.Add(
            wx.StaticText(panel, label="Reset Configuration"),
            0,
            wx.LEFT | wx.TOP,
            5,
        )
        sizer.Add(
            wx.StaticText(panel, label="Restore all settings to their default values."),
            0,
            wx.LEFT,
            5,
        )

        reset_btn = wx.Button(panel, label="Reset all settings to defaults")
        reset_btn.Bind(wx.EVT_BUTTON, self._on_reset_defaults)
        sizer.Add(reset_btn, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        # Full Data Reset
        sizer.Add(
            wx.StaticText(panel, label="Full Data Reset"),
            0,
            wx.LEFT,
            5,
        )
        sizer.Add(
            wx.StaticText(
                panel,
                label="Reset all application data: settings, locations, caches, and alert state.",
            ),
            0,
            wx.LEFT,
            5,
        )

        full_reset_btn = wx.Button(panel, label="Reset all app data (settings, locations, caches)")
        full_reset_btn.Bind(wx.EVT_BUTTON, self._on_full_reset)
        sizer.Add(full_reset_btn, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        # Configuration Files
        sizer.Add(
            wx.StaticText(panel, label="Configuration Files"),
            0,
            wx.LEFT,
            5,
        )

        open_config_btn = wx.Button(panel, label="Open current config directory")
        open_config_btn.Bind(wx.EVT_BUTTON, self._on_open_config_dir)
        sizer.Add(open_config_btn, 0, wx.LEFT | wx.TOP, 10)

        open_installed_config_btn = wx.Button(
            panel, label="Open installed config directory (source)"
        )
        open_installed_config_btn.Bind(wx.EVT_BUTTON, self._on_open_installed_config_dir)
        sizer.Add(open_installed_config_btn, 0, wx.LEFT | wx.TOP, 10)

        if self._is_runtime_portable_mode():
            migrate_config_btn = wx.Button(panel, label="Copy installed config to portable")
            migrate_config_btn.Bind(wx.EVT_BUTTON, self._on_copy_installed_config_to_portable)
            sizer.Add(migrate_config_btn, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        # Settings Backup
        sizer.Add(
            wx.StaticText(panel, label="Settings Backup"),
            0,
            wx.LEFT | wx.TOP,
            5,
        )

        export_btn = wx.Button(panel, label="Export Settings...")
        export_btn.Bind(wx.EVT_BUTTON, self._on_export_settings)
        sizer.Add(export_btn, 0, wx.LEFT | wx.TOP, 10)

        import_btn = wx.Button(panel, label="Import Settings...")
        import_btn.Bind(wx.EVT_BUTTON, self._on_import_settings)
        sizer.Add(import_btn, 0, wx.LEFT | wx.TOP, 10)

        sizer.Add(
            wx.StaticText(panel, label="API Key Portability (Encrypted)"),
            0,
            wx.LEFT | wx.TOP,
            5,
        )
        sizer.Add(
            wx.StaticText(
                panel,
                label=(
                    "Optional: export API keys to an encrypted bundle for transfer. "
                    "Import requires your passphrase and stores keys in this machine's keyring."
                ),
            ),
            0,
            wx.LEFT,
            5,
        )

        export_api_keys_btn = wx.Button(panel, label="Export API keys (encrypted)")
        export_api_keys_btn.Bind(wx.EVT_BUTTON, self._on_export_encrypted_api_keys)
        sizer.Add(export_api_keys_btn, 0, wx.LEFT | wx.TOP, 10)

        import_api_keys_btn = wx.Button(panel, label="Import API keys (encrypted)")
        import_api_keys_btn.Bind(wx.EVT_BUTTON, self._on_import_encrypted_api_keys)
        sizer.Add(import_api_keys_btn, 0, wx.LEFT | wx.TOP, 10)

        # Sound Pack Files
        sizer.Add(
            wx.StaticText(panel, label="Sound Pack Files"),
            0,
            wx.LEFT | wx.TOP,
            5,
        )

        open_sounds_btn = wx.Button(panel, label="Open sound packs folder")
        open_sounds_btn.Bind(wx.EVT_BUTTON, self._on_open_soundpacks_dir)
        sizer.Add(open_sounds_btn, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Advanced")

    def _load_settings(self):
        """Load current settings into UI controls."""
        try:
            settings = self.config_manager.get_settings()

            # General tab
            self._controls["update_interval"].SetValue(
                getattr(settings, "update_interval_minutes", 10)
            )
            self._controls["show_nationwide"].SetValue(
                getattr(self.config_manager.get_settings(), "show_nationwide_location", True)
            )
            # Disable checkbox if data source isn't NWS-compatible
            data_source = getattr(settings, "data_source", "auto")
            if data_source not in ("auto", "nws"):
                self._controls["show_nationwide"].SetValue(False)
                self._controls["show_nationwide"].Enable(False)
            else:
                self._controls["show_nationwide"].Enable(True)

            # Display tab
            temp_unit = getattr(settings, "temperature_unit", "both")
            temp_map = {"f": 0, "fahrenheit": 0, "c": 1, "celsius": 1, "both": 2}
            self._controls["temp_unit"].SetSelection(temp_map.get(temp_unit, 2))

            self._controls["show_dewpoint"].SetValue(getattr(settings, "show_dewpoint", True))
            self._controls["show_visibility"].SetValue(getattr(settings, "show_visibility", True))
            self._controls["show_uv_index"].SetValue(getattr(settings, "show_uv_index", True))
            self._controls["show_pressure_trend"].SetValue(
                getattr(settings, "show_pressure_trend", True)
            )
            self._controls["detailed_forecast"].SetValue(
                getattr(settings, "show_detailed_forecast", True)
            )
            forecast_duration_days = getattr(settings, "forecast_duration_days", 7)
            forecast_duration_map = {3: 0, 5: 1, 7: 2, 10: 3, 14: 4, 15: 5}
            self._controls["forecast_duration_days"].SetSelection(
                forecast_duration_map.get(forecast_duration_days, 2)
            )

            forecast_time_reference = getattr(settings, "forecast_time_reference", "location")
            forecast_time_reference_map = {"location": 0, "user_local": 1}
            self._controls["forecast_time_reference"].SetSelection(
                forecast_time_reference_map.get(forecast_time_reference, 0)
            )

            time_mode = getattr(settings, "time_display_mode", "local")
            time_mode_map = {"local": 0, "utc": 1, "both": 2}
            self._controls["time_display_mode"].SetSelection(time_mode_map.get(time_mode, 0))

            self._controls["time_format_12hour"].SetValue(
                getattr(settings, "time_format_12hour", True)
            )
            self._controls["show_timezone_suffix"].SetValue(
                getattr(settings, "show_timezone_suffix", False)
            )

            verbosity = getattr(settings, "verbosity_level", "standard")
            verbosity_map = {"minimal": 0, "standard": 1, "detailed": 2}
            self._controls["verbosity_level"].SetSelection(verbosity_map.get(verbosity, 1))

            self._controls["severe_weather_override"].SetValue(
                getattr(settings, "severe_weather_override", True)
            )

            # Data sources tab
            data_source = getattr(settings, "data_source", "auto")
            source_map = {"auto": 0, "nws": 1, "openmeteo": 2, "visualcrossing": 3}
            self._controls["data_source"].SetSelection(source_map.get(data_source, 0))

            vc_key = getattr(settings, "visual_crossing_api_key", "") or ""
            self._controls["vc_key"].SetValue(str(vc_key))
            self._original_vc_key = str(vc_key)

            # Source priority
            us_priority = getattr(
                settings, "source_priority_us", ["nws", "openmeteo", "visualcrossing"]
            )
            us_map = {
                ("nws", "openmeteo", "visualcrossing"): 0,
                ("nws", "visualcrossing", "openmeteo"): 1,
                ("openmeteo", "nws", "visualcrossing"): 2,
            }
            self._controls["us_priority"].SetSelection(us_map.get(tuple(us_priority[:3]), 0))

            intl_priority = getattr(
                settings, "source_priority_international", ["openmeteo", "visualcrossing"]
            )
            intl_map = {
                ("openmeteo", "visualcrossing"): 0,
                ("visualcrossing", "openmeteo"): 1,
            }
            self._controls["intl_priority"].SetSelection(intl_map.get(tuple(intl_priority[:2]), 0))

            # Open-Meteo model
            model = getattr(settings, "openmeteo_weather_model", "best_match")
            model_map = {
                "best_match": 0,
                "icon_seamless": 1,
                "icon_global": 2,
                "icon_eu": 3,
                "icon_d2": 4,
                "gfs_seamless": 5,
                "gfs_global": 6,
                "ecmwf_ifs04": 7,
                "meteofrance_seamless": 8,
                "gem_seamless": 9,
                "jma_seamless": 10,
            }
            self._controls["openmeteo_model"].SetSelection(model_map.get(model, 0))

            strategy = getattr(settings, "station_selection_strategy", "hybrid_default")
            strategy_map = {
                "hybrid_default": 0,
                "nearest": 1,
                "major_airport_preferred": 2,
                "freshest_observation": 3,
            }
            self._controls["station_selection_strategy"].SetSelection(strategy_map.get(strategy, 0))

            # Notifications tab
            self._controls["enable_alerts"].SetValue(getattr(settings, "enable_alerts", True))
            self._controls["alert_notif"].SetValue(
                getattr(settings, "alert_notifications_enabled", True)
            )
            # Alert radius type: map value to choice index
            radius_type = getattr(settings, "alert_radius_type", "point")
            radius_type_map = {"point": 0, "zone": 1, "state": 2}
            self._controls["alert_radius_type"].SetSelection(radius_type_map.get(radius_type, 0))
            self._controls["notify_extreme"].SetValue(
                getattr(settings, "alert_notify_extreme", True)
            )
            self._controls["notify_severe"].SetValue(getattr(settings, "alert_notify_severe", True))
            self._controls["notify_moderate"].SetValue(
                getattr(settings, "alert_notify_moderate", True)
            )
            self._controls["notify_minor"].SetValue(getattr(settings, "alert_notify_minor", False))
            self._controls["notify_unknown"].SetValue(
                getattr(settings, "alert_notify_unknown", False)
            )
            self._controls["global_cooldown"].SetValue(
                getattr(settings, "alert_global_cooldown_minutes", 5)
            )
            self._controls["per_alert_cooldown"].SetValue(
                getattr(settings, "alert_per_alert_cooldown_minutes", 60)
            )
            self._controls["freshness_window"].SetValue(
                getattr(settings, "alert_freshness_window_minutes", 15)
            )
            self._controls["max_notifications"].SetValue(
                getattr(settings, "alert_max_notifications_per_hour", 10)
            )

            # Event-based notifications
            self._controls["notify_discussion_update"].SetValue(
                getattr(settings, "notify_discussion_update", True)
            )
            self._controls["notify_severe_risk_change"].SetValue(
                getattr(settings, "notify_severe_risk_change", False)
            )

            # Audio tab
            self._controls["sound_enabled"].SetValue(getattr(settings, "sound_enabled", True))
            current_pack = getattr(settings, "sound_pack", "default")
            try:
                pack_idx = self._sound_pack_ids.index(current_pack)
                self._controls["sound_pack"].SetSelection(pack_idx)
            except (ValueError, AttributeError):
                self._controls["sound_pack"].SetSelection(0)

            # Updates tab
            self._controls["auto_update"].SetValue(getattr(settings, "auto_update_enabled", True))
            channel = getattr(settings, "update_channel", "stable")
            self._controls["update_channel"].SetSelection(0 if channel == "stable" else 1)
            self._controls["update_check_interval"].SetValue(
                getattr(settings, "update_check_interval_hours", 24)
            )

            # AI tab
            openrouter_key = getattr(settings, "openrouter_api_key", "") or ""
            self._controls["openrouter_key"].SetValue(str(openrouter_key))
            self._original_openrouter_key = str(openrouter_key)

            ai_model = getattr(settings, "ai_model_preference", "openrouter/free")
            if ai_model == "openrouter/free":
                self._controls["ai_model"].SetSelection(0)
            elif ai_model == "meta-llama/llama-3.3-70b-instruct:free":
                self._controls["ai_model"].SetSelection(1)
            elif ai_model == "auto":
                self._controls["ai_model"].SetSelection(2)
            else:
                # Specific model was selected - add it to the dropdown
                model_display = f"Selected: {ai_model.split('/')[-1]}"
                self._controls["ai_model"].Append(model_display)
                self._controls["ai_model"].SetSelection(3)
                self._selected_specific_model = ai_model

            ai_style = getattr(settings, "ai_explanation_style", "standard")
            style_map = {"brief": 0, "standard": 1, "detailed": 2}
            self._controls["ai_style"].SetSelection(style_map.get(ai_style, 1))

            custom_prompt = getattr(settings, "custom_system_prompt", "") or ""
            self._controls["custom_prompt"].SetValue(custom_prompt)

            custom_instructions = getattr(settings, "custom_instructions", "") or ""
            self._controls["custom_instructions"].SetValue(custom_instructions)

            # Advanced tab
            minimize_to_tray = getattr(settings, "minimize_to_tray", False)
            self._controls["minimize_tray"].SetValue(minimize_to_tray)
            self._controls["minimize_on_startup"].SetValue(
                getattr(settings, "minimize_on_startup", False)
            )
            # Link settings: disable minimize_on_startup if minimize_to_tray is disabled
            self._update_minimize_on_startup_state(minimize_to_tray)

            # General tab - taskbar icon text options
            taskbar_text_enabled = getattr(settings, "taskbar_icon_text_enabled", False)
            self._controls["taskbar_icon_text_enabled"].SetValue(taskbar_text_enabled)
            self._controls["taskbar_icon_dynamic_enabled"].SetValue(
                getattr(settings, "taskbar_icon_dynamic_enabled", True)
            )
            self._controls["taskbar_icon_text_format"].SetValue(
                getattr(settings, "taskbar_icon_text_format", "{temp} {condition}")
            )
            self._update_taskbar_text_controls_state(taskbar_text_enabled)
            self._controls["startup"].SetValue(getattr(settings, "startup_enabled", False))
            self._controls["weather_history"].SetValue(
                getattr(settings, "weather_history_enabled", True)
            )
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def _save_settings(self) -> bool:
        """Save settings from UI controls."""
        try:
            # Map selections back to values
            source_values = ["auto", "nws", "openmeteo", "visualcrossing"]
            temp_values = ["f", "c", "both"]
            forecast_duration_values = [3, 5, 7, 10, 14, 15]
            forecast_time_reference_values = ["location", "user_local"]
            time_mode_values = ["local", "utc", "both"]
            verbosity_values = ["minimal", "standard", "detailed"]
            model_values = [
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
            ]
            style_values = ["brief", "standard", "detailed"]
            station_strategy_values = [
                "hybrid_default",
                "nearest",
                "major_airport_preferred",
                "freshest_observation",
            ]

            # Update nationwide visibility
            show_nationwide = self._controls["show_nationwide"].GetValue()
            # Nationwide visibility is persisted via settings_dict below

            settings_dict = {
                # General
                "update_interval_minutes": self._controls["update_interval"].GetValue(),
                "show_nationwide_location": show_nationwide,
                "taskbar_icon_text_enabled": self._controls["taskbar_icon_text_enabled"].GetValue(),
                "taskbar_icon_dynamic_enabled": self._controls[
                    "taskbar_icon_dynamic_enabled"
                ].GetValue(),
                "taskbar_icon_text_format": self._controls["taskbar_icon_text_format"].GetValue(),
                # Display
                "temperature_unit": temp_values[self._controls["temp_unit"].GetSelection()],
                "show_dewpoint": self._controls["show_dewpoint"].GetValue(),
                "show_visibility": self._controls["show_visibility"].GetValue(),
                "show_uv_index": self._controls["show_uv_index"].GetValue(),
                "show_pressure_trend": self._controls["show_pressure_trend"].GetValue(),
                "show_detailed_forecast": self._controls["detailed_forecast"].GetValue(),
                "forecast_duration_days": forecast_duration_values[
                    self._controls["forecast_duration_days"].GetSelection()
                ],
                "forecast_time_reference": forecast_time_reference_values[
                    self._controls["forecast_time_reference"].GetSelection()
                ],
                "time_display_mode": time_mode_values[
                    self._controls["time_display_mode"].GetSelection()
                ],
                "time_format_12hour": self._controls["time_format_12hour"].GetValue(),
                "show_timezone_suffix": self._controls["show_timezone_suffix"].GetValue(),
                "verbosity_level": verbosity_values[
                    self._controls["verbosity_level"].GetSelection()
                ],
                "severe_weather_override": self._controls["severe_weather_override"].GetValue(),
                # Data sources
                "data_source": source_values[self._controls["data_source"].GetSelection()],
                "visual_crossing_api_key": self._controls["vc_key"].GetValue(),
                "source_priority_us": [
                    ["nws", "openmeteo", "visualcrossing"],
                    ["nws", "visualcrossing", "openmeteo"],
                    ["openmeteo", "nws", "visualcrossing"],
                ][max(0, self._controls["us_priority"].GetSelection())],
                "source_priority_international": [
                    ["openmeteo", "visualcrossing"],
                    ["visualcrossing", "openmeteo"],
                ][max(0, self._controls["intl_priority"].GetSelection())],
                "openmeteo_weather_model": model_values[
                    self._controls["openmeteo_model"].GetSelection()
                ],
                "station_selection_strategy": station_strategy_values[
                    max(0, self._controls["station_selection_strategy"].GetSelection())
                ],
                # Notifications
                "enable_alerts": self._controls["enable_alerts"].GetValue(),
                "alert_notifications_enabled": self._controls["alert_notif"].GetValue(),
                "alert_radius_type": ["point", "zone", "state"][
                    self._controls["alert_radius_type"].GetSelection()
                ],
                "alert_notify_extreme": self._controls["notify_extreme"].GetValue(),
                "alert_notify_severe": self._controls["notify_severe"].GetValue(),
                "alert_notify_moderate": self._controls["notify_moderate"].GetValue(),
                "alert_notify_minor": self._controls["notify_minor"].GetValue(),
                "alert_notify_unknown": self._controls["notify_unknown"].GetValue(),
                "alert_global_cooldown_minutes": self._controls["global_cooldown"].GetValue(),
                "alert_per_alert_cooldown_minutes": self._controls["per_alert_cooldown"].GetValue(),
                "alert_freshness_window_minutes": self._controls["freshness_window"].GetValue(),
                "alert_max_notifications_per_hour": self._controls["max_notifications"].GetValue(),
                # Event-based notifications
                "notify_discussion_update": self._controls["notify_discussion_update"].GetValue(),
                "notify_severe_risk_change": self._controls["notify_severe_risk_change"].GetValue(),
                # Audio
                "sound_enabled": self._controls["sound_enabled"].GetValue(),
                "sound_pack": self._sound_pack_ids[self._controls["sound_pack"].GetSelection()]
                if hasattr(self, "_sound_pack_ids")
                and self._controls["sound_pack"].GetSelection() < len(self._sound_pack_ids)
                else "default",
                # Updates
                "auto_update_enabled": self._controls["auto_update"].GetValue(),
                "update_channel": "stable"
                if self._controls["update_channel"].GetSelection() == 0
                else "dev",
                "update_check_interval_hours": self._controls["update_check_interval"].GetValue(),
                # AI
                "openrouter_api_key": self._controls["openrouter_key"].GetValue(),
                "ai_model_preference": self._get_ai_model_preference(),
                "ai_explanation_style": style_values[self._controls["ai_style"].GetSelection()],
                "custom_system_prompt": self._controls["custom_prompt"].GetValue() or None,
                "custom_instructions": self._controls["custom_instructions"].GetValue() or None,
                # Advanced
                "minimize_to_tray": self._controls["minimize_tray"].GetValue(),
                "minimize_on_startup": self._controls["minimize_on_startup"].GetValue(),
                "startup_enabled": self._controls["startup"].GetValue(),
                "weather_history_enabled": self._controls["weather_history"].GetValue(),
            }
            # Source priority
            us_idx = self._controls["us_priority"].GetSelection()
            us_priorities = [
                ["nws", "openmeteo", "visualcrossing"],
                ["nws", "visualcrossing", "openmeteo"],
                ["openmeteo", "nws", "visualcrossing"],
            ]
            settings_dict["source_priority_us"] = us_priorities[us_idx if us_idx >= 0 else 0]

            intl_idx = self._controls["intl_priority"].GetSelection()
            intl_priorities = [
                ["openmeteo", "visualcrossing"],
                ["visualcrossing", "openmeteo"],
            ]
            settings_dict["source_priority_international"] = intl_priorities[
                intl_idx if intl_idx >= 0 else 0
            ]

            # Guard: never wipe a previously-set API key with an empty string.
            # If the field is blank but the original value was non-empty, the
            # keyring load failed transiently — keep the existing keyring value.
            for key, orig_attr in (
                ("visual_crossing_api_key", "_original_vc_key"),
                ("openrouter_api_key", "_original_openrouter_key"),
            ):
                if not settings_dict.get(key) and getattr(self, orig_attr, ""):
                    logger.warning(
                        "Skipping empty %s save — original value was non-empty; "
                        "keyring may have failed to load. Existing keyring value preserved.",
                        key,
                    )
                    settings_dict.pop(key, None)

            success = self.config_manager.update_settings(**settings_dict)
            if success:
                logger.info("Settings saved successfully")
                if hasattr(self, "app") and self._is_runtime_portable_mode():
                    self._maybe_update_portable_bundle_after_save(settings_dict)
            return success

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def _setup_accessibility(self):
        """Set up accessibility labels for controls."""
        control_names = {
            "update_interval": "Update Interval (minutes)",
            "show_nationwide": "Show Nationwide location (requires Auto or NWS data source)",
            "taskbar_icon_text_enabled": "Show weather text on tray icon",
            "taskbar_icon_dynamic_enabled": "Update tray text dynamically",
            "taskbar_icon_text_format": "Tray text format",
            "temp_unit": "Temperature Display",
            "show_dewpoint": "Show dewpoint",
            "show_visibility": "Show visibility",
            "show_uv_index": "Show UV index",
            "show_pressure_trend": "Show pressure trend",
            "detailed_forecast": "Show detailed forecast information",
            "forecast_duration_days": "Forecast duration",
            "forecast_time_reference": "Forecast time display",
            "time_display_mode": "Time zone display",
            "time_format_12hour": "Use 12-hour time format (e.g., 3:00 PM)",
            "show_timezone_suffix": "Show timezone abbreviations (e.g., EST, UTC)",
            "verbosity_level": "Verbosity level",
            "severe_weather_override": "Automatically prioritize severe weather info",
            "data_source": "Weather Data Source",
            "vc_key": "API Key",
            "us_priority": "US Locations Priority",
            "intl_priority": "International Locations Priority",
            "openmeteo_model": "Open-Meteo Weather Model",
            "station_selection_strategy": "Station selection strategy",
            "enable_alerts": "Enable weather alerts",
            "alert_notif": "Enable alert notifications",
            "alert_radius_type": "Alert Area",
            "notify_extreme": "Extreme - Life-threatening events (e.g., Tornado Warning)",
            "notify_severe": "Severe - Significant hazards (e.g., Severe Thunderstorm Warning)",
            "notify_moderate": "Moderate - Potentially hazardous (e.g., Winter Weather Advisory)",
            "notify_minor": "Minor - Low impact events (e.g., Frost Advisory, Fog Advisory)",
            "notify_unknown": "Unknown - Uncategorized alerts",
            "notify_discussion_update": "Notify when Area Forecast Discussion is updated (NWS US only)",
            "notify_severe_risk_change": "Notify when severe weather risk level changes (Visual Crossing only)",
            "global_cooldown": "Global cooldown (minutes)",
            "per_alert_cooldown": "Per-alert cooldown (minutes)",
            "freshness_window": "Alert freshness window (minutes)",
            "max_notifications": "Maximum notifications per hour",
            "sound_enabled": "Enable Sounds",
            "sound_pack": "Active sound pack",
            "auto_update": "Check for updates automatically",
            "update_channel": "Update Channel",
            "update_check_interval": "Check Interval (hours)",
            "openrouter_key": "OpenRouter API Key",
            "ai_model": "Model Preference",
            "ai_style": "Explanation Style",
            "custom_prompt": "Custom System Prompt (optional)",
            "custom_instructions": "Custom Instructions (optional)",
            "minimize_tray": "Minimize to notification area when closing",
            "minimize_on_startup": "Start minimized to notification area",
            "startup": "Launch automatically at startup",
            "weather_history": "Enable weather history comparisons",
        }

        for key, name in control_names.items():
            self._controls[key].SetName(name)

    def _get_ai_model_preference(self) -> str:
        """Get the AI model preference based on UI selection."""
        selection = self._controls["ai_model"].GetSelection()
        if selection == 0:
            return "openrouter/free"
        if selection == 1:
            return "meta-llama/llama-3.3-70b-instruct:free"
        if selection == 2:
            return "auto"
        if selection == 3 and self._selected_specific_model:
            return self._selected_specific_model
        return "openrouter/free"

    def _on_ok(self, event):
        """Handle OK button press."""
        if self._save_settings():
            self.EndModal(wx.ID_OK)
        else:
            wx.MessageBox("Failed to save settings.", "Error", wx.OK | wx.ICON_ERROR)

    # Event handlers for buttons
    def _on_get_vc_api_key(self, event):
        """Open Visual Crossing signup page."""
        webbrowser.open("https://www.visualcrossing.com/sign-up")

    def _on_validate_vc_api_key(self, event):
        """Validate Visual Crossing API key."""
        key = self._controls["vc_key"].GetValue()
        if not key:
            wx.MessageBox("Please enter an API key first.", "Validation", wx.OK | wx.ICON_WARNING)
            return

        # Show busy cursor during validation
        wx.BeginBusyCursor()
        try:
            import asyncio

            from ...models import Location
            from ...visual_crossing_client import VisualCrossingApiError, VisualCrossingClient

            # Test with a known location (New York City)
            test_location = Location(name="Test", latitude=40.7128, longitude=-74.0060)
            client = VisualCrossingClient(api_key=key)

            async def test_key():
                try:
                    await client.get_current_conditions(test_location)
                    return True, None
                except VisualCrossingApiError as e:
                    if e.status_code == 401:
                        return False, "Invalid API key"
                    if e.status_code == 429:
                        return False, "Rate limit exceeded - but key appears valid"
                    return False, str(e.message)
                except Exception as e:
                    return False, str(e)

            # Run the async validation
            loop = asyncio.new_event_loop()
            try:
                valid, error = loop.run_until_complete(test_key())
            finally:
                loop.close()

            if valid:
                wx.MessageBox(
                    "API key is valid!",
                    "Validation Successful",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    f"API key validation failed: {error}",
                    "Validation Failed",
                    wx.OK | wx.ICON_ERROR,
                )
        except Exception as e:
            logger.error(f"Error validating Visual Crossing API key: {e}")
            wx.MessageBox(
                f"Error during validation: {e}",
                "Validation Error",
                wx.OK | wx.ICON_ERROR,
            )
        finally:
            wx.EndBusyCursor()

    def _on_validate_openrouter_key(self, event):
        """Validate OpenRouter API key."""
        key = self._controls["openrouter_key"].GetValue()
        if not key:
            wx.MessageBox("Please enter an API key first.", "Validation", wx.OK | wx.ICON_WARNING)
            return

        # Show busy cursor during validation
        wx.BeginBusyCursor()
        try:
            import asyncio

            from ...ai_explainer import AIExplainer

            explainer = AIExplainer()

            # Run the async validation
            loop = asyncio.new_event_loop()
            try:
                valid = loop.run_until_complete(explainer.validate_api_key(key))
            finally:
                loop.close()

            if valid:
                wx.MessageBox(
                    "API key is valid!",
                    "Validation Successful",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    "API key validation failed. Please check your key and try again.",
                    "Validation Failed",
                    wx.OK | wx.ICON_ERROR,
                )
        except Exception as e:
            logger.error(f"Error validating OpenRouter API key: {e}")
            wx.MessageBox(
                f"Error during validation: {e}",
                "Validation Error",
                wx.OK | wx.ICON_ERROR,
            )
        finally:
            wx.EndBusyCursor()

    def _on_browse_models(self, event):
        """Browse available AI models."""
        from .model_browser_dialog import show_model_browser_dialog

        api_key = self._controls["openrouter_key"].GetValue()
        selected_model_id = show_model_browser_dialog(self, api_key=api_key or None)

        if selected_model_id:
            # Update the model preference based on selection
            # Check if it's a known preset (indices must match _get_ai_model_preference)
            if selected_model_id == "openrouter/free":
                self._controls["ai_model"].SetSelection(0)
            elif selected_model_id == "meta-llama/llama-3.3-70b-instruct:free":
                self._controls["ai_model"].SetSelection(1)
            elif selected_model_id == "openrouter/auto":
                self._controls["ai_model"].SetSelection(2)
            else:
                # Add as "Specific Model" option at index 3 (after the 3 built-in presets)
                model_display = f"Selected: {selected_model_id.split('/')[-1]}"
                if self._controls["ai_model"].GetCount() > 3:
                    # Replace existing specific model choice
                    self._controls["ai_model"].SetString(3, model_display)
                else:
                    # Add new specific model choice
                    self._controls["ai_model"].Append(model_display)
                self._controls["ai_model"].SetSelection(3)
                # Store the full model ID for saving
                self._selected_specific_model = selected_model_id

    def _on_reset_prompt(self, event):
        """Reset custom prompt to default."""
        self._controls["custom_prompt"].SetValue("")

    def _on_test_sound(self, event):
        """Play a test sound from the selected pack."""
        try:
            from ...notifications.sound_player import play_sample_sound

            pack_idx = self._controls["sound_pack"].GetSelection()
            if hasattr(self, "_sound_pack_ids") and pack_idx < len(self._sound_pack_ids):
                pack_id = self._sound_pack_ids[pack_idx]
            else:
                pack_id = "default"
            play_sample_sound(pack_id)
        except Exception as e:
            logger.error(f"Failed to play test sound: {e}")
            wx.MessageBox(f"Failed to play test sound: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_manage_soundpacks(self, event):
        """Open sound pack management."""
        try:
            from .soundpack_manager_dialog import show_soundpack_manager_dialog

            show_soundpack_manager_dialog(self, self.app)

            # Refresh sound pack list after managing
            self._refresh_sound_pack_list()
        except Exception as e:
            logger.error(f"Failed to open sound pack manager: {e}")
            wx.MessageBox(
                f"Failed to open sound pack manager: {e}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def _refresh_sound_pack_list(self):
        """Refresh the sound pack dropdown after changes."""
        try:
            from ...notifications.sound_player import get_available_sound_packs

            # Remember current selection
            current_idx = self._controls["sound_pack"].GetSelection()
            current_id = (
                self._sound_pack_ids[current_idx]
                if current_idx < len(self._sound_pack_ids)
                else "default"
            )

            # Reload packs
            packs = get_available_sound_packs()
            self._sound_pack_ids = list(packs.keys())
            pack_names = [packs[pid].get("name", pid) for pid in self._sound_pack_ids]

            # Update dropdown
            self._controls["sound_pack"].Clear()
            for name in pack_names:
                self._controls["sound_pack"].Append(name)

            # Restore selection
            try:
                new_idx = self._sound_pack_ids.index(current_id)
                self._controls["sound_pack"].SetSelection(new_idx)
            except ValueError:
                if self._sound_pack_ids:
                    self._controls["sound_pack"].SetSelection(0)
        except Exception as e:
            logger.warning(f"Failed to refresh sound pack list: {e}")

    def _on_check_updates(self, event):
        """Check for updates using the UpdateService."""
        import sys

        # Skip update checks when running from source
        if not getattr(sys, "frozen", False):
            wx.MessageBox(
                "Update checking is only available in installed builds.\n"
                "You're running from source — use git pull to update.",
                "Running from Source",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self._controls["update_status"].SetLabel("Checking for updates...")

        def do_update_check():
            import asyncio

            from ...services.simple_update import (
                UpdateService,
                parse_nightly_date,
            )

            try:
                # Get current version and nightly date from the app
                current_version = getattr(self.app, "version", "0.0.0")
                # Check if running a nightly build (tag embedded at build time)
                build_tag = getattr(self.app, "build_tag", None)
                current_nightly_date = parse_nightly_date(build_tag) if build_tag else None
                # Show nightly date in UI when running a nightly build
                if current_nightly_date:
                    current_version = current_nightly_date

                # Determine which channel to check
                channel_idx = self._controls["update_channel"].GetSelection()
                channel = "nightly" if channel_idx == 1 else "stable"

                async def check():
                    service = UpdateService("AccessiWeather")
                    try:
                        return await service.check_for_updates(
                            current_version=current_version,
                            current_nightly_date=current_nightly_date,
                            channel=channel,
                        )
                    finally:
                        await service.close()

                update_info = asyncio.run(check())

                if update_info is None:
                    # Provide context-aware message
                    if current_nightly_date and channel == "stable":
                        status_msg = (
                            f"You're on nightly ({current_nightly_date}).\n"
                            "No newer stable release available."
                        )
                    elif current_nightly_date:
                        status_msg = f"You're on the latest nightly ({current_nightly_date})."
                    else:
                        status_msg = f"You're up to date ({current_version})."

                    wx.CallAfter(
                        self._controls["update_status"].SetLabel,
                        status_msg,
                    )
                    wx.CallAfter(
                        wx.MessageBox,
                        status_msg,
                        "No Updates Available",
                        wx.OK | wx.ICON_INFORMATION,
                    )
                    return

                # Update available - ask user if they want to download
                wx.CallAfter(
                    self._controls["update_status"].SetLabel,
                    f"Update available: {update_info.version}",
                )

                def prompt_download():
                    from .update_dialog import UpdateAvailableDialog

                    channel_label = "Nightly" if update_info.is_nightly else "Stable"
                    dlg = UpdateAvailableDialog(
                        parent=self,
                        current_version=current_version,
                        new_version=update_info.version,
                        channel_label=channel_label,
                        release_notes=update_info.release_notes,
                    )
                    result = dlg.ShowModal()
                    dlg.Destroy()
                    if result == wx.ID_OK:
                        self.app._download_and_apply_update(update_info)

                wx.CallAfter(prompt_download)

            except Exception as e:
                logger.error(f"Error checking for updates: {e}")
                wx.CallAfter(
                    self._controls["update_status"].SetLabel,
                    "Could not check for updates",
                )
                wx.CallAfter(
                    wx.MessageBox,
                    f"Failed to check for updates:\n{e}",
                    "Update Check Failed",
                    wx.OK | wx.ICON_ERROR,
                )

        # Run update check in background thread
        import threading

        thread = threading.Thread(target=do_update_check, daemon=True)
        thread.start()

    def _on_reset_defaults(self, event):
        """Reset settings to defaults."""
        result = wx.MessageBox(
            "Are you sure you want to reset all settings to defaults?\n\n"
            "Your saved locations will be preserved.",
            "Confirm Reset",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result == wx.YES:
            try:
                if self.config_manager.reset_to_defaults():
                    # Reload settings into UI
                    self._load_settings()
                    wx.MessageBox(
                        "Settings have been reset to defaults.\n\n"
                        "Your locations have been preserved.",
                        "Reset Complete",
                        wx.OK | wx.ICON_INFORMATION,
                    )
                else:
                    wx.MessageBox(
                        "Failed to reset settings. Please try again.",
                        "Reset Failed",
                        wx.OK | wx.ICON_ERROR,
                    )
            except Exception as e:
                logger.error(f"Error resetting settings: {e}")
                wx.MessageBox(
                    f"Error resetting settings: {e}",
                    "Reset Error",
                    wx.OK | wx.ICON_ERROR,
                )

    def _on_full_reset(self, event):
        """Full data reset."""
        result = wx.MessageBox(
            "Are you sure you want to reset ALL application data?\n\n"
            "This will delete:\n"
            "• All settings\n"
            "• All saved locations\n"
            "• All caches\n"
            "• Alert history\n\n"
            "This action cannot be undone!",
            "Confirm Full Reset",
            wx.YES_NO | wx.ICON_WARNING,
        )
        if result == wx.YES:
            # Double-confirm for destructive action
            result2 = wx.MessageBox(
                "This is your last chance to cancel.\n\n"
                "Are you absolutely sure you want to delete all data?",
                "Final Confirmation",
                wx.YES_NO | wx.ICON_EXCLAMATION,
            )
            if result2 == wx.YES:
                try:
                    if self.config_manager.reset_all_data():
                        # Reload settings into UI
                        self._load_settings()
                        wx.MessageBox(
                            "All application data has been reset.\n\n"
                            "The application will now use default settings.",
                            "Reset Complete",
                            wx.OK | wx.ICON_INFORMATION,
                        )
                    else:
                        wx.MessageBox(
                            "Failed to reset application data. Please try again.",
                            "Reset Failed",
                            wx.OK | wx.ICON_ERROR,
                        )
                except Exception as e:
                    logger.error(f"Error during full reset: {e}")
                    wx.MessageBox(
                        f"Error during reset: {e}",
                        "Reset Error",
                        wx.OK | wx.ICON_ERROR,
                    )

    def _on_open_config_dir(self, event):
        """Open configuration directory."""
        import os
        import subprocess

        config_dir = str(self.config_manager.config_dir)
        if os.path.exists(config_dir):
            subprocess.Popen(["explorer", config_dir])
        else:
            wx.MessageBox(
                f"Config directory not found: {config_dir}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    _PORTABLE_KEY_SETTINGS = ("visual_crossing_api_key", "openrouter_api_key")

    def _maybe_update_portable_bundle_after_save(self, settings_dict: dict) -> None:
        """
        After saving settings in portable mode, keep the bundle in sync.

        If any API key was changed:
        - Passphrase cached → silently re-encrypt bundle via export_encrypted_api_keys
        - No cached passphrase → prompt for passphrase, then export
        """
        changed_keys = {
            k: v for k, v in settings_dict.items() if k in self._PORTABLE_KEY_SETTINGS and v
        }
        if not changed_keys:
            return

        from ...config.secure_storage import SecureStorage

        app = self.app
        _PASSPHRASE_KEY = getattr(
            app, "_PORTABLE_PASSPHRASE_KEYRING_KEY", "portable_bundle_passphrase"
        )
        config_dir = self.config_manager.config_dir
        bundle_names = ("api-keys.keys", "api-keys.awkeys")
        bundle_path = next(
            (config_dir / n for n in bundle_names if (config_dir / n).exists()), None
        )

        # Get or prompt for passphrase.
        passphrase = (SecureStorage.get_password(_PASSPHRASE_KEY) or "").strip()

        if not passphrase:
            if bundle_path:
                msg = (
                    "Your API keys have been updated.\n\n"
                    "Enter your bundle passphrase to re-encrypt the portable key bundle, "
                    "or Cancel to leave the bundle unchanged (keys are active this session only)."
                )
            else:
                msg = (
                    "Your API keys have been updated.\n\n"
                    "Enter a passphrase to create an encrypted key bundle so your keys "
                    "persist across launches, or Cancel to skip (keys active this session only)."
                )
            with wx.TextEntryDialog(
                self,
                msg,
                "Portable key bundle",
                style=wx.OK | wx.CANCEL | wx.TE_PASSWORD,
            ) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                passphrase = dlg.GetValue().strip()
            if not passphrase:
                return
            # Cache for future use.
            SecureStorage.set_password(_PASSPHRASE_KEY, passphrase)

        # Write/update the bundle — export_encrypted_api_keys reads all keys
        # from in-memory settings + keyring, so no manual merge needed.
        if bundle_path is None:
            bundle_path = config_dir / "api-keys.keys"

        try:
            ok = self.config_manager.export_encrypted_api_keys(bundle_path, passphrase)
            if ok:
                logger.info("Portable key bundle updated after settings save.")
            else:
                wx.MessageBox(
                    "No API keys found to export. Keys are active this session but won't persist.",
                    "Bundle update skipped",
                    wx.OK | wx.ICON_WARNING,
                )
        except Exception as exc:
            logger.error("Failed to update portable key bundle: %s", exc)
            wx.MessageBox(
                "Failed to update the key bundle. Keys are active this session but won't persist.",
                "Bundle update failed",
                wx.OK | wx.ICON_WARNING,
            )

    def _is_runtime_portable_mode(self) -> bool:
        """Return portable mode using runtime app/config state (single source of truth)."""
        app_portable = getattr(self.app, "_portable_mode", None)
        if app_portable is not None:
            return bool(app_portable)

        # Fallback for tests/edge cases where app flag is unavailable.
        try:
            from ...config_utils import is_portable_mode

            return bool(is_portable_mode())
        except Exception:
            return False

    def _has_meaningful_installed_config_data(
        self, installed_config_dir: Path
    ) -> tuple[bool, str | None]:
        """Pre-check whether installed config has meaningful data to transfer."""
        if not installed_config_dir.exists() or not installed_config_dir.is_dir():
            return False, "Installed config directory not found."

        try:
            has_any_entries = any(installed_config_dir.iterdir())
        except Exception:
            has_any_entries = False
        if not has_any_entries:
            return False, "Installed config directory is empty."

        config_file = installed_config_dir / "accessiweather.json"
        if not config_file.exists() or not config_file.is_file():
            return False, "Required config file accessiweather.json is missing."

        try:
            if config_file.stat().st_size <= 0:
                return False, "Config file accessiweather.json is empty."
        except Exception:
            return False, "Could not read accessiweather.json."

        try:
            config_data = self._read_config_json(installed_config_dir)
        except Exception:
            return False, "Config file accessiweather.json is invalid or unreadable."

        locations = (
            config_data.get("locations") if isinstance(config_data.get("locations"), list) else []
        )

        if len(locations) == 0:
            return False, "Installed config has no saved locations to transfer."

        return True, None

    def _get_installed_config_dir(self):
        """Return the standard installed config directory path."""
        import os
        from pathlib import Path

        local_appdata = os.environ.get("LOCALAPPDATA")
        author = getattr(self.app.paths, "_author", "Orinks")
        app_name = getattr(self.app.paths, "_app_name", "AccessiWeather")
        if local_appdata:
            return Path(local_appdata) / str(author) / str(app_name) / "Config"
        return Path.home() / "AppData" / "Local" / str(author) / str(app_name) / "Config"

    def _on_open_installed_config_dir(self, event):
        """Open installed config directory."""
        import subprocess

        installed_config_dir = self._get_installed_config_dir()
        if installed_config_dir.exists():
            subprocess.Popen(["explorer", str(installed_config_dir)])
        else:
            wx.MessageBox(
                f"Installed config directory not found: {installed_config_dir}",
                "Info",
                wx.OK | wx.ICON_INFORMATION,
            )

    def _read_config_json(self, config_dir: Path) -> dict:
        """Read accessiweather.json from a config directory."""
        config_file = config_dir / "accessiweather.json"
        if not config_file.exists():
            raise FileNotFoundError(f"Required config file not found: {config_file}")
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid config payload in {config_file}: expected object")
        return data

    def _validate_portable_copy(
        self, installed_config_dir: Path, portable_config_dir: Path
    ) -> tuple[bool, list[str]]:
        """Validate copied portable config has required non-secret settings/state."""
        messages: list[str] = []
        try:
            src_cfg = self._read_config_json(installed_config_dir)
            dst_cfg = self._read_config_json(portable_config_dir)
        except Exception as e:
            return False, [str(e)]

        src_settings = src_cfg.get("settings") if isinstance(src_cfg.get("settings"), dict) else {}
        dst_settings = dst_cfg.get("settings") if isinstance(dst_cfg.get("settings"), dict) else {}

        required_setting_keys = ["ai_model_preference", "data_source", "temperature_unit"]
        for key in required_setting_keys:
            src_value = src_settings.get(key)
            dst_value = dst_settings.get(key)
            if src_value != dst_value:
                messages.append(
                    f"Setting '{key}' did not copy correctly (installed={src_value!r}, portable={dst_value!r})."
                )

        src_locations = (
            src_cfg.get("locations") if isinstance(src_cfg.get("locations"), list) else []
        )
        dst_locations = (
            dst_cfg.get("locations") if isinstance(dst_cfg.get("locations"), list) else []
        )
        if len(src_locations) != len(dst_locations):
            messages.append(
                f"Location count mismatch after copy (installed={len(src_locations)}, portable={len(dst_locations)})."
            )

        if messages:
            return False, messages
        return True, []

    def _build_portable_copy_summary(self, portable_config_dir: Path) -> list[str]:
        """Build concise summary lines describing migrated non-secret config values."""
        config_data = self._read_config_json(portable_config_dir)
        settings = (
            config_data.get("settings") if isinstance(config_data.get("settings"), dict) else {}
        )
        locations = (
            config_data.get("locations") if isinstance(config_data.get("locations"), list) else []
        )

        custom_prompt_present = any(
            bool(str(settings.get(key, "")).strip())
            for key in (
                "custom_system_prompt",
                "custom_instructions",
                "prompt",
                "assistant_prompt",
            )
            if key in settings
        )

        return [
            f"• locations: {len(locations)}",
            f"• data source: {settings.get('data_source', 'not set')}",
            f"• AI model preference: {settings.get('ai_model_preference', 'not set')}",
            f"• temperature unit: {settings.get('temperature_unit', 'not set')}",
            f"• custom prompt: {'yes' if custom_prompt_present else 'no'}",
        ]

    def _on_copy_installed_config_to_portable(self, event):
        """Copy installed config files into the current portable config directory."""
        import shutil

        portable_config_dir = self.config_manager.config_dir
        installed_config_dir = self._get_installed_config_dir()

        has_data, precheck_reason = self._has_meaningful_installed_config_data(installed_config_dir)
        if not has_data:
            detail = f"\n\nDetails: {precheck_reason}" if precheck_reason else ""
            wx.MessageBox(
                f"Nothing to transfer from installed config.\n{installed_config_dir}{detail}",
                "Nothing to copy",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if installed_config_dir.resolve() == portable_config_dir.resolve():
            wx.MessageBox(
                "Installed and portable config directories are the same location."
                "\n\nNo copy is needed.",
                "Nothing to copy",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        result = wx.MessageBox(
            "Copy settings and locations from installed config to this portable config?\n\n"
            "Only core config files are copied. Cache files are skipped and will regenerate.\n\n"
            "Existing files in portable config with the same name will be overwritten.",
            "Copy installed config to portable",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result != wx.YES:
            return

        # Flush pending in-memory state before filesystem mutation.
        self.config_manager.save_config()

        try:
            portable_config_dir.mkdir(parents=True, exist_ok=True)

            transferable_items = ["accessiweather.json"]
            copied_items: list[str] = []

            for name in transferable_items:
                item = installed_config_dir / name
                if not item.exists():
                    continue

                dst = portable_config_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dst)
                copied_items.append(item.name)

            if not copied_items:
                wx.MessageBox(
                    "Nothing to transfer from installed config."
                    "\n\nNo transferable config files were found.",
                    "Nothing to copy",
                    wx.OK | wx.ICON_WARNING,
                )
                return

            valid, validation_errors = self._validate_portable_copy(
                installed_config_dir, portable_config_dir
            )
            if not valid:
                details = "\n".join(f"• {msg}" for msg in validation_errors)
                wx.MessageBox(
                    "Config copy completed, but validation found problems."
                    "\n\nPortable data may be incomplete."
                    f"\n\n{details}",
                    "Copy incomplete",
                    wx.OK | wx.ICON_WARNING,
                )
                return

            # Reload from copied files so future saves preserve migrated data.
            self.config_manager._config = None
            self.config_manager.load_config()
            self._load_settings()

            copied_list = "\n".join(f"• {name}" for name in copied_items)
            summary_lines = self._build_portable_copy_summary(portable_config_dir)
            summary_block = "\n".join(summary_lines)
            wx.MessageBox(
                "Copied these config item(s):\n"
                f"{copied_list}\n\n"
                "Copied settings summary:\n"
                f"{summary_block}\n\n"
                f"From:\n{installed_config_dir}\n\n"
                f"To:\n{portable_config_dir}",
                "Copy complete",
                wx.OK | wx.ICON_INFORMATION,
            )

            # Offer to export API keys from keyring to encrypted bundle.
            self._offer_api_key_export_after_copy(portable_config_dir)
        except Exception as e:
            logger.error(f"Failed to copy installed config to portable: {e}")
            wx.MessageBox(
                f"Failed to copy config: {e}",
                "Copy failed",
                wx.OK | wx.ICON_ERROR,
            )

    def _offer_api_key_export_after_copy(self, portable_config_dir: Path) -> None:
        """After copying installed config to portable, offer to export API keys."""
        result = wx.MessageBox(
            "Config copied. Your API keys are stored in the system keyring and were not "
            "copied.\n\n"
            "Would you like to export them to an encrypted bundle now so they work in "
            "portable mode?",
            "Export API keys?",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result != wx.YES:
            wx.MessageBox(
                "You can export API keys later from Settings > Advanced > "
                "Export API keys (encrypted).",
                "API keys not exported",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        passphrase = self._prompt_passphrase(
            "Export API keys (encrypted)",
            "Enter a passphrase to encrypt your API keys.",
        )
        if passphrase is None:
            return

        confirm = self._prompt_passphrase(
            "Confirm passphrase",
            "Re-enter the passphrase to confirm.",
        )
        if confirm is None:
            return
        if passphrase != confirm:
            wx.MessageBox(
                "Passphrases do not match. API keys were not exported.",
                "Export cancelled",
                wx.OK | wx.ICON_WARNING,
            )
            return

        bundle_path = portable_config_dir / "api-keys.keys"
        try:
            ok = self.config_manager.export_encrypted_api_keys(bundle_path, passphrase)
            if ok:
                wx.MessageBox(
                    f"API keys exported to:\n{bundle_path}",
                    "Export complete",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    "No API keys found to export. You can add keys in Settings > Data Sources "
                    "and export later.",
                    "No keys to export",
                    wx.OK | wx.ICON_WARNING,
                )
        except Exception as exc:
            logger.error("Failed to export API keys after config copy: %s", exc)
            wx.MessageBox(
                f"Failed to export API keys: {exc}",
                "Export failed",
                wx.OK | wx.ICON_ERROR,
            )

    def _prompt_passphrase(self, title: str, message: str) -> str | None:
        """Prompt for passphrase using masked text entry."""
        with wx.TextEntryDialog(
            self, message, title, style=wx.OK | wx.CANCEL | wx.TE_PASSWORD
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return None
            value = dlg.GetValue().strip()
            return value or None

    def _on_export_encrypted_api_keys(self, event):
        """Export API keys from keyring to encrypted bundle file."""
        from pathlib import Path

        passphrase = self._prompt_passphrase(
            "Export API keys (encrypted)",
            "Enter a passphrase to encrypt exported API keys.",
        )
        if passphrase is None:
            return

        confirm = self._prompt_passphrase(
            "Confirm passphrase",
            "Re-enter the passphrase to confirm encrypted export.",
        )
        if confirm is None:
            return
        if passphrase != confirm:
            wx.MessageBox("Passphrases do not match.", "Export Cancelled", wx.OK | wx.ICON_WARNING)
            return

        with wx.FileDialog(
            self,
            "Export API keys (encrypted)",
            wildcard="Encrypted bundle (*.keys)|*.keys|Legacy bundle (*.awkeys)|*.awkeys",
            defaultFile="accessiweather_api_keys.keys",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            export_path = Path(dlg.GetPath())
            if self.config_manager.export_encrypted_api_keys(export_path, passphrase):
                wx.MessageBox(
                    f"Encrypted API key bundle exported successfully to:\n{export_path}",
                    "Export Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    "Failed to export encrypted API keys. Ensure at least one API key is saved.",
                    "Export Failed",
                    wx.OK | wx.ICON_ERROR,
                )

    def _on_import_encrypted_api_keys(self, event):
        """Import encrypted API key bundle into local secure storage."""
        from pathlib import Path

        with wx.FileDialog(
            self,
            "Import API keys (encrypted)",
            wildcard="Encrypted bundle (*.keys)|*.keys|Legacy bundle (*.awkeys)|*.awkeys",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            import_path = Path(dlg.GetPath())

        passphrase = self._prompt_passphrase(
            "Import API keys (encrypted)",
            "Enter the passphrase used when exporting this encrypted bundle.",
        )
        if passphrase is None:
            return

        if self.config_manager.import_encrypted_api_keys(import_path, passphrase):
            self._load_settings()
            wx.MessageBox(
                "Encrypted API keys imported successfully into this machine's secure keyring.",
                "Import Complete",
                wx.OK | wx.ICON_INFORMATION,
            )
        else:
            wx.MessageBox(
                "Failed to import encrypted API keys. Check passphrase and bundle file.",
                "Import Failed",
                wx.OK | wx.ICON_ERROR,
            )

    def _on_export_settings(self, event):
        """Export settings to file."""
        from pathlib import Path

        with wx.FileDialog(
            self,
            "Export Settings",
            wildcard="JSON files (*.json)|*.json",
            defaultFile="accessiweather_settings.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                export_path = Path(dlg.GetPath())
                try:
                    if self.config_manager.export_settings(export_path):
                        wx.MessageBox(
                            f"Settings exported successfully to:\n{export_path}\n\n"
                            f"Note: {API_KEYS_TRANSFER_NOTE}",
                            "Export Complete",
                            wx.OK | wx.ICON_INFORMATION,
                        )
                    else:
                        wx.MessageBox(
                            "Failed to export settings. Please try again.",
                            "Export Failed",
                            wx.OK | wx.ICON_ERROR,
                        )
                except Exception as e:
                    logger.error(f"Error exporting settings: {e}")
                    wx.MessageBox(
                        f"Error exporting settings: {e}",
                        "Export Error",
                        wx.OK | wx.ICON_ERROR,
                    )

    def _on_import_settings(self, event):
        """Import settings from file."""
        from pathlib import Path

        with wx.FileDialog(
            self,
            "Import Settings",
            wildcard="JSON files (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                import_path = Path(dlg.GetPath())
                result = wx.MessageBox(
                    "Importing settings will overwrite your current preferences.\n\n"
                    "Your saved locations will NOT be affected.\n\n"
                    f"Important: {API_KEYS_TRANSFER_NOTE}\n\n"
                    "Do you want to continue?",
                    "Confirm Import",
                    wx.YES_NO | wx.ICON_QUESTION,
                )
                if result == wx.YES:
                    try:
                        if self.config_manager.import_settings(import_path):
                            # Reload settings into UI
                            self._load_settings()
                            wx.MessageBox(
                                "Settings imported successfully!\n\n"
                                f"Note: {API_KEYS_TRANSFER_NOTE}",
                                "Import Complete",
                                wx.OK | wx.ICON_INFORMATION,
                            )
                        else:
                            wx.MessageBox(
                                "Failed to import settings.\n\n"
                                "The file may be invalid or corrupted.",
                                "Import Failed",
                                wx.OK | wx.ICON_ERROR,
                            )
                    except Exception as e:
                        logger.error(f"Error importing settings: {e}")
                        wx.MessageBox(
                            f"Error importing settings: {e}",
                            "Import Error",
                            wx.OK | wx.ICON_ERROR,
                        )

    def _on_minimize_tray_changed(self, event):
        """Handle minimize to tray checkbox state change."""
        minimize_to_tray_enabled = self._controls["minimize_tray"].GetValue()
        self._update_minimize_on_startup_state(minimize_to_tray_enabled)
        event.Skip()

    def _on_taskbar_icon_text_enabled_changed(self, event):
        """Enable/disable taskbar text controls when main toggle changes."""
        taskbar_text_enabled = self._controls["taskbar_icon_text_enabled"].GetValue()
        self._update_taskbar_text_controls_state(taskbar_text_enabled)
        event.Skip()

    def _update_minimize_on_startup_state(self, minimize_to_tray_enabled: bool):
        """
        Update the enabled state of minimize_on_startup based on minimize_to_tray.

        Args:
            minimize_to_tray_enabled: Whether minimize to tray is enabled

        """
        self._controls["minimize_on_startup"].Enable(minimize_to_tray_enabled)
        if not minimize_to_tray_enabled:
            # If minimize to tray is disabled, also uncheck minimize on startup
            self._controls["minimize_on_startup"].SetValue(False)

    def _update_taskbar_text_controls_state(self, taskbar_text_enabled: bool):
        """Enable/disable dependent taskbar text controls."""
        self._controls["taskbar_icon_dynamic_enabled"].Enable(taskbar_text_enabled)
        self._controls["taskbar_icon_text_format"].Enable(taskbar_text_enabled)

    def _on_open_soundpacks_dir(self, event):
        """Open sound packs directory."""
        import subprocess

        from ...soundpack_paths import get_soundpacks_dir

        soundpacks_dir = get_soundpacks_dir()
        if soundpacks_dir.exists():
            subprocess.Popen(["explorer", str(soundpacks_dir)])
        else:
            wx.MessageBox(
                f"Sound packs directory not found: {soundpacks_dir}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )


def show_settings_dialog(parent, app: AccessiWeatherApp, tab: str | None = None) -> bool:
    """
    Show the settings dialog.

    Args:
        parent: Parent window
        app: Application instance
        tab: Optional tab name to switch to (e.g., 'Updates', 'General')

    Returns:
        True if settings were changed, False otherwise

    """
    try:
        parent_ctrl = parent

        dlg = SettingsDialogSimple(parent_ctrl, app)

        # Switch to specified tab if provided
        if tab:
            for i in range(dlg.notebook.GetPageCount()):
                if dlg.notebook.GetPageText(i) == tab:
                    dlg.notebook.SetSelection(i)
                    break

        result = dlg.ShowModal() == wx.ID_OK
        dlg.Destroy()
        return result

    except Exception as e:
        logger.error(f"Failed to show settings dialog: {e}")
        wx.MessageBox(
            f"Failed to open settings: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return False
