"""Advanced location dialog for manual lat/lon entry."""

import wx

from ..ui_components import (
    AccessibleButton,
    AccessibleStaticText,
    AccessibleTextCtrl,
)


class AdvancedLocationDialog(wx.Dialog):
    """Dialog for manually entering lat/lon coordinates"""

    def __init__(self, parent, title="Advanced Location Options", lat=None, lon=None):
        """Initialize the advanced location dialog

        Args:
            parent: Parent window
            title: Dialog title
            lat: Initial latitude
            lon: Initial longitude
        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)

        # Create a panel with accessible widgets
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Latitude field
        lat_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lat_label = AccessibleStaticText(panel, label="Latitude:")
        self.lat_ctrl = AccessibleTextCtrl(
            panel, value=str(lat) if lat is not None else "", label="Latitude"
        )
        lat_sizer.Add(lat_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        lat_sizer.Add(self.lat_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(lat_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Longitude field
        lon_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lon_label = AccessibleStaticText(panel, label="Longitude:")
        self.lon_ctrl = AccessibleTextCtrl(
            panel, value=str(lon) if lon is not None else "", label="Longitude"
        )
        lon_sizer.Add(lon_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        lon_sizer.Add(self.lon_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(lon_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Description for screen readers
        help_text = AccessibleStaticText(
            panel, label="Enter latitude and longitude in decimal format (e.g., 35.123, -80.456)"
        )
        sizer.Add(help_text, 0, wx.ALL, 10)

        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        self.ok_button = AccessibleButton(panel, wx.ID_OK, "Save")
        self.cancel_button = AccessibleButton(panel, wx.ID_CANCEL, "Cancel")

        btn_sizer.AddButton(self.ok_button)
        btn_sizer.AddButton(self.cancel_button)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)
        sizer.Fit(self)

        # Set initial focus for accessibility
        self.lat_ctrl.SetFocus()

        # Connect events
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)

    def OnOK(self, event):
        """Handle OK button event

        Args:
            event: Button event
        """
        try:
            # Validate inputs
            lat = float(self.lat_ctrl.GetValue())
            lon = float(self.lon_ctrl.GetValue())

            # Check range
            if lat < -90 or lat > 90:
                wx.MessageBox(
                    "Latitude must be between -90 and 90 degrees",
                    "Validation Error",
                    wx.OK | wx.ICON_ERROR,
                )
                return

            if lon < -180 or lon > 180:
                wx.MessageBox(
                    "Longitude must be between -180 and 180 degrees",
                    "Validation Error",
                    wx.OK | wx.ICON_ERROR,
                )
                return

            # Continue with default handler
            event.Skip()

        except ValueError:
            wx.MessageBox(
                "Please enter valid numbers for latitude and longitude",
                "Validation Error",
                wx.OK | wx.ICON_ERROR,
            )

    def GetValues(self):
        """Get the dialog values

        Returns:
            Tuple of (latitude, longitude)
        """
        try:
            lat = float(self.lat_ctrl.GetValue())
            lon = float(self.lon_ctrl.GetValue())
            return lat, lon
        except ValueError:
            return None, None
