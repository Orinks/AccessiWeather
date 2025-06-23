"""Tab component builders for the settings dialog.

This module contains builder classes for each settings tab, handling
UI component creation and layout for better organization and maintainability.
"""

import logging

import wx

from accessiweather.format_string_parser import FormatStringParser

from .constants import (
    DEFAULT_UPDATE_CHECK_INTERVAL,
    MAX_UPDATE_CHECK_INTERVAL,
    MIN_ALERT_RADIUS,
    MIN_CACHE_TTL,
    MIN_UPDATE_CHECK_INTERVAL,
    MIN_UPDATE_INTERVAL,
)

logger = logging.getLogger(__name__)


class GeneralTabBuilder:
    """Builder for the General settings tab."""

    def __init__(self, parent_dialog):
        self.dialog = parent_dialog

    def build_tab(self, panel):
        """Build the General tab UI components."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Input Fields
        grid_sizer = wx.FlexGridSizer(rows=9, cols=2, vgap=10, hgap=5)
        grid_sizer.AddGrowableCol(1, 1)

        # Data Source Selection
        data_source_label = wx.StaticText(panel, label="Weather Data Source:")
        self.dialog.data_source_ctrl = wx.Choice(panel, name="Data Source")
        self.dialog.data_source_ctrl.AppendItems(
            [
                "National Weather Service (NWS)",
                "Open-Meteo (International)",
                "Automatic (NWS for US, Open-Meteo for non-US)",
            ]
        )
        tooltip_data_source = (
            "Select which weather data provider to use. "
            "NWS provides data for US locations only (includes weather alerts). "
            "Open-Meteo provides free weather data for international locations (no alerts available). "
            "Automatic option uses NWS for US locations and Open-Meteo for non-US locations."
        )
        self.dialog.data_source_ctrl.SetToolTip(tooltip_data_source)
        grid_sizer.Add(data_source_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.dialog.data_source_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        # Update Interval
        update_interval_label = wx.StaticText(panel, label="Update Interval (minutes):")
        self.dialog.update_interval_ctrl = wx.SpinCtrl(
            panel, min=MIN_UPDATE_INTERVAL, max=1440, initial=10, name="Update Interval"
        )
        tooltip_interval = "How often to automatically refresh all weather data including forecasts and alerts (in minutes)."
        self.dialog.update_interval_ctrl.SetToolTip(tooltip_interval)
        grid_sizer.Add(update_interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.dialog.update_interval_ctrl, 0, wx.ALL, 5)

        # Alert Radius
        alert_radius_label = wx.StaticText(panel, label="Alert Radius (miles):")
        self.dialog.alert_radius_ctrl = wx.SpinCtrl(
            panel, min=MIN_ALERT_RADIUS, max=500, initial=10, name="Alert Radius"
        )
        tooltip_radius = (
            "Radius around location to check for alerts (in miles). "
            "Only used as fallback when precise point-based alerts are unavailable. "
            "Smaller values (5-15 miles) are recommended for most locations."
        )
        self.dialog.alert_radius_ctrl.SetToolTip(tooltip_radius)
        grid_sizer.Add(alert_radius_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.dialog.alert_radius_ctrl, 0, wx.ALL, 5)

        # Precise Location Alerts Toggle
        precise_alerts_label = "Use point-based alerts (more precise)"
        self.dialog.precise_alerts_ctrl = wx.CheckBox(
            panel, label=precise_alerts_label, name="Precise Location Alerts"
        )
        tooltip_precise = (
            "When checked, shows only alerts that specifically affect your exact location coordinates. "
            "When unchecked, shows all alerts for your county/zone (may include more alerts from nearby areas). "
            "Point-based alerts are more precise but may miss some relevant regional alerts."
        )
        self.dialog.precise_alerts_ctrl.SetToolTip(tooltip_precise)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.dialog.precise_alerts_ctrl, 0, wx.ALL, 5)

        # Show Nationwide Location Toggle
        show_nationwide_label = "Show Nationwide location"
        self.dialog.show_nationwide_ctrl = wx.CheckBox(
            panel, label=show_nationwide_label, name="Show Nationwide Location"
        )
        tooltip_nationwide = (
            "When checked, shows the Nationwide location in the location list. "
            "When unchecked, hides it from view."
        )
        self.dialog.show_nationwide_ctrl.SetToolTip(tooltip_nationwide)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.dialog.show_nationwide_ctrl, 0, wx.ALL, 5)

        # Auto-Refresh National Data Toggle
        auto_refresh_national_label = "Auto-refresh national data"
        self.dialog.auto_refresh_national_ctrl = wx.CheckBox(
            panel, label=auto_refresh_national_label, name="Auto-Refresh National Data"
        )
        tooltip_auto_refresh = (
            "When checked, national data will be automatically refreshed when the timer fires. "
            "When unchecked, you must manually refresh national data."
        )
        self.dialog.auto_refresh_national_ctrl.SetToolTip(tooltip_auto_refresh)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.dialog.auto_refresh_national_ctrl, 0, wx.ALL, 5)

        sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(sizer)


class DisplayTabBuilder:
    """Builder for the Display settings tab."""

    def __init__(self, parent_dialog):
        self.dialog = parent_dialog

    def build_tab(self, panel):
        """Build the Display tab UI components."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Input Fields
        grid_sizer = wx.FlexGridSizer(rows=4, cols=2, vgap=10, hgap=5)
        grid_sizer.AddGrowableCol(1, 1)

        # Measurement Unit System Selection
        temp_unit_label = wx.StaticText(panel, label="Measurement Units:")
        from ..ui_components import AccessibleChoice

        self.dialog.temp_unit_ctrl = AccessibleChoice(
            panel,
            choices=["Imperial (Fahrenheit)", "Metric (Celsius)", "Both"],
            label="Measurement Units",
        )
        tooltip_temp_unit = (
            "Select your preferred measurement unit system. "
            "Affects temperature, pressure, wind speed, and other measurements. "
            "'Both' will show temperatures in both Fahrenheit and Celsius."
        )
        self.dialog.temp_unit_ctrl.SetToolTip(tooltip_temp_unit)
        grid_sizer.Add(temp_unit_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.dialog.temp_unit_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        # Taskbar Icon Text Toggle
        taskbar_text_label = "Show weather information in taskbar icon"
        self.dialog.taskbar_text_ctrl = wx.CheckBox(
            panel, label=taskbar_text_label, name="Taskbar Icon Text"
        )
        tooltip_taskbar = (
            "When checked, the taskbar icon will display weather information "
            "according to the format string below."
        )
        self.dialog.taskbar_text_ctrl.SetToolTip(tooltip_taskbar)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.dialog.taskbar_text_ctrl, 0, wx.ALL, 5)

        # Dynamic Format Switching Toggle
        dynamic_format_label = "Enable dynamic format switching"
        self.dialog.dynamic_format_ctrl = wx.CheckBox(
            panel, label=dynamic_format_label, name="Dynamic Format Switching"
        )
        tooltip_dynamic = (
            "When ENABLED: Format automatically changes for severe weather and alerts "
            "(e.g., '⚠️ Tornado Warning: Severe'). "
            "When DISABLED: Your custom format below is always used, regardless of conditions."
        )
        self.dialog.dynamic_format_ctrl.SetToolTip(tooltip_dynamic)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.dialog.dynamic_format_ctrl, 0, wx.ALL, 5)

        # Taskbar Icon Text Format
        taskbar_format_label = wx.StaticText(panel, label="Taskbar Icon Text Format:")
        self.dialog.taskbar_format_ctrl = wx.TextCtrl(panel, name="Taskbar Format")
        tooltip_format = (
            "Enter your preferred format with placeholders like {temp}, {condition}, etc. "
            "When dynamic switching is OFF, this format is always used. "
            "When dynamic switching is ON, this serves as the default format for normal conditions "
            "and as a fallback for severe weather/alerts."
        )
        self.dialog.taskbar_format_ctrl.SetToolTip(tooltip_format)
        grid_sizer.Add(taskbar_format_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.dialog.taskbar_format_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        # Add the grid sizer to the main sizer
        sizer.Add(grid_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Add help text for placeholders
        help_label = wx.StaticText(panel, label="Available Placeholders:")
        sizer.Add(help_label, 0, wx.LEFT | wx.TOP, 15)

        # Create a read-only text control for the placeholder help
        self.dialog.placeholder_help_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
            size=(-1, 150),
            name="Placeholder Help",
        )

        # Get the help text from the FormatStringParser
        help_text = FormatStringParser.get_supported_placeholders_help()
        self.dialog.placeholder_help_ctrl.SetValue(help_text)

        # Add the help text control to the sizer
        sizer.Add(self.dialog.placeholder_help_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        # Set the sizer for the panel
        panel.SetSizer(sizer)

        # Bind events
        self.dialog.taskbar_text_ctrl.Bind(wx.EVT_CHECKBOX, self.dialog._on_taskbar_text_toggle)


class AdvancedTabBuilder:
    """Builder for the Advanced settings tab."""

    def __init__(self, parent_dialog):
        self.dialog = parent_dialog

    def build_tab(self, panel):
        """Build the Advanced tab UI components."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Input Fields
        grid_sizer = wx.FlexGridSizer(rows=3, cols=2, vgap=10, hgap=5)
        grid_sizer.AddGrowableCol(1, 1)

        # Minimize to Tray Toggle
        minimize_to_tray_label = "Minimize to system tray when closing"
        self.dialog.minimize_to_tray_ctrl = wx.CheckBox(
            panel, label=minimize_to_tray_label, name="Minimize to Tray"
        )
        tooltip_minimize = (
            "When checked, clicking the X button will minimize the app to the system tray "
            "instead of closing it. You can still exit from the system tray menu."
        )
        self.dialog.minimize_to_tray_ctrl.SetToolTip(tooltip_minimize)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.dialog.minimize_to_tray_ctrl, 0, wx.ALL, 5)

        # Cache Enabled Toggle
        cache_enabled_label = "Enable caching of weather data"
        self.dialog.cache_enabled_ctrl = wx.CheckBox(
            panel, label=cache_enabled_label, name="Enable Caching"
        )
        tooltip_cache = (
            "When checked, weather data will be cached to reduce API calls. "
            "This can improve performance and reduce data usage."
        )
        self.dialog.cache_enabled_ctrl.SetToolTip(tooltip_cache)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.dialog.cache_enabled_ctrl, 0, wx.ALL, 5)

        # Cache TTL
        cache_ttl_label = wx.StaticText(panel, label="Cache Time-to-Live (seconds):")
        self.dialog.cache_ttl_ctrl = wx.SpinCtrl(
            panel, min=MIN_CACHE_TTL, max=3600, initial=300, name="Cache TTL"
        )
        tooltip_ttl = "How long cached data remains valid (in seconds)."
        self.dialog.cache_ttl_ctrl.SetToolTip(tooltip_ttl)
        grid_sizer.Add(cache_ttl_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.dialog.cache_ttl_ctrl, 0, wx.ALL, 5)

        sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(sizer)


class UpdatesTabBuilder:
    """Builder for the Updates settings tab."""

    def __init__(self, parent_dialog):
        self.dialog = parent_dialog

    def build_tab(self, panel):
        """Build the Updates tab UI components."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Input Fields
        grid_sizer = wx.FlexGridSizer(rows=4, cols=2, vgap=10, hgap=5)
        grid_sizer.AddGrowableCol(1, 1)

        # Auto-check for updates toggle
        auto_check_label = "Automatically check for updates"
        self.dialog.auto_update_check_ctrl = wx.CheckBox(
            panel, label=auto_check_label, name="Auto Check Updates"
        )
        tooltip_auto_check = (
            "When checked, AccessiWeather will automatically check for updates "
            "in the background according to the interval below."
        )
        self.dialog.auto_update_check_ctrl.SetToolTip(tooltip_auto_check)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.dialog.auto_update_check_ctrl, 0, wx.ALL, 5)

        # Update check interval
        interval_label = wx.StaticText(panel, label="Check interval (hours):")
        self.dialog.update_check_interval_ctrl = wx.SpinCtrl(
            panel,
            min=MIN_UPDATE_CHECK_INTERVAL,
            max=MAX_UPDATE_CHECK_INTERVAL,
            initial=DEFAULT_UPDATE_CHECK_INTERVAL,
            name="Update Check Interval",
        )
        tooltip_interval = (
            "How often to check for updates (in hours). Minimum 1 hour, maximum 1 week."
        )
        self.dialog.update_check_interval_ctrl.SetToolTip(tooltip_interval)
        grid_sizer.Add(interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.dialog.update_check_interval_ctrl, 0, wx.ALL, 5)

        # Update channel selection
        channel_label = wx.StaticText(panel, label="Update channel:")
        self.dialog.update_channel_ctrl = wx.Choice(panel, name="Update Channel")
        self.dialog.update_channel_ctrl.AppendItems(
            ["Stable releases only", "Development builds (includes pre-releases)"]
        )
        tooltip_channel = (
            "Choose which type of updates to receive. "
            "Stable releases are tested and recommended for most users. "
            "Development builds include the latest features but may be less stable."
        )
        self.dialog.update_channel_ctrl.SetToolTip(tooltip_channel)
        grid_sizer.Add(channel_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.dialog.update_channel_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        # Manual check button
        check_now_label = wx.StaticText(panel, label="Manual check:")
        self.dialog.check_now_button = wx.Button(
            panel, label="Check for Updates Now", name="Check Now"
        )
        tooltip_check_now = "Click to immediately check for available updates."
        self.dialog.check_now_button.SetToolTip(tooltip_check_now)
        grid_sizer.Add(check_now_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.dialog.check_now_button, 0, wx.ALL, 5)

        sizer.Add(grid_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Add informational text
        info_text = (
            "Update Information:\n\n"
            "• Stable releases are thoroughly tested and recommended for daily use\n"
            "• Development builds include the latest features and bug fixes\n"
            "• When updates are available, you can choose to download manually or install automatically\n"
            "• Automatic installation requires administrator privileges and UAC confirmation"
        )
        info_label = wx.StaticText(panel, label=info_text)
        info_label.SetFont(info_label.GetFont().Smaller())
        sizer.Add(info_label, 0, wx.ALL, 15)

        panel.SetSizer(sizer)

        # Bind events
        self.dialog.auto_update_check_ctrl.Bind(wx.EVT_CHECKBOX, self.dialog._on_auto_update_toggle)
        self.dialog.check_now_button.Bind(wx.EVT_BUTTON, self.dialog._on_check_now)
