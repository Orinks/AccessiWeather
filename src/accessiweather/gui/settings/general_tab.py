"""General settings tab for the settings dialog."""

import wx

from .constants import (
    ALERT_RADIUS_KEY,
    AUTO_REFRESH_NATIONAL_KEY,
    DATA_SOURCE_AUTO,
    DATA_SOURCE_KEY,
    DATA_SOURCE_NWS,
    DATA_SOURCE_OPENMETEO,
    DEFAULT_DATA_SOURCE,
    PRECISE_LOCATION_ALERTS_KEY,
    SHOW_NATIONWIDE_KEY,
    UPDATE_INTERVAL_KEY,
)


class GeneralTab:
    """Handles the General tab of the settings dialog."""

    def __init__(self, parent_panel):
        """Initialize the General tab.
        
        Args:
            parent_panel: The parent panel for this tab
        """
        self.panel = parent_panel
        self._init_ui()

    def _init_ui(self):
        """Initialize the General tab controls."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Input Fields ---
        grid_sizer = wx.FlexGridSizer(
            rows=9, cols=2, vgap=10, hgap=5
        )  # 9 rows (increased for hyperlink)
        grid_sizer.AddGrowableCol(1, 1)  # Make the input column growable

        # Data Source Selection
        data_source_label = wx.StaticText(self.panel, label="Weather Data Source:")
        self.data_source_ctrl = wx.Choice(self.panel, name="Data Source")
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

        # Update Interval
        update_interval_label = wx.StaticText(self.panel, label="Update Interval (minutes):")
        self.update_interval_ctrl = wx.SpinCtrl(
            self.panel, min=1, max=1440, initial=10, name="Update Interval"
        )
        tooltip_interval = "How often to automatically refresh all weather data including forecasts and alerts (in minutes)."
        self.update_interval_ctrl.SetToolTip(tooltip_interval)
        grid_sizer.Add(update_interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.update_interval_ctrl, 0, wx.ALL, 5)

        # Alert Radius
        alert_radius_label = wx.StaticText(self.panel, label="Alert Radius (miles):")
        self.alert_radius_ctrl = wx.SpinCtrl(self.panel, min=1, max=500, initial=25, name="Alert Radius")
        tooltip_radius = "Radius around location to check for alerts (in miles)."
        self.alert_radius_ctrl.SetToolTip(tooltip_radius)
        grid_sizer.Add(alert_radius_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.alert_radius_ctrl, 0, wx.ALL, 5)

        # Precise Location Alerts Toggle
        precise_alerts_label = "Use precise location for alerts"
        self.precise_alerts_ctrl = wx.CheckBox(
            self.panel, label=precise_alerts_label, name="Precise Location Alerts"
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
            self.panel, label=show_nationwide_label, name="Show Nationwide Location"
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
            self.panel, label=auto_refresh_national_label, name="Auto-Refresh National Data"
        )
        tooltip_auto_refresh = (
            "When checked, national data will be automatically refreshed when the timer fires. "
            "When unchecked, you must manually refresh national data."
        )
        self.auto_refresh_national_ctrl.SetToolTip(tooltip_auto_refresh)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.auto_refresh_national_ctrl, 0, wx.ALL, 5)

        sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 10)
        self.panel.SetSizer(sizer)

    def load_settings(self, settings):
        """Load settings into the controls.
        
        Args:
            settings: Dictionary containing current settings
        """
        # Load general settings
        update_interval = settings.get(UPDATE_INTERVAL_KEY, 10)
        alert_radius = settings.get(ALERT_RADIUS_KEY, 25)
        precise_alerts = settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
        show_nationwide = settings.get(SHOW_NATIONWIDE_KEY, True)
        auto_refresh_national = settings.get(AUTO_REFRESH_NATIONAL_KEY, True)

        # Load data source settings
        data_source = settings.get(DATA_SOURCE_KEY, DEFAULT_DATA_SOURCE)

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

    def get_settings(self):
        """Get settings from the controls.
        
        Returns:
            Dictionary containing the settings from this tab
        """
        # Determine data source
        selection = self.data_source_ctrl.GetSelection()
        if selection == 1:
            data_source = DATA_SOURCE_OPENMETEO
        elif selection == 2:
            data_source = DATA_SOURCE_AUTO
        else:
            data_source = DATA_SOURCE_NWS

        return {
            DATA_SOURCE_KEY: data_source,
            UPDATE_INTERVAL_KEY: self.update_interval_ctrl.GetValue(),
            ALERT_RADIUS_KEY: self.alert_radius_ctrl.GetValue(),
            PRECISE_LOCATION_ALERTS_KEY: self.precise_alerts_ctrl.GetValue(),
            SHOW_NATIONWIDE_KEY: self.show_nationwide_ctrl.GetValue(),
            AUTO_REFRESH_NATIONAL_KEY: self.auto_refresh_national_ctrl.GetValue(),
        }

    def validate(self):
        """Validate the settings in this tab.
        
        Returns:
            Tuple of (is_valid, error_message, focus_control)
        """
        interval = self.update_interval_ctrl.GetValue()
        radius = self.alert_radius_ctrl.GetValue()

        if interval < 1:
            return False, "Update interval must be at least 1 minute.", self.update_interval_ctrl

        if radius < 1:
            return False, "Alert radius must be at least 1 mile.", self.alert_radius_ctrl

        return True, None, None
