"""Data transformer and formatter for Toga app.

This module provides transformation and formatting functions to convert data from the
NWS-compatible format (used by both NWS and Open-Meteo mappers) to formatted text
ready for display in the Toga app.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TogaDataTransformer:
    """Transforms and formats NWS-compatible data for Toga app display."""

    def __init__(self, config=None):
        """Initialize the transformer.

        Args:
            config: App configuration dictionary for temperature unit preferences
        """
        self.config = config or {}

    def transform_current_conditions(self, nws_data: dict[str, Any]) -> dict[str, Any]:
        """Transform NWS-compatible current conditions to Toga formatter format.
        
        Args:
            nws_data: Data in NWS-compatible format (from NWS API or Open-Meteo mapper)
            
        Returns:
            Dictionary in format expected by TogaWeatherFormatter
        """
        if not nws_data:
            return {}
            
        try:
            # Extract properties from NWS format
            properties = nws_data.get("properties", {})
            
            # Transform to flat format expected by Toga formatter
            transformed = {}
            
            # Temperature
            temp_data = properties.get("temperature", {})
            if isinstance(temp_data, dict) and temp_data.get("value") is not None:
                temp_f = temp_data["value"]
                transformed["temperature"] = temp_f
                # Convert to Celsius
                transformed["temperature_c"] = (temp_f - 32) * 5 / 9
            
            # Apparent temperature (feels like)
            apparent_temp_data = properties.get("apparentTemperature", {})
            if isinstance(apparent_temp_data, dict) and apparent_temp_data.get("value") is not None:
                feels_like_f = apparent_temp_data["value"]
                transformed["feelslike"] = feels_like_f
                transformed["feelslike_c"] = (feels_like_f - 32) * 5 / 9
            
            # Humidity
            humidity_data = properties.get("relativeHumidity", {})
            if isinstance(humidity_data, dict) and humidity_data.get("value") is not None:
                transformed["humidity"] = humidity_data["value"]
            
            # Wind speed
            wind_speed_data = properties.get("windSpeed", {})
            if isinstance(wind_speed_data, dict) and wind_speed_data.get("value") is not None:
                wind_speed_ms = wind_speed_data["value"]
                # Convert m/s to mph
                wind_speed_mph = wind_speed_ms * 2.237
                transformed["wind_speed"] = wind_speed_mph
                # Convert to kph
                transformed["wind_speed_kph"] = wind_speed_ms * 3.6
            
            # Wind direction
            wind_dir_data = properties.get("windDirection", {})
            if isinstance(wind_dir_data, dict) and wind_dir_data.get("value") is not None:
                wind_dir_degrees = wind_dir_data["value"]
                transformed["wind_direction"] = self._degrees_to_cardinal(wind_dir_degrees)
            
            # Pressure
            pressure_data = properties.get("barometricPressure", {})
            if isinstance(pressure_data, dict) and pressure_data.get("value") is not None:
                pressure_pa = pressure_data["value"]
                # Convert Pa to inHg
                pressure_inhg = pressure_pa * 0.0002953
                transformed["pressure"] = pressure_inhg
                # Convert Pa to mb/hPa
                transformed["pressure_mb"] = pressure_pa / 100
            
            # Weather condition
            text_description = properties.get("textDescription", "Unknown")
            transformed["condition"] = text_description
            
            logger.debug(f"Transformed current conditions: {transformed}")
            return transformed
            
        except Exception as e:
            logger.error(f"Error transforming current conditions: {e}")
            return {}
    
    def transform_forecast(self, nws_data: dict[str, Any]) -> dict[str, Any]:
        """Transform NWS-compatible forecast to Toga formatter format.
        
        Args:
            nws_data: Data in NWS-compatible format (from NWS API or Open-Meteo mapper)
            
        Returns:
            Dictionary in format expected by TogaWeatherFormatter
        """
        if not nws_data:
            return {}
            
        try:
            # Extract properties from NWS format
            properties = nws_data.get("properties", {})
            periods = properties.get("periods", [])
            
            if not periods:
                return {}
            
            # Transform periods to format expected by Toga formatter
            transformed = {
                "periods": periods  # Periods are already in the correct format
            }
            
            logger.debug(f"Transformed forecast with {len(periods)} periods")
            return transformed
            
        except Exception as e:
            logger.error(f"Error transforming forecast: {e}")
            return {}
    
    def _degrees_to_cardinal(self, degrees: float) -> str:
        """Convert wind direction degrees to cardinal direction.
        
        Args:
            degrees: Wind direction in degrees (0-360)
            
        Returns:
            Cardinal direction string (N, NE, E, SE, S, SW, W, NW)
        """
        if degrees is None:
            return ""
            
        # Normalize degrees to 0-360 range
        degrees = degrees % 360
        
        # Define cardinal directions
        directions = [
            "N", "NNE", "NE", "ENE",
            "E", "ESE", "SE", "SSE", 
            "S", "SSW", "SW", "WSW",
            "W", "WNW", "NW", "NNW"
        ]
        
        # Calculate index (each direction covers 22.5 degrees)
        index = round(degrees / 22.5) % 16
        return directions[index]

    def format_current_conditions(self, nws_data: dict[str, Any], location_name: str) -> str:
        """Transform NWS data and format current conditions for Toga display.

        Args:
            nws_data: Data in NWS-compatible format
            location_name: Name of the location

        Returns:
            Formatted text ready for display
        """
        # Transform the data first
        transformed = self.transform_current_conditions(nws_data)

        if not transformed:
            return f"Current conditions for {location_name}\n\nNo current weather data available"

        try:
            # Extract values with defaults
            temperature = transformed.get("temperature", "N/A")
            condition = transformed.get("condition", "Unknown")
            feelslike = transformed.get("feelslike", "N/A")
            humidity = transformed.get("humidity", "N/A")
            wind_speed = transformed.get("wind_speed", "N/A")
            wind_direction = transformed.get("wind_direction", "N/A")
            pressure = transformed.get("pressure", "N/A")

            # Format temperature
            temp_str = f"{temperature:.1f}°F" if isinstance(temperature, (int, float)) else str(temperature)
            feels_str = f"{feelslike:.1f}°F" if isinstance(feelslike, (int, float)) else str(feelslike)

            # Format humidity
            humidity_str = f"{humidity:.0f}%" if isinstance(humidity, (int, float)) else str(humidity)

            # Format wind
            wind_str = f"{wind_speed:.1f} mph" if isinstance(wind_speed, (int, float)) else str(wind_speed)

            # Format pressure
            pressure_str = f"{pressure:.0f} inHg" if isinstance(pressure, (int, float)) else str(pressure)

            # Build the formatted text
            text = f"Current conditions for {location_name}\n\n"
            text += f"Temperature: {temp_str}, {condition}\n"
            text += f"Feels like: {feels_str}\n"
            text += f"Humidity: {humidity_str}\n"
            text += f"Wind: {wind_direction} at {wind_str}\n"
            text += f"Pressure: {pressure_str}"

            return text

        except Exception as e:
            logger.error(f"Error formatting current conditions: {e}")
            return f"Current conditions for {location_name}\n\nError formatting weather data: {e}"

    def format_forecast(self, nws_data: dict[str, Any], location_name: str) -> str:
        """Transform NWS data and format forecast for Toga display.

        Args:
            nws_data: Data in NWS-compatible format
            location_name: Name of the location

        Returns:
            Formatted text ready for display
        """
        # Transform the data first
        transformed = self.transform_forecast(nws_data)

        if not transformed:
            return f"Forecast for {location_name}\n\nNo forecast data available"

        try:
            periods = transformed.get("periods", [])
            if not periods:
                return f"Forecast for {location_name}\n\nNo forecast periods available"

            text = f"Forecast for {location_name}\n\n"

            # Format each forecast period
            for period in periods[:7]:  # Limit to 7 periods for readability
                name = period.get("name", "Unknown")
                temperature = period.get("temperature")
                short_forecast = period.get("shortForecast", "")

                # Format temperature
                if temperature is not None:
                    temp_str = f"{temperature:.0f}°F"
                else:
                    temp_str = "N/A"

                text += f"{name}: {temp_str}, {short_forecast}\n"

            return text

        except Exception as e:
            logger.error(f"Error formatting forecast: {e}")
            return f"Forecast for {location_name}\n\nError formatting forecast data: {e}"
