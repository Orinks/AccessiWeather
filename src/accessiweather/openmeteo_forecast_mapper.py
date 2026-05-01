"""Forecast mapping sections for Open-Meteo responses."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from .openmeteo_client import OpenMeteoApiClient

logger = logging.getLogger(__name__)


def map_forecast(
    mapper: Any, openmeteo_data: dict[str, Any], parse_datetime: Any
) -> dict[str, Any]:
    """Map Open-Meteo daily forecast data to NWS-compatible format."""
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
                date_str_utc = parse_datetime(date_str, utc_offset_seconds)
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
                        int(temp_max[i]) if i < len(temp_max) and temp_max[i] is not None else None
                    ),
                    "temperatureUnit": (
                        "F" if "°f" in daily_units.get("temperature_2m_max", "°F").lower() else "C"
                    ),
                    "temperatureTrend": None,
                    "windSpeed": f"{daily.get('wind_speed_10m_max', [None])[i] or 0} {daily_units.get('wind_speed_10m_max', 'mph')}",
                    "windDirection": mapper._degrees_to_direction(
                        daily.get("wind_direction_10m_dominant", [None])[i]
                    ),
                    "icon": f"https://open-meteo.com/images/weather/{weather_codes[i] if i < len(weather_codes) else 0}.png",
                    "shortForecast": OpenMeteoApiClient.get_weather_description(
                        weather_codes[i] if i < len(weather_codes) else 0
                    ),
                    "detailedForecast": mapper._create_detailed_forecast(
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
                        int(temp_min[i]) if i < len(temp_min) and temp_min[i] is not None else None
                    ),
                    "temperatureUnit": (
                        "F" if "°f" in daily_units.get("temperature_2m_min", "°F").lower() else "C"
                    ),
                    "temperatureTrend": None,
                    "windSpeed": f"{daily.get('wind_speed_10m_max', [None])[i] or 0} {daily_units.get('wind_speed_10m_max', 'mph')}",
                    "windDirection": mapper._degrees_to_direction(
                        daily.get("wind_direction_10m_dominant", [None])[i]
                    ),
                    "icon": f"https://open-meteo.com/images/weather/{weather_codes[i] if i < len(weather_codes) else 0}.png",
                    "shortForecast": OpenMeteoApiClient.get_weather_description(
                        weather_codes[i] if i < len(weather_codes) else 0
                    ),
                    "detailedForecast": mapper._create_detailed_forecast(
                        daily, daily_units, i, False
                    ),
                }

                periods.extend([day_period, night_period])

            except Exception as e:
                logger.warning(f"Error processing forecast day {i}: {str(e)}")
                continue

        # Mirror NWS high/low pairing so display layers can render day highs
        # alongside the following overnight low.
        for i, period in enumerate(periods):
            if period.get("isDaytime") and i + 1 < len(periods):
                next_period = periods[i + 1]
                if not next_period.get("isDaytime"):
                    night_temperature = next_period.get("temperature")
                    if night_temperature is not None:
                        period["temperature_low"] = night_temperature

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


def map_hourly_forecast(
    mapper: Any, openmeteo_data: dict[str, Any], parse_datetime: Any
) -> dict[str, Any]:
    """Map Open-Meteo hourly forecast data to NWS-compatible format."""
    try:
        hourly = openmeteo_data.get("hourly", {})
        hourly_units = openmeteo_data.get("hourly_units", {})
        utc_offset_seconds = openmeteo_data.get("utc_offset_seconds")

        if not hourly:
            return {"properties": {"periods": []}}

        periods = []
        times = hourly.get("time", [])
        temperatures = hourly.get("temperature_2m", [])
        humidities = hourly.get("relative_humidity_2m", [])
        dew_points = hourly.get("dew_point_2m", [])
        weather_codes = hourly.get("weather_code", [])
        wind_speeds = hourly.get("wind_speed_10m", [])
        wind_directions = hourly.get("wind_direction_10m", [])
        is_day = hourly.get("is_day", [])

        for i, time_str in enumerate(times):
            try:
                # Parse the time - convert from local time to UTC
                time_str_utc = parse_datetime(time_str, utc_offset_seconds)
                if time_str_utc:
                    time_obj = datetime.fromisoformat(time_str_utc)
                else:
                    # Fallback to treating as UTC if parsing fails
                    time_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                end_time = time_obj.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

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
                    "relativeHumidity": {
                        "value": (
                            humidities[i]
                            if i < len(humidities) and humidities[i] is not None
                            else None
                        ),
                        "unitCode": "wmoUnit:percent",
                        "qualityControl": "qc:V",
                    },
                    "dewpoint": {
                        "value": (
                            dew_points[i]
                            if i < len(dew_points) and dew_points[i] is not None
                            else mapper._calculate_dewpoint(
                                temperatures[i] if i < len(temperatures) else None,
                                humidities[i] if i < len(humidities) else None,
                                hourly_units.get("temperature_2m", "°F"),
                            )
                        ),
                        "unitCode": mapper._get_temperature_unit_code(
                            hourly_units.get("temperature_2m", "°F")
                        ),
                        "qualityControl": "qc:V",
                    },
                    "windSpeed": f"{wind_speeds[i] if i < len(wind_speeds) and wind_speeds[i] is not None else 0} {hourly_units.get('wind_speed_10m', 'mph')}",
                    "windDirection": mapper._degrees_to_direction(
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
