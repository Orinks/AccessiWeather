"""
Data mapper for Open-Meteo API responses.

This module provides functionality to transform Open-Meteo API responses
into the internal data format expected by WeatherService and UI components.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

# For Python 3.10 compatibility
try:
    from datetime import UTC
except ImportError:
    UTC = UTC

from .openmeteo_client import OpenMeteoApiClient
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
        """
        Map Open-Meteo daily forecast data to NWS-compatible format.

        Args:
        ----
            openmeteo_data: Raw response from Open-Meteo forecast API

        Returns:
        -------
            Dictionary in NWS forecast format

        """
        try:
            daily = openmeteo_data.get("daily", {})
            daily_units = openmeteo_data.get("daily_units", {})
            utc_offset_seconds = openmeteo_data.get("utc_offset_seconds")

            logger.debug(
                "Open-Meteo forecast raw daily keys=%s day_count=%s",
                list(daily.keys()) if isinstance(daily, dict) else None,
                len(daily.get("time", [])) if isinstance(daily, dict) else 0,
            )
            logger.debug(f"Open-Meteo forecast UTC offset: {utc_offset_seconds} seconds")

            if not daily:
                return {"properties": {"periods": []}}

            periods = []
            dates = daily.get("time", [])
            weather_codes = daily.get("weather_code", [])
            temp_max = daily.get("temperature_2m_max", [])
            temp_min = daily.get("temperature_2m_min", [])

            for i, date_str in enumerate(dates):
                try:
                    # Parse the date - convert from local time to UTC
                    date_str_utc = _parse_openmeteo_datetime(date_str, utc_offset_seconds)
                    if date_str_utc:
                        date_obj = datetime.fromisoformat(date_str_utc)
                    else:
                        # Fallback to treating as UTC if parsing fails
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
                    "updated": datetime.now(UTC).isoformat(),
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
                    "generatedAt": datetime.now(UTC).isoformat(),
                    "periods": periods,
                }
            }

            logger.debug(f"Mapped forecast with {len(periods)} periods")
            return mapped_data

        except Exception as e:
            logger.error(f"Error mapping forecast: {str(e)}")
            raise ValueError(f"Failed to map forecast: {str(e)}") from e

    def map_hourly_forecast(self, openmeteo_data: dict[str, Any]) -> dict[str, Any]:
        """
        Map Open-Meteo hourly forecast data to NWS-compatible format.

        Args:
        ----
            openmeteo_data: Raw response from Open-Meteo hourly forecast API

        Returns:
        -------
            Dictionary in NWS hourly forecast format

        """
        try:
            hourly = openmeteo_data.get("hourly", {})
            hourly_units = openmeteo_data.get("hourly_units", {})
            utc_offset_seconds = openmeteo_data.get("utc_offset_seconds")

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
                    # Parse the time - convert from local time to UTC
                    time_str_utc = _parse_openmeteo_datetime(time_str, utc_offset_seconds)
                    if time_str_utc:
                        time_obj = datetime.fromisoformat(time_str_utc)
                    else:
                        # Fallback to treating as UTC if parsing fails
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
                    "updated": datetime.now(UTC).isoformat(),
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
                    "generatedAt": datetime.now(UTC).isoformat(),
                    "periods": periods,
                }
            }

            logger.debug(f"Mapped hourly forecast with {len(periods)} periods")
            return mapped_data

        except Exception as e:
            logger.error(f"Error mapping hourly forecast: {str(e)}")
            raise ValueError(f"Failed to map hourly forecast: {str(e)}") from e

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
