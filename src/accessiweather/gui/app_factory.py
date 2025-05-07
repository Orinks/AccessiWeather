"""Factory for creating the WeatherApp with the service layer.

This module provides a factory function for creating the WeatherApp
with the service layer.
"""

import logging
import os
from typing import Any, Dict, Optional

from accessiweather.api_client import NoaaApiClient
from accessiweather.location import LocationManager
from accessiweather.notifications import WeatherNotifier
from accessiweather.services.location_service import LocationService
from accessiweather.services.notification_service import NotificationService
from accessiweather.services.weather_service import WeatherService

from .weather_app import WeatherApp

logger = logging.getLogger(__name__)


def create_weather_app(
    parent=None,
    config: Optional[Dict[str, Any]] = None,
    config_path: Optional[str] = None,
    enable_caching: bool = True,
    cache_ttl: int = 300,
    debug_options: Optional[Dict[str, Any]] = None,
) -> WeatherApp:
    """Create a WeatherApp instance with the service layer.

    Args:
        parent: Parent window
        config: Configuration dictionary (optional)
        config_path: Custom path to config file (optional)
        enable_caching: Whether to enable API response caching (default: True)
        cache_ttl: Time-to-live for cached responses in seconds (default: 5 minutes)
        debug_options: Dictionary of debug options for testing features (optional)

    Returns:
        WeatherApp instance
    """
    # Create the API client with caching enabled
    api_settings = config.get("api_settings", {}) if config else {}
    contact_info = api_settings.get("contact_info")

    api_client = NoaaApiClient(
        user_agent="AccessiWeather",
        contact_info=contact_info,
        enable_caching=enable_caching,
        cache_ttl=cache_ttl,
    )

    # Create the location manager
    # Extract config_dir from config_path if available
    config_dir = os.path.dirname(config_path) if config_path else None

    # Get show_nationwide setting from config, default to True if not found
    show_nationwide = True
    if config and "settings" in config:
        show_nationwide = config["settings"].get("show_nationwide_location", True)

    location_manager = LocationManager(config_dir, show_nationwide=show_nationwide)

    # Create the notifier
    notifier = WeatherNotifier()

    # Create the services
    weather_service = WeatherService(api_client)
    location_service = LocationService(location_manager)
    notification_service = NotificationService(notifier)

    # Create the WeatherApp
    app = WeatherApp(
        parent=parent,
        weather_service=weather_service,
        location_service=location_service,
        notification_service=notification_service,
        api_client=api_client,  # For backward compatibility
        config=config,
        config_path=config_path,
        debug_options=debug_options,
    )

    return app
