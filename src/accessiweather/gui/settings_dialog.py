"""
Dialog for configuring AccessiWeather settings.
"""

import logging

import wx
import wx.adv

from accessiweather.format_string_parser import FormatStringParser
from accessiweather.utils.temperature_utils import TemperatureUnit

logger = logging.getLogger(__name__)

# Define constants for settings keys if needed, or use strings directly
UPDATE_INTERVAL_KEY = "update_interval_minutes"
ALERT_RADIUS_KEY = "alert_radius_miles"
PRECISE_LOCATION_ALERTS_KEY = "precise_location_alerts"
SHOW_NATIONWIDE_KEY = "show_nationwide_location"
AUTO_REFRESH_NATIONAL_KEY = "auto_refresh_national"

# Advanced settings keys
CACHE_ENABLED_KEY = "cache_enabled"
CACHE_TTL_KEY = "cache_ttl"

# System tray settings
MINIMIZE_ON_STARTUP_KEY = "minimize_on_startup"
MINIMIZE_TO_TRAY_KEY = "minimize_to_tray"

# Display settings keys
TASKBAR_ICON_TEXT_ENABLED_KEY = "taskbar_icon_text_enabled"
TASKBAR_ICON_TEXT_FORMAT_KEY = "taskbar_icon_text_format"
TEMPERATURE_UNIT_KEY = "temperature_unit"
DEFAULT_TEMPERATURE_UNIT = TemperatureUnit.FAHRENHEIT.value

# Data source constants
DATA_SOURCE_KEY = "data_source"
API_KEYS_SECTION = "api_keys"

# Valid data source values
DATA_SOURCE_NWS = "nws"
DATA_SOURCE_OPENMETEO = "openmeteo"
DATA_SOURCE_AUTO = "auto"
VALID_DATA_SOURCES = [DATA_SOURCE_NWS, DATA_SOURCE_OPENMETEO, DATA_SOURCE_AUTO]

# Default values
DEFAULT_DATA_SOURCE = DATA_SOURCE_AUTO


class SettingsDialog(wx.Dialog):
    """
    A dialog window for modifying application settings.
    """

    def __init__(self, parent, current_settings):
        """
        Initialize the Settings Dialog.

        Args:
            parent: The parent window.
            current_settings (dict): A dictionary containing the current values
                                     for the settings to be edited.
                                     Expected keys: 'api_contact',
                                     'update_interval_minutes',
                                     'alert_radius_miles'.
        """
        super().__init__(parent, title="Settings", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.current_settings = current_settings
        self._init_ui()
        self._load_settings()
        self.SetSizerAndFit(self.main_sizer)
        self.CenterOnParent()

    def _init_ui(self):
        """Initialize the UI components of the dialog."""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create notebook (tab control)
        self.notebook = wx.Notebook(self)
        self.main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

        # We don't need a title since the dialog already has a title bar

        # Create General tab
        self.general_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.general_panel, "General")
        self._init_general_tab()

        # Create Display tab
        self.display_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.display_panel, "Display")
        self._init_display_tab()

        # Create Advanced tab
        self.advanced_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.advanced_panel, "Advanced")
        self._init_advanced_tab()

        # --- Buttons ---
        button_sizer = wx.StdDialogButtonSizer()

        ok_button = wx.Button(self, wx.ID_OK)
        ok_button.SetDefault()
        button_sizer.AddButton(ok_button)

        cancel_button = wx.Button(self, wx.ID_CANCEL)
        button_sizer.AddButton(cancel_button)

        button_sizer.Realize()

        self.main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        # Bind events
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        # Cancel is handled automatically by wx.Dialog

    def _init_general_tab(self):
        """Initialize the General tab controls."""
        panel = self.general_panel
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Input Fields ---
        grid_sizer = wx.FlexGridSizer(
            rows=9, cols=2, vgap=10, hgap=5
        )  # 9 rows (increased for hyperlink)
        grid_sizer.AddGrowableCol(1, 1)  # Make the input column growable

        # Data Source Selection
        data_source_label = wx.StaticText(panel, label="Weather Data Source:")
        self.data_source_ctrl = wx.Choice(panel, name="Data Source")
        self.data_source_ctrl.AppendItems(
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
        self.data_source_ctrl.SetToolTip(tooltip_data_source)
        grid_sizer.Add(data_source_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.data_source_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        # Placeholder for future weather API integration

        # Update Interval
        update_interval_label = wx.StaticText(panel, label="Update Interval (minutes):")
        self.update_interval_ctrl = wx.SpinCtrl(
            panel, min=1, max=1440, initial=10, name="Update Interval"
        )
        tooltip_interval = "How often to automatically refresh all weather data including forecasts and alerts (in minutes)."
        self.update_interval_ctrl.SetToolTip(tooltip_interval)
        grid_sizer.Add(update_interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.update_interval_ctrl, 0, wx.ALL, 5)

        # Alert Radius
        alert_radius_label = wx.StaticText(panel, label="Alert Radius (miles):")
        self.alert_radius_ctrl = wx.SpinCtrl(panel, min=1, max=500, initial=25, name="Alert Radius")
        tooltip_radius = "Radius around location to check for alerts (in miles)."
        self.alert_radius_ctrl.SetToolTip(tooltip_radius)
        grid_sizer.Add(alert_radius_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.alert_radius_ctrl, 0, wx.ALL, 5)

        # Precise Location Alerts Toggle
        precise_alerts_label = "Use precise location for alerts"
        self.precise_alerts_ctrl = wx.CheckBox(
            panel, label=precise_alerts_label, name="Precise Location Alerts"
        )
        tooltip_precise = (
            "When checked, only shows alerts for your specific location. "
            "When unchecked, shows all alerts for your state."
        )
        self.precise_alerts_ctrl.SetToolTip(tooltip_precise)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.precise_alerts_ctrl, 0, wx.ALL, 5)

        # Show Nationwide Location Toggle
        show_nationwide_label = "Show Nationwide location"
        self.show_nationwide_ctrl = wx.CheckBox(
            panel, label=show_nationwide_label, name="Show Nationwide Location"
        )
        tooltip_nationwide = (
            "When checked, shows the Nationwide location in the location list. "
            "When unchecked, hides it from view."
        )
        self.show_nationwide_ctrl.SetToolTip(tooltip_nationwide)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.show_nationwide_ctrl, 0, wx.ALL, 5)

        # Auto-Refresh National Data Toggle
        auto_refresh_national_label = "Auto-refresh national data"
        self.auto_refresh_national_ctrl = wx.CheckBox(
            panel, label=auto_refresh_national_label, name="Auto-Refresh National Data"
        )
        tooltip_auto_refresh = (
            "When checked, national data will be automatically refreshed when the timer fires. "
            "When unchecked, you must manually refresh national data."
        )
        self.auto_refresh_national_ctrl.SetToolTip(tooltip_auto_refresh)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.auto_refresh_national_ctrl, 0, wx.ALL, 5)

        sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(sizer)

    def _init_display_tab(self):
        """Initialize the Display tab controls."""
        panel = self.display_panel
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Input Fields ---
        grid_sizer = wx.FlexGridSizer(rows=4, cols=2, vgap=10, hgap=5)
        grid_sizer.AddGrowableCol(1, 1)  # Make the input column growable

        # Measurement Unit System Selection
        temp_unit_label = wx.StaticText(panel, label="Measurement Units:")
        from .ui_components import AccessibleChoice

        self.temp_unit_ctrl = AccessibleChoice(
            panel,
            choices=["Imperial (Fahrenheit)", "Metric (Celsius)", "Both"],
            label="Measurement Units",
        )
        tooltip_temp_unit = (
            "Select your preferred measurement unit system. "
            "Affects temperature, pressure, wind speed, and other measurements. "
            "'Both' will show temperatures in both Fahrenheit and Celsius."
        )
        self.temp_unit_ctrl.SetToolTip(tooltip_temp_unit)
        grid_sizer.Add(temp_unit_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.temp_unit_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        # Taskbar Icon Text Toggle
        taskbar_text_label = "Show weather information in taskbar icon"
        self.taskbar_text_ctrl = wx.CheckBox(
            panel, label=taskbar_text_label, name="Taskbar Icon Text"
        )
        tooltip_taskbar = (
            "When checked, the taskbar icon will display weather information "
            "according to the format string below."
        )
        self.taskbar_text_ctrl.SetToolTip(tooltip_taskbar)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)  # Empty cell for alignment
        grid_sizer.Add(self.taskbar_text_ctrl, 0, wx.ALL, 5)

        # Taskbar Icon Text Format
        taskbar_format_label = wx.StaticText(panel, label="Taskbar Icon Text Format:")
        self.taskbar_format_ctrl = wx.TextCtrl(panel, name="Taskbar Format")
        tooltip_format = (
            "Enter a format string with placeholders like {temp}, {condition}, etc. "
            "These will be replaced with actual weather data."
        )
        self.taskbar_format_ctrl.SetToolTip(tooltip_format)
        grid_sizer.Add(taskbar_format_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.taskbar_format_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        # Add the grid sizer to the main sizer
        sizer.Add(grid_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Add help text for placeholders
        help_label = wx.StaticText(panel, label="Available Placeholders:")
        sizer.Add(help_label, 0, wx.LEFT | wx.TOP, 15)

        # Create a read-only text control for the placeholder help
        self.placeholder_help_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
            size=(-1, 150),
            name="Placeholder Help",
        )

        # Get the help text from the FormatStringParser
        help_text = FormatStringParser.get_supported_placeholders_help()
        self.placeholder_help_ctrl.SetValue(help_text)

        # Add the help text control to the sizer
        sizer.Add(self.placeholder_help_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        # Set the sizer for the panel
        panel.SetSizer(sizer)

        # Bind events
        self.taskbar_text_ctrl.Bind(wx.EVT_CHECKBOX, self._on_taskbar_text_toggle)

    def _init_advanced_tab(self):
        """Initialize the Advanced tab controls."""
        panel = self.advanced_panel
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Input Fields ---
        grid_sizer = wx.FlexGridSizer(rows=3, cols=2, vgap=10, hgap=5)  # Increased rows to 3
        grid_sizer.AddGrowableCol(1, 1)  # Make the input column growable

        # Minimize to Tray Toggle
        minimize_to_tray_label = "Minimize to system tray when closing"
        self.minimize_to_tray_ctrl = wx.CheckBox(
            panel, label=minimize_to_tray_label, name="Minimize to Tray"
        )
        tooltip_minimize = (
            "When checked, clicking the X button will minimize the app to the system tray "
            "instead of closing it. You can still exit from the system tray menu."
        )
        self.minimize_to_tray_ctrl.SetToolTip(tooltip_minimize)
        # Add a spacer in the first column
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.minimize_to_tray_ctrl, 0, wx.ALL, 5)

        # Cache Enabled Toggle
        cache_enabled_label = "Enable caching of weather data"
        self.cache_enabled_ctrl = wx.CheckBox(
            panel, label=cache_enabled_label, name="Enable Caching"
        )
        tooltip_cache = (
            "When checked, weather data will be cached to reduce API calls. "
            "This can improve performance and reduce data usage."
        )
        self.cache_enabled_ctrl.SetToolTip(tooltip_cache)
        # Add a spacer in the first column
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.cache_enabled_ctrl, 0, wx.ALL, 5)

        # Cache TTL
        cache_ttl_label = wx.StaticText(panel, label="Cache Time-to-Live (seconds):")
        self.cache_ttl_ctrl = wx.SpinCtrl(panel, min=60, max=3600, initial=300, name="Cache TTL")
        tooltip_ttl = "How long cached data remains valid (in seconds)."
        self.cache_ttl_ctrl.SetToolTip(tooltip_ttl)
        grid_sizer.Add(cache_ttl_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        # Don't expand spin control
        grid_sizer.Add(self.cache_ttl_ctrl, 0, wx.ALL, 5)

        sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(sizer)

    def _on_taskbar_text_toggle(self, event):
        """Handle taskbar text toggle checkbox."""
        enabled = self.taskbar_text_ctrl.GetValue()
        self.taskbar_format_ctrl.Enable(enabled)

    def _load_settings(self):
        """Load current settings into the UI controls."""
        try:
            # Load general settings
            update_interval = self.current_settings.get(UPDATE_INTERVAL_KEY, 10)
            alert_radius = self.current_settings.get(ALERT_RADIUS_KEY, 25)
            precise_alerts = self.current_settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
            show_nationwide = self.current_settings.get(SHOW_NATIONWIDE_KEY, True)
            auto_refresh_national = self.current_settings.get(AUTO_REFRESH_NATIONAL_KEY, True)

            # Load data source settings
            data_source = self.current_settings.get(DATA_SOURCE_KEY, DEFAULT_DATA_SOURCE)

            # Set data source dropdown
            if data_source == DATA_SOURCE_OPENMETEO:
                self.data_source_ctrl.SetSelection(1)  # Open-Meteo
            elif data_source == DATA_SOURCE_AUTO:
                self.data_source_ctrl.SetSelection(2)  # Automatic
            else:
                self.data_source_ctrl.SetSelection(0)  # NWS (default)

            self.update_interval_ctrl.SetValue(update_interval)
            self.alert_radius_ctrl.SetValue(alert_radius)
            self.precise_alerts_ctrl.SetValue(precise_alerts)
            self.show_nationwide_ctrl.SetValue(show_nationwide)
            self.auto_refresh_national_ctrl.SetValue(auto_refresh_national)

            # Load display settings
            taskbar_text_enabled = self.current_settings.get(TASKBAR_ICON_TEXT_ENABLED_KEY, False)
            taskbar_text_format = self.current_settings.get(
                TASKBAR_ICON_TEXT_FORMAT_KEY, "{temp} {condition}"
            )

            self.taskbar_text_ctrl.SetValue(taskbar_text_enabled)
            self.taskbar_format_ctrl.SetValue(taskbar_text_format)
            self.taskbar_format_ctrl.Enable(taskbar_text_enabled)

            # Load advanced settings
            minimize_to_tray = self.current_settings.get(MINIMIZE_TO_TRAY_KEY, True)
            cache_enabled = self.current_settings.get(CACHE_ENABLED_KEY, True)
            cache_ttl = self.current_settings.get(CACHE_TTL_KEY, 300)

            self.minimize_to_tray_ctrl.SetValue(minimize_to_tray)
            self.cache_enabled_ctrl.SetValue(cache_enabled)
            self.cache_ttl_ctrl.SetValue(cache_ttl)

            # Load temperature unit setting
            temperature_unit = self.current_settings.get(
                TEMPERATURE_UNIT_KEY, DEFAULT_TEMPERATURE_UNIT
            )
            # Set temperature unit dropdown
            if temperature_unit == TemperatureUnit.FAHRENHEIT.value:
                self.temp_unit_ctrl.SetSelection(0)  # Imperial (Fahrenheit)
            elif temperature_unit == TemperatureUnit.CELSIUS.value:
                self.temp_unit_ctrl.SetSelection(1)  # Metric (Celsius)
            elif temperature_unit == TemperatureUnit.BOTH.value:
                self.temp_unit_ctrl.SetSelection(2)  # Both
            else:
                # Default to Fahrenheit for unknown values
                self.temp_unit_ctrl.SetSelection(0)

            logger.debug("Settings loaded into dialog.")
        except Exception as e:
            logger.error(f"Error loading settings into dialog: {e}")
            wx.MessageBox(f"Error loading settings: {e}", "Error", wx.OK | wx.ICON_ERROR, self)

    def _on_ok(self, event):  # event is required by wx
        """Handle OK button click: Validate and signal success."""
        # Basic validation (more can be added)
        interval = self.update_interval_ctrl.GetValue()
        radius = self.alert_radius_ctrl.GetValue()
        cache_ttl = self.cache_ttl_ctrl.GetValue()

        if interval < 1:
            wx.MessageBox(
                "Update interval must be at least 1 minute.",
                "Invalid Setting",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.notebook.SetSelection(0)  # Switch to General tab
            self.update_interval_ctrl.SetFocus()
            return  # Prevent dialog closing

        if radius < 1:
            wx.MessageBox(
                "Alert radius must be at least 1 mile.",
                "Invalid Setting",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.notebook.SetSelection(0)  # Switch to General tab
            self.alert_radius_ctrl.SetFocus()
            return  # Prevent dialog closing

        if cache_ttl < 60:
            wx.MessageBox(
                "Cache TTL must be at least 60 seconds.",
                "Invalid Setting",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.notebook.SetSelection(1)  # Switch to Advanced tab
            self.cache_ttl_ctrl.SetFocus()
            return  # Prevent dialog closing

        # If validation passes, end the modal dialog with wx.ID_OK
        self.EndModal(wx.ID_OK)

    def get_settings(self):
        """
        Retrieve the modified settings from the UI controls.

        Should only be called after the dialog returns wx.ID_OK.

        Returns:
            dict: A dictionary containing the updated settings.
        """
        # Determine data source
        selection = self.data_source_ctrl.GetSelection()
        if selection == 1:
            data_source = DATA_SOURCE_OPENMETEO
        elif selection == 2:
            data_source = DATA_SOURCE_AUTO
        else:
            data_source = DATA_SOURCE_NWS

        # Get temperature unit selection
        temp_unit_idx = self.temp_unit_ctrl.GetSelection()
        if temp_unit_idx == 0:
            temperature_unit = TemperatureUnit.FAHRENHEIT.value
        elif temp_unit_idx == 1:
            temperature_unit = TemperatureUnit.CELSIUS.value
        elif temp_unit_idx == 2:
            temperature_unit = TemperatureUnit.BOTH.value
        else:
            temperature_unit = DEFAULT_TEMPERATURE_UNIT

        # Validate taskbar format string if enabled
        taskbar_text_enabled = self.taskbar_text_ctrl.GetValue()
        taskbar_text_format = self.taskbar_format_ctrl.GetValue()

        if taskbar_text_enabled and taskbar_text_format:
            # Validate the format string
            parser = FormatStringParser()
            is_valid, error = parser.validate_format_string(taskbar_text_format)
            if not is_valid:
                # If invalid, log the error but still save (will use default format)
                logger.warning(f"Invalid taskbar format string: {error}")
                # We could show a message box here, but for now we'll just log it

        return {
            # Data source setting
            DATA_SOURCE_KEY: data_source,
            # General settings
            UPDATE_INTERVAL_KEY: self.update_interval_ctrl.GetValue(),
            ALERT_RADIUS_KEY: self.alert_radius_ctrl.GetValue(),
            PRECISE_LOCATION_ALERTS_KEY: self.precise_alerts_ctrl.GetValue(),
            SHOW_NATIONWIDE_KEY: self.show_nationwide_ctrl.GetValue(),
            AUTO_REFRESH_NATIONAL_KEY: self.auto_refresh_national_ctrl.GetValue(),
            # Display settings
            TEMPERATURE_UNIT_KEY: temperature_unit,
            TASKBAR_ICON_TEXT_ENABLED_KEY: taskbar_text_enabled,
            TASKBAR_ICON_TEXT_FORMAT_KEY: taskbar_text_format,
            # Advanced settings
            MINIMIZE_TO_TRAY_KEY: self.minimize_to_tray_ctrl.GetValue(),
            CACHE_ENABLED_KEY: self.cache_enabled_ctrl.GetValue(),
            CACHE_TTL_KEY: self.cache_ttl_ctrl.GetValue(),
        }

    def get_api_settings(self):
        """
        Retrieve the API-specific settings from the UI controls.

        Should only be called after the dialog returns wx.ID_OK.

        Returns:
            dict: A dictionary containing the updated API settings.
        """
        return {}

    def get_api_keys(self):
        """
        Retrieve the API keys from the UI controls.

        Should only be called after the dialog returns wx.ID_OK.

        Returns:
            dict: A dictionary containing the updated API keys.
        """
        return {}
