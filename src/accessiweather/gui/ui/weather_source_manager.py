"""Weather Source Manager for AccessiWeather UI.

This module provides classes for managing weather source detection
and UI updates based on the current weather source.
"""

import logging

logger = logging.getLogger(__name__)


class WeatherSourceManager:
    """Manages weather source detection and UI updates."""

    def __init__(self, frame):
        """Initialize the weather source manager.

        Args:
            frame: The main WeatherApp frame instance.
        """
        self.frame = frame

    def is_using_openmeteo(self) -> bool:
        """Determine if the current location is using Open-Meteo as the weather source.

        Returns:
            bool: True if Open-Meteo is being used, False otherwise
        """
        logger.debug("is_using_openmeteo: Starting weather source detection")
        try:
            # Get the current location coordinates
            if not hasattr(self.frame, "location_service") or not self.frame.location_service:
                logger.debug("is_using_openmeteo: No location service available")
                return False

            current_location = self.frame.location_service.get_current_location()
            logger.debug(f"is_using_openmeteo: current_location = {current_location}")
            if not current_location:
                logger.debug("is_using_openmeteo: No current location")
                return False

            # Extract coordinates from the current location tuple (name, lat, lon)
            if len(current_location) == 3:
                location_name, lat, lon = current_location
                logger.debug(
                    f"is_using_openmeteo: extracted from current_location - name={location_name}, lat={lat}, lon={lon}"
                )
            else:
                logger.debug("is_using_openmeteo: Invalid current_location format")
                return False

            # Check if we have a weather service to determine the source
            if hasattr(self.frame, "weather_service") and self.frame.weather_service:
                logger.debug(
                    "is_using_openmeteo: Weather service available, calling _should_use_openmeteo"
                )
                # Use the weather service's logic to determine if Open-Meteo should be used
                result = bool(self.frame.weather_service._should_use_openmeteo(lat, lon))
                logger.debug(
                    f"is_using_openmeteo: weather_service._should_use_openmeteo returned {result}"
                )
                return result
            else:
                logger.debug("is_using_openmeteo: No weather service available, using fallback")

            # Fallback: check config directly
            return self._check_config_for_openmeteo(lat, lon)

        except Exception as e:
            logger.warning(f"Error determining weather source: {e}")
            return False

    def _check_config_for_openmeteo(self, lat, lon) -> bool:
        """Check configuration to determine if Open-Meteo should be used.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            bool: True if Open-Meteo should be used
        """
        from accessiweather.gui.settings.constants import DATA_SOURCE_AUTO, DATA_SOURCE_OPENMETEO

        data_source = self.frame.config.get("settings", {}).get("data_source", "nws")

        if data_source == DATA_SOURCE_OPENMETEO:
            return True
        elif data_source == DATA_SOURCE_AUTO:
            # For auto mode, check if location is outside US
            from accessiweather.geocoding import GeocodingService

            geocoding_service = GeocodingService(
                user_agent="AccessiWeather-UIManager", data_source="auto"
            )
            is_us = geocoding_service.validate_coordinates(lat, lon, us_only=True)
            return not is_us

        return False

    def update_ui_for_weather_source(self, openmeteo_hidden_elements=None):
        """Update UI elements based on the current weather source (show/hide Open-Meteo incompatible elements).

        Args:
            openmeteo_hidden_elements: List of (element, name) tuples to hide for Open-Meteo
        """
        try:
            is_openmeteo = self.is_using_openmeteo()
            logger.debug(f"Updating UI for weather source, is_openmeteo: {is_openmeteo}")

            # Show or hide elements based on weather source
            if openmeteo_hidden_elements:
                for element, name in openmeteo_hidden_elements:
                    if element and hasattr(element, "Show"):
                        element.Show(not is_openmeteo)
                        logger.debug(f"{'Hiding' if is_openmeteo else 'Showing'} {name}")

            # Force layout update
            if hasattr(self.frame, "panel") and self.frame.panel:
                self.frame.panel.Layout()

        except Exception as e:
            logger.error(f"Error updating UI for weather source: {e}")

    def update_ui_for_location_change(self, openmeteo_hidden_elements=None):
        """Update UI elements when the location changes (called from location handlers).

        Args:
            openmeteo_hidden_elements: List of (element, name) tuples to hide for Open-Meteo
        """
        logger.debug("update_ui_for_location_change: Called from location handlers")
        self.update_ui_for_weather_source(openmeteo_hidden_elements)
