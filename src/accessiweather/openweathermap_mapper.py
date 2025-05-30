"""Data mapping functions for OpenWeatherMap API responses.

This module provides functions to transform OpenWeatherMap API response data
into the standardized format expected by the AccessiWeather application.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def map_current_conditions(owm_data: Dict[str, Any]) -> Dict[str, Any]:
    """Map OpenWeatherMap current weather data to AccessiWeather format.

    Args:
        owm_data: Raw OpenWeatherMap current weather response

    Returns:
        Dictionary containing current conditions in AccessiWeather format
    """
    try:
        # Extract main weather data
        main = owm_data.get("main", {})
        weather = owm_data.get("weather", [{}])[0]
        wind = owm_data.get("wind", {})
        clouds = owm_data.get("clouds", {})
        sys = owm_data.get("sys", {})
        coord = owm_data.get("coord", {})

        # Map to AccessiWeather format
        mapped_data = {
            "location": {
                "name": owm_data.get("name", "Unknown"),
                "lat": coord.get("lat"),
                "lon": coord.get("lon"),
                "country": sys.get("country"),
                "timezone": owm_data.get("timezone", 0),  # Offset in seconds
            },
            "current": {
                "temperature": main.get("temp"),
                "feels_like": main.get("feels_like"),
                "humidity": main.get("humidity"),
                "pressure": main.get("pressure"),
                "visibility": owm_data.get("visibility"),  # In meters
                "uv_index": None,  # Not available in current weather endpoint
                "condition": weather.get("main", "Unknown"),
                "description": weather.get("description", ""),
                "icon": weather.get("icon"),
                "wind": {
                    "speed": wind.get("speed"),
                    "direction": wind.get("deg"),
                    "gust": wind.get("gust"),
                },
                "clouds": clouds.get("all", 0),  # Cloud coverage percentage
                "last_updated": datetime.fromtimestamp(
                    owm_data.get("dt", 0), tz=timezone.utc
                ).isoformat(),
            },
        }

        logger.debug(f"Mapped current conditions for {mapped_data['location']['name']}")
        return mapped_data

    except Exception as e:
        logger.error(f"Error mapping current conditions: {str(e)}")
        raise ValueError(f"Failed to map current conditions data: {str(e)}") from e


def map_forecast(owm_data: Dict[str, Any], days: int = 7) -> Dict[str, Any]:
    """Map OpenWeatherMap One Call daily forecast data to AccessiWeather format.

    Args:
        owm_data: Raw OpenWeatherMap One Call response
        days: Number of days to include in forecast

    Returns:
        Dictionary containing forecast data in AccessiWeather format
    """
    try:
        daily_data = owm_data.get("daily", [])
        current_data = owm_data.get("current", {})

        # Limit to requested number of days
        daily_data = daily_data[:days]

        forecast_days = []
        for day_data in daily_data:
            temp = day_data.get("temp", {})
            weather = day_data.get("weather", [{}])[0]
            wind = day_data.get("wind_speed", 0)
            wind_deg = day_data.get("wind_deg", 0)

            forecast_day = {
                "date": datetime.fromtimestamp(day_data.get("dt", 0), tz=timezone.utc)
                .date()
                .isoformat(),
                "temperature": {
                    "high": temp.get("max"),
                    "low": temp.get("min"),
                    "morning": temp.get("morn"),
                    "day": temp.get("day"),
                    "evening": temp.get("eve"),
                    "night": temp.get("night"),
                },
                "condition": weather.get("main", "Unknown"),
                "description": weather.get("description", ""),
                "icon": weather.get("icon"),
                "humidity": day_data.get("humidity"),
                "pressure": day_data.get("pressure"),
                "wind": {
                    "speed": wind,
                    "direction": wind_deg,
                    "gust": day_data.get("wind_gust"),
                },
                "clouds": day_data.get("clouds", 0),
                "uv_index": day_data.get("uvi"),
                "pop": day_data.get("pop", 0),  # Probability of precipitation
                "rain": day_data.get("rain", {}).get("1h", 0) if day_data.get("rain") else 0,
                "snow": day_data.get("snow", {}).get("1h", 0) if day_data.get("snow") else 0,
            }
            forecast_days.append(forecast_day)

        mapped_data = {
            "location": {
                "lat": owm_data.get("lat"),
                "lon": owm_data.get("lon"),
                "timezone": owm_data.get("timezone"),
                "timezone_offset": owm_data.get("timezone_offset", 0),
            },
            "forecast": {
                "days": forecast_days,
                "generated_at": datetime.fromtimestamp(
                    current_data.get("dt", 0), tz=timezone.utc
                ).isoformat(),
            },
        }

        logger.debug(f"Mapped {len(forecast_days)} day forecast")
        return mapped_data

    except Exception as e:
        logger.error(f"Error mapping forecast data: {str(e)}")
        raise ValueError(f"Failed to map forecast data: {str(e)}") from e


def map_hourly_forecast(owm_data: Dict[str, Any], hours: int = 48) -> Dict[str, Any]:
    """Map OpenWeatherMap One Call hourly forecast data to AccessiWeather format.

    Args:
        owm_data: Raw OpenWeatherMap One Call response
        hours: Number of hours to include in forecast

    Returns:
        Dictionary containing hourly forecast data in AccessiWeather format
    """
    try:
        hourly_data = owm_data.get("hourly", [])
        current_data = owm_data.get("current", {})

        # Limit to requested number of hours
        hourly_data = hourly_data[:hours]

        forecast_hours = []
        for hour_data in hourly_data:
            weather = hour_data.get("weather", [{}])[0]
            wind = hour_data.get("wind_speed", 0)
            wind_deg = hour_data.get("wind_deg", 0)

            forecast_hour = {
                "datetime": datetime.fromtimestamp(
                    hour_data.get("dt", 0), tz=timezone.utc
                ).isoformat(),
                "temperature": hour_data.get("temp"),
                "feels_like": hour_data.get("feels_like"),
                "condition": weather.get("main", "Unknown"),
                "description": weather.get("description", ""),
                "icon": weather.get("icon"),
                "humidity": hour_data.get("humidity"),
                "pressure": hour_data.get("pressure"),
                "wind": {
                    "speed": wind,
                    "direction": wind_deg,
                    "gust": hour_data.get("wind_gust"),
                },
                "clouds": hour_data.get("clouds", 0),
                "visibility": hour_data.get("visibility"),
                "uv_index": hour_data.get("uvi"),
                "pop": hour_data.get("pop", 0),  # Probability of precipitation
                "rain": hour_data.get("rain", {}).get("1h", 0) if hour_data.get("rain") else 0,
                "snow": hour_data.get("snow", {}).get("1h", 0) if hour_data.get("snow") else 0,
            }
            forecast_hours.append(forecast_hour)

        mapped_data = {
            "location": {
                "lat": owm_data.get("lat"),
                "lon": owm_data.get("lon"),
                "timezone": owm_data.get("timezone"),
                "timezone_offset": owm_data.get("timezone_offset", 0),
            },
            "hourly_forecast": {
                "hours": forecast_hours,
                "generated_at": datetime.fromtimestamp(
                    current_data.get("dt", 0), tz=timezone.utc
                ).isoformat(),
            },
        }

        logger.debug(f"Mapped {len(forecast_hours)} hour forecast")
        return mapped_data

    except Exception as e:
        logger.error(f"Error mapping hourly forecast data: {str(e)}")
        raise ValueError(f"Failed to map hourly forecast data: {str(e)}") from e


def map_alerts(owm_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map OpenWeatherMap One Call alerts data to AccessiWeather format.

    Args:
        owm_data: Raw OpenWeatherMap One Call response

    Returns:
        List of dictionaries containing weather alerts in AccessiWeather format
    """
    try:
        alerts_data = owm_data.get("alerts", [])

        mapped_alerts = []
        for alert_data in alerts_data:
            mapped_alert = {
                "id": f"owm_{alert_data.get('start', 0)}_{hash(alert_data.get('event', ''))}",
                "title": alert_data.get("event", "Weather Alert"),
                "description": alert_data.get("description", ""),
                "sender": alert_data.get("sender_name", "OpenWeatherMap"),
                "start": datetime.fromtimestamp(
                    alert_data.get("start", 0), tz=timezone.utc
                ).isoformat(),
                "end": datetime.fromtimestamp(
                    alert_data.get("end", 0), tz=timezone.utc
                ).isoformat(),
                "tags": alert_data.get("tags", []),
                "severity": _map_alert_severity(alert_data.get("tags", [])),
                "urgency": "unknown",  # OpenWeatherMap doesn't provide urgency
                "certainty": "unknown",  # OpenWeatherMap doesn't provide certainty
            }
            mapped_alerts.append(mapped_alert)

        logger.debug(f"Mapped {len(mapped_alerts)} weather alerts")
        return mapped_alerts

    except Exception as e:
        logger.error(f"Error mapping alerts data: {str(e)}")
        raise ValueError(f"Failed to map alerts data: {str(e)}") from e


def _map_alert_severity(tags: List[str]) -> str:
    """Map OpenWeatherMap alert tags to severity level.

    Args:
        tags: List of alert tags from OpenWeatherMap

    Returns:
        Severity level string
    """
    # OpenWeatherMap doesn't provide explicit severity, so we infer from tags
    severe_keywords = ["extreme", "severe", "major", "dangerous"]
    moderate_keywords = ["moderate", "watch", "advisory"]

    tags_lower = [tag.lower() for tag in tags]

    for keyword in severe_keywords:
        if any(keyword in tag for tag in tags_lower):
            return "severe"

    for keyword in moderate_keywords:
        if any(keyword in tag for tag in tags_lower):
            return "moderate"

    return "minor"
