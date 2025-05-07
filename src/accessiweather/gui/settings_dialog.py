"""
Dialog for configuring AccessiWeather settings.
"""

import logging

import wx

logger = logging.getLogger(__name__)

# Define constants for settings keys if needed, or use strings directly
API_CONTACT_KEY = "api_contact"
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
        grid_sizer = wx.FlexGridSizer(rows=6, cols=2, vgap=10, hgap=5)  # 6 rows
        grid_sizer.AddGrowableCol(1, 1)  # Make the input column growable

        # API Contact
        api_contact_label = wx.StaticText(panel, label="API Contact (Email/Website):")
        self.api_contact_ctrl = wx.TextCtrl(panel, name="API Contact")
        tooltip_api = "Enter the email or website required by the weather API provider."
        self.api_contact_ctrl.SetToolTip(tooltip_api)
        grid_sizer.Add(api_contact_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.api_contact_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        # Update Interval
        update_interval_label = wx.StaticText(panel, label="Update Interval (minutes):")
        self.update_interval_ctrl = wx.SpinCtrl(
            panel, min=1, max=1440, initial=30, name="Update Interval"
        )
        tooltip_interval = "How often to automatically refresh weather data (in minutes)."
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

    def _load_settings(self):
        """Load current settings into the UI controls."""
        try:
            # Load general settings
            api_contact = self.current_settings.get(API_CONTACT_KEY, "")
            update_interval = self.current_settings.get(UPDATE_INTERVAL_KEY, 30)
            alert_radius = self.current_settings.get(ALERT_RADIUS_KEY, 25)
            precise_alerts = self.current_settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
            show_nationwide = self.current_settings.get(SHOW_NATIONWIDE_KEY, True)
            auto_refresh_national = self.current_settings.get(AUTO_REFRESH_NATIONAL_KEY, True)

            self.api_contact_ctrl.SetValue(api_contact)
            self.update_interval_ctrl.SetValue(update_interval)
            self.alert_radius_ctrl.SetValue(alert_radius)
            self.precise_alerts_ctrl.SetValue(precise_alerts)
            self.show_nationwide_ctrl.SetValue(show_nationwide)
            self.auto_refresh_national_ctrl.SetValue(auto_refresh_national)

            # Load advanced settings
            minimize_to_tray = self.current_settings.get(MINIMIZE_TO_TRAY_KEY, True)
            cache_enabled = self.current_settings.get(CACHE_ENABLED_KEY, True)
            cache_ttl = self.current_settings.get(CACHE_TTL_KEY, 300)

            self.minimize_to_tray_ctrl.SetValue(minimize_to_tray)
            self.cache_enabled_ctrl.SetValue(cache_enabled)
            self.cache_ttl_ctrl.SetValue(cache_ttl)

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
        return {
            # General settings
            UPDATE_INTERVAL_KEY: self.update_interval_ctrl.GetValue(),
            ALERT_RADIUS_KEY: self.alert_radius_ctrl.GetValue(),
            PRECISE_LOCATION_ALERTS_KEY: self.precise_alerts_ctrl.GetValue(),
            SHOW_NATIONWIDE_KEY: self.show_nationwide_ctrl.GetValue(),
            AUTO_REFRESH_NATIONAL_KEY: self.auto_refresh_national_ctrl.GetValue(),
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
        return {
            API_CONTACT_KEY: self.api_contact_ctrl.GetValue(),
        }
