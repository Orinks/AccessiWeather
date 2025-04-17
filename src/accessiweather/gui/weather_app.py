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
from .settings_dialog import (
    ALERT_RADIUS_KEY,
    API_CONTACT_KEY,
    CACHE_ENABLED_KEY,
    CACHE_TTL_KEY,
    MINIMIZE_ON_STARTUP_KEY,
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
            api_client: ApiClient instance (potentially from tests)
            config: Configuration dictionary (optional)
            config_path: Custom path to config file (optional)
        """
        # 1. Initialize the superclass (wx.Frame)
        super().__init__(parent, title="AccessiWeather", size=(900, 700))
        self._setup_logging()

        # 2. Load Configuration and Set Skip Flag
        self._config_path = config_path or CONFIG_PATH
        self.config = config if config is not None else self._load_config()
        self._should_check_api_contact = not self.config.get("skip_api_contact_check", False)

        # 3. Initialize Services (using self.config)
        # Use provided services or initialize defaults
        self.api_client = api_client or ApiClient(self.config.get("api_settings", {}))
        self.weather_service = weather_service or WeatherService(self.api_client, self.config.get("api_settings", {}))
        self.location_service = location_service or LocationService(self.config.get("settings", {}).get(ALERT_RADIUS_KEY, 25))
        self.notification_service = notification_service or NotificationService(self)

        # --- Internal State Variables ---
        self.updating = False
        self._forecast_complete = False  # Flag for forecast fetch completion
        self._alerts_complete = False  # Flag for alerts fetch completion

        # Initialize UI using UIManager
        self.ui_manager = UIManager(self, self.notification_service.notifier)

        # Set up status bar
        self.CreateStatusBar()
        self.SetStatusText("Ready")

        # Start update timer
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
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

        # Create system tray icon
        self.taskbar_icon = TaskBarIcon(self)

        # Test hooks for async tests
        self._testing_forecast_callback = None
        self._testing_forecast_error_callback = None
        self._testing_alerts_callback = None
        self._testing_alerts_error_callback = None
        self._testing_discussion_callback = None
        self._testing_discussion_error_callback = None
        # --- End Internal State ---

        # 4. Initialize UI (uses services)
        self._init_ui() # Sets up menus, status bar, panels, etc.

        # 5. Load Initial Data and Update UI
        self.LoadLocations()
        self.LoadCurrentLocation()
        self.UpdateLocationDropdown()
        self.StartUpdateTimer() # Start the timer after UI is ready
        wx.CallAfter(self.UpdateWeatherData) # Schedule initial update

        # 6. Conditional API Contact Check (at the end, using the flag)
        if self._should_check_api_contact:
            self._check_api_contact_configured()

        # Check if we should start minimized
        if self.config.get("settings", {}).get(MINIMIZE_ON_STARTUP_KEY, False):
            logger.info("Starting minimized to system tray")
            self.Hide()

    def _setup_logging(self):
        # --- Logging Setup (Explicit Handler Management) ---
        log_dir = os.path.join(os.getenv("APPDATA"), ".accessiweather")
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, "app.log") # Store log file path

        root_logger = logging.getLogger() # Get root logger
        root_logger.setLevel(logging.INFO) # Ensure level is set

        # Remove existing handlers pointing to the same log file
        for handler in root_logger.handlers[:]: # Iterate over a copy
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == self.log_file:
                handler.close()
                root_logger.removeHandler(handler)
                logging.debug(f"Removed existing file handler for {self.log_file}")

        # Create and add the file handler
        log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        file_handler = logging.FileHandler(self.log_file, mode='a')
        file_handler.setFormatter(log_formatter)
        root_logger.addHandler(file_handler)
        # --- End Logging Setup ---

        logging.info("Application started.")

        # Initialize services if not provided
        # Bind Close event
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Setup logging shutdown on close
        self.Bind(wx.EVT_CLOSE, self._on_close_shutdown_logging)

    def _on_close_shutdown_logging(self, event):
        """Ensure logging is shut down when the app closes."""
        logging.info("Shutting down logging.")
        logging.shutdown()
        event.Skip() # Allow other close handlers to run

    def _init_ui(self):
        # Menu Bar Setup (Remove call to non-existent method)
        # self.ui_manager._setup_menubar() # Error: Method does not exist

        # Panel and Sizer Setup (Using UIManager)
        self.ui_manager._setup_ui() # Corrected method name

        # Bind events
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        # self.Bind(wx.EVT_TIMER, self.OnUpdateTimer, self.update_timer) # Redundant and incorrect

    # Load configuration from file
    def _load_config(self):
        # Load configuration from file or return default
        try:
            with open(self._config_path, "r") as f:
                loaded_config = json.load(f)
                # --- Ensure essential keys exist --- Start
                default_config = self._get_default_config()
                # Ensure top-level keys
                for key, value in default_config.items():
                    if key not in loaded_config:
                        loaded_config[key] = value
                    # Ensure second-level keys (settings, api_settings)
                    elif isinstance(value, dict):
                        if key not in loaded_config or not isinstance(loaded_config[key], dict):
                             loaded_config[key] = {}
                        for sub_key, sub_value in value.items():
                            if sub_key not in loaded_config[key]:
                                loaded_config[key][sub_key] = sub_value
                # --- Ensure essential keys exist --- End
                return loaded_config
        except FileNotFoundError:
            logging.warning(f"Config file not found: {self._config_path}. Using default config.")
            return self._get_default_config()
        except json.JSONDecodeError:
            logging.error(f"Error decoding config file: {self._config_path}. Using default config.")
            return self._get_default_config()
        except Exception as e:
             logging.error(f"Unexpected error loading config: {e}. Using default config.")
             return self._get_default_config()

    def _get_default_config(self):
        """Returns the default configuration structure."""
        return {
            "locations": {},
            "current": None,
            "settings": {
                UPDATE_INTERVAL_KEY: 30,
                ALERT_RADIUS_KEY: 25,
                PRECISE_LOCATION_ALERTS_KEY: True,  # Default to precise location alerts
                MINIMIZE_ON_STARTUP_KEY: False,  # Default to not minimizing on startup
                CACHE_ENABLED_KEY: True,  # Default to enabled caching
                CACHE_TTL_KEY: 300,  # Default to 5 minutes (300 seconds)
            },
            "api_settings": {API_CONTACT_KEY: ""},
        }

    # Check if API contact is configured
    def _check_api_contact_configured(self):
        """Check if API contact is configured and prompt user if not."""
        api_settings = self.config.get("api_settings", {})
        api_contact = api_settings.get(API_CONTACT_KEY, "")
        if not api_contact:
            logging.warning("API contact email is not configured.")
            try:
                # Use wx.CallAfter to ensure the dialog runs in the main UI thread
                # This helps prevent issues in tests or complex UI scenarios
                wx.CallAfter(self._show_api_contact_dialog)
            except Exception as e:
                logging.error(f"Error scheduling API contact dialog: {e}")

    def _show_api_contact_dialog(self):
        # This method contains the actual dialog creation and showing
        # It's called via wx.CallAfter to ensure it runs safely in the main thread
        try:
            dlg = wx.MessageDialog(
                self,
                "The National Weather Service API requires a contact email for identification. "
                "This helps them contact you if your application causes issues. "
                "Would you like to add your email now in the settings?",
                "Configure API Contact",
                wx.YES_NO | wx.ICON_QUESTION,
            )
            response = dlg.ShowModal()
            dlg.Destroy()
            if response == wx.ID_YES:
                self.OnSettings(None) # Open settings dialog
        except RuntimeError as e:
            # Catch potential errors if the dialog can't be shown (e.g., tests)
            logging.error(f"Could not show API contact dialog: {e}")

    # Event Handlers
    def OnClose(self, event):
        # Handle window close event
        logging.info("Application closing.")
        self.timer.Stop()
        # Save config before destroying?
        # self.SaveConfig()
        self.Destroy()

    def OnUpdateTimer(self, event):
        """Handle the update timer event."""
        self.UpdateWeatherData()

    def StartUpdateTimer(self):
        """Start the update timer based on config."""
        update_interval_sec = self.config.get("settings", {}).get(UPDATE_INTERVAL_KEY, 30)
        update_interval_ms = update_interval_sec * 1000
        if not self.timer.IsRunning():
            logger.info(f"Starting update timer with interval {update_interval_sec} seconds")
            self.timer.Start(update_interval_ms)

    def StopUpdateTimer(self):
        """Stop the update timer."""
        if self.timer.IsRunning():
            self.timer.Stop()

    # --- Location Data Management ---
    def LoadLocations(self):
        """Load locations dictionary from config."""
        self.locations = self.config.get("locations", {})
        logging.info(f"Loaded {len(self.locations)} locations from config.")

    def SaveLocations(self):
        """Save locations dictionary to config."""
        self.config["locations"] = self.locations
        self._save_config()

    def LoadCurrentLocation(self):
        """Load the name of the current location from config."""
        self.current_location_name = self.config.get("current", None)
        if self.current_location_name:
             logging.info(f"Loaded current location: {self.current_location_name}")
        else:
             logging.info("No current location set in config.")

    def SaveCurrentLocation(self):
        """Save the name of the current location to config."""
        self.config["current"] = self.current_location_name
        self._save_config()

    def _save_config(self):
        """Save the current configuration dictionary to the file."""
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, "w") as f:
                json.dump(self.config, f, indent=4)
            logging.info(f"Configuration saved to {self._config_path}")
        except Exception as e:
            logging.error(f"Failed to save config: {str(e)}")
    # --- End Location Data Management ---

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

        # Nationwide logic
        if self.location_service.is_nationwide_location(name):
            try:
                forecast_data = self.weather_service.get_national_forecast_data()
                # Add a label for accessibility and clarity
                if isinstance(forecast_data, dict):
                    forecast_data = dict(forecast_data)  # Ensure mutable
                    forecast_data['properties'] = forecast_data.get('properties', {})
                    forecast_data['properties']['title'] = 'National Forecast'
                self._on_forecast_fetched(forecast_data)
                self._forecast_complete = True
                self._alerts_complete = True  # No alerts for nationwide
                self.SetStatusText("National forecast loaded.")
                self.refresh_btn.Enable()
                return
            except Exception as e:
                self._on_forecast_error(str(e))
                self._forecast_complete = True
                self._alerts_complete = True
                self.refresh_btn.Enable()
                return

        # Start forecast fetching thread for regular locations
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
        # Save forecast data
        self.current_forecast = forecast_data

        # Update display
        self.ui_manager._UpdateForecastDisplay(forecast_data)  # Use UIManager

        # Update timestamp
        self.last_update = time.time()

        # Mark forecast as complete and check overall completion
        self._forecast_complete = True
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

        # Notify testing framework if hook is set
        if self._testing_forecast_error_callback:
            self._testing_forecast_error_callback(error)

    def _on_alerts_fetched(self, alerts_data):
        """Handle the fetched alerts in the main thread

        Args:
            alerts_data: Dictionary with alerts data
        """
        # Process alerts using the notification service
        processed_alerts = self.notification_service.process_alerts(alerts_data)
        self.current_alerts = processed_alerts

        # Update display
        self.ui_manager._UpdateAlertsDisplay(alerts_data)

        # Notify user of alerts if any
        if self.current_alerts:
            self.notification_service.notify_alerts(self.current_alerts)

        # Update timestamp
        self.last_update = time.time()

        # Mark alerts as complete and check overall completion
        self._alerts_complete = True
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
        self.alerts_list.DeleteAllItems()
        self.alerts_list.InsertItem(0, "Error")
        self.alerts_list.SetItem(0, 1, f"Error fetching alerts: {error}")

        # Mark alerts as complete and check overall completion
        self._alerts_complete = True
        self._check_update_complete()

        # Notify testing framework if hook is set
        if self._testing_alerts_error_callback:
            self._testing_alerts_error_callback(error)

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

        # Use default text if none provided
        if not discussion_text:
            discussion_text = "No discussion available"

        # Create title with location name if provided
        title = f"Forecast Discussion for {name}" if name else "Weather Discussion"

        # Show discussion dialog
        logger.debug("Creating and showing discussion dialog")
        dialog = WeatherDiscussionDialog(self, title, discussion_text)
        # Attempt to show the dialog; catch initialization errors (e.g., in tests)
        try:
            dialog.ShowModal()
            dialog.Destroy()
            logger.debug("Discussion dialog closed")
        except RuntimeError as e:
            logger.warning(f"Skipping ShowModal/Destroy due to runtime error: {e}")

        # Re-enable button if it exists
        if hasattr(self, "discussion_btn") and self.discussion_btn:
            self.discussion_btn.Enable()

        # Notify testing framework if hook is set
        if self._testing_discussion_callback:
            self._testing_discussion_callback(discussion_text)

    def _cleanup_discussion_loading(self, loading_dialog=None):
        """Clean up the discussion loading dialog and timer

        Args:
            loading_dialog: Progress dialog instance passed from the callback (optional)
        """
        logger.debug("Cleaning up discussion loading resources")

        # --- Timer Cleanup ---
        if hasattr(self, "_discussion_timer"):
            timer = self._discussion_timer
            if timer.IsRunning():
                logger.debug("Stopping discussion timer")
                timer.Stop()
            # Always try to unbind to prevent issues if Stop() failed or wasn't needed
            try:
                # Make sure the handler reference is correct
                handler_method = getattr(self, "_on_discussion_timer", None)
                if handler_method:
                    self.Unbind(wx.EVT_TIMER, handler=handler_method, source=timer)
                    logger.debug("Unbound timer event")
                else:
                    logger.warning("Could not find _on_discussion_timer method to unbind")
            except Exception as e:
                # Log error but continue cleanup
                logger.error(f"Error unbinding timer event: {e}", exc_info=True)
            # Remove timer reference (optional, but good practice)
            # del self._discussion_timer

        # --- Dialog Cleanup ---
        # Primarily use the dialog passed via the callback
        dialog_to_close = loading_dialog

        # Fallback: If no dialog was passed, try the instance variable
        if not dialog_to_close and hasattr(self, "_discussion_loading_dialog"):
            dialog_to_close = self._discussion_loading_dialog
            logger.debug("Using instance variable for loading dialog cleanup")

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

        # --- Clear Reference ---
        # Always clear the instance variable after attempting cleanup
        if hasattr(self, "_discussion_loading_dialog"):
            logger.debug("Clearing discussion loading dialog reference")
            self._discussion_loading_dialog = None

        # --- Force UI Update ---
        # Process pending events more thoroughly
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
