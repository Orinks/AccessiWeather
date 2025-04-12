"""Main application window for AccessiWeather

This module provides the main application window and integrates all components.
"""

import functools  # Import functools
import json
import logging

# import wx.richtext  # Removed screen reader import
import os
import time

import wx

from .async_fetchers import AlertsFetcher, DiscussionFetcher, ForecastFetcher

# Import local modules
from .dialogs import LocationDialog, WeatherDiscussionDialog

# Import SettingsDialog and keys (split for length)
from .settings_dialog import (
    ALERT_RADIUS_KEY,
    API_CONTACT_KEY,
    PRECISE_LOCATION_ALERTS_KEY,
    UPDATE_INTERVAL_KEY,
    SettingsDialog,
)
from .ui_manager import UIManager  # Import the new UI Manager

# Import local modules
# from ..constants import UPDATE_INTERVAL  # Removed unused import


# Logger
logger = logging.getLogger(__name__)

# Constants (UPDATE_INTERVAL moved to accessiweather.constants)
CONFIG_PATH = os.path.expanduser("~/.accessiweather/config.json")


class WeatherApp(wx.Frame):
    """Main application window"""

    def __init__(
        self,
        parent=None,
        location_manager=None,
        api_client=None,
        notifier=None,
        config=None,
        config_path=None,
    ):
        """Initialize the weather app

        Args:
            parent: Parent window
            location_manager: LocationManager instance
            api_client: NoaaApiClient instance
            notifier: WeatherNotifier instance
            config: Configuration dictionary (optional)
            config_path: Custom path to config file (optional, used only if
                         config is None)
        """
        super().__init__(parent, title="AccessiWeather", size=(800, 600))

        # Set config path
        self._config_path = config_path or CONFIG_PATH

        # Load or use provided config
        self.config = config if config is not None else self._load_config()

        # Store provided dependencies
        self.api_client = api_client
        self.notifier = notifier
        self.location_manager = location_manager

        # Validate required dependencies
        if not all([self.api_client, self.notifier, self.location_manager]):
            raise ValueError(
                "Required dependencies (location_manager, api_client, " "notifier) must be provided"
            )

        # Initialize async fetchers
        self.forecast_fetcher = ForecastFetcher(self.api_client)
        self.alerts_fetcher = AlertsFetcher(self.api_client)
        self.discussion_fetcher = DiscussionFetcher(self.api_client)

        # State variables
        self.current_forecast = None
        self.current_alerts = []
        self.updating = False
        self._forecast_complete = False  # Flag for forecast fetch completion
        self._alerts_complete = False  # Flag for alerts fetch completion

        # Initialize UI using UIManager
        # UI elements are now attached to self by UIManager
        self.ui_manager = UIManager(self, self.notifier)  # Pass notifier

        # Set up menu bar
        # self._setup_menu_bar() # Removed menu bar setup

        # Set up status bar
        self.CreateStatusBar()
        self.SetStatusText("Ready")

        # Start update timer
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        # Bind Close event here as it's frame-level, not UI-element specific
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.timer.Start(1000)  # Check every 1 second for updates

        # Last update timestamp
        self.last_update = 0

        # Register with accessibility system
        self.SetName("AccessiWeather")
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName("AccessiWeather")
            accessible.SetRole(wx.ACC_ROLE_WINDOW)

        # Test hooks for async tests
        self._testing_forecast_callback = None
        self._testing_forecast_error_callback = None
        self._testing_alerts_callback = None
        self._testing_alerts_error_callback = None
        self._testing_discussion_callback = None
        self._testing_discussion_error_callback = None

        # Initialize UI with location data
        self.UpdateLocationDropdown()
        self.UpdateWeatherData()

        # Check if API contact is configured
        self._check_api_contact_configured()

    def _load_config(self):
        """Load configuration from file

        Returns:
            Dict containing configuration or empty dict if not found
        """
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config: {str(e)}")

        # Return default config structure
        return {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},  # Added default
            "api_settings": {"api_contact": ""},  # Added default
        }

    # _initialize_api_client method removed as API client is now injected
    # directly

    # InitUI method removed, handled by UIManager

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

    def UpdateLocationDropdown(self):
        """Update the location dropdown with saved locations"""
        if self.location_manager is None:
            return

        # Get all locations
        locations = self.location_manager.get_all_locations()

        # Clear and repopulate dropdown
        self.location_choice.Clear()
        for location in locations:
            self.location_choice.Append(location)

        # Select current location
        current = self.location_manager.get_current_location_name()
        if current and current in locations:
            self.location_choice.SetStringSelection(current)

    def UpdateWeatherData(self):
        """Update weather data in a separate thread"""
        # Even if updating is true, we still want to proceed if this is a
        # location change
        # This is to ensure that location changes always trigger a data refresh

        if self.location_manager is None:
            return

        # Get current location
        location = self.location_manager.get_current_location()
        if location is None:
            self.SetStatusText("No location selected")
            return

        # Always reset updating flag to ensure we can fetch for a new location
        # This is critical for location changes to work properly
        self.updating = True
        self._FetchWeatherData(location)

    def _FetchWeatherData(self, location):
        """Fetch weather data from NOAA API

        Args:
            location: Tuple of (name, lat, lon)
        """
        name, lat, lon = location
        self.SetStatusText(f"Updating weather data for {name}...")

        # --- Start Loading State ---
        self.refresh_btn.Disable()  # Disable refresh button
        # Show loading message
        self.forecast_text.SetValue("Loading forecast...")
        self.alerts_list.DeleteAllItems()  # Clear previous alerts
        # Optional: Add a placeholder item
        # self.alerts_list.InsertItem(0, "Loading alerts...")
        # self.alerts_list.SetItem(0, 1, "...")
        # self.alerts_list.SetItem(0, 2, "...")
        # --- End Loading State ---

        # Reset completion flags for this fetch cycle
        self._forecast_complete = False
        self._alerts_complete = False

        # Start forecast fetching thread
        self.forecast_fetcher.fetch(
            lat, lon, on_success=self._on_forecast_fetched, on_error=self._on_forecast_error
        )

        # Start alerts fetching thread
        self.alerts_fetcher.fetch(
            lat, lon, on_success=self._on_alerts_fetched, on_error=self._on_alerts_error
        )

    def _check_update_complete(self):
        """Check if both forecast and alerts fetches are complete."""
        if self._forecast_complete and self._alerts_complete:
            self.updating = False
            self.SetStatusText("Ready")  # Set final status only when both done
            self.refresh_btn.Enable()  # Re-enable refresh button
            log_msg = "Both forecast and alerts fetch complete. " "Refresh button re-enabled."
            logger.debug(log_msg)

    def _on_forecast_fetched(self, forecast_data):
        """Handle the fetched forecast in the main thread

        Args:
            forecast_data: Dictionary with forecast data
        """
        # Save forecast data
        self.current_forecast = forecast_data

        # Update display
        self.ui_manager._UpdateForecastDisplay(forecast_data)  # Use UIManager

        # Update timestamp
        self.last_update = time.time()

        # Mark forecast as complete and check overall completion
        self._forecast_complete = True
        self._check_update_complete()
        # self._announce_to_screen_reader("Forecast updated.")
        # Removed announcement

        # Notify testing framework if hook is set
        if self._testing_forecast_callback:
            self._testing_forecast_callback(forecast_data)

    def _on_forecast_error(self, error_message):
        """Handle errors during forecast fetching

        Args:
            error_message: Error message
        """
        # Update status immediately for error
        self.SetStatusText("Error fetching forecast")

        # Show error message box
        wx.MessageBox(
            f"Failed to fetch forecast data:\n\n{error_message}",
            "Forecast Error",
            wx.OK | wx.ICON_ERROR,
        )

        # Show error in forecast display
        # Keep error in text area too
        self.forecast_text.SetValue(f"Error fetching forecast: {error_message}")

        # Mark forecast as complete (due to error) and check overall completion
        self._forecast_complete = True
        self._check_update_complete()

        # Notify testing framework if hook is set
        if self._testing_forecast_error_callback:
            self._testing_forecast_error_callback(error_message)

    def _on_alerts_fetched(self, alerts_data):
        """Handle the fetched alerts in the main thread

        Args:
            alerts_data: Dictionary with alerts data
        """
        # Update alerts display
        # Use UIManager and store the processed alerts it returns
        self.current_alerts = self.ui_manager._UpdateAlertsDisplay(alerts_data)

        # Notify user if there are alerts
        # (moved here from _UpdateAlertsDisplay)
        if self.current_alerts:
            self.notifier.notify_alerts(len(self.current_alerts))

        # Update timestamp
        self.last_update = time.time()

        # Mark alerts as complete and check overall completion
        self._alerts_complete = True
        self._check_update_complete()
        # Announce update (split for line length)
        # self._announce_to_screen_reader("Weather alerts updated.")
        # Removed announcement

        # Notify testing framework if hook is set
        if self._testing_alerts_callback:
            self._testing_alerts_callback(alerts_data)

    def _on_alerts_error(self, error_message):
        """Handle errors during alerts fetching

        Args:
            error_message: Error message
        """
        # Update status immediately for error
        self.SetStatusText("Error fetching alerts")

        # Show error message box
        wx.MessageBox(
            f"Failed to fetch weather alerts:\n\n{error_message}",
            "Alerts Error",
            wx.OK | wx.ICON_ERROR,
        )

        # Clear alerts list
        self.alerts_list.DeleteAllItems()
        self.current_alerts = []

        # Mark alerts as complete (due to error) and check overall completion
        self._alerts_complete = True
        self._check_update_complete()

        # Notify testing framework if hook is set
        if self._testing_alerts_error_callback:
            self._testing_alerts_error_callback(error_message)

    # _UpdateForecastDisplay method removed, handled by UIManager
    # _UpdateAlertsDisplay method removed, handled by UIManager

    def OnLocationChange(self, event):
        """Handle location choice change

        Args:
            event: Choice event
        """
        if self.location_manager is None:
            return

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
        if self.location_manager is None:
            return

        # Show location dialog
        dialog = LocationDialog(self, "Add Location")
        if dialog.ShowModal() == wx.ID_OK:
            location_name = dialog.GetLocationName()
            lat = dialog.GetLatitude()
            lon = dialog.GetLongitude()

            if location_name and lat is not None and lon is not None:
                # Add location
                self.location_manager.add_location(location_name, lat, lon)

                # Update dropdown
                self.UpdateLocationDropdown()

                # Select new location
                self.location_choice.SetStringSelection(location_name)

                # Trigger update
                self.OnLocationChange(None)

        dialog.Destroy()

    def OnRemoveLocation(self, event):
        """Handle remove location button click

        Args:
            event: Button event
        """
        if self.location_manager is None:
            return

        # Get selected location
        selected = self.location_choice.GetStringSelection()
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
        if self.location_manager is None:
            return

        # Get current location
        location = self.location_manager.get_current_location()
        if location is None:
            wx.MessageBox(
                "Please select a location first.", "No Location Selected", wx.OK | wx.ICON_WARNING
            )
            return

        name, lat, lon = location

        # Disable button temporarily
        self.discussion_btn.Disable()

        # Show loading dialog
        loading_dialog = wx.ProgressDialog(
            "Fetching Discussion",
            f"Fetching forecast discussion for {name}...",
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT,
        )
        loading_dialog.Pulse()

        # Fetch discussion
        self.discussion_fetcher.fetch(
            lat,
            lon,
            # Use functools.partial to pass extra args to callbacks
            on_success=functools.partial(
                self._on_discussion_fetched, name=name, loading_dialog=loading_dialog
            ),
            on_error=functools.partial(
                self._on_discussion_error, name=name, loading_dialog=loading_dialog
            ),
            # name=name, # Removed incorrect kwargs
            # loading_dialog=loading_dialog # Removed incorrect kwargs
        )

    def _on_discussion_fetched(self, discussion_text, name, loading_dialog):
        """Handle the fetched discussion in the main thread

        Args:
            discussion_text: Fetched discussion text
            name: Location name
            loading_dialog: Progress dialog instance
        """
        # Close loading dialog
        loading_dialog.Destroy()

        # Show discussion dialog
        dialog = WeatherDiscussionDialog(self, f"Forecast Discussion for {name}", discussion_text)
        dialog.ShowModal()
        dialog.Destroy()

        # Re-enable button
        self.discussion_btn.Enable()

        # Notify testing framework if hook is set
        if self._testing_discussion_callback:
            self._testing_discussion_callback(discussion_text)

    def _on_discussion_error(self, error_message, name, loading_dialog):
        """Handle errors during discussion fetching

        Args:
            error_message: Error message
            name: Location name
            loading_dialog: Progress dialog instance
        """
        # Close loading dialog
        loading_dialog.Destroy()

        # Show error message
        msg = f"Failed to fetch forecast discussion for {name}:\n\n" f"{error_message}"
        wx.MessageBox(msg, "Discussion Error", wx.OK | wx.ICON_ERROR)

        # Re-enable button after error
        self.discussion_btn.Enable()

        # Notify testing framework if hook is set
        if self._testing_discussion_error_callback:
            self._testing_discussion_error_callback(error_message)

    def OnViewAlert(self, event):
        """Handle view alert details button click

        Args:
            event: Button event
        """
        # Get selected alert index
        selected_index = self.alerts_list.GetFirstSelected()

        if selected_index == -1:
            wx.MessageBox(
                "Please select an alert to view details.",
                "No Alert Selected",
                wx.OK | wx.ICON_WARNING,
            )
            return

        # Get alert data
        if selected_index < len(self.current_alerts):
            alert_props = self.current_alerts[selected_index]

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
                f"current_alerts (len={len(self.current_alerts)})"
            )
            wx.MessageBox("Error retrieving alert details.", "Error", wx.OK | wx.ICON_ERROR)

    def OnAlertActivated(self, event):
        """Handle double-click or Enter on an alert item

        Args:
            event: List event
        """
        # Trigger the same action as clicking the "View Alert Details" button
        self.OnViewAlert(event)

    def OnClose(self, event):
        """Handle window close event

        Args:
            event: Close event
        """
        # Stop timer
        self.timer.Stop()

        # Save config before closing
        self._save_config()

        # Destroy window
        self.Destroy()

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

    # Removed _announce_to_screen_reader method

    # _setup_menu_bar method removed as settings are now accessed via button
    def OnSettings(self, event):
        """Show the settings dialog and handle updates."""
        # Prepare current settings from self.config
        current_api_settings = self.config.get("api_settings", {})
        current_app_settings = self.config.get("settings", {})

        dialog_settings = {
            API_CONTACT_KEY: current_api_settings.get(API_CONTACT_KEY, ""),
            UPDATE_INTERVAL_KEY: current_app_settings.get(UPDATE_INTERVAL_KEY, 30),
            ALERT_RADIUS_KEY: current_app_settings.get(ALERT_RADIUS_KEY, 25),
        }

        dialog = SettingsDialog(self, dialog_settings)

        if dialog.ShowModal() == wx.ID_OK:
            new_settings = dialog.get_settings()
            logger.info(f"Settings updated via dialog: {new_settings}")

            # Update self.config structure
            if "api_settings" not in self.config:
                self.config["api_settings"] = {}
            if "settings" not in self.config:
                self.config["settings"] = {}

            self.config["api_settings"][API_CONTACT_KEY] = new_settings[API_CONTACT_KEY]
            self.config["settings"][UPDATE_INTERVAL_KEY] = new_settings[UPDATE_INTERVAL_KEY]
            self.config["settings"][ALERT_RADIUS_KEY] = new_settings[ALERT_RADIUS_KEY]

            # Save the updated configuration
            self._save_config()

            # Apply relevant changes immediately (e.g., restart timer)
            old_interval = current_app_settings.get(UPDATE_INTERVAL_KEY)
            new_interval = new_settings[UPDATE_INTERVAL_KEY]
            self._apply_settings_changes(old_interval, new_interval)

        dialog.Destroy()

    def _apply_settings_changes(self, old_interval, new_interval):
        """Apply changes made in the settings dialog."""
        # Restart timer only if the interval changed
        if old_interval != new_interval:
            log_msg = (
                f"Update interval changed from {old_interval} to "
                f"{new_interval}. Restarting timer."
            )
            logger.info(log_msg)
            self.timer.Stop()
            # Use the new interval immediately for the next check cycle
            self.timer.Start(1000)  # Keep checking every second
            # The OnTimer logic will now use the updated interval from config
            # Force an immediate update check after changing interval? Optional
            # self.last_update = 0 # Reset last update to force check sooner
            # self.OnTimer(None) # Trigger timer logic

    def _save_config(self):
        """Save the current configuration to the config file."""
        try:
            # Ensure the directory exists
            config_dir = os.path.dirname(self._config_path)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
                logger.info(f"Created config directory: {config_dir}")

            # Write the config file
            with open(self._config_path, "w") as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration saved to {self._config_path}")

        except Exception as e:
            log_msg = f"Failed to save configuration to " f"{self._config_path}: {e}"
            logger.error(log_msg)
            # Optionally notify the user
            wx.MessageBox(f"Error saving settings: {e}", "Save Error", wx.OK | wx.ICON_ERROR, self)

    def _check_api_contact_configured(self):
        """
        Check if the API contact information is configured.

        If not, display a message dialog prompting the user to configure it.
        If the user clicks OK, automatically open the settings dialog.
        """
        # Get API contact from config
        api_settings = self.config.get("api_settings", {})
        api_contact = api_settings.get("api_contact", "")

        # Check if API contact is missing or empty
        if not api_contact:
            # Show message dialog
            dialog = wx.MessageDialog(
                self,
                "API contact information is missing or empty. "
                "This information is required for making API requests. "
                "Would you like to configure it now?",
                "API Contact Required",
                wx.OK | wx.ICON_INFORMATION,
            )

            # If user clicks OK, open settings dialog
            if dialog.ShowModal() == wx.ID_OK:
                self.OnSettings(None)
