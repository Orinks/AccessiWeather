"""Factory for creating the WeatherApp with the service layer.

This module provides a factory function for creating the WeatherApp
with the service layer.
"""

import logging
import os
from typing import Any, Dict, Optional

from accessiweather.api_client import NoaaApiClient

# NoaaApiWrapper is used in create_app
from accessiweather.api_wrapper import NoaaApiWrapper  # noqa: F401
from accessiweather.gui.settings_dialog import API_KEYS_SECTION, WEATHERAPI_KEY
from accessiweather.location import LocationManager
from accessiweather.notifications import WeatherNotifier
from accessiweather.services.location_service import LocationService
from accessiweather.services.notification_service import NotificationService
from accessiweather.services.weather_service import WeatherService
from accessiweather.weatherapi_wrapper import WeatherApiWrapper

from .weather_app import WeatherApp

logger = logging.getLogger(__name__)


def create_weather_app(
    parent=None,
    config: Optional[Dict[str, Any]] = None,
    config_path: Optional[str] = None,
    enable_caching: bool = True,
    cache_ttl: int = 300,
    debug_mode: bool = False,
) -> WeatherApp:
    """Create a WeatherApp instance with the service layer.

    Args:
        parent: Parent window
        config: Configuration dictionary (optional)
        config_path: Custom path to config file (optional)
        enable_caching: Whether to enable API response caching (default: True)
        cache_ttl: Time-to-live for cached responses in seconds (default: 5 minutes)
        debug_mode: Whether to enable debug mode with additional logging and alert testing features (default: False)

    Returns:
        WeatherApp instance
    """
    # Initialize configuration
    config = config or {}

    # Create the NWS API client with caching enabled
    api_settings = config.get("api_settings", {})
    contact_info = api_settings.get("contact_info")

    nws_client = NoaaApiClient(
        user_agent="AccessiWeather",
        contact_info=contact_info,
        enable_caching=enable_caching,
        cache_ttl=cache_ttl,
    )

    # Create the WeatherAPI.com client if API key is available
    weatherapi_wrapper = None
    api_keys = config.get(API_KEYS_SECTION, {})
    weatherapi_key = api_keys.get(WEATHERAPI_KEY)

    if weatherapi_key:
        logger.info("Initializing WeatherAPI.com client with provided API key")
        weatherapi_wrapper = WeatherApiWrapper(
            api_key=weatherapi_key,
            user_agent="AccessiWeather",
            enable_caching=enable_caching,
            cache_ttl=cache_ttl,
        )
    else:
        logger.info(
            "No WeatherAPI.com API key provided, WeatherAPI.com client will not be available"
        )

    # Create the location manager
    # Extract config_dir from config_path if available
    config_dir = os.path.dirname(config_path) if config_path else None

    # Get show_nationwide setting from config, default to True if not found
    show_nationwide = True
    if "settings" in config:
        show_nationwide = config["settings"].get("show_nationwide_location", True)

    # Get data source setting from config, default to "nws" if not found
    data_source = "nws"
    if "settings" in config:
        data_source = config["settings"].get("data_source", "nws")

    location_manager = LocationManager(
        config_dir, show_nationwide=show_nationwide, data_source=data_source
    )

    # Create the notifier with persistent storage
    notifier = WeatherNotifier(config_dir=config_dir, enable_persistence=True)

    # Create the services
    weather_service = WeatherService(
        nws_client=nws_client, weatherapi_wrapper=weatherapi_wrapper, config=config
    )
    location_service = LocationService(location_manager)
    notification_service = NotificationService(notifier)

    # Create the WeatherApp
    app = WeatherApp(
        parent=parent,
        weather_service=weather_service,
        location_service=location_service,
        notification_service=notification_service,
        api_client=nws_client,  # For backward compatibility
        config=config,
        config_path=config_path,
        debug_mode=debug_mode,
    )

    return app
