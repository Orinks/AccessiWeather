"""Location handlers for the WeatherApp class

This module contains the location-related handlers for the WeatherApp class.
"""

import logging

import wx

from ..dialogs import LocationDialog
from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppLocationHandlers(WeatherAppHandlerBase):
    """Location handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides location-related event handlers for the WeatherApp class.
    """

    def OnLocationChange(self, event):  # event is required by wx
        """Handle location change event

        Args:
            event: Choice event
        """
        # Get selected location
        selected = self.location_choice.GetStringSelection()
        if not selected:
            return

        # Check if this is the Nationwide location and disable remove button if it is
        if hasattr(self, "remove_btn") and self.location_service.is_nationwide_location(selected):
            self.remove_btn.Disable()
            # Accessibility: update accessible description
            self.remove_btn.SetHelpText("Remove button is disabled for nationwide location")
            self.remove_btn.SetToolTip("Cannot remove nationwide location")
            # Set nationwide mode flag if not already set
            if hasattr(self, "_in_nationwide_mode"):
                self._in_nationwide_mode = True
                # Reset nationwide discussion data to ensure fresh fetch
                self._nationwide_wpc_full = None
                self._nationwide_spc_full = None
        elif hasattr(self, "remove_btn"):
            self.remove_btn.Enable()
            # Reset accessible description
            self.remove_btn.SetHelpText("Remove the selected location")
            self.remove_btn.SetToolTip("Remove the selected location")
            # Reset nationwide mode flag if set
            if hasattr(self, "_in_nationwide_mode"):
                self._in_nationwide_mode = False
                self._nationwide_wpc_full = None
                self._nationwide_spc_full = None

        # Set current location using the location service
        self.location_service.set_current_location(selected)

        # Set status and update weather
        self.SetStatusText(f"Loading weather data for {selected}...")
        self.UpdateWeatherData()

        # Explicitly clear the selection in the alerts list and disable the alert button
        # to prevent accessing a cached alert for a previous location
        if hasattr(self, "alerts_list") and hasattr(self, "alert_btn"):
            self.alerts_list.DeleteAllItems()
            self.alert_btn.Disable()

    def OnAddLocation(self, event):  # event is required by wx
        """Handle add location button click

        Args:
            event: Button event
        """
        # Show location dialog
        dialog = LocationDialog(self)
        result = dialog.ShowModal()

        if result == wx.ID_OK:
            # Get location data using the GetValues method
            name, lat, lon = dialog.GetValues()

            if name and lat is not None and lon is not None:
                # Add location using the location service
                self.location_service.add_location(name, lat, lon)

                # Update dropdown
                self.UpdateLocationDropdown()

                # Select the newly added location
                self.location_choice.SetStringSelection(name)

                # Set as current location
                self.location_service.set_current_location(name)

                # Update weather data
                self.UpdateWeatherData()

        dialog.Destroy()

    def OnRemoveLocation(self, event):  # event is required by wx
        """Handle remove location button click

        Args:
            event: Button event
        """
        # Get selected location
        selected = self.location_choice.GetStringSelection()
        if not selected:
            wx.MessageBox(
                "Please select a location to remove", "No Location Selected", wx.OK | wx.ICON_ERROR
            )
            return

        # Check if this is the Nationwide location
        if self.location_service.is_nationwide_location(selected):
            wx.MessageBox(
                "The Nationwide location cannot be removed.",
                "Cannot Remove",
                wx.OK | wx.ICON_INFORMATION,
            )
            # Accessibility: announce for screen readers
            if hasattr(self, "AnnounceForScreenReader"):
                self.AnnounceForScreenReader("The Nationwide location cannot be removed.")
            return

        # Confirm removal
        confirm = wx.MessageBox(
            f"Are you sure you want to remove {selected}?",
            "Confirm Removal",
            wx.YES_NO | wx.ICON_QUESTION,
        )

        if confirm == wx.YES:
            # Remove location using the location service
            removed = self.location_service.remove_location(selected)

            if not removed:
                wx.MessageBox(f"Could not remove {selected}.", "Error", wx.OK | wx.ICON_ERROR)
                return

            # Update dropdown
            self.UpdateLocationDropdown()

            # Clear forecast and alerts if current location was removed
            if self.location_service.get_current_location_name() is None:
                self.forecast_text.SetValue("Select a location to view the forecast")
                self.alerts_list.DeleteAllItems()  # Clear display
                self.current_alerts = []
                self.SetStatusText("Location removed. Select a new location.")
            else:
                # If another location is now current, update data
                self.UpdateWeatherData()
