"""Core initialization and configuration management for WeatherApp.

This module handles the core initialization, configuration loading/saving,
service management, and lifecycle operations for the WeatherApp.
"""

import json
import logging
import os
from typing import Any

from accessiweather.config_utils import get_config_dir
from accessiweather.gui.settings.constants import (
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

logger = logging.getLogger(__name__)

# Constants
CONFIG_DIR = get_config_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


class WeatherAppCore:
    """Core initialization and configuration management for WeatherApp."""

    def __init__(self, weather_app):
        """Initialize the core module.

        Args:
            weather_app: Reference to the main WeatherApp instance

        """
        self.app = weather_app
        logger.debug("WeatherAppCore initialized")

    def initialize_app(
        self,
        parent=None,
        weather_service=None,
        location_service=None,
        notification_service=None,
        api_client=None,
        config=None,
        config_path=None,
        debug_mode=False,
    ):
        """Initialize the weather app with all required services and configuration.

        Args:
            parent: Parent window
            weather_service: WeatherService instance
            location_service: LocationService instance
            notification_service: NotificationService instance
            api_client: NoaaApiClient instance (for backward compatibility)
            config: Configuration dictionary (optional)
            config_path: Custom path to config file (optional)
            debug_mode: Whether to enable debug mode

        """
        # Set config path
        self.app._config_path = config_path or CONFIG_PATH

        # Load or use provided config
        self.app.config = config if config is not None else self.load_config()

        # Store provided services
        self.app.weather_service = weather_service
        self.app.location_service = location_service
        self.app.notification_service = notification_service

        # For backward compatibility
        self.app.api_client = api_client

        # Debug mode
        self.app.debug_mode = debug_mode
        # For backward compatibility, debug_alerts is now the same as debug_mode
        self.app.debug_alerts = debug_mode

        # Always log debug mode status
        logger.info(f"Debug mode status: debug_mode={self.app.debug_mode}")

        if self.app.debug_mode:
            logger.info("Debug mode enabled for additional debug information and alert testing")

        # Validate required services
        if not all(
            [self.app.weather_service, self.app.location_service, self.app.notification_service]
        ):
            raise ValueError(
                "Required services (weather_service, location_service, notification_service) "
                "must be provided"
            )

        # Initialize async fetchers
        self._initialize_fetchers()

        # Initialize state variables
        self._initialize_state()

        logger.info("WeatherApp core initialization complete")

    def _initialize_fetchers(self):
        """Initialize async fetchers using the weather service."""
        from accessiweather.national_forecast_fetcher import NationalForecastFetcher

        from ..async_fetchers import AlertsFetcher, DiscussionFetcher, ForecastFetcher
        from ..current_conditions_fetcher import CurrentConditionsFetcher
        from ..hourly_forecast_fetcher import HourlyForecastFetcher

        # Initialize async fetchers (always using the weather service)
        # This ensures that the WeatherService's logic for choosing between NWS and WeatherAPI is used
        self.app.forecast_fetcher = ForecastFetcher(self.app.weather_service)
        self.app.alerts_fetcher = AlertsFetcher(self.app.weather_service)
        self.app.discussion_fetcher = DiscussionFetcher(self.app.weather_service)
        self.app.current_conditions_fetcher = CurrentConditionsFetcher(self.app.weather_service)
        self.app.hourly_forecast_fetcher = HourlyForecastFetcher(self.app.weather_service)
        self.app.national_forecast_fetcher = NationalForecastFetcher(self.app.weather_service)

        logger.debug("Async fetchers initialized")

    def _initialize_state(self):
        """Initialize state variables for the weather app."""
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
        self.app.last_update = 0.0

        # Add force close flag
        self.app._force_close = True  # Default to force close when clicking X

        # Test hooks for async tests
        self.app._testing_forecast_callback = None
        self.app._testing_forecast_error_callback = None
        self.app._testing_alerts_callback = None
        self.app._testing_alerts_error_callback = None
        self.app._testing_discussion_callback = None
        self.app._testing_discussion_error_callback = None

        logger.debug("State variables initialized")

    def load_config(self) -> dict[str, Any]:
        """Load configuration from file.

        Returns:
            Dict containing configuration or empty dict if not found

        """
        from accessiweather.config_utils import ensure_config_defaults

        if os.path.exists(self.app._config_path):
            try:
                with open(self.app._config_path) as f:
                    config = json.load(f)
                    # Ensure config has all required defaults
                    updated_config = ensure_config_defaults(config)
                    logger.debug(f"Configuration loaded from {self.app._config_path}")
                    return updated_config
            except Exception as e:
                logger.error(f"Failed to load config: {str(e)}")

        # Return default config structure
        default_config = {
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
        logger.debug("Using default configuration")
        return default_config

    def initialize_update_service(self):
        """Initialize the update service for automatic updates."""
        try:
            from accessiweather.services.update_service import UpdateService

            config_dir = os.path.dirname(self.app._config_path)

            # Initialize update service
            self.app.update_service = UpdateService(
                config_dir=config_dir,
                notification_callback=self.app._on_update_available,
                progress_callback=self.app._on_update_progress,
            )

            # Load settings and start background checking if enabled
            self.app._load_update_settings()

            logger.info("Update service initialized")

        except Exception as e:
            logger.error(f"Failed to initialize update service: {e}")
            self.app.update_service = None

    def handle_data_source_change(self):
        """Handle changes to the data source or API settings.

        This method is called when the data source or API settings are changed
        in the settings dialog. It reinitializes the WeatherService with the new
        settings and updates the fetchers to use the new service.
        """
        from accessiweather.api_wrapper import NoaaApiWrapper
        from accessiweather.openmeteo_client import OpenMeteoApiClient
        from accessiweather.services.weather_service import WeatherService

        logger.info("Reinitializing WeatherService due to data source or API key change")

        # Log the current settings
        data_source = self.app.config.get("settings", {}).get(DATA_SOURCE_KEY, "nws")
        logger.info(f"Current data source: {data_source}")
        logger.info(f"Full config: {self.app.config}")

        # Create the NWS API client (always needed)
        nws_client = NoaaApiWrapper(
            user_agent="AccessiWeather",
            enable_caching=True,  # Default to enabled
            cache_ttl=300,  # Default to 5 minutes
        )

        # Create the Open-Meteo API client
        openmeteo_client = OpenMeteoApiClient(user_agent="AccessiWeather")

        # Create the new WeatherService
        self.app.weather_service = WeatherService(
            nws_client=nws_client, openmeteo_client=openmeteo_client, config=self.app.config
        )

        # Update the location service with the new data source
        self.app.location_service.update_data_source(data_source)

        # Update the fetchers to use the new service
        self.app.forecast_fetcher.service = self.app.weather_service
        self.app.alerts_fetcher.service = self.app.weather_service
        self.app.discussion_fetcher.service = self.app.weather_service
        self.app.current_conditions_fetcher.service = self.app.weather_service
        self.app.hourly_forecast_fetcher.service = self.app.weather_service
        self.app.national_forecast_fetcher.service = self.app.weather_service

        # For backward compatibility
        self.app.api_client = nws_client

        # Update UI elements based on new weather source
        if hasattr(self.app, "ui_manager") and self.app.ui_manager:
            self.app.ui_manager.update_ui_for_location_change()

        # Refresh weather data to apply new settings
        self.app.UpdateWeatherData()

        logger.info("Data source change handling complete")

    @property
    def location_manager(self):
        """Provide backward compatibility with the location_manager property."""
        return self.app.location_service.location_manager

    @property
    def notifier(self):
        """Provide backward compatibility with the notifier property."""
        return self.app.notification_service.notifier
