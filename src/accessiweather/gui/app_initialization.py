"""Application initialization module for AccessiWeather.

This module handles the complex initialization logic for the WeatherApp,
including service setup, fetcher initialization, UI setup, and system tray creation.
"""

import json
import logging
import os

import wx

from accessiweather.config_utils import get_config_dir
from accessiweather.national_forecast_fetcher import NationalForecastFetcher

from .async_fetchers import AlertsFetcher, DiscussionFetcher, ForecastFetcher
from .current_conditions_fetcher import CurrentConditionsFetcher
from .hourly_forecast_fetcher import HourlyForecastFetcher
from .settings_dialog import (
    ALERT_RADIUS_KEY,
    API_KEYS_SECTION,
    DATA_SOURCE_KEY,
    DEFAULT_DATA_SOURCE,
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


class AppInitializer:
    """Handles initialization logic for the WeatherApp."""

    def __init__(self, app_instance):
        """Initialize the AppInitializer.

        Args:
            app_instance: The WeatherApp instance to initialize
        """
        self.app = app_instance
        self.logger = logger

    def initialize_services(
        self, weather_service, location_service, notification_service, api_client
    ):
        """Initialize and validate required services.

        Args:
            weather_service: WeatherService instance
            location_service: LocationService instance
            notification_service: NotificationService instance
            api_client: NoaaApiClient instance (for backward compatibility)

        Raises:
            ValueError: If required services are not provided
        """
        # Store provided services
        self.app.weather_service = weather_service
        self.app.location_service = location_service
        self.app.notification_service = notification_service
        self.app.api_client = api_client  # For backward compatibility

        # Validate required services
        if not all([weather_service, location_service, notification_service]):
            raise ValueError(
                "Required services (weather_service, location_service, notification_service) "
                "must be provided"
            )

    def initialize_fetchers(self):
        """Initialize async fetchers using the weather service."""
        self.logger.debug("Initializing async fetchers")

        # Initialize async fetchers (always using the weather service)
        # This ensures that the WeatherService's logic for choosing between NWS and WeatherAPI is used
        self.app.forecast_fetcher = ForecastFetcher(self.app.weather_service)
        self.app.alerts_fetcher = AlertsFetcher(self.app.weather_service)
        self.app.discussion_fetcher = DiscussionFetcher(self.app.weather_service)
        self.app.current_conditions_fetcher = CurrentConditionsFetcher(self.app.weather_service)
        self.app.hourly_forecast_fetcher = HourlyForecastFetcher(self.app.weather_service)
        self.app.national_forecast_fetcher = NationalForecastFetcher(self.app.weather_service)

    def initialize_state_variables(self):
        """Initialize application state variables."""
        self.logger.debug("Initializing state variables")

        # State variables
        self.app.current_forecast = None
        self.app.current_alerts = []
        self.app.updating = False
        self.app._forecast_complete = False  # Flag for forecast fetch completion
        self.app._alerts_complete = False  # Flag for alerts fetch completion

        # Nationwide discussion state
        self.app._in_nationwide_mode = False
        self.app._nationwide_wpc_full = None
        self.app._nationwide_spc_full = None

        # Last update timestamp
        self.app.last_update: float = 0.0

        # Add force close flag
        self.app._force_close = True  # Default to force close when clicking X

    def initialize_ui_manager(self):
        """Initialize the UI manager."""
        self.logger.debug("Initializing UI manager")

        # Initialize UI using UIManager
        # UI elements are now attached to self.app by UIManager
        self.app.ui_manager = UIManager(self.app, self.app.notification_service.notifier)

    def setup_status_bar(self, debug_mode):
        """Set up the status bar based on debug mode.

        Args:
            debug_mode: Whether debug mode is enabled
        """
        self.logger.debug(f"Setting up status bar (debug_mode={debug_mode})")

        if debug_mode:
            # Use the debug status bar in debug mode
            from .debug_status_bar import DebugStatusBar

            self.app.status_bar = DebugStatusBar(self.app, UPDATE_INTERVAL_KEY)
            self.app.SetStatusBar(self.app.status_bar)
        else:
            # Use the standard status bar
            self.app.CreateStatusBar()

        self.app.SetStatusText("Ready")

    def setup_timer(self):
        """Set up the update timer."""
        self.logger.debug("Setting up update timer")

        # Start update timer
        self.app.timer = wx.Timer(self.app)
        self.app.Bind(wx.EVT_TIMER, self.app.OnTimer, self.app.timer)

        # Log the update interval from config
        update_interval = self.app.config.get("settings", {}).get(UPDATE_INTERVAL_KEY, 10)
        self.logger.debug(f"Starting timer with update interval: {update_interval} minutes")

        self.app.timer.Start(1000)  # Check every 1 second for updates

    def setup_event_bindings(self):
        """Set up event bindings for the application."""
        self.logger.debug("Setting up event bindings")

        # Bind Close event here as it's frame-level, not UI-element specific
        self.app.Bind(wx.EVT_CLOSE, self.app.OnClose)
        self.app.Bind(wx.EVT_ICONIZE, self.app.OnMinimize)

        # Bind character hook for global keyboard shortcuts
        self.app.Bind(wx.EVT_CHAR_HOOK, self.app.OnCharHook)

    def setup_system_tray(self):
        """Set up the system tray icon."""
        self.logger.debug("Setting up system tray")

        # Create system tray icon - cleanup any existing instance first
        TaskBarIcon.cleanup_existing_instance()
        self.app.taskbar_icon = TaskBarIcon(self.app)

    def setup_accessibility(self):
        """Set up accessibility features."""
        self.logger.debug("Setting up accessibility")

        # Register with accessibility system
        self.app.SetName("AccessiWeather")
        accessible = self.app.GetAccessible()
        if accessible:
            accessible.SetName("AccessiWeather")
            accessible.SetRole(wx.ACC_ROLE_WINDOW)

    def setup_testing_hooks(self):
        """Set up testing hooks for async tests."""
        self.logger.debug("Setting up testing hooks")

        # Test hooks for async tests
        self.app._testing_forecast_callback = None
        self.app._testing_forecast_error_callback = None
        self.app._testing_alerts_callback = None
        self.app._testing_alerts_error_callback = None
        self.app._testing_discussion_callback = None
        self.app._testing_discussion_error_callback = None

    def initialize_update_service(self, config_path):
        """Initialize the update service manually.

        Args:
            config_path: Path to the configuration file
        """
        self.logger.debug("Initializing update service")

        try:
            from accessiweather.services.update_service import UpdateService

            config_dir = os.path.dirname(config_path)

            # Initialize update service
            self.app.update_service = UpdateService(
                config_dir=config_dir,
                notification_callback=self.app._on_update_available,
                progress_callback=self.app._on_update_progress,
            )

            # Load settings and start background checking if enabled
            self.app._load_update_settings()

            self.logger.info("Update service initialized manually")

        except Exception as e:
            self.logger.error(f"Failed to initialize update service manually: {e}")
            self.app.update_service = None

    def load_config(self, config_path):
        """Load configuration from file.

        Args:
            config_path: Path to the configuration file

        Returns:
            Dict containing configuration or empty dict if not found
        """
        from accessiweather.config_utils import ensure_config_defaults

        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    # Ensure config has all required defaults
                    updated_config = ensure_config_defaults(config)
                    return updated_config
            except Exception as e:
                self.logger.error(f"Failed to load config: {str(e)}")

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

    def finalize_initialization(self):
        """Finalize the initialization process."""
        self.logger.debug("Finalizing initialization")

        # Initialize UI with location data
        self.app.UpdateLocationDropdown()

        # Update UI elements based on initial weather source (show/hide Open-Meteo incompatible elements)
        if hasattr(self.app, "ui_manager") and self.app.ui_manager:
            self.app.ui_manager.update_ui_for_location_change()

        self.app.UpdateWeatherData()
