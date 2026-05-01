"""
Data mapper for Open-Meteo API responses.

This module provides functionality to transform Open-Meteo API responses
into the internal data format expected by WeatherService and UI components.
"""

import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from .models import HourlyUVIndex
from .openmeteo_client import OpenMeteoApiClient
from .openmeteo_forecast_mapper import (
    map_forecast as map_openmeteo_forecast,
    map_hourly_forecast as map_openmeteo_hourly_forecast,
)
from .utils import TemperatureUnit, calculate_dewpoint

logger = logging.getLogger(__name__)


def _parse_openmeteo_datetime(
    datetime_str: str | None, utc_offset_seconds: int | None
) -> str | None:
    """
    Parse a datetime string from Open-Meteo and convert to UTC ISO format.

    When Open-Meteo uses timezone="auto", it returns naive datetime strings
    in the local timezone. We need to convert these to UTC for consistent storage.

    Args:
    ----
        datetime_str: ISO format datetime string from Open-Meteo (naive, in local time)
        utc_offset_seconds: UTC offset in seconds from the Open-Meteo response

    Returns:
    -------
        ISO format datetime string in UTC with timezone info, or None if parsing fails

    """
    if not datetime_str or utc_offset_seconds is None:
        return datetime_str

    try:
        # Parse the naive datetime string
        dt_naive = datetime.fromisoformat(datetime_str.replace("Z", ""))

        # Create timezone object from offset
        tz = timezone(timedelta(seconds=utc_offset_seconds))

        # Attach the timezone to make it aware
        dt_aware = dt_naive.replace(tzinfo=tz)

        # Convert to UTC and return as ISO string
        dt_utc = dt_aware.astimezone(UTC)

        logger.info(
            f"Converted Open-Meteo datetime: '{datetime_str}' "
            f"(offset={utc_offset_seconds}s) -> UTC: '{dt_utc.isoformat()}'"
        )
        return dt_utc.isoformat()
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to parse Open-Meteo datetime '{datetime_str}': {e}")
        return datetime_str


class OpenMeteoMapper:
    """Maps Open-Meteo API responses to internal data format."""

    def __init__(self):
        """Initialize the mapper."""

    def map_current_conditions(self, openmeteo_data: dict[str, Any]) -> dict[str, Any]:
        """
        Map Open-Meteo current weather data to NWS-compatible format.

        Args:
        ----
            openmeteo_data: Raw response from Open-Meteo current weather API

        Returns:
        -------
            Dictionary in NWS current conditions format

        """
        try:
            current = openmeteo_data.get("current", {})
            current_units = openmeteo_data.get("current_units", {})
            daily = openmeteo_data.get("daily", {})
            uv_index_values = daily.get("uv_index_max") if daily else None
            uv_index_value = uv_index_values[0] if uv_index_values else None

            # Extract timezone offset for proper datetime conversion
            utc_offset_seconds = openmeteo_data.get("utc_offset_seconds")

            logger.debug(f"Open-Meteo current data keys: {list(current.keys())}")
            logger.debug(f"Open-Meteo current units: {current_units}")
            logger.debug(f"Open-Meteo daily data keys: {list(daily.keys()) if daily else 'None'}")
            logger.debug(f"Open-Meteo UTC offset: {utc_offset_seconds} seconds")

            # Map the data to NWS-like structure
            temperature_unit = current_units.get("temperature_2m", "°C")

            mapped_data = {
                "properties": {
                    "@id": f"open-meteo-current-{datetime.now(UTC).isoformat()}",
                    "timestamp": _parse_openmeteo_datetime(current.get("time"), utc_offset_seconds)
                    or datetime.now(UTC).isoformat(),
                    "temperature": {
                        "value": current.get("temperature_2m"),
                        "unitCode": self._get_temperature_unit_code(
                            current_units.get("temperature_2m", "°F")
                        ),
                        "qualityControl": "qc:V",
                    },
                    "dewpoint": {
                        "value": self._calculate_dewpoint(
                            current.get("temperature_2m"),
                            current.get("relative_humidity_2m"),
                            temperature_unit,
                        ),
                        "unitCode": self._get_temperature_unit_code(temperature_unit),
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
                        "value": (
                            current.get("pressure_msl") * 100
                            if current.get("pressure_msl") is not None
                            else None
                        ),
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
                    "uvIndex": {
                        "value": uv_index_value,
                        "unitCode": "unit:dimensionless",
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
                    # Sunrise/sunset from daily data (today's values)
                    # Keep these in local time (don't convert to UTC) since they're displayed in local time
                    "sunrise": daily.get("sunrise", [None])[0]
                    if daily and daily.get("sunrise")
                    else None,
                    "sunset": daily.get("sunset", [None])[0]
                    if daily and daily.get("sunset")
                    else None,
                }
            }

            logger.debug(f"Mapped current conditions: {mapped_data}")
            return mapped_data

        except Exception as e:
            logger.error(f"Error mapping current conditions: {str(e)}")
            raise ValueError(f"Failed to map current conditions: {str(e)}") from e

    def map_forecast(self, openmeteo_data: dict[str, Any]) -> dict[str, Any]:
        """Map Open-Meteo daily forecast data to NWS-compatible format."""
        return map_openmeteo_forecast(self, openmeteo_data, _parse_openmeteo_datetime)

    def map_hourly_forecast(self, openmeteo_data: dict[str, Any]) -> dict[str, Any]:
        """Map Open-Meteo hourly forecast data to NWS-compatible format."""
        return map_openmeteo_hourly_forecast(self, openmeteo_data, _parse_openmeteo_datetime)

    def _get_temperature_unit_code(self, unit_str: str) -> str:
        """Convert temperature unit string to WMO unit code."""
        if "fahrenheit" in unit_str.lower() or "°f" in unit_str.lower():
            return "wmoUnit:degF"
        return "wmoUnit:degC"

    def _get_wind_speed_unit_code(self, unit_str: str) -> str:
        """Convert wind speed unit string to WMO unit code."""
        unit_lower = unit_str.lower()
        if "mph" in unit_lower:
            return "wmoUnit:mi_h-1"
        if "kmh" in unit_lower or "km/h" in unit_lower:
            return "wmoUnit:km_h-1"
        if "m/s" in unit_lower or "ms" in unit_lower:
            return "wmoUnit:m_s-1"
        if "kn" in unit_lower or "knot" in unit_lower:
            return "wmoUnit:kn"
        return "wmoUnit:m_s-1"  # Default

    def _calculate_dewpoint(
        self,
        temperature: float | None,
        humidity: float | None,
        unit_hint: str | TemperatureUnit | None = None,
    ) -> float | None:
        """Calculate dewpoint from temperature and relative humidity."""
        if temperature is None or humidity is None:
            return None

        try:
            return calculate_dewpoint(
                temperature,
                humidity,
                unit=unit_hint or TemperatureUnit.CELSIUS,
            )
        except Exception:
            logger.debug("Failed to calculate dewpoint from Open-Meteo data", exc_info=True)
            return None

    def _cloud_cover_to_amount(self, cloud_cover: float | None) -> str:
        """Convert cloud cover percentage to NWS cloud amount description."""
        if cloud_cover is None:
            return "UNK"

        if cloud_cover <= 12.5:
            return "CLR"  # Clear
        if cloud_cover <= 25:
            return "FEW"  # Few
        if cloud_cover <= 50:
            return "SCT"  # Scattered
        if cloud_cover <= 87.5:
            return "BKN"  # Broken
        return "OVC"  # Overcast

    def _degrees_to_direction(self, degrees: float | None) -> str:
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
        self, daily: dict[str, Any], daily_units: dict[str, Any], index: int, is_daytime: bool
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

    def map_hourly_uv_index(self, openmeteo_data: dict[str, Any]) -> list[HourlyUVIndex]:
        """
        Map Open-Meteo hourly UV index data to HourlyUVIndex objects.

        Args:
        ----
            openmeteo_data: Raw response from Open-Meteo hourly API

        Returns:
        -------
            List of HourlyUVIndex objects (empty list if no data available)

        """
        try:
            hourly = openmeteo_data.get("hourly", {})
            utc_offset_seconds = openmeteo_data.get("utc_offset_seconds")

            if not hourly:
                logger.debug("No hourly data in Open-Meteo response")
                return []

            times = hourly.get("time", [])
            uv_indices = hourly.get("uv_index", [])

            if not times or not uv_indices:
                logger.debug("No UV index data in hourly forecast")
                return []

            hourly_uv_list: list[HourlyUVIndex] = []

            for i, time_str in enumerate(times):
                if i >= len(uv_indices):
                    break

                uv_value = uv_indices[i]
                if uv_value is None:
                    continue

                try:
                    # Parse the time - convert from local time to UTC
                    time_str_utc = _parse_openmeteo_datetime(time_str, utc_offset_seconds)
                    if time_str_utc:
                        time_obj = datetime.fromisoformat(time_str_utc)
                    else:
                        # Fallback to treating as UTC if parsing fails
                        time_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))

                    # Map UV index to category
                    category = self._get_uv_category(uv_value)

                    hourly_uv = HourlyUVIndex(
                        timestamp=time_obj,
                        uv_index=float(uv_value),
                        category=category,
                    )
                    hourly_uv_list.append(hourly_uv)

                except Exception as e:
                    logger.warning(f"Error processing hourly UV entry {i}: {str(e)}")
                    continue

            logger.debug(f"Mapped {len(hourly_uv_list)} hourly UV index entries")
            return hourly_uv_list

        except Exception as e:
            logger.error(f"Error mapping hourly UV index: {str(e)}")
            return []

    def _get_uv_category(self, uv_index: float) -> str:
        """
        Map UV index value to EPA/WHO category.

        Categories based on EPA/WHO standard:
        - Low: 0-2
        - Moderate: 3-5
        - High: 6-7
        - Very High: 8-10
        - Extreme: 11+

        Args:
        ----
            uv_index: UV index value (typically 0-15, can be higher)

        Returns:
        -------
            Category string

        """
        if uv_index <= 2:
            return "Low"
        if uv_index <= 5:
            return "Moderate"
        if uv_index <= 7:
            return "High"
        if uv_index <= 10:
            return "Very High"
        return "Extreme"
