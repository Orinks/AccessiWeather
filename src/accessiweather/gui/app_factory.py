"""Factory for creating the WeatherApp with the service layer.

This module provides a factory function for creating the WeatherApp
with the service layer.
"""

import logging
from typing import Optional, Dict, Any

from accessiweather.api_client import NoaaApiClient
from accessiweather.location import LocationManager
from accessiweather.notifications import WeatherNotifier
from accessiweather.services.location_service import LocationService
from accessiweather.services.notification_service import NotificationService
from accessiweather.services.weather_service import WeatherService
from .weather_app_refactored import WeatherApp

logger = logging.getLogger(__name__)


def create_weather_app(
    parent=None,
    config: Optional[Dict[str, Any]] = None,
    config_path: Optional[str] = None,
) -> WeatherApp:
    """Create a WeatherApp instance with the service layer.

    Args:
        parent: Parent window
        config: Configuration dictionary (optional)
        config_path: Custom path to config file (optional)

    Returns:
        WeatherApp instance
    """
    # Create the API client
    api_client = NoaaApiClient()

    # Create the location manager
    location_manager = LocationManager(config)

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
    )

    return app
