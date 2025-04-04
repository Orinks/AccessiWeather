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
        super().__init__(
            parent,
            title="Settings",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.current_settings = current_settings
        self._init_ui()
        self._load_settings()
        self.SetSizerAndFit(self.main_sizer)
        self.CenterOnParent()

    def _init_ui(self):
        """Initialize the UI components of the dialog."""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Input Fields ---
        grid_sizer = wx.FlexGridSizer(rows=3, cols=2, vgap=10, hgap=5)
        grid_sizer.AddGrowableCol(1, 1)  # Make the input column growable

        # API Contact
        api_contact_label = wx.StaticText(
            self, label="API Contact (Email/Website):"
        )
        self.api_contact_ctrl = wx.TextCtrl(self, name="API Contact")
        tooltip_api = (
            "Enter the email or website required by the weather "
            "API provider."
        )
        self.api_contact_ctrl.SetToolTip(tooltip_api)
        grid_sizer.Add(
            api_contact_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5
        )
        grid_sizer.Add(self.api_contact_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        # Update Interval
        update_interval_label = wx.StaticText(
            self, label="Update Interval (minutes):"
        )
        # 1 min to 24 hours
        self.update_interval_ctrl = wx.SpinCtrl(
            self, min=1, max=1440, initial=30, name="Update Interval"
        )
        tooltip_interval = (
            "How often to automatically refresh weather data " "(in minutes)."
        )
        self.update_interval_ctrl.SetToolTip(tooltip_interval)
        grid_sizer.Add(
            update_interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5
        )
        # Don't expand spin control
        grid_sizer.Add(self.update_interval_ctrl, 0, wx.ALL, 5)

        # Alert Radius (Optional - Add if needed by API or features)
        # Assuming it might be needed later or by tests
        alert_radius_label = wx.StaticText(self, label="Alert Radius (miles):")
        self.alert_radius_ctrl = wx.SpinCtrl(
            self, min=1, max=500, initial=25, name="Alert Radius"
        )
        tooltip_radius = (
            "Radius around location to check for alerts " "(in miles)."
        )
        self.alert_radius_ctrl.SetToolTip(tooltip_radius)
        grid_sizer.Add(
            alert_radius_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5
        )
        # Don't expand spin control
        grid_sizer.Add(self.alert_radius_ctrl, 0, wx.ALL, 5)

        self.main_sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 10)

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

    def _load_settings(self):
        """Load current settings into the UI controls."""
        try:
            api_contact = self.current_settings.get(API_CONTACT_KEY, "")
            update_interval = self.current_settings.get(
                UPDATE_INTERVAL_KEY, 30
            )
            alert_radius = self.current_settings.get(ALERT_RADIUS_KEY, 25)

            self.api_contact_ctrl.SetValue(api_contact)
            self.update_interval_ctrl.SetValue(update_interval)
            self.alert_radius_ctrl.SetValue(alert_radius)
            logger.debug("Settings loaded into dialog.")
        except Exception as e:
            logger.error(f"Error loading settings into dialog: {e}")
            wx.MessageBox(
                f"Error loading settings: {e}",
                "Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )

    def _on_ok(self, event):
        """Handle OK button click: Validate and signal success."""
        # Basic validation (more can be added)
        interval = self.update_interval_ctrl.GetValue()
        radius = self.alert_radius_ctrl.GetValue()

        if interval < 1:
            wx.MessageBox(
                "Update interval must be at least 1 minute.",
                "Invalid Setting",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.update_interval_ctrl.SetFocus()
            return  # Prevent dialog closing

        if radius < 1:
            wx.MessageBox(
                "Alert radius must be at least 1 mile.",
                "Invalid Setting",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.alert_radius_ctrl.SetFocus()
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
            API_CONTACT_KEY: self.api_contact_ctrl.GetValue(),
            UPDATE_INTERVAL_KEY: self.update_interval_ctrl.GetValue(),
            ALERT_RADIUS_KEY: self.alert_radius_ctrl.GetValue(),
        }
