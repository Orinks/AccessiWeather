"""Main application window for AccessiWeather

This module provides the main application window and integrates all components
using the service layer for business logic.
"""

import json
import logging
import os
import time
import wx

from accessiweather.config_utils import get_config_dir

from .async_fetchers import AlertsFetcher, DiscussionFetcher, ForecastFetcher
from .dialogs import WeatherDiscussionDialog
from accessiweather.national_forecast_fetcher import NationalForecastFetcher
from .settings_dialog import (
    ALERT_RADIUS_KEY,
    API_CONTACT_KEY,
    PRECISE_LOCATION_ALERTS_KEY,
    UPDATE_INTERVAL_KEY,
)
from .system_tray import TaskBarIcon
from .ui_manager import UIManager
from .weather_app_handlers import WeatherAppHandlers

logger = logging.getLogger(__name__)

# Constants
CONFIG_DIR = get_config_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


class WeatherApp(wx.Frame, WeatherAppHandlers):
    """Main application window for AccessiWeather."""

    def __init__(
        self,
        parent=None,
        weather_service=None,
        location_service=None,
        notification_service=None,
        api_client=None,  # For backward compatibility
        config=None,
        config_path=None,
    ):
        """Initialize the weather app

        Args:
            parent: Parent window
            weather_service: WeatherService instance
            location_service: LocationService instance
            notification_service: NotificationService instance
            api_client: NoaaApiClient instance (for backward compatibility)
            config: Configuration dictionary (optional)
            config_path: Custom path to config file (optional)
        """
        super().__init__(parent, title="AccessiWeather", size=(800, 600))

        # Set config path
        self._config_path = config_path or CONFIG_PATH

        # Load or use provided config
        self.config = config if config is not None else self._load_config()

        # Store provided services
        self.weather_service = weather_service
        self.location_service = location_service
        self.notification_service = notification_service

        # For backward compatibility
        self.api_client = api_client

        # Validate required services
        if not all([self.weather_service, self.location_service, self.notification_service]):
            raise ValueError(
                "Required services (weather_service, location_service, notification_service) "
                "must be provided"
            )

        # Initialize async fetchers (using the weather service)
        self.forecast_fetcher = ForecastFetcher(self.api_client)
        self.alerts_fetcher = AlertsFetcher(self.api_client)
        self.discussion_fetcher = DiscussionFetcher(self.api_client)
        self.national_forecast_fetcher = NationalForecastFetcher(self.weather_service)

        # State variables
        self.current_forecast = None
        self.current_alerts = []
        self.updating = False
        self._forecast_complete = False  # Flag for forecast fetch completion
        self._alerts_complete = False  # Flag for alerts fetch completion

        # Nationwide discussion state
        self._in_nationwide_mode = False
        self._nationwide_wpc_full = None
        self._nationwide_spc_full = None

        # Initialize UI using UIManager
        # UI elements are now attached to self by UIManager
        self.ui_manager = UIManager(self, self.notification_service.notifier)

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
        self.last_update: float = 0.0

        # Create system tray icon
        self.taskbar_icon = TaskBarIcon(self)

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
            "settings": {
                UPDATE_INTERVAL_KEY: 30,
                ALERT_RADIUS_KEY: 25,
                PRECISE_LOCATION_ALERTS_KEY: True,  # Default to precise location alerts
            },
            "api_settings": {API_CONTACT_KEY: ""},  # Added default
        }

    def UpdateLocationDropdown(self):
        """Update the location dropdown with saved locations"""
        # Get all locations from the location service
        locations = self.location_service.get_all_locations()
        current = self.location_service.get_current_location_name()

        # Update dropdown
        self.location_choice.Clear()

        # Check if the selected location is the Nationwide location
        selected_is_nationwide = current and self.location_service.is_nationwide_location(current)

        for location in locations:
            self.location_choice.Append(location)

            # If this is the Nationwide location and it's selected, disable the remove button
            is_nationwide = self.location_service.is_nationwide_location(location)
            if hasattr(self, "remove_btn") and is_nationwide and selected_is_nationwide:
                self.remove_btn.Disable()

        # Set current selection
        if current and current in locations:
            self.location_choice.SetStringSelection(current)

    def UpdateWeatherData(self):
        """Update weather data in a separate thread"""
        # Even if updating is true, we still want to proceed if this is a
        # location change
        # This is to ensure that location changes always trigger a data refresh

        # Get current location from the location service
        location = self.location_service.get_current_location()
        if location is None:
            self.SetStatusText("No location selected")
            return

        # Always reset updating flag to ensure we can fetch for a new location
        # This is critical for location changes to work properly
        self.updating = True
        self._FetchWeatherData(location)

    def _FetchWeatherData(self, location):
        """Fetch weather data using the weather service

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
        # --- End Loading State ---

        # Reset completion flags for this fetch cycle
        self._forecast_complete = False
        self._alerts_complete = False

        # Check if this is the nationwide location
        if self.location_service.is_nationwide_location(name):
            # Nationwide: Use the dedicated async fetcher
            logger.info("Initiating nationwide forecast fetch using NationalForecastFetcher")
            self.national_forecast_fetcher.fetch(
                on_success=self._on_forecast_fetched,
                on_error=self._on_forecast_error
            )
            # Note: Status updates and button enabling will happen in the callbacks
            return # Return after initiating the fetch

        # Start forecast fetching thread
        self.forecast_fetcher.fetch(
            lat, lon, on_success=self._on_forecast_fetched, on_error=self._on_forecast_error
        )

        # Get precise location setting from config
        precise_location = self.config.get("settings", {}).get(PRECISE_LOCATION_ALERTS_KEY, True)
        alert_radius = self.config.get("settings", {}).get(ALERT_RADIUS_KEY, 25)

        # Start alerts fetching thread with precise location setting
        self.alerts_fetcher.fetch(
            lat,
            lon,
            on_success=self._on_alerts_fetched,
            on_error=self._on_alerts_error,
            precise_location=precise_location,
            radius=alert_radius,
        )

    def _check_update_complete(self):
        """Check if both forecast and alerts fetches are complete."""
        if self._forecast_complete and self._alerts_complete:
            self.updating = False
            self.SetStatusText("Ready")  # Set final status only when both done
            self.refresh_btn.Enable()  # Re-enable refresh button
            log_msg = "Both forecast and alerts fetch complete. Refresh button re-enabled."
            logger.debug(log_msg)

    def _on_forecast_fetched(self, forecast_data):
        """Handle the fetched forecast in the main thread

        Args:
            forecast_data: Dictionary with forecast data
        """
        print("[DEBUG] _on_forecast_fetched received:", forecast_data)
        # Save forecast data
        self.current_forecast = forecast_data

        # Update display using UIManager
        self.ui_manager._UpdateForecastDisplay(forecast_data)

        # Update timestamp
        self.last_update = time.time()

        # Mark forecast as complete
        self._forecast_complete = True

        # If it's national data (identified by the specific key), mark alerts as complete too
        if "national_discussion_summaries" in forecast_data:
            self._alerts_complete = True

        # Check overall completion
        self._check_update_complete()

        # Notify testing framework if hook is set
        if self._testing_forecast_callback:
            self._testing_forecast_callback(forecast_data)

    def _on_forecast_error(self, error):
        """Handle forecast fetch error

        Args:
            error: Error message
        """
        logger.error(f"Forecast fetch error: {error}")
        self.forecast_text.SetValue(f"Error fetching forecast: {error}")

        # Mark forecast as complete and check overall completion
        self._forecast_complete = True
        self._check_update_complete()

    def _format_national_forecast(self, national_data):
        """Format national forecast data for display."""
        lines = []

        # Check if data is nested in national_discussion_summaries
        if "national_discussion_summaries" in national_data:
            # Extract the actual data from the wrapper
            forecast_data = national_data["national_discussion_summaries"]
        else:
            # Use the data as is if not wrapped
            forecast_data = national_data

        # Log the structure to help debug
        logger.debug(f"Formatting national forecast with data structure: {forecast_data.keys() if isinstance(forecast_data, dict) else 'not a dict'}")

        # WPC
        wpc_data = forecast_data.get("wpc", {})
        if wpc_data and wpc_data.get("short_range_summary"):
            lines.append("=== WEATHER PREDICTION CENTER (WPC) ===")
            lines.append(wpc_data["short_range_summary"])

            # Store the full text for button clicks
            if wpc_data.get("short_range_full"):
                self._nationwide_wpc_full = wpc_data["short_range_full"]
            else:
                self._nationwide_wpc_full = None

        # SPC
        spc_data = forecast_data.get("spc", {})
        if spc_data and spc_data.get("day1_summary"):
            lines.append("\n=== STORM PREDICTION CENTER (SPC) ===")
            lines.append(spc_data["day1_summary"])

            # Store the full text for button clicks
            if spc_data.get("day1_full"):
                self._nationwide_spc_full = spc_data["day1_full"]
            else:
                self._nationwide_spc_full = None

        # Set flag to indicate we're in nationwide mode
        self._in_nationwide_mode = True

        # Attribution
        attribution = forecast_data.get("attribution")
        if attribution:
            lines.append(f"\nSource: {attribution}")

        if not lines:
            lines.append("No data available for national forecast.")

        return "\n".join(lines)

    def _on_discussion_fetched(self, discussion_text, name=None, loading_dialog=None):
        """Handle the fetched discussion in the main thread

        Args:
            discussion_text: Fetched discussion text
            name: Location name (optional)
            loading_dialog: Progress dialog instance (optional)
        """
        logger.debug("Discussion fetched successfully, handling in main thread")

        # Make sure we clean up properly before showing the discussion dialog
        self._cleanup_discussion_loading(loading_dialog)

        # Show discussion in a dialog
        discussion_dialog = WeatherDiscussionDialog(
            self, "Weather Discussion", text=discussion_text
        )
        discussion_dialog.ShowModal()
        discussion_dialog.Destroy()

        # Re-enable button if it exists
        if hasattr(self, "discussion_btn") and self.discussion_btn:
            self.discussion_btn.Enable()

        # Notify testing framework if hook is set
        if self._testing_discussion_callback:
            self._testing_discussion_callback(discussion_text)

    def _on_nationwide_discussion_fetched(self, discussion_text, name=None, loading_dialog=None):
        """Handle the fetched nationwide discussion in the main thread

        Args:
            discussion_text: Fetched discussion text
            name: Location name (optional)
            loading_dialog: Progress dialog instance (optional)
        """
        logger.debug("Nationwide discussion fetched successfully, handling in main thread")

        # --- Stop Timer --- (if applicable)
        if hasattr(self, "_discussion_timer") and self._discussion_timer:
            logger.debug("Stopping discussion timer")
            self._discussion_timer.Stop()
            self._discussion_timer = None

        # --- Close Dialog --- Determine which dialog instance to close
        dialog_to_close = loading_dialog
        if not dialog_to_close and hasattr(self, "_discussion_loading_dialog"):
            dialog_to_close = self._discussion_loading_dialog

        if dialog_to_close:
            try:
                # Check if it's a valid wx window instance before proceeding
                if isinstance(dialog_to_close, wx.Window) and dialog_to_close.IsShown():
                    logger.debug("Hiding loading dialog")
                    dialog_to_close.Hide()
                    wx.SafeYield()  # Give UI a chance to process Hide
                    logger.debug("Destroying loading dialog")
                    dialog_to_close.Destroy()
                    wx.SafeYield()  # Give UI a chance to process Destroy
                elif isinstance(dialog_to_close, wx.Window):
                    logger.debug(
                        "Loading dialog exists but is not shown, attempting destroy anyway."
                    )
                    # Attempt destroy even if not shown, might already be destroyed
                    try:
                        dialog_to_close.Destroy()
                        wx.SafeYield()
                    except wx.wxAssertionError:
                        logger.debug("Dialog likely already destroyed.")  # Expected if already gone
                    except Exception as destroy_e:
                        logger.error(
                            f"Error destroying hidden/non-window dialog: {destroy_e}", exc_info=True
                        )
                else:
                    logger.warning(
                        f"Item to close is not a valid wx.Window: {type(dialog_to_close)}"
                    )

            except wx.wxAssertionError:
                # This often happens if the dialog is already destroyed (e.g., by Cancel)
                logger.debug("Loading dialog was likely already destroyed.")
            except Exception as e:
                logger.error(f"Error closing loading dialog: {e}", exc_info=True)

        # --- Clear Reference --- Always clear the instance variable
        if hasattr(self, "_discussion_loading_dialog"):
            logger.debug("Clearing discussion loading dialog reference")
            self._discussion_loading_dialog = None

        # --- Force UI Update ---
        logger.debug("Processing pending events after cleanup")
        wx.GetApp().ProcessPendingEvents()
        wx.SafeYield()
        logger.debug("Cleanup processing complete")

    def _on_discussion_error(self, error, name=None, loading_dialog=None):
        """Handle discussion fetch error

        Args:
            error: Error message
            name: Location name (optional)
            loading_dialog: Progress dialog instance (optional)
        """
        location_str = name if name else "unknown location"
        logger.debug(f"Discussion fetch error for {location_str}, handling in main thread")

        # Make sure we clean up properly before showing the error message
        self._cleanup_discussion_loading(loading_dialog)

        logger.error(f"Discussion fetch error: {error}")

        # Create a more informative error message if we have the location name
        location_info = f" for {name}" if name else ""
        wx.MessageBox(
            f"Error fetching forecast discussion{location_info}: {error}",
            "Fetch Error",
            wx.OK | wx.ICON_ERROR,
        )

        # Re-enable button if it exists
        if hasattr(self, "discussion_btn") and self.discussion_btn:
            self.discussion_btn.Enable()

        # Notify testing framework if hook is set
        if self._testing_discussion_error_callback:
            self._testing_discussion_error_callback(error)

    # For backward compatibility with WeatherAppHandlers
    @property
    def location_manager(self):
        """Provide backward compatibility with the location_manager property."""
        return self.location_service.location_manager

    @property
    def notifier(self):
        """Provide backward compatibility with the notifier property."""
        return self.notification_service.notifier

    def _on_alerts_fetched(self, alerts_data):
        """Handle the fetched alerts in the main thread

        Args:
            alerts_data: Dictionary with alerts data
        """
        logger.debug("Alerts fetched successfully, handling in main thread")

        # Process alerts through notification service
        processed_alerts = self.notification_service.process_alerts(alerts_data)

        # Save processed alerts
        self.current_alerts = processed_alerts

        # Update display using UIManager
        self.ui_manager._UpdateAlertsDisplay(alerts_data)

        # Notify user about alerts
        self.notification_service.notify_alerts(processed_alerts)

        # Mark alerts as complete
        self._alerts_complete = True

        # Check overall completion
        self._check_update_complete()

        # Notify testing framework if hook is set
        if self._testing_alerts_callback:
            self._testing_alerts_callback(alerts_data)

    def _on_alerts_error(self, error):
        """Handle alerts fetch error

        Args:
            error: Error message
        """
        logger.error(f"Alerts fetch error: {error}")

        # Clear alerts list
        self.alerts_list.DeleteAllItems()

        # Add error message to alerts list
        index = self.alerts_list.InsertItem(0, "Error")
        self.alerts_list.SetItem(index, 1, f"Error fetching alerts: {error}")

        # Mark alerts as complete and check overall completion
        self._alerts_complete = True
        self._check_update_complete()

        # Notify testing framework if hook is set
        if self._testing_alerts_error_callback:
            self._testing_alerts_error_callback(error)

    def _cleanup_discussion_loading(self, loading_dialog=None):
        """Clean up resources related to discussion loading

        Args:
            loading_dialog: Progress dialog instance (optional)
        """
        # --- Stop Timer --- (if applicable)
        if hasattr(self, "_discussion_timer") and self._discussion_timer:
            logger.debug("Stopping discussion timer")
            self._discussion_timer.Stop()
            self._discussion_timer = None

        # --- Close Dialog --- Determine which dialog instance to close
        dialog_to_close = loading_dialog
        if not dialog_to_close and hasattr(self, "_discussion_loading_dialog"):
            dialog_to_close = self._discussion_loading_dialog

        if dialog_to_close:
            try:
                # Check if it's a valid wx window instance before proceeding
                if isinstance(dialog_to_close, wx.Window) and dialog_to_close.IsShown():
                    logger.debug("Hiding loading dialog")
                    dialog_to_close.Hide()
                    wx.SafeYield()  # Give UI a chance to process Hide
                    logger.debug("Destroying loading dialog")
                    dialog_to_close.Destroy()
                    wx.SafeYield()  # Give UI a chance to process Destroy
                elif isinstance(dialog_to_close, wx.Window):
                    logger.debug(
                        "Loading dialog exists but is not shown, attempting destroy anyway."
                    )
                    # Attempt destroy even if not shown, might already be destroyed
                    try:
                        dialog_to_close.Destroy()
                        wx.SafeYield()
                    except wx.wxAssertionError:
                        logger.debug("Dialog likely already destroyed.")  # Expected if already gone
                    except Exception as destroy_e:
                        logger.error(
                            f"Error destroying hidden/non-window dialog: {destroy_e}", exc_info=True
                        )
                else:
                    logger.warning(
                        f"Item to close is not a valid wx.Window: {type(dialog_to_close)}"
                    )

            except wx.wxAssertionError:
                # This often happens if the dialog is already destroyed (e.g., by Cancel)
                logger.debug("Loading dialog was likely already destroyed.")
            except Exception as e:
                logger.error(f"Error closing loading dialog: {e}", exc_info=True)

        # --- Clear Reference --- Always clear the instance variable
        if hasattr(self, "_discussion_loading_dialog"):
            logger.debug("Clearing discussion loading dialog reference")
            self._discussion_loading_dialog = None

        # --- Force UI Update ---
        logger.debug("Processing pending events after cleanup")
        wx.GetApp().ProcessPendingEvents()
        wx.SafeYield()
        logger.debug("Cleanup processing complete")
