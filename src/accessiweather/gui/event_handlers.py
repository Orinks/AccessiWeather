"""Event handlers for the AccessiWeather application."""

import functools
import logging

import wx

from .dialogs import LocationDialog
from .settings_dialog import SettingsDialog  # Import SettingsDialog from here
from .settings_dialog import ALERT_RADIUS_KEY, API_CONTACT_KEY, UPDATE_INTERVAL_KEY

logger = logging.getLogger(__name__)


class WeatherAppEventHandlers:
    """Handles UI events for the WeatherApp frame."""

    def __init__(self, frame):
        """Initialize the event handlers.

        Args:
            frame: The main WeatherApp frame instance.
        """
        self.frame = frame

    def OnLocationChange(self, event):
        """Handle location choice change.

        Args:
            event: Choice event
        """
        if self.frame.location_manager is None:
            return

        # Get selected location
        selected = self.frame.location_choice.GetStringSelection()
        if not selected:
            return

        # Set current location
        self.frame.location_manager.set_current_location(selected)

        # Update weather data
        self.frame.UpdateWeatherData()

    def OnAddLocation(self, event):
        """Handle add location button click.

        Args:
            event: Button event
        """
        if self.frame.location_manager is None:
            return

        # Show location dialog
        dialog = LocationDialog(self.frame, "Add Location")
        if dialog.ShowModal() == wx.ID_OK:
            # Use the updated GetValues method from LocationDialog
            location_name, lat, lon = dialog.GetValues()

            if location_name and lat is not None and lon is not None:
                # Add location
                self.frame.location_manager.add_location(location_name, lat, lon)

                # Update dropdown
                self.frame.UpdateLocationDropdown()

                # Select new location
                self.frame.location_choice.SetStringSelection(location_name)

                # Trigger update
                self.OnLocationChange(None)  # Call handler method

        dialog.Destroy()

    def OnRemoveLocation(self, event):
        """Handle remove location button click.

        Args:
            event: Button event
        """
        if self.frame.location_manager is None:
            return

        # Get selected location
        selected = self.frame.location_choice.GetStringSelection()
        if not selected:
            wx.MessageBox(
                "Please select a location to remove.",
                "No Location Selected",
                wx.OK | wx.ICON_WARNING,
            )
            return

        # Confirm removal
        confirm = wx.MessageBox(
            f"Are you sure you want to remove '{selected}'?",
            "Confirm Removal",
            wx.YES_NO | wx.ICON_QUESTION,
        )

        if confirm == wx.YES:
            # Remove location
            self.frame.location_manager.remove_location(selected)

            # Update dropdown
            self.frame.UpdateLocationDropdown()

            # Clear forecast and alerts if current location was removed
            if self.frame.location_manager.get_current_location_name() is None:
                self.frame.forecast_text.SetValue("Select a location to view the forecast")
                self.frame.alerts_list.DeleteAllItems()  # Clear display
                self.frame.current_alerts = []
                self.frame.SetStatusText("Location removed. Select a new location.")
            else:
                # If another location is now current, update data
                self.frame.UpdateWeatherData()

    def OnRefresh(self, event):
        """Handle refresh button click.

        Args:
            event: Button event
        """
        # Trigger weather data update
        self.frame.UpdateWeatherData()

    def OnViewDiscussion(self, event):
        """Handle view discussion button click.

        Args:
            event: Button event
        """
        if self.frame.location_manager is None:
            return

        # Get current location
        location = self.frame.location_manager.get_current_location()
        if location is None:
            wx.MessageBox(
                "Please select a location first.",
                "No Location Selected",
                wx.OK | wx.ICON_WARNING,
            )
            return

        name, lat, lon = location

        # Disable button temporarily
        self.frame.discussion_btn.Disable()

        # Show loading dialog
        loading_dialog = wx.ProgressDialog(
            "Fetching Discussion",
            f"Fetching forecast discussion for {name}...",
            maximum=100,
            parent=self.frame,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT,
        )
        loading_dialog.Pulse()

        # Fetch discussion using the frame's fetcher
        self.frame.discussion_fetcher.fetch(
            lat,
            lon,
            # Use functools.partial to pass extra args to callbacks
            on_success=functools.partial(
                self.frame._on_discussion_fetched,  # Call frame's method
                name=name,
                loading_dialog=loading_dialog,
            ),
            on_error=functools.partial(
                self.frame._on_discussion_error,  # Call frame's method
                name=name,
                loading_dialog=loading_dialog,
            ),
        )

    def OnViewAlert(self, event):
        """Handle view alert details button click.

        Args:
            event: Button event
        """
        # Get selected alert index
        selected_index = self.frame.alerts_list.GetFirstSelected()

        if selected_index == -1:
            wx.MessageBox(
                "Please select an alert to view details.",
                "No Alert Selected",
                wx.OK | wx.ICON_WARNING,
            )
            return

        # Get alert data
        if selected_index < len(self.frame.current_alerts):
            alert_props = self.frame.current_alerts[selected_index]

            # Format details
            details = (
                f"Event: {alert_props.get('event', 'N/A')}\n"
                f"Severity: {alert_props.get('severity', 'N/A')}\n"
                f"Headline: {alert_props.get('headline', 'N/A')}\n\n"
                f"Description:\n{alert_props.get('description', 'N/A')}\n\n"
                f"Instructions:\n{alert_props.get('instruction', 'N/A')}"
            )

            # Show details in message box
            wx.MessageBox(details, "Alert Details", wx.OK | wx.ICON_INFORMATION)
        else:
            logger.error(
                f"Selected index {selected_index} out of range for "
                f"current_alerts (len={len(self.frame.current_alerts)})"
            )
            wx.MessageBox(
                "Error retrieving alert details.",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def OnAlertActivated(self, event):
        """Handle double-click or Enter on an alert item.

        Args:
            event: List event
        """
        # Trigger the same action as clicking the "View Alert Details" button
        self.OnViewAlert(event)

    def OnSettings(self, event):
        """Show the settings dialog and handle updates."""
        # Prepare current settings from self.frame.config
        current_api_settings = self.frame.config.get("api_settings", {})
        current_app_settings = self.frame.config.get("settings", {})

        dialog_settings = {
            API_CONTACT_KEY: current_api_settings.get(API_CONTACT_KEY, ""),
            UPDATE_INTERVAL_KEY: current_app_settings.get(UPDATE_INTERVAL_KEY, 30),
            ALERT_RADIUS_KEY: current_app_settings.get(ALERT_RADIUS_KEY, 25),
        }

        dialog = SettingsDialog(self.frame, dialog_settings)

        if dialog.ShowModal() == wx.ID_OK:
            new_settings = dialog.get_settings()
            logger.info(f"Settings updated via dialog: {new_settings}")

            # Update self.frame.config structure
            if "api_settings" not in self.frame.config:
                self.frame.config["api_settings"] = {}
            if "settings" not in self.frame.config:
                self.frame.config["settings"] = {}

            self.frame.config["api_settings"][API_CONTACT_KEY] = new_settings[API_CONTACT_KEY]
            self.frame.config["settings"][UPDATE_INTERVAL_KEY] = new_settings[UPDATE_INTERVAL_KEY]
            self.frame.config["settings"][ALERT_RADIUS_KEY] = new_settings[ALERT_RADIUS_KEY]

            # Save the updated configuration using frame's method
            self.frame._save_config()

            # Apply relevant changes immediately (e.g., restart timer)
            old_interval = current_app_settings.get(UPDATE_INTERVAL_KEY)
            new_interval = new_settings[UPDATE_INTERVAL_KEY]
            # Call frame's method to apply changes
            self.frame._apply_settings_changes(old_interval, new_interval)

        dialog.Destroy()

    def OnKeyDown(self, event):
        """Handle key down events for accessibility.

        Args:
            event: Key event
        """
        # Handle key events for accessibility
        # For example, F5 to refresh
        if event.GetKeyCode() == wx.WXK_F5:
            self.OnRefresh(event)
        else:
            event.Skip()
