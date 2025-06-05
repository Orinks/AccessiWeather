"""Data mapper for Open-Meteo API responses.

This module provides functionality to transform Open-Meteo API responses
into the internal data format expected by WeatherService and UI components.
"""

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .openmeteo_client import OpenMeteoApiClient

logger = logging.getLogger(__name__)


class OpenMeteoMapper:
    """Maps Open-Meteo API responses to internal data format."""

    def __init__(self):
        """Initialize the mapper."""
        pass

    def map_current_conditions(self, openmeteo_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Open-Meteo current weather data to NWS-compatible format.

        Args:
            openmeteo_data: Raw response from Open-Meteo current weather API

        Returns:
            Dictionary in NWS current conditions format
        """
        try:
            current = openmeteo_data.get("current", {})
            current_units = openmeteo_data.get("current_units", {})

            logger.debug(f"Open-Meteo current data keys: {list(current.keys())}")
            logger.debug(f"Open-Meteo current units: {current_units}")

            # Map the data to NWS-like structure
            mapped_data = {
                "properties": {
                    "@id": f"open-meteo-current-{datetime.now(timezone.utc).isoformat()}",
                    "timestamp": current.get("time", datetime.now(timezone.utc).isoformat()),
                    "temperature": {
                        "value": current.get("temperature_2m"),
                        "unitCode": self._get_temperature_unit_code(
                            current_units.get("temperature_2m", "°F")
                        ),
                        "qualityControl": "qc:V",
                    },
                    "dewpoint": {
                        "value": self._calculate_dewpoint(
                            current.get("temperature_2m"), current.get("relative_humidity_2m")
                        ),
                        "unitCode": self._get_temperature_unit_code(
                            current_units.get("temperature_2m", "°F")
                        ),
                        "qualityControl": "qc:V",
                    },
                    "apparentTemperature": {
                        "value": current.get("apparent_temperature"),
                        "unitCode": self._get_temperature_unit_code(
                            current_units.get("apparent_temperature", "°F")
                        ),
                        "qualityControl": "qc:V",
                    },
                    "windDirection": {
                        "value": current.get("wind_direction_10m"),
                        "unitCode": "wmoUnit:degree_(angle)",
                        "qualityControl": "qc:V",
                    },
                    "windSpeed": {
                        "value": current.get("wind_speed_10m"),
                        "unitCode": self._get_wind_speed_unit_code(
                            current_units.get("wind_speed_10m", "mph")
                        ),
                        "qualityControl": "qc:V",
                    },
                    "windGust": {
                        "value": current.get("wind_gusts_10m"),
                        "unitCode": self._get_wind_speed_unit_code(
                            current_units.get("wind_speed_10m", "mph")
                        ),
                        "qualityControl": "qc:V",
                    },
                    "barometricPressure": {
                        "value": current.get("pressure_msl"),
                        "unitCode": "wmoUnit:Pa",
                        "qualityControl": "qc:V",
                    },
                    "relativeHumidity": {
                        "value": current.get("relative_humidity_2m"),
                        "unitCode": "wmoUnit:percent",
                        "qualityControl": "qc:V",
                    },
                    "visibility": {
                        "value": None,  # Open-Meteo doesn't provide visibility
                        "unitCode": "wmoUnit:m",
                        "qualityControl": "qc:Z",
                    },
                    "cloudLayers": (
                        [
                            {
                                "amount": self._cloud_cover_to_amount(current.get("cloud_cover")),
                                "base": {"value": None, "unitCode": "wmoUnit:m"},
                            }
                        ]
                        if current.get("cloud_cover") is not None
                        else []
                    ),
                    "textDescription": OpenMeteoApiClient.get_weather_description(
                        current.get("weather_code", 0)
                    ),
                    # Additional fields for compatibility
                    "rawMessage": f"Open-Meteo data: {current.get('weather_code', 0)}",
                    "presentWeather": [
                        {
                            "intensity": None,
                            "modifier": None,
                            "weather": OpenMeteoApiClient.get_weather_description(
                                current.get("weather_code", 0)
                            ),
                            "rawString": str(current.get("weather_code", 0)),
                        }
                    ],
                }
            }

            logger.debug(f"Mapped current conditions: {mapped_data}")
            return mapped_data

        except Exception as e:
            logger.error(f"Error mapping current conditions: {str(e)}")
            raise ValueError(f"Failed to map current conditions: {str(e)}")

    def map_forecast(self, openmeteo_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Open-Meteo daily forecast data to NWS-compatible format.

        Args:
            openmeteo_data: Raw response from Open-Meteo forecast API

        Returns:
            Dictionary in NWS forecast format
        """
        try:
            daily = openmeteo_data.get("daily", {})
            daily_units = openmeteo_data.get("daily_units", {})

            if not daily:
                return {"properties": {"periods": []}}

            periods = []
            dates = daily.get("time", [])
            weather_codes = daily.get("weather_code", [])
            temp_max = daily.get("temperature_2m_max", [])
            temp_min = daily.get("temperature_2m_min", [])

            for i, date_str in enumerate(dates):
                try:
                    # Parse the date
                    date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

                    # Create day and night periods (NWS style)
                    day_period = {
                        "number": i * 2 + 1,
                        "name": date_obj.strftime("%A") if i == 0 else date_obj.strftime("%A"),
                        "startTime": date_obj.replace(hour=6).isoformat(),
                        "endTime": date_obj.replace(hour=18).isoformat(),
                        "isDaytime": True,
                        "temperature": (
                            int(temp_max[i])
                            if i < len(temp_max) and temp_max[i] is not None
                            else None
                        ),
                        "temperatureUnit": (
                            "F"
                            if "°f" in daily_units.get("temperature_2m_max", "°F").lower()
                            else "C"
                        ),
                        "temperatureTrend": None,
                        "windSpeed": f"{daily.get('wind_speed_10m_max', [None])[i] or 0} {daily_units.get('wind_speed_10m_max', 'mph')}",
                        "windDirection": self._degrees_to_direction(
                            daily.get("wind_direction_10m_dominant", [None])[i]
                        ),
                        "icon": f"https://open-meteo.com/images/weather/{weather_codes[i] if i < len(weather_codes) else 0}.png",
                        "shortForecast": OpenMeteoApiClient.get_weather_description(
                            weather_codes[i] if i < len(weather_codes) else 0
                        ),
                        "detailedForecast": self._create_detailed_forecast(
                            daily, daily_units, i, True
                        ),
                    }

                    night_period = {
                        "number": i * 2 + 2,
                        "name": f"{date_obj.strftime('%A')} Night",
                        "startTime": date_obj.replace(hour=18).isoformat(),
                        "endTime": (date_obj.replace(hour=6) + timedelta(days=1)).isoformat(),
                        "isDaytime": False,
                        "temperature": (
                            int(temp_min[i])
                            if i < len(temp_min) and temp_min[i] is not None
                            else None
                        ),
                        "temperatureUnit": (
                            "F"
                            if "°f" in daily_units.get("temperature_2m_min", "°F").lower()
                            else "C"
                        ),
                        "temperatureTrend": None,
                        "windSpeed": f"{daily.get('wind_speed_10m_max', [None])[i] or 0} {daily_units.get('wind_speed_10m_max', 'mph')}",
                        "windDirection": self._degrees_to_direction(
                            daily.get("wind_direction_10m_dominant", [None])[i]
                        ),
                        "icon": f"https://open-meteo.com/images/weather/{weather_codes[i] if i < len(weather_codes) else 0}.png",
                        "shortForecast": OpenMeteoApiClient.get_weather_description(
                            weather_codes[i] if i < len(weather_codes) else 0
                        ),
                        "detailedForecast": self._create_detailed_forecast(
                            daily, daily_units, i, False
                        ),
                    }

                    periods.extend([day_period, night_period])

                except Exception as e:
                    logger.warning(f"Error processing forecast day {i}: {str(e)}")
                    continue

            mapped_data = {
                "properties": {
                    "updated": datetime.now(timezone.utc).isoformat(),
                    "units": {
                        "temperature": (
                            "F"
                            if (
                                "fahrenheit" in str(daily_units).lower()
                                or "°f" in str(daily_units).lower()
                            )
                            else "C"
                        ),
                        "windSpeed": daily_units.get("wind_speed_10m_max", "mph"),
                        "precipitation": daily_units.get("precipitation_sum", "in"),
                    },
                    "forecastGenerator": "Open-Meteo API",
                    "generatedAt": datetime.now(timezone.utc).isoformat(),
                    "periods": periods,
                }
            }

            logger.debug(f"Mapped forecast with {len(periods)} periods")
            return mapped_data

        except Exception as e:
            logger.error(f"Error mapping forecast: {str(e)}")
            raise ValueError(f"Failed to map forecast: {str(e)}")

    def map_hourly_forecast(self, openmeteo_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Open-Meteo hourly forecast data to NWS-compatible format.

        Args:
            openmeteo_data: Raw response from Open-Meteo hourly forecast API

        Returns:
            Dictionary in NWS hourly forecast format
        """
        try:
            hourly = openmeteo_data.get("hourly", {})
            hourly_units = openmeteo_data.get("hourly_units", {})

            if not hourly:
                return {"properties": {"periods": []}}

            periods = []
            times = hourly.get("time", [])
            temperatures = hourly.get("temperature_2m", [])
            weather_codes = hourly.get("weather_code", [])
            wind_speeds = hourly.get("wind_speed_10m", [])
            wind_directions = hourly.get("wind_direction_10m", [])
            is_day = hourly.get("is_day", [])

            for i, time_str in enumerate(times):
                try:
                    # Parse the time
                    time_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    end_time = time_obj.replace(minute=0, second=0, microsecond=0) + timedelta(
                        hours=1
                    )

                    period = {
                        "number": i + 1,
                        "name": "This Hour" if i == 0 else time_obj.strftime("%I %p").lstrip("0"),
                        "startTime": time_obj.isoformat(),
                        "endTime": end_time.isoformat(),
                        "isDaytime": bool(is_day[i]) if i < len(is_day) else True,
                        "temperature": (
                            int(temperatures[i])
                            if i < len(temperatures) and temperatures[i] is not None
                            else None
                        ),
                        "temperatureUnit": (
                            "F" if "°f" in hourly_units.get("temperature_2m", "°F").lower() else "C"
                        ),
                        "temperatureTrend": None,
                        "windSpeed": f"{wind_speeds[i] if i < len(wind_speeds) and wind_speeds[i] is not None else 0} {hourly_units.get('wind_speed_10m', 'mph')}",
                        "windDirection": self._degrees_to_direction(
                            wind_directions[i] if i < len(wind_directions) else None
                        ),
                        "icon": f"https://open-meteo.com/images/weather/{weather_codes[i] if i < len(weather_codes) else 0}.png",
                        "shortForecast": OpenMeteoApiClient.get_weather_description(
                            weather_codes[i] if i < len(weather_codes) else 0
                        ),
                        "detailedForecast": "",
                    }

                    periods.append(period)

                except Exception as e:
                    logger.warning(f"Error processing hourly forecast hour {i}: {str(e)}")
                    continue

            mapped_data = {
                "properties": {
                    "updated": datetime.now(timezone.utc).isoformat(),
                    "units": {
                        "temperature": (
                            "F"
                            if (
                                "fahrenheit" in str(hourly_units).lower()
                                or "°f" in str(hourly_units).lower()
                            )
                            else "C"
                        ),
                        "windSpeed": hourly_units.get("wind_speed_10m", "mph"),
                        "precipitation": hourly_units.get("precipitation", "in"),
                    },
                    "forecastGenerator": "Open-Meteo API",
                    "generatedAt": datetime.now(timezone.utc).isoformat(),
                    "periods": periods,
                }
            }

            logger.debug(f"Mapped hourly forecast with {len(periods)} periods")
            return mapped_data

        except Exception as e:
            logger.error(f"Error mapping hourly forecast: {str(e)}")
            raise ValueError(f"Failed to map hourly forecast: {str(e)}")

    def _get_temperature_unit_code(self, unit_str: str) -> str:
        """Convert temperature unit string to WMO unit code."""
        if "fahrenheit" in unit_str.lower() or "°f" in unit_str.lower():
            return "wmoUnit:degF"
        else:
            return "wmoUnit:degC"

    def _get_wind_speed_unit_code(self, unit_str: str) -> str:
        """Convert wind speed unit string to WMO unit code."""
        unit_lower = unit_str.lower()
        if "mph" in unit_lower:
            return "wmoUnit:mi_h-1"
        elif "kmh" in unit_lower or "km/h" in unit_lower:
            return "wmoUnit:km_h-1"
        elif "m/s" in unit_lower or "ms" in unit_lower:
            return "wmoUnit:m_s-1"
        elif "kn" in unit_lower or "knot" in unit_lower:
            return "wmoUnit:kn"
        else:
            return "wmoUnit:m_s-1"  # Default

    def _calculate_dewpoint(
        self, temperature: Optional[float], humidity: Optional[float]
    ) -> Optional[float]:
        """Calculate dewpoint from temperature and relative humidity."""
        if temperature is None or humidity is None:
            return None

        try:
            # Magnus formula approximation
            a = 17.27
            b = 237.7

            # Convert Fahrenheit to Celsius if needed
            temp_c = temperature
            if temperature > 50:  # Assume Fahrenheit if > 50
                temp_c = (temperature - 32) * 5 / 9

            alpha = ((a * temp_c) / (b + temp_c)) + math.log(humidity / 100.0)
            dewpoint_c = (b * alpha) / (a - alpha)

            # Convert back to Fahrenheit if original was Fahrenheit
            if temperature > 50:
                return dewpoint_c * 9 / 5 + 32
            else:
                return dewpoint_c

        except Exception:
            return None

    def _cloud_cover_to_amount(self, cloud_cover: Optional[float]) -> str:
        """Convert cloud cover percentage to NWS cloud amount description."""
        if cloud_cover is None:
            return "UNK"

        if cloud_cover <= 12.5:
            return "CLR"  # Clear
        elif cloud_cover <= 25:
            return "FEW"  # Few
        elif cloud_cover <= 50:
            return "SCT"  # Scattered
        elif cloud_cover <= 87.5:
            return "BKN"  # Broken
        else:
            return "OVC"  # Overcast

    def _degrees_to_direction(self, degrees: Optional[float]) -> str:
        """Convert wind direction in degrees to cardinal direction."""
        if degrees is None:
            return "VAR"

        directions = [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]

        # Normalize degrees to 0-360
        degrees = degrees % 360

        # Calculate index (16 directions, so 360/16 = 22.5 degrees per direction)
        index = int((degrees + 11.25) / 22.5) % 16

        return directions[index]

    def _create_detailed_forecast(
        self, daily: Dict[str, Any], daily_units: Dict[str, Any], index: int, is_daytime: bool
    ) -> str:
        """Create a detailed forecast description."""
        try:
            weather_code = (
                daily.get("weather_code", [0])[index]
                if index < len(daily.get("weather_code", []))
                else 0
            )
            description = OpenMeteoApiClient.get_weather_description(weather_code)

            if is_daytime:
                temp = daily.get("temperature_2m_max", [None])[index]
            else:
                temp = daily.get("temperature_2m_min", [None])[index]

            wind_speed = daily.get("wind_speed_10m_max", [None])[index]
            wind_unit = daily_units.get("wind_speed_10m_max", "mph")
            wind_dir = daily.get("wind_direction_10m_dominant", [None])[index]
            precip = daily.get("precipitation_sum", [None])[index]
            precip_unit = daily_units.get("precipitation_sum", "in")

            parts = [description]

            if temp is not None:
                temp_str = "high" if is_daytime else "low"
                parts.append(f"with a {temp_str} near {int(temp)}")

            if wind_speed is not None and wind_speed > 0:
                wind_dir_str = self._degrees_to_direction(wind_dir) if wind_dir is not None else ""
                parts.append(f"Wind {wind_dir_str} {wind_speed:.0f} {wind_unit}")

            if precip is not None and precip > 0:
                parts.append(f"Precipitation {precip:.2f} {precip_unit}")

            return ". ".join(parts) + "."

        except Exception as e:
            logger.warning(f"Error creating detailed forecast: {str(e)}")
            return "Weather conditions expected."
