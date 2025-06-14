"""Configuration and utility functions for WeatherService.

This module contains configuration-related methods and utility functions
that were extracted from the main WeatherService class to improve modularity.
"""

import logging
from typing import Any, Dict

from accessiweather.gui.settings_dialog import DATA_SOURCE_AUTO, DATA_SOURCE_OPENMETEO

logger = logging.getLogger(__name__)


class WeatherServiceConfig:
    """Configuration and utility methods for WeatherService."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the configuration helper.

        Args:
            config: Configuration dictionary containing settings.
        """
        self.config = config

    def get_temperature_unit_preference(self) -> str:
        """Get the user's temperature unit preference for Open-Meteo API calls.

        Returns:
            str: "celsius" or "fahrenheit" for Open-Meteo API
        """
        from accessiweather.gui.settings_dialog import (
            DEFAULT_TEMPERATURE_UNIT,
            TEMPERATURE_UNIT_KEY,
        )
        from accessiweather.utils.temperature_utils import TemperatureUnit

        settings = self.config.get("settings", {})
        unit_pref = settings.get(TEMPERATURE_UNIT_KEY, DEFAULT_TEMPERATURE_UNIT)

        # Convert to Open-Meteo API format
        if unit_pref == TemperatureUnit.CELSIUS.value:
            return "celsius"
        else:
            # Default to fahrenheit for both "fahrenheit" and "both" preferences
            return "fahrenheit"

    def get_data_source(self) -> str:
        """Get the configured data source.

        Returns:
            String indicating which data source to use ('nws', 'openmeteo', or 'auto')
        """
        data_source = self.config.get("settings", {}).get("data_source", DATA_SOURCE_AUTO)
        logger.debug(
            f"get_data_source: config={self.config.get('settings', {})}, data_source={data_source}"
        )
        return str(data_source)

    def is_location_in_us(self, lat: float, lon: float) -> bool:
        """Check if a location is within the United States.

        This method uses the geocoding service to determine if the given coordinates
        are within the United States.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            True if the location is within the US, False otherwise
        """
        from accessiweather.geocoding import GeocodingService

        # Create a geocoding service instance with the correct data source
        # Using 'auto' as data source to ensure it doesn't filter based on data source
        # but only on the explicit us_only parameter
        geocoding_service = GeocodingService(
            user_agent="AccessiWeather-WeatherService", data_source="auto"
        )

        # Use the validate_coordinates method to check if the location is in the US
        # Explicitly set us_only=True to check for US location regardless of data source
        is_us = geocoding_service.validate_coordinates(lat, lon, us_only=True)
        logger.debug(f"Location ({lat}, {lon}) is {'in' if is_us else 'not in'} the US")
        return is_us

    def should_use_openmeteo(self, lat: float, lon: float) -> bool:
        """Determine if Open-Meteo should be used for the given location.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location

        Returns:
            True if Open-Meteo should be used, False if NWS should be used
        """
        data_source = self.get_data_source()
        logger.debug(f"should_use_openmeteo: data_source={data_source}, lat={lat}, lon={lon}")

        # If Open-Meteo is explicitly selected, always use it
        if data_source == DATA_SOURCE_OPENMETEO:
            logger.debug("should_use_openmeteo: Open-Meteo explicitly selected")
            return True

        # If Automatic mode is selected, use Open-Meteo for non-US locations
        if data_source == DATA_SOURCE_AUTO:
            # Check if location is in the US
            is_us_location = self.is_location_in_us(lat, lon)
            logger.debug(f"should_use_openmeteo: Automatic mode, is_us_location={is_us_location}")
            return not is_us_location

        # Default to NWS
        logger.debug("should_use_openmeteo: Defaulting to NWS API")
        return False
