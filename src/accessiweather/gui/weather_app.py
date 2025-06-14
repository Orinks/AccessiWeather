"""Main application window for AccessiWeather

This module provides the main application window and integrates all components
using the service layer for business logic.
"""

import logging
import os

import wx

from accessiweather.config_utils import get_config_dir

from .app_initialization import AppInitializer
from .callback_handlers import CallbackHandlers
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
from .menu_factory import MenuFactory
from .settings_dialog import UPDATE_INTERVAL_KEY
from .testing_utilities import TestingUtilities
from .timer_manager import TimerManager

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

        # Debug mode
        self.debug_mode = debug_mode
        # For backward compatibility, debug_alerts is now the same as debug_mode
        self.debug_alerts = debug_mode

        # Always log debug mode status
        logger.info(f"Debug mode status: debug_mode={self.debug_mode}")

        if self.debug_mode:
            logger.info("Debug mode enabled for additional debug information and alert testing")

        # Initialize the app initializer and use it to set up the application
        self.app_initializer = AppInitializer(self)

        # Load or use provided config
        self.config = (
            config if config is not None else self.app_initializer.load_config(self._config_path)
        )

        # Initialize services
        self.app_initializer.initialize_services(
            weather_service, location_service, notification_service, api_client
        )

        # Initialize fetchers
        self.app_initializer.initialize_fetchers()

        # Initialize state variables
        self.app_initializer.initialize_state_variables()

        # Initialize UI manager
        self.app_initializer.initialize_ui_manager()

        # Set up status bar
        self.app_initializer.setup_status_bar(self.debug_mode)

        # Set up timer
        self.app_initializer.setup_timer()

        # Set up event bindings
        self.app_initializer.setup_event_bindings()

        # Set up system tray
        self.app_initializer.setup_system_tray()

        # Set up accessibility
        self.app_initializer.setup_accessibility()

        # Set up testing hooks
        self.app_initializer.setup_testing_hooks()

        # Initialize extracted modules
        self.callback_handlers = CallbackHandlers(self)
        self.timer_manager = TimerManager(self)
        self.menu_factory = MenuFactory(self)
        self.testing_utilities = TestingUtilities(self)

        # Create menu bar using menu factory
        self.menu_factory.create_menu_bar()

        # Initialize update service
        self.app_initializer.initialize_update_service(self._config_path)

        # Finalize initialization
        self.app_initializer.finalize_initialization()

    def _init_update_service_manually(self):
        """Manually initialize the update service since multiple inheritance doesn't call handler __init__."""
        try:
            # Get config directory from the config path
            import os

            from accessiweather.services.update_service import UpdateService

            config_dir = os.path.dirname(self._config_path)

            # Initialize update service
            self.update_service = UpdateService(
                config_dir=config_dir,
                notification_callback=self._on_update_available,
                progress_callback=self._on_update_progress,
            )

            # Load settings and start background checking if enabled
            self._load_update_settings()

            logger.info("Update service initialized manually")

        except Exception as e:
            logger.error(f"Failed to initialize update service manually: {e}")
            self.update_service = None

    def _on_update_available(self, update_info):
        """Handle update available notification - delegate to update handlers."""
        from .handlers.update_handlers import WeatherAppUpdateHandlers

        WeatherAppUpdateHandlers._on_update_available(self, update_info)

    def _on_update_progress(self, progress):
        """Handle update progress - delegate to update handlers."""
        from .handlers.update_handlers import WeatherAppUpdateHandlers

        WeatherAppUpdateHandlers._on_update_progress(self, progress)

    def _load_update_settings(self):
        """Load update settings - delegate to update handlers."""
        from .handlers.update_handlers import WeatherAppUpdateHandlers

        WeatherAppUpdateHandlers._load_update_settings(self)

    # UpdateLocationDropdown is now implemented in WeatherAppLocationHandlers
    # UpdateWeatherData, UpdateAlerts, _FetchWeatherData, and _check_update_complete
    # are now implemented in WeatherAppRefreshHandlers
    # OnClose, OnMinimize, and _stop_fetcher_threads are now implemented in WeatherAppSystemHandlers

    def _on_national_forecast_fetched(self, forecast_data):
        """Handle the fetched national forecast in the main thread

        Args:
            forecast_data: Dictionary with national forecast data
        """
        self.callback_handlers.on_national_forecast_fetched(forecast_data)

    def _on_current_conditions_fetched(self, conditions_data):
        """Handle the fetched current conditions in the main thread

        Args:
            conditions_data: Dictionary with current conditions data
        """
        self.callback_handlers.on_current_conditions_fetched(conditions_data)

    def _on_current_conditions_error(self, error):
        """Handle current conditions fetch error

        Args:
            error: Error message
        """
        self.callback_handlers.on_current_conditions_error(error)

    def _on_hourly_forecast_fetched(self, hourly_forecast_data):
        """Handle the fetched hourly forecast in the main thread

        Args:
            hourly_forecast_data: Dictionary with hourly forecast data
        """
        self.callback_handlers.on_hourly_forecast_fetched(hourly_forecast_data)

    def _on_forecast_fetched(self, forecast_data):
        """Handle the fetched forecast in the main thread

        Args:
            forecast_data: Dictionary with forecast data
        """
        self.callback_handlers.on_forecast_fetched(forecast_data)

    def _on_forecast_error(self, error):
        """Handle forecast fetch error

        Args:
            error: Error message
        """
        self.callback_handlers.on_forecast_error(error)

    def _on_alerts_fetched(self, alerts_data):
        """Handle the fetched alerts in the main thread

        Args:
            alerts_data: Dictionary with alerts data
        """
        self.callback_handlers.on_alerts_fetched(alerts_data)

    def _on_alerts_error(self, error):
        """Handle alerts fetch error

        Args:
            error: Error message
        """
        self.callback_handlers.on_alerts_error(error)

    def _on_discussion_fetched(self, discussion_text, name, loading_dialog):
        """Handle the fetched discussion in the main thread

        Args:
            discussion_text: The discussion text
            name: Location name
            loading_dialog: Progress dialog to close
        """
        self.callback_handlers.on_discussion_fetched(discussion_text, name, loading_dialog)

    def _on_discussion_error(self, error_message, name, loading_dialog):
        """Handle discussion fetch error in the main thread

        Args:
            error_message: Error message
            name: Location name
            loading_dialog: Progress dialog to close
        """
        self.callback_handlers.on_discussion_error(error_message, name, loading_dialog)

    def OnTimer(self, event):  # event is required by wx
        """Handle timer event for periodic updates

        Args:
            event: Timer event
        """
        self.timer_manager.on_timer(event)

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
        self.testing_utilities.test_alert_update()

    def OnAbout(self, event):  # event is required by wx
        """Show the about dialog.

        Args:
            event: Menu event
        """
        self.menu_factory.on_about(event)

    def verify_update_interval(self):
        """Verify the unified update interval by logging detailed information.

        This method is only available in debug mode.
        """
        self.testing_utilities.verify_update_interval()
