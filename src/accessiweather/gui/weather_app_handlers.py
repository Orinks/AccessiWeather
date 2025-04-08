"""Event handlers for the WeatherApp class

This module contains event handlers for the WeatherApp class.
"""

import json
import logging
import os
import time

import wx

from .dialogs import LocationDialog, WeatherDiscussionDialog
from .settings_dialog import ALERT_RADIUS_KEY, API_CONTACT_KEY, UPDATE_INTERVAL_KEY, SettingsDialog

logger = logging.getLogger(__name__)


class WeatherAppHandlers:
    """Event handlers for the WeatherApp class"""

    def OnKeyDown(self, event):
        """Handle key down events for accessibility

        Args:
            event: Key event
        """
        # Handle key events for accessibility
        # For example, F5 to refresh
        if event.GetKeyCode() == wx.WXK_F5:
            self.OnRefresh(event)
        else:
            event.Skip()

    def OnClose(self, event):
        """Handle close event

        Args:
            event: Close event
        """
        # Stop the timer
        self.timer.Stop()

        # Clean up any resources
        # ...

        # Destroy the window
        self.Destroy()

    def OnLocationChange(self, event):
        """Handle location change event

        Args:
            event: Choice event
        """
        # Get selected location
        selected = self.location_choice.GetStringSelection()
        if not selected:
            return

        # Set current location
        self.location_manager.set_current_location(selected)

        # Update weather data
        self.UpdateWeatherData()

    def OnAddLocation(self, event):
        """Handle add location button click

        Args:
            event: Button event
        """
        # Show location dialog
        dialog = LocationDialog(self)
        result = dialog.ShowModal()

        if result == wx.ID_OK:
            # Get location data
            name = dialog.name
            lat = dialog.latitude
            lon = dialog.longitude

            if name and lat is not None and lon is not None:
                # Add location
                self.location_manager.add_location(name, lat, lon)

                # Update dropdown
                self.UpdateLocationDropdown()

                # Update weather data
                self.UpdateWeatherData()

        dialog.Destroy()

    def OnRemoveLocation(self, event):
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

        # Confirm removal
        confirm = wx.MessageBox(
            f"Are you sure you want to remove {selected}?",
            "Confirm Removal",
            wx.YES_NO | wx.ICON_QUESTION,
        )

        if confirm == wx.YES:
            # Remove location
            self.location_manager.remove_location(selected)

            # Update dropdown
            self.UpdateLocationDropdown()

            # Clear forecast and alerts if current location was removed
            if self.location_manager.get_current_location_name() is None:
                self.forecast_text.SetValue("Select a location to view the forecast")
                self.alerts_list.DeleteAllItems()  # Clear display
                self.current_alerts = []
                self.SetStatusText("Location removed. Select a new location.")
            else:
                # If another location is now current, update data
                self.UpdateWeatherData()

    def OnRefresh(self, event):
        """Handle refresh button click

        Args:
            event: Button event
        """
        # Trigger weather data update
        self.UpdateWeatherData()

    def OnViewDiscussion(self, event):
        """Handle view discussion button click

        Args:
            event: Button event
        """
        # Get current location
        location = self.location_manager.get_current_location()
        if location is None:
            wx.MessageBox(
                "Please select a location first", "No Location Selected", wx.OK | wx.ICON_ERROR
            )
            return

        # Show loading dialog
        name, lat, lon = location
        self.SetStatusText(f"Loading forecast discussion for {name}...")

        # Fetch discussion data
        self.discussion_fetcher.fetch(
            lat,
            lon,
            on_success=self._on_discussion_fetched,
            on_error=self._on_discussion_error,
        )

    def OnViewAlert(self, event):
        """Handle view alert button click

        Args:
            event: Button event
        """
        # Get selected alert
        selected = self.alerts_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Please select an alert to view", "No Alert Selected", wx.OK | wx.ICON_ERROR)
            return

        # Get alert data
        if selected < len(self.current_alerts):
            alert = self.current_alerts[selected]
            title = alert.get("properties", {}).get("headline", "Weather Alert")
            description = alert.get("properties", {}).get("description", "No details available")

            # Show alert dialog
            wx.MessageBox(description, title, wx.OK | wx.ICON_INFORMATION)

    def OnAlertActivated(self, event):
        """Handle alert list item activation (double-click)

        Args:
            event: List item activated event
        """
        # Just call the view alert handler
        self.OnViewAlert(event)

    def OnSettings(self, event):
        """Handle settings button click

        Args:
            event: Button event
        """
        # Get current settings
        settings = self.config.get("settings", {})
        api_settings = self.config.get("api_settings", {})

        # Create settings dialog
        dialog = SettingsDialog(self, settings, api_settings)
        result = dialog.ShowModal()

        if result == wx.ID_OK:
            # Get updated settings
            updated_settings = dialog.get_settings()
            updated_api_settings = dialog.get_api_settings()

            # Update config
            self.config["settings"] = updated_settings
            self.config["api_settings"] = updated_api_settings

            # Save config
            self._save_config()

            # Update API client contact info
            api_contact = updated_api_settings.get(API_CONTACT_KEY, "")
            self.api_client.set_contact_info(api_contact)

            # Update notifier settings
            alert_radius = updated_settings.get(ALERT_RADIUS_KEY, 25)
            self.api_client.set_alert_radius(alert_radius)

        dialog.Destroy()

    def OnTimer(self, event):
        """Handle timer event for periodic updates

        Args:
            event: Timer event
        """
        # Get update interval from config (default to 30 minutes)
        update_interval_minutes = self.config.get("settings", {}).get("update_interval_minutes", 30)
        update_interval_seconds = update_interval_minutes * 60

        # Check if it's time to update
        now = time.time()
        if (now - self.last_update) >= update_interval_seconds:
            if not self.updating:
                logger.info("Timer triggered weather update.")
                self.UpdateWeatherData()
            else:
                logger.debug("Timer skipped update: already updating.")

    def _save_config(self):
        """Save configuration to file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)

            # Save config
            with open(self._config_path, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config: {str(e)}")
            wx.MessageBox(
                f"Failed to save configuration: {str(e)}",
                "Configuration Error",
                wx.OK | wx.ICON_ERROR,
            )

    def _check_api_contact_configured(self):
        """Check if API contact information is configured and prompt if not"""
        # Check if api_settings section exists
        if "api_settings" not in self.config:
            logger.warning("API settings section missing from config")
            self.config["api_settings"] = {}

        # Check if api_contact is set
        api_contact = self.config.get("api_settings", {}).get(API_CONTACT_KEY, "")
        if not api_contact:
            logger.warning("API contact information not configured")
            dialog = wx.MessageDialog(
                self,
                "API contact information is required for NOAA API access. "
                "Would you like to configure it now?",
                "API Configuration Required",
                wx.YES_NO | wx.ICON_QUESTION,
            )
            result = dialog.ShowModal()
            dialog.Destroy()

            if result == wx.ID_YES:
                # Open settings dialog
                self.OnSettings(None)
