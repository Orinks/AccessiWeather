"""Alert handlers for the WeatherApp class

This module contains the alert-related handlers for the WeatherApp class.
"""

import logging

import wx

from ..alert_dialog import AlertDetailsDialog
from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppAlertHandlers(WeatherAppHandlerBase):
    """Alert handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides alert-related event handlers for the WeatherApp class.
    """

    def OnViewAlert(self, event):  # event is required by wx
        """Handle view alert button click

        Args:
            event: Button event

        """
        # Get selected alert
        selected = self.alerts_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox(
                "Please select an alert to view", "No Alert Selected", wx.OK | wx.ICON_ERROR
            )
            return

        # Get alert data
        if selected < len(self.current_alerts):
            alert = self.current_alerts[selected]
            title = alert.get("headline", "Weather Alert")

            # Create and show the alert details dialog
            dialog = AlertDetailsDialog(self, title, alert)
            dialog.ShowModal()
            dialog.Destroy()
        else:
            logger.error(
                f"Selected index {selected} out of range for "
                f"current_alerts (len={len(self.current_alerts)})"
            )
            wx.MessageBox("Error retrieving alert details.", "Error", wx.OK | wx.ICON_ERROR)

    def OnAlertActivated(self, event):
        """Handle alert list item activation (double-click)

        Args:
            event: List item activated event

        """
        # Just call the view alert handler
        self.OnViewAlert(event)
