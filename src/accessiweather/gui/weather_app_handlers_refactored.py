"""Event handlers for the WeatherApp class (Refactored)

This module contains event handlers for the WeatherApp class,
refactored to use the service layer.
"""

import functools
import json
import logging
import os
import time
from typing import Any

import wx

from .alert_dialog import AlertDetailsDialog
from .dialogs import LocationDialog
from .settings_dialog import (
    ALERT_RADIUS_KEY,
    API_CONTACT_KEY,
    PRECISE_LOCATION_ALERTS_KEY,
    SettingsDialog,
)

logger = logging.getLogger(__name__)


class WeatherAppHandlers:
    """Event handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides event handlers for the WeatherApp class.
    """

    # Type annotations for attributes that will be provided by WeatherApp
    timer: wx.Timer
    location_choice: wx.Choice
    location_service: Any
    forecast_text: wx.TextCtrl
    alerts_list: wx.ListCtrl
    current_alerts: list
    updating: bool
    last_update: float
    config: dict
    _config_path: str
    api_client: Any
    weather_service: Any
    notification_service: Any
    discussion_fetcher: Any
    _on_discussion_fetched: Any
    _on_discussion_error: Any

    # Methods that will be provided by WeatherApp
    def Destroy(self) -> None:
        """Placeholder for wx.Frame.Destroy method"""
        pass

    def UpdateWeatherData(self) -> None:
        """Placeholder for WeatherApp.UpdateWeatherData method"""
        pass

    def UpdateLocationDropdown(self) -> None:
        """Placeholder for WeatherApp.UpdateLocationDropdown method"""
        pass

    def SetStatusText(self, text: str) -> None:
        """Placeholder for wx.Frame.SetStatusText method"""
        pass

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

    def OnClose(self, event):  # event is required by wx
        """Handle close event

        Args:
            event: Close event
        """
        # Stop the timer
        self.timer.Stop()

        # Save configuration before closing
        logger.debug("Saving configuration before closing")
        self._save_config()

        # Clean up any resources
        # Add any additional cleanup here

        # Destroy the window
        self.Destroy()

    def OnLocationChange(self, event):  # event is required by wx
        """Handle location change event

        Args:
            event: Choice event
        """
        # Get selected location
        selected = self.location_choice.GetStringSelection()
        if not selected:
            return

        # Set current location using the location service
        self.location_service.set_current_location(selected)

        # Update weather data
        self.UpdateWeatherData()

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

        # Confirm removal
        confirm = wx.MessageBox(
            f"Are you sure you want to remove {selected}?",
            "Confirm Removal",
            wx.YES_NO | wx.ICON_QUESTION,
        )

        if confirm == wx.YES:
            # Remove location using the location service
            self.location_service.remove_location(selected)

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

    def OnRefresh(self, event):  # event is required by wx
        """Handle refresh button click

        Args:
            event: Button event
        """
        # Trigger weather data update
        self.UpdateWeatherData()

    def OnViewDiscussion(self, event):  # event is required by wx
        """Handle view discussion button click

        Args:
            event: Button event
        """
        # Get current location from the location service
        location = self.location_service.get_current_location()
        if location is None:
            wx.MessageBox(
                "Please select a location first", "No Location Selected", wx.OK | wx.ICON_ERROR
            )
            return

        # Show loading dialog
        name, lat, lon = location
        self.SetStatusText(f"Loading forecast discussion for {name}...")

        # Create a progress dialog
        loading_dialog = wx.ProgressDialog(
            "Fetching Discussion",
            f"Fetching forecast discussion for {name}...",
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT,
        )

        # Store the loading dialog as an instance variable so we can access it later
        self._discussion_loading_dialog = loading_dialog

        # Start a timer to pulse the dialog and check for cancel
        self._discussion_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_discussion_timer, self._discussion_timer)
        self._discussion_timer.Start(100)  # Check every 100ms

        # Fetch discussion data
        self.discussion_fetcher.fetch(
            lat,
            lon,
            on_success=functools.partial(
                self._on_discussion_fetched, name=name, loading_dialog=loading_dialog
            ),
            on_error=functools.partial(
                self._on_discussion_error, name=name, loading_dialog=loading_dialog
            ),
        )

    def _on_discussion_timer(self, event):  # event is required by wx
        """Handle timer events for the discussion loading dialog

        Args:
            event: Timer event
        """
        has_dialog = hasattr(self, "_discussion_loading_dialog")
        dialog_exists = has_dialog and self._discussion_loading_dialog is not None

        if not dialog_exists:
            # Dialog no longer exists, stop the timer
            if hasattr(self, "_discussion_timer"):
                logger.debug("Dialog no longer exists, stopping timer")
                self._discussion_timer.Stop()
                # Try to unbind the timer event to prevent memory leaks
                try:
                    self.Unbind(
                        wx.EVT_TIMER,
                        handler=self._on_discussion_timer,
                        source=self._discussion_timer,
                    )
                except Exception as e:
                    logger.error(f"Error unbinding timer event: {e}")
            return

        try:
            # Pulse the dialog and check for cancel
            # The first return value indicates if the user wants to continue (hasn't clicked cancel)
            # The second return value (skip) is not used in this implementation
            cont, _ = self._discussion_loading_dialog.Pulse()
            if not cont:  # User clicked cancel
                logger.debug("Cancel button clicked on discussion loading dialog")

                # Stop the fetching
                if hasattr(self, "discussion_fetcher"):
                    # Set the stop event to cancel the fetch
                    if hasattr(self.discussion_fetcher, "_stop_event"):
                        logger.debug("Setting stop event for discussion fetcher")
                        self.discussion_fetcher._stop_event.set()

                # Force immediate cleanup
                try:
                    logger.debug("Destroying discussion loading dialog")
                    self._discussion_loading_dialog.Destroy()
                except Exception as destroy_e:
                    logger.error(f"Error destroying dialog: {destroy_e}")
                    # Try to hide it if we can't destroy it
                    try:
                        self._discussion_loading_dialog.Hide()
                    except Exception:
                        pass

                # Clear references
                self._discussion_loading_dialog = None

                # Stop the timer
                logger.debug("Stopping discussion timer")
                self._discussion_timer.Stop()
                # Try to unbind the timer event to prevent memory leaks
                try:
                    self.Unbind(
                        wx.EVT_TIMER,
                        handler=self._on_discussion_timer,
                        source=self._discussion_timer,
                    )
                except Exception as e:
                    logger.error(f"Error unbinding timer event: {e}")

                # Re-enable the discussion button
                if hasattr(self, "discussion_btn") and self.discussion_btn:
                    logger.debug("Re-enabling discussion button")
                    self.discussion_btn.Enable()

                # Update status
                self.SetStatusText("Discussion fetch cancelled")

                # Force a UI update
                wx.SafeYield()
                # Process pending events to ensure UI is updated
                wx.GetApp().ProcessPendingEvents()
        except Exception as e:
            # Dialog might have been destroyed already
            logger.error(f"Error in discussion timer: {e}")
            if hasattr(self, "_discussion_timer"):
                self._discussion_timer.Stop()
                # Try to unbind the timer event to prevent memory leaks
                try:
                    self.Unbind(
                        wx.EVT_TIMER,
                        handler=self._on_discussion_timer,
                        source=self._discussion_timer,
                    )
                except Exception as unbind_e:
                    logger.error(f"Error unbinding timer event: {unbind_e}")

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

    def OnSettings(self, event):  # event is required by wx
        """Handle settings button click

        Args:
            event: Button event
        """
        # Get current settings
        settings = self.config.get("settings", {})
        api_settings = self.config.get("api_settings", {})

        # Combine settings and api_settings for the dialog
        combined_settings = settings.copy()
        combined_settings.update(api_settings)

        # Create settings dialog
        dialog = SettingsDialog(self, combined_settings)
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

            # If precise location setting changed, refresh alerts
            old_precise_setting = settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
            new_precise_setting = updated_settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
            if old_precise_setting != new_precise_setting:
                logger.info(
                    f"Precise location setting changed from {old_precise_setting} "
                    f"to {new_precise_setting}, refreshing alerts"
                )
                # Refresh weather data to apply new setting
                self.UpdateWeatherData()

        dialog.Destroy()

    def OnTimer(self, event):  # event is required by wx
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
