"""Data Extractors for AccessiWeather UI.

This module provides classes for extracting weather data from various APIs
for use in taskbar icons and other UI components.
"""

import logging

from .ui_utils import (
    convert_wind_direction_to_cardinal,
    create_standardized_taskbar_data,
    format_combined_wind,
    safe_get_location_name,
)

logger = logging.getLogger(__name__)


class WeatherDataExtractor:
    """Extracts weather data from various API formats for UI use."""

    def __init__(self, frame):
        """Initialize the data extractor.

        Args:
            frame: The main WeatherApp frame instance.

        """
        self.frame = frame

    def extract_weatherapi_data_for_taskbar(self, conditions_data):
        """Extract relevant data from WeatherAPI.com conditions for the taskbar icon.

        Args:
            conditions_data: Dictionary with WeatherAPI.com current conditions data

        Returns:
            dict: Dictionary with extracted data for taskbar icon

        """
        if not conditions_data:
            return {}

        # Extract the current conditions
        current = conditions_data.get("current", {})
        condition = current.get("condition", {})

        # Create a dictionary with the data we want to display in the taskbar
        data = {
            "temp": current.get("temp_f"),
            "temp_f": current.get("temp_f"),
            "temp_c": current.get("temp_c"),
            "condition": condition.get("text", ""),
            "humidity": current.get("humidity"),
            "wind_speed": current.get("wind_mph"),
            "wind_dir": current.get("wind_dir"),
            "pressure": current.get("pressure_in"),
            "feels_like": current.get("feelslike_f"),
            "uv": current.get("uv"),
            "visibility": current.get("vis_miles"),
            "precip": current.get("precip_in"),
            "weather_code": condition.get("code"),  # WeatherAPI condition code
        }

        # Add location information if available
        location = conditions_data.get("location", {})
        if location:
            data["location"] = location.get("name", "")

        return data

    def extract_nws_data_for_taskbar(self, conditions_data):
        """Extract relevant data from NWS API conditions for the taskbar icon.

        Args:
            conditions_data: Dictionary with NWS API current conditions data

        Returns:
            dict: Dictionary with extracted data for taskbar icon

        """
        try:
            if not conditions_data or "properties" not in conditions_data:
                logger.warning("NWS data extraction: Invalid or missing conditions data")
                return create_standardized_taskbar_data()

            properties = conditions_data.get("properties", {})
            logger.debug(
                f"NWS data extraction: Processing properties with keys: {list(properties.keys())}"
            )

            # Extract temperature with error handling
            temperature_f = None
            temperature_c = None
            try:
                temperature_value = properties.get("temperature", {}).get("value")
                temp_unit_code = properties.get("temperature", {}).get("unitCode", "")

                if temperature_value is not None:
                    if "degF" in temp_unit_code:
                        temperature_f = float(temperature_value)
                        temperature_c = (temperature_f - 32) * 5 / 9
                    else:
                        temperature_c = float(temperature_value)
                        temperature_f = (temperature_c * 9 / 5) + 32
                    logger.debug(
                        f"NWS temperature extracted: {temperature_f}°F / {temperature_c}°C"
                    )
                else:
                    logger.warning("NWS data extraction: No temperature value found")
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"NWS data extraction: Error processing temperature: {e}")

            # Extract humidity with error handling
            humidity = None
            try:
                humidity_value = properties.get("relativeHumidity", {}).get("value")
                if humidity_value is not None:
                    humidity = float(humidity_value)
                    logger.debug(f"NWS humidity extracted: {humidity}%")
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"NWS data extraction: Error processing humidity: {e}")

            # Extract wind data with error handling
            wind_speed_mph = None
            wind_dir = ""
            try:
                wind_speed_kph = properties.get("windSpeed", {}).get("value")
                if wind_speed_kph is not None:
                    wind_speed_mph = float(wind_speed_kph) * 0.621371
                    logger.debug(f"NWS wind speed extracted: {wind_speed_mph} mph")

                wind_direction_degrees = properties.get("windDirection", {}).get("value")
                if wind_direction_degrees is not None:
                    wind_dir = convert_wind_direction_to_cardinal(wind_direction_degrees)
                    logger.debug(
                        f"NWS wind direction extracted: {wind_direction_degrees}° -> {wind_dir}"
                    )
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"NWS data extraction: Error processing wind data: {e}")

            # Extract barometric pressure with error handling
            pressure_inhg = None
            try:
                pressure_pa = properties.get("barometricPressure", {}).get("value")
                if pressure_pa is not None:
                    pressure_inhg = float(pressure_pa) / 3386.39
                    logger.debug(f"NWS pressure extracted: {pressure_inhg} inHg")
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"NWS data extraction: Error processing pressure: {e}")

            # Extract feels like temperature with error handling
            feels_like_f = None
            feels_like_c = None
            try:
                apparent_temp_value = properties.get("apparentTemperature", {}).get("value")
                apparent_temp_unit_code = properties.get("apparentTemperature", {}).get(
                    "unitCode", ""
                )

                if apparent_temp_value is not None:
                    if "degF" in apparent_temp_unit_code:
                        feels_like_f = float(apparent_temp_value)
                        feels_like_c = (feels_like_f - 32) * 5 / 9
                    else:
                        feels_like_c = float(apparent_temp_value)
                        feels_like_f = (feels_like_c * 9 / 5) + 32
                    logger.debug(f"NWS feels like extracted: {feels_like_f}°F / {feels_like_c}°C")
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"NWS data extraction: Error processing feels like temperature: {e}")

            # Get location information with thread safety
            location_name = safe_get_location_name(
                getattr(self.frame, "location_service", None), fallback=""
            )

            # Create combined wind placeholder using utility function
            wind_combined = format_combined_wind(wind_speed_mph, wind_dir, "mph")

            # Extract weather code for dynamic format management
            weather_code = None
            # Check if this is Open-Meteo data mapped to NWS format
            present_weather = properties.get("presentWeather", [])
            if present_weather and len(present_weather) > 0:
                raw_string = present_weather[0].get("rawString")
                if raw_string and raw_string.isdigit():
                    weather_code = int(raw_string)

            # Get weather condition
            condition = properties.get("textDescription", "")
            logger.debug(f"NWS condition extracted: {condition}")

            # Create standardized data structure
            return create_standardized_taskbar_data(
                temp=temperature_f,
                temp_f=temperature_f,
                temp_c=temperature_c,
                condition=condition,
                humidity=humidity,
                wind_speed=wind_speed_mph,
                wind_dir=wind_dir,
                wind=wind_combined,
                pressure=pressure_inhg,
                feels_like=feels_like_f,
                feels_like_f=feels_like_f,
                feels_like_c=feels_like_c,
                location=location_name,
                weather_code=weather_code,
            )

        except Exception as e:
            logger.error(f"NWS data extraction: Unexpected error: {e}")
            return create_standardized_taskbar_data()
