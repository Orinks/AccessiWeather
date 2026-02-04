"""Settings dialog for application configuration using wxPython."""

from __future__ import annotations

import logging
import webbrowser
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)


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

        # Time & Date Display Section
        sizer.Add(
            wx.StaticText(panel, label="Time & Date Display:"),
            0,
            wx.ALL,
            5,
        )

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
                label="When using Auto mode, data is merged from multiple sources in priority order.",
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

        self._controls["debug"] = wx.CheckBox(panel, label="Enable Debug Mode")
        sizer.Add(self._controls["debug"], 0, wx.LEFT | wx.BOTTOM, 5)

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

        open_config_btn = wx.Button(panel, label="Open config directory")
        open_config_btn.Bind(wx.EVT_BUTTON, self._on_open_config_dir)
        sizer.Add(open_config_btn, 0, wx.LEFT | wx.TOP, 10)

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

            # Source priority (simplified - just use defaults for now)
            self._controls["us_priority"].SetSelection(0)
            self._controls["intl_priority"].SetSelection(0)

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
                getattr(settings, "notify_discussion_update", False)
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

            ai_model = getattr(
                settings, "ai_model_preference", "meta-llama/llama-3.3-70b-instruct:free"
            )
            if ai_model == "meta-llama/llama-3.3-70b-instruct:free":
                self._controls["ai_model"].SetSelection(0)
            elif ai_model == "auto":
                self._controls["ai_model"].SetSelection(1)
            else:
                # Specific model was selected - add it to the dropdown
                model_display = f"Selected: {ai_model.split('/')[-1]}"
                self._controls["ai_model"].Append(model_display)
                self._controls["ai_model"].SetSelection(2)
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
            self._controls["startup"].SetValue(getattr(settings, "startup_enabled", False))
            self._controls["weather_history"].SetValue(
                getattr(settings, "weather_history_enabled", True)
            )
            self._controls["debug"].SetValue(getattr(settings, "debug_mode", False))

        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def _save_settings(self) -> bool:
        """Save settings from UI controls."""
        try:
            # Map selections back to values
            source_values = ["auto", "nws", "openmeteo", "visualcrossing"]
            temp_values = ["f", "c", "both"]
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

            settings_dict = {
                # General
                "update_interval_minutes": self._controls["update_interval"].GetValue(),
                # Display
                "temperature_unit": temp_values[self._controls["temp_unit"].GetSelection()],
                "show_dewpoint": self._controls["show_dewpoint"].GetValue(),
                "show_visibility": self._controls["show_visibility"].GetValue(),
                "show_uv_index": self._controls["show_uv_index"].GetValue(),
                "show_pressure_trend": self._controls["show_pressure_trend"].GetValue(),
                "show_detailed_forecast": self._controls["detailed_forecast"].GetValue(),
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
                "openmeteo_weather_model": model_values[
                    self._controls["openmeteo_model"].GetSelection()
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
                "debug_mode": self._controls["debug"].GetValue(),
            }

            success = self.config_manager.update_settings(**settings_dict)
            if success:
                logger.info("Settings saved successfully")
            return success

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def _setup_accessibility(self):
        """Set up accessibility labels for controls."""
        # Set accessible names for key controls
        self._controls["update_interval"].SetName("Update interval in minutes")
        self._controls["temp_unit"].SetName("Temperature unit selection")
        self._controls["data_source"].SetName("Weather data source selection")
        self._controls["vc_key"].SetName("Visual Crossing API key")
        self._controls["openrouter_key"].SetName("OpenRouter API key")

    def _get_ai_model_preference(self) -> str:
        """Get the AI model preference based on UI selection."""
        selection = self._controls["ai_model"].GetSelection()
        if selection == 0:
            return "meta-llama/llama-3.3-70b-instruct:free"
        if selection == 1:
            return "auto"
        if selection == 2 and self._selected_specific_model:
            return self._selected_specific_model
        return "meta-llama/llama-3.3-70b-instruct:free"

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
            # Check if it's a known preset
            if selected_model_id == "meta-llama/llama-3.3-70b-instruct:free":
                self._controls["ai_model"].SetSelection(0)
            elif selected_model_id == "openrouter/auto":
                self._controls["ai_model"].SetSelection(1)
            else:
                # Add as "Specific Model" option or update existing
                model_display = f"Selected: {selected_model_id.split('/')[-1]}"
                if self._controls["ai_model"].GetCount() > 2:
                    # Replace existing specific model choice
                    self._controls["ai_model"].SetString(2, model_display)
                else:
                    # Add new specific model choice
                    self._controls["ai_model"].Append(model_display)
                self._controls["ai_model"].SetSelection(2)
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
            self._controls["update_status"].SetLabel("Running from source — use git pull to update")
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
                        # Running nightly, checked stable - explain the situation
                        status_msg = (
                            f"You're on nightly ({current_nightly_date}). "
                            f"No newer stable release available."
                        )
                    elif current_nightly_date:
                        status_msg = f"You're on the latest nightly ({current_nightly_date})"
                    else:
                        status_msg = f"You're up to date ({current_version})"

                    wx.CallAfter(
                        self._controls["update_status"].SetLabel,
                        status_msg,
                    )
                    return

                # Update available - ask user if they want to download
                wx.CallAfter(
                    self._controls["update_status"].SetLabel,
                    f"Update available: {update_info.version}",
                )

                def prompt_download():
                    channel_label = "Nightly" if update_info.is_nightly else "Stable"
                    result = wx.MessageBox(
                        f"A new {channel_label} version is available!\n\n"
                        f"Current: {current_version}\n"
                        f"Latest: {update_info.version}\n\n"
                        f"Download now?",
                        "Update Available",
                        wx.YES_NO | wx.ICON_INFORMATION,
                    )
                    if result == wx.YES:
                        # Use app's download method
                        self.app._download_and_apply_update(update_info)

                wx.CallAfter(prompt_download)

            except Exception as e:
                logger.error(f"Error checking for updates: {e}")
                wx.CallAfter(
                    self._controls["update_status"].SetLabel,
                    "Could not check for updates",
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

        config_dir = str(self.app.paths.config)
        if os.path.exists(config_dir):
            subprocess.Popen(["explorer", config_dir])
        else:
            wx.MessageBox(
                f"Config directory not found: {config_dir}",
                "Error",
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
                            "Note: API keys are NOT included in the export for security.",
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
                                "Note: API keys must be configured separately.",
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
