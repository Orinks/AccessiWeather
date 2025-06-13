"""Main application window for AccessiWeather

This module provides the main application window and integrates all components
using the service layer for business logic.
"""

import json
import logging
import os
import time

import wx
import wx.adv

from accessiweather.config_utils import get_config_dir
from accessiweather.national_forecast_fetcher import NationalForecastFetcher
from accessiweather.version import __version__

from .async_fetchers import AlertsFetcher, DiscussionFetcher, ForecastFetcher
from .current_conditions_fetcher import CurrentConditionsFetcher
from .handlers import (
    WeatherAppAlertHandlers,
    WeatherAppBaseHandlers,
    WeatherAppConfigHandlers,
    WeatherAppDebugHandlers,
    WeatherAppDialogHandlers,
    WeatherAppDiscussionHandlers,
    WeatherAppLocationHandlers,
    WeatherAppMenuHandlers,
    WeatherAppRefreshHandlers,
    WeatherAppSettingsHandlers,
    WeatherAppSystemHandlers,
    WeatherAppTimerHandlers,
    WeatherAppUpdateHandlers,
)
from .hourly_forecast_fetcher import HourlyForecastFetcher
from .settings_dialog import (
    ALERT_RADIUS_KEY,
    DEFAULT_TEMPERATURE_UNIT,
    MINIMIZE_TO_TRAY_KEY,
    PRECISE_LOCATION_ALERTS_KEY,
    TEMPERATURE_UNIT_KEY,
    UPDATE_INTERVAL_KEY,
)
from .system_tray import TaskBarIcon
from .ui_manager import UIManager

logger = logging.getLogger(__name__)

# Constants
CONFIG_DIR = get_config_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


class WeatherApp(
    wx.Frame,
    WeatherAppBaseHandlers,
    WeatherAppLocationHandlers,
    WeatherAppAlertHandlers,
    WeatherAppDebugHandlers,
    WeatherAppDialogHandlers,
    WeatherAppDiscussionHandlers,
    WeatherAppMenuHandlers,
    WeatherAppRefreshHandlers,
    WeatherAppSettingsHandlers,
    WeatherAppSystemHandlers,
    WeatherAppTimerHandlers,
    WeatherAppConfigHandlers,
    WeatherAppUpdateHandlers,
):
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
        debug_mode=False,
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
            debug_mode: Whether to enable debug mode with additional logging and alert testing features (default: False)
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

        # Debug mode
        self.debug_mode = debug_mode
        # For backward compatibility, debug_alerts is now the same as debug_mode
        self.debug_alerts = debug_mode

        # Always log debug mode status
        logger.info(f"Debug mode status: debug_mode={self.debug_mode}")

        if self.debug_mode:
            logger.info("Debug mode enabled for additional debug information and alert testing")

        # Validate required services
        if not all([self.weather_service, self.location_service, self.notification_service]):
            raise ValueError(
                "Required services (weather_service, location_service, notification_service) "
                "must be provided"
            )

        # Initialize async fetchers (always using the weather service)
        # This ensures that the WeatherService's logic for choosing between NWS and WeatherAPI is used
        self.forecast_fetcher = ForecastFetcher(self.weather_service)
        self.alerts_fetcher = AlertsFetcher(self.weather_service)
        self.discussion_fetcher = DiscussionFetcher(self.weather_service)
        self.current_conditions_fetcher = CurrentConditionsFetcher(self.weather_service)
        self.hourly_forecast_fetcher = HourlyForecastFetcher(self.weather_service)
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
        if self.debug_mode:
            # Use the debug status bar in debug mode
            from .debug_status_bar import DebugStatusBar

            self.status_bar = DebugStatusBar(self, UPDATE_INTERVAL_KEY)
            self.SetStatusBar(self.status_bar)
        else:
            # Use the standard status bar
            self.CreateStatusBar()

        self.SetStatusText("Ready")

        # Start update timer
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        # Bind Close event here as it's frame-level, not UI-element specific
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_ICONIZE, self.OnMinimize)

        # Bind character hook for global keyboard shortcuts
        self.Bind(wx.EVT_CHAR_HOOK, self.OnCharHook)

        # Log the update interval from config
        update_interval = self.config.get("settings", {}).get(UPDATE_INTERVAL_KEY, 10)
        logger.debug(f"Starting timer with update interval: {update_interval} minutes")

        self.timer.Start(1000)  # Check every 1 second for updates

        # Last update timestamp
        self.last_update: float = 0.0

        # Create system tray icon - cleanup any existing instance first
        TaskBarIcon.cleanup_existing_instance()
        self.taskbar_icon = TaskBarIcon(self)

        # Register with accessibility system
        self.SetName("AccessiWeather")
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName("AccessiWeather")
            accessible.SetRole(wx.ACC_ROLE_WINDOW)

        # Create menu bar
        self._create_menu_bar()

        # Test hooks for async tests
        self._testing_forecast_callback = None
        self._testing_forecast_error_callback = None
        self._testing_alerts_callback = None
        self._testing_alerts_error_callback = None
        self._testing_discussion_callback = None
        self._testing_discussion_error_callback = None

        # Initialize UI with location data
        self.UpdateLocationDropdown()

        # Update UI elements based on initial weather source (show/hide Open-Meteo incompatible elements)
        if hasattr(self, "ui_manager") and self.ui_manager:
            self.ui_manager.update_ui_for_location_change()

        self.UpdateWeatherData()

        # Add force close flag
        self._force_close = True  # Default to force close when clicking X

    def _load_config(self):
        """Load configuration from file

        Returns:
            Dict containing configuration or empty dict if not found
        """
        from accessiweather.config_utils import ensure_config_defaults
        from accessiweather.gui.settings_dialog import (
            API_KEYS_SECTION,
            DATA_SOURCE_KEY,
            DEFAULT_DATA_SOURCE,
        )

        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, "r") as f:
                    config = json.load(f)
                    # Ensure config has all required defaults
                    updated_config = ensure_config_defaults(config)
                    return updated_config
            except Exception as e:
                logger.error(f"Failed to load config: {str(e)}")

        # Return default config structure
        return {
            "locations": {},
            "current": None,
            "settings": {
                UPDATE_INTERVAL_KEY: 10,
                ALERT_RADIUS_KEY: 25,
                PRECISE_LOCATION_ALERTS_KEY: True,  # Default to precise location alerts
                MINIMIZE_TO_TRAY_KEY: True,  # Default to minimize to tray when closing
                DATA_SOURCE_KEY: DEFAULT_DATA_SOURCE,  # Default to NWS
                TEMPERATURE_UNIT_KEY: DEFAULT_TEMPERATURE_UNIT,  # Default to Fahrenheit
            },
            "api_settings": {},  # Default empty API settings
            API_KEYS_SECTION: {},  # Default empty API keys
        }

    # UpdateLocationDropdown is now implemented in WeatherAppLocationHandlers

    # UpdateWeatherData, UpdateAlerts, _FetchWeatherData, and _check_update_complete
    # are now implemented in WeatherAppRefreshHandlers

    # OnClose, OnMinimize, and _stop_fetcher_threads are now implemented in WeatherAppSystemHandlers

    def _on_national_forecast_fetched(self, forecast_data):
        """Handle the fetched national forecast in the main thread

        Args:
            forecast_data: Dictionary with national forecast data
        """
        logger.debug("National forecast fetch callback received data")
        # Save forecast data
        self.current_forecast = forecast_data

        # Extract and store full discussions for WPC and SPC
        try:
            summaries = forecast_data.get("national_discussion_summaries", {})
            wpc_data = summaries.get("wpc", {})
            spc_data = summaries.get("spc", {})

            # Store full discussions from scraper data
            self._nationwide_wpc_full = wpc_data.get("full")
            self._nationwide_spc_full = spc_data.get("full")

            wpc_len = len(self._nationwide_wpc_full) if self._nationwide_wpc_full else 0
            spc_len = len(self._nationwide_spc_full) if self._nationwide_spc_full else 0
            logger.debug(f"Stored WPC discussion (length: {wpc_len})")
            logger.debug(f"Stored SPC discussion (length: {spc_len})")
        except Exception as e:
            logger.error(f"Error extracting national discussions: {e}")
            self._nationwide_wpc_full = None
            self._nationwide_spc_full = None

        # Update the UI
        self.ui_manager.display_forecast(forecast_data)

        # Update timestamp
        self.last_update = time.time()

        # Mark both forecast and alerts as complete for nationwide view
        self._forecast_complete = True
        self._alerts_complete = True  # No alerts for nationwide view

        # Check overall completion
        self._check_update_complete()

        # Notify testing framework if hook is set
        if self._testing_forecast_callback:
            self._testing_forecast_callback(forecast_data)

    def _on_current_conditions_fetched(self, conditions_data):
        """Handle the fetched current conditions in the main thread

        Args:
            conditions_data: Dictionary with current conditions data
        """
        logger.debug("_on_current_conditions_fetched received data")

        # Update the UI
        self.ui_manager.display_current_conditions(conditions_data)

    def _on_current_conditions_error(self, error):
        """Handle current conditions fetch error

        Args:
            error: Error message
        """
        logger.error(f"Current conditions fetch error: {error}")

        # Update the UI - use ui_manager to ensure proper error handling
        try:
            self.ui_manager.display_forecast_error(error)
        except Exception as e:
            logger.error(f"Error updating UI with current conditions error: {e}")

    def _on_hourly_forecast_fetched(self, hourly_forecast_data):
        """Handle the fetched hourly forecast in the main thread

        Args:
            hourly_forecast_data: Dictionary with hourly forecast data
        """
        logger.debug("_on_hourly_forecast_fetched received data")

        # Store the hourly forecast data to be used when displaying the regular forecast
        self.hourly_forecast_data = hourly_forecast_data

        # If we already have the regular forecast data, update the display
        if hasattr(self, "current_forecast") and self.current_forecast:
            self.ui_manager.display_forecast(self.current_forecast, hourly_forecast_data)

    def _on_forecast_fetched(self, forecast_data):
        """Handle the fetched forecast in the main thread

        Args:
            forecast_data: Dictionary with forecast data
        """
        logger.debug("_on_forecast_fetched received data")
        # Save forecast data
        self.current_forecast = forecast_data

        # Update the UI with both forecast and hourly forecast if available
        hourly_data = getattr(self, "hourly_forecast_data", None)
        self.ui_manager.display_forecast(forecast_data, hourly_data)

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

        # Update the UI
        self.ui_manager.display_forecast_error(error)

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
        logger.debug("Alerts fetched successfully, handling in main thread")

        # Process alerts through notification service
        # The notification service will handle notifications for new/updated alerts
        # Unpack all three return values from process_alerts
        processed_alerts, new_count, updated_count = self.notification_service.process_alerts(
            alerts_data
        )

        # Log notification status
        logger.info(
            f"Alert processing complete: {len(processed_alerts)} total, {new_count} new, {updated_count} updated"
        )

        # Save processed alerts
        self.current_alerts = processed_alerts

        # Update the UI with the processed alerts
        self.ui_manager.display_alerts_processed(processed_alerts)

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

        # Update the UI
        self.ui_manager.display_alerts_error(error)

        # Mark alerts as complete and check overall completion
        self._alerts_complete = True

        self._check_update_complete()

        # Notify testing framework if hook is set
        if self._testing_alerts_error_callback:
            self._testing_alerts_error_callback(error)

    def _on_discussion_fetched(self, discussion_text, name, loading_dialog):
        """Handle the fetched discussion in the main thread

        Args:
            discussion_text: The discussion text
            name: Location name
            loading_dialog: Progress dialog to close
        """
        logger.debug(f"Discussion fetch callback received for {name}")

        # Clean up loading state
        self._cleanup_discussion_loading(loading_dialog)

        # Re-enable discussion button
        if hasattr(self, "discussion_btn") and self.discussion_btn:
            self.discussion_btn.Enable()

        # Show discussion dialog
        if discussion_text:
            title = f"Forecast Discussion for {name}"
            self.ShowWeatherDiscussionDialog(title, discussion_text)
        else:
            self.ShowMessageDialog(
                f"No forecast discussion available for {name}",
                "No Discussion Available",
                wx.OK | wx.ICON_INFORMATION,
            )

    def _on_discussion_error(self, error_message, name, loading_dialog):
        """Handle discussion fetch error in the main thread

        Args:
            error_message: Error message
            name: Location name
            loading_dialog: Progress dialog to close
        """
        logger.error(f"Discussion fetch error for {name}: {error_message}")

        # Clean up loading state
        self._cleanup_discussion_loading(loading_dialog)

        # Re-enable discussion button
        if hasattr(self, "discussion_btn") and self.discussion_btn:
            self.discussion_btn.Enable()

        # Show error message
        self.ShowMessageDialog(
            f"Error fetching forecast discussion for {name}: {error_message}",
            "Discussion Error",
            wx.OK | wx.ICON_ERROR,
        )

    def _cleanup_discussion_loading(self, loading_dialog=None):
        """Clean up resources related to discussion loading

        Args:
            loading_dialog: Progress dialog instance (optional)
        """
        timer_id = None

        try:
            # --- Stop Timer --- (if applicable)
            if hasattr(self, "_discussion_timer") and self._discussion_timer:
                logger.debug("Stopping discussion timer")
                try:
                    # Store timer ID before stopping for unbinding
                    if hasattr(self._discussion_timer, "GetId"):
                        timer_id = self._discussion_timer.GetId()

                    # Stop the timer if it's running
                    if self._discussion_timer.IsRunning():
                        self._discussion_timer.Stop()
                except Exception as timer_e:
                    logger.error(f"Error stopping discussion timer: {timer_e}", exc_info=True)

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
                            logger.debug(
                                "Dialog likely already destroyed."
                            )  # Expected if already gone
                        except Exception as destroy_e:
                            logger.error(
                                f"Error destroying hidden/non-window dialog: {destroy_e}",
                                exc_info=True,
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
        finally:
            # --- Always unbind the timer event to prevent memory leaks ---
            try:
                if hasattr(self, "_discussion_timer") and self._discussion_timer:
                    # Try to unbind using the handler and source
                    try:
                        self.Unbind(
                            wx.EVT_TIMER,
                            handler=self._on_discussion_timer,
                            source=self._discussion_timer,
                        )
                        logger.debug("Unbound discussion timer event using handler and source")
                    except Exception as unbind_e:
                        logger.debug(f"Could not unbind timer with handler and source: {unbind_e}")

                        # Fall back to unbinding by ID if we have it
                        if timer_id is not None:
                            try:
                                self.Unbind(wx.EVT_TIMER, id=timer_id)
                                logger.debug(f"Unbound discussion timer event using ID: {timer_id}")
                            except Exception as id_unbind_e:
                                logger.error(
                                    f"Error unbinding timer event by ID: {id_unbind_e}",
                                    exc_info=True,
                                )
            except Exception as unbind_e:
                logger.error(f"Error during timer unbinding: {unbind_e}", exc_info=True)

            # --- Always clear references ---
            try:
                # Clear timer reference
                if hasattr(self, "_discussion_timer"):
                    self._discussion_timer = None

                # Clear dialog reference
                if hasattr(self, "_discussion_loading_dialog"):
                    logger.debug("Clearing discussion loading dialog reference")
                    self._discussion_loading_dialog = None

                # --- Force UI Update ---
                logger.debug("Processing pending events after cleanup")
                wx.GetApp().ProcessPendingEvents()
                wx.SafeYield()
            except Exception as cleanup_e:
                logger.error(f"Error during final cleanup: {cleanup_e}", exc_info=True)

            logger.debug("Discussion timer cleanup complete")

    def OnTimer(self, event):  # event is required by wx
        """Handle timer event for periodic updates

        Args:
            event: Timer event
        """
        # Get update interval from config (default to 10 minutes)
        settings = self.config.get("settings", {})
        update_interval_minutes = settings.get(UPDATE_INTERVAL_KEY, 10)
        update_interval_seconds = update_interval_minutes * 60

        # Calculate time since last update
        now = time.time()
        time_since_last_update = now - self.last_update
        next_update_in = update_interval_seconds - time_since_last_update

        # Enhanced logging in debug mode
        if self.debug_mode:
            logger.info(
                f"[DEBUG] Timer check: interval={update_interval_minutes}min, "
                f"time_since_last={time_since_last_update:.1f}s, "
                f"next_update_in={next_update_in:.1f}s"
            )
        else:
            # Regular debug logging
            logger.debug(
                f"Timer check: interval={update_interval_minutes}min, "
                f"time_since_last={time_since_last_update:.1f}s, "
                f"next_update_in={next_update_in:.1f}s"
            )

        # Check if it's time to update
        if time_since_last_update >= update_interval_seconds:
            if not self.updating:
                logger.info(
                    f"Timer triggered weather update. "
                    f"Interval: {update_interval_minutes} minutes, "
                    f"Time since last update: {time_since_last_update:.1f} seconds"
                )
                self.UpdateWeatherData()
            else:
                logger.debug("Timer skipped update: already updating.")

    # For backward compatibility with WeatherAppHandlers
    @property
    def location_manager(self):
        """Provide backward compatibility with the location_manager property."""
        return self.location_service.location_manager

    @property
    def notifier(self):
        """Provide backward compatibility with the notifier property."""
        return self.notification_service.notifier

    def _handle_data_source_change(self):
        """Handle changes to the data source or API settings.

        This method is called when the data source or API settings are changed
        in the settings dialog. It reinitializes the WeatherService with the new
        settings and updates the fetchers to use the new service.
        """
        from accessiweather.api_wrapper import NoaaApiWrapper
        from accessiweather.services.weather_service import WeatherService

        logger.info("Reinitializing WeatherService due to data source or API key change")

        # Log the current settings
        from accessiweather.gui.settings_dialog import DATA_SOURCE_KEY

        data_source = self.config.get("settings", {}).get(DATA_SOURCE_KEY, "nws")
        logger.info(f"Current data source: {data_source}")
        logger.info(f"Full config: {self.config}")

        # Create the NWS API client (always needed)
        nws_client = NoaaApiWrapper(
            user_agent="AccessiWeather",
            enable_caching=True,  # Default to enabled
            cache_ttl=300,  # Default to 5 minutes
        )

        # Create the Open-Meteo API client
        from accessiweather.openmeteo_client import OpenMeteoApiClient

        openmeteo_client = OpenMeteoApiClient(user_agent="AccessiWeather")

        # Create the new WeatherService
        self.weather_service = WeatherService(
            nws_client=nws_client, openmeteo_client=openmeteo_client, config=self.config
        )

        # Update the location service with the new data source
        self.location_service.update_data_source(data_source)

        # Update the fetchers to use the new service
        self.forecast_fetcher.service = self.weather_service
        self.alerts_fetcher.service = self.weather_service
        self.discussion_fetcher.service = self.weather_service
        self.current_conditions_fetcher.service = self.weather_service
        self.hourly_forecast_fetcher.service = self.weather_service
        self.national_forecast_fetcher.service = self.weather_service

        # For backward compatibility
        self.api_client = nws_client

        # Update UI elements based on new weather source (show/hide Open-Meteo incompatible elements)
        if hasattr(self, "ui_manager") and self.ui_manager:
            self.ui_manager.update_ui_for_location_change()

        # Refresh weather data to apply new settings
        self.UpdateWeatherData()

    def OnCharHook(self, event):
        """Handle character hook events for global keyboard shortcuts.

        This is a higher-level event handler that will catch keyboard events
        before they reach individual controls.

        Args:
            event: Character hook event
        """
        key_code = event.GetKeyCode()

        if key_code == wx.WXK_ESCAPE:
            # Escape key to minimize to system tray
            logger.info("Escape key pressed in CharHook, hiding to system tray")
            if hasattr(self, "taskbar_icon") and self.taskbar_icon:
                logger.info("Hiding app to system tray from CharHook")
                self.Hide()
                return  # Don't skip the event - we've handled it

        # For all other keys, allow normal processing
        event.Skip()

    def test_alert_update(self):
        """Manually trigger an alert update for testing purposes.

        This method is only available in debug mode.
        """
        if not self.debug_mode:
            logger.warning("test_alert_update called but debug mode is not enabled")
            return

        logger.info("[DEBUG] Manually triggering alert update")

        # Get current location
        location = self.location_service.get_current_location()
        if not location:
            logger.error("[DEBUG ALERTS] No location selected for alert testing")
            return

        # Extract coordinates
        _, lat, lon = location

        # Get alert settings from config
        settings = self.config.get("settings", {})
        precise_location = settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
        alert_radius = settings.get(ALERT_RADIUS_KEY, 25)

        # Log the alert fetch parameters
        logger.info(
            f"[DEBUG ALERTS] Fetching alerts for coordinates ({lat}, {lon}), "
            f"precise_location={precise_location}, radius={alert_radius}"
        )

        # Start alerts fetching thread
        self.alerts_fetcher.fetch(
            lat,
            lon,
            on_success=self._on_alerts_fetched,
            on_error=self._on_alerts_error,
            precise_location=precise_location,
            radius=alert_radius,
        )

    def _create_menu_bar(self):
        """Create the menu bar for the application.

        This method creates a menu bar with File and Help menus.
        If debug_mode or debug_alerts is enabled, it also adds a Debug menu.
        """
        # Create menu bar
        menu_bar = wx.MenuBar()

        # Create File menu
        file_menu = wx.Menu()
        refresh_item = file_menu.Append(wx.ID_REFRESH, "&Refresh\tF5", "Refresh weather data")
        file_menu.AppendSeparator()
        settings_item = file_menu.Append(wx.ID_PREFERENCES, "&Settings...", "Open settings dialog")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "E&xit", "Exit the application")

        # Add File menu to menu bar
        menu_bar.Append(file_menu, "&File")

        # Add Debug menu if debug_mode is enabled
        if self.debug_mode:
            debug_menu = self.CreateDebugMenu()
            menu_bar.Append(debug_menu, "&Debug")

        # Create Help menu
        help_menu = wx.Menu()
        check_updates_item = help_menu.Append(
            wx.ID_ANY, "Check for &Updates...", "Check for application updates"
        )
        help_menu.AppendSeparator()
        about_item = help_menu.Append(wx.ID_ABOUT, "&About", "About AccessiWeather")

        # Add Help menu to menu bar
        menu_bar.Append(help_menu, "&Help")

        # Set the menu bar
        self.SetMenuBar(menu_bar)

        # Bind events
        self.Bind(wx.EVT_MENU, self.OnRefresh, refresh_item)
        self.Bind(wx.EVT_MENU, self.OnSettings, settings_item)
        self.Bind(wx.EVT_MENU, lambda e: self.Close(True), exit_item)
        self.Bind(wx.EVT_MENU, self.OnCheckForUpdates, check_updates_item)
        self.Bind(wx.EVT_MENU, self.OnAbout, about_item)

    def OnAbout(self, event):  # event is required by wx
        """Show the about dialog.

        Args:
            event: Menu event
        """
        info = wx.adv.AboutDialogInfo()
        info.SetName("AccessiWeather")
        info.SetVersion(__version__)
        info.SetDescription("An accessible weather application using NOAA data")
        info.SetCopyright("(C) 2023")
        info.SetWebSite("https://github.com/Orinks/AccessiWeather")

        wx.adv.AboutBox(info)

    def verify_update_interval(self):
        """Verify the unified update interval by logging detailed information.

        This method is only available in debug mode.
        """
        if not self.debug_mode:
            logger.warning("verify_update_interval called but debug mode is not enabled")
            return

        # Get update interval from config
        settings = self.config.get("settings", {})
        update_interval_minutes = settings.get(UPDATE_INTERVAL_KEY, 10)
        update_interval_seconds = update_interval_minutes * 60

        # Calculate time since last update
        now = time.time()
        time_since_last_update = now - self.last_update
        next_update_in = update_interval_seconds - time_since_last_update

        # Log detailed information
        logger.info(
            f"[DEBUG] Update interval verification:\n"
            f"  - Configured interval: {update_interval_minutes} minutes ({update_interval_seconds} seconds)\n"
            f"  - Last update timestamp: {self.last_update} ({time.ctime(self.last_update)})\n"
            f"  - Current timestamp: {now} ({time.ctime(now)})\n"
            f"  - Time since last update: {time_since_last_update:.1f} seconds\n"
            f"  - Next update in: {next_update_in:.1f} seconds\n"
            f"  - Update due: {'Yes' if time_since_last_update >= update_interval_seconds else 'No'}"
        )
