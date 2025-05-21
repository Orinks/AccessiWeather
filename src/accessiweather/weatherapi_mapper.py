"""Data mapping module for WeatherAPI.com responses.

This module provides functions to map WeatherAPI.com response data to the format
expected by the AccessiWeather UI components.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def map_current_conditions(api_response: Dict[str, Any]) -> Dict[str, Any]:
    """Map current conditions data from WeatherAPI.com format to internal format.

    Args:
        api_response: The WeatherAPI.com response data

    Returns:
        Dict containing mapped current conditions data
    """
    if not api_response or "current" not in api_response:
        logger.warning("Invalid or empty API response for current conditions")
        return {}

    current = api_response.get("current", {})
    condition = current.get("condition", {})

    # Map the data to the format expected by the UI
    return {
        "temperature": current.get("temp_f"),
        "temperature_c": current.get("temp_c"),
        "condition": condition.get("text"),
        "condition_icon": condition.get("icon"),
        "condition_code": condition.get("code"),
        "humidity": current.get("humidity"),
        "wind_speed": current.get("wind_mph"),
        "wind_speed_kph": current.get("wind_kph"),
        "wind_direction": current.get("wind_dir"),
        "wind_degree": current.get("wind_degree"),
        "pressure": current.get("pressure_in"),
        "pressure_mb": current.get("pressure_mb"),
        "precipitation": current.get("precip_in"),
        "precipitation_mm": current.get("precip_mm"),
        "feelslike": current.get("feelslike_f"),
        "feelslike_c": current.get("feelslike_c"),
        "visibility": current.get("vis_miles"),
        "visibility_km": current.get("vis_km"),
        "uv_index": current.get("uv"),
        "gust": current.get("gust_mph"),
        "gust_kph": current.get("gust_kph"),
        "is_day": current.get("is_day"),
        "last_updated": current.get("last_updated"),
    }


def map_forecast(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map forecast data from WeatherAPI.com format to internal format.

    Args:
        api_response: The WeatherAPI.com response data

    Returns:
        List of dicts containing mapped forecast data for each day
    """
    if not api_response or "forecast" not in api_response:
        logger.warning("Invalid or empty API response for forecast")
        return []

    forecast_days = []
    for day in api_response.get("forecast", {}).get("forecastday", []):
        day_data = day.get("day", {})
        condition = day_data.get("condition", {})

        forecast_days.append(
            {
                "date": day.get("date"),
                "date_epoch": day.get("date_epoch"),
                "high": day_data.get("maxtemp_f"),
                "high_c": day_data.get("maxtemp_c"),
                "low": day_data.get("mintemp_f"),
                "low_c": day_data.get("mintemp_c"),
                "condition": condition.get("text"),
                "condition_icon": condition.get("icon"),
                "condition_code": condition.get("code"),
                "precipitation_probability": day_data.get("daily_chance_of_rain"),
                "snow_probability": day_data.get("daily_chance_of_snow"),
                "precipitation_amount": day_data.get("totalprecip_in"),
                "precipitation_amount_mm": day_data.get("totalprecip_mm"),
                "snow_amount_cm": day_data.get("totalsnow_cm"),
                "max_wind_speed": day_data.get("maxwind_mph"),
                "max_wind_speed_kph": day_data.get("maxwind_kph"),
                "avg_humidity": day_data.get("avghumidity"),
                "avg_visibility": day_data.get("avgvis_miles"),
                "avg_visibility_km": day_data.get("avgvis_km"),
                "uv_index": day_data.get("uv"),
                "will_it_rain": day_data.get("daily_will_it_rain"),
                "will_it_snow": day_data.get("daily_will_it_snow"),
            }
        )

    return forecast_days


def map_hourly_forecast(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map hourly forecast data from WeatherAPI.com format to internal format.

    Args:
        api_response: The WeatherAPI.com response data

    Returns:
        List of dicts containing mapped hourly forecast data
    """
    if not api_response or "forecast" not in api_response:
        logger.warning("Invalid or empty API response for hourly forecast")
        return []

    hourly_forecast = []
    for day in api_response.get("forecast", {}).get("forecastday", []):
        for hour in day.get("hour", []):
            condition = hour.get("condition", {})

            hourly_forecast.append(
                {
                    "time": hour.get("time"),
                    "time_epoch": hour.get("time_epoch"),
                    "temperature": hour.get("temp_f"),
                    "temperature_c": hour.get("temp_c"),
                    "condition": condition.get("text"),
                    "condition_icon": condition.get("icon"),
                    "condition_code": condition.get("code"),
                    "wind_speed": hour.get("wind_mph"),
                    "wind_speed_kph": hour.get("wind_kph"),
                    "wind_direction": hour.get("wind_dir"),
                    "wind_degree": hour.get("wind_degree"),
                    "pressure": hour.get("pressure_in"),
                    "pressure_mb": hour.get("pressure_mb"),
                    "precipitation": hour.get("precip_in"),
                    "precipitation_mm": hour.get("precip_mm"),
                    "humidity": hour.get("humidity"),
                    "cloud": hour.get("cloud"),
                    "feelslike": hour.get("feelslike_f"),
                    "feelslike_c": hour.get("feelslike_c"),
                    "windchill": hour.get("windchill_f"),
                    "windchill_c": hour.get("windchill_c"),
                    "heatindex": hour.get("heatindex_f"),
                    "heatindex_c": hour.get("heatindex_c"),
                    "dewpoint": hour.get("dewpoint_f"),
                    "dewpoint_c": hour.get("dewpoint_c"),
                    "will_it_rain": hour.get("will_it_rain"),
                    "chance_of_rain": hour.get("chance_of_rain"),
                    "will_it_snow": hour.get("will_it_snow"),
                    "chance_of_snow": hour.get("chance_of_snow"),
                    "visibility": hour.get("vis_miles"),
                    "visibility_km": hour.get("vis_km"),
                    "gust": hour.get("gust_mph"),
                    "gust_kph": hour.get("gust_kph"),
                    "uv_index": hour.get("uv"),
                    "is_day": hour.get("is_day"),
                }
            )

    return hourly_forecast


def map_alerts(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map alerts data from WeatherAPI.com format to internal format.

    Args:
        api_response: The WeatherAPI.com response data

    Returns:
        List of dicts containing mapped alerts data
    """
    if not api_response or "alerts" not in api_response:
        logger.debug("No alerts in API response")
        return []

    alerts = []
    for alert in api_response.get("alerts", {}).get("alert", []):
        alerts.append(
            {
                "headline": alert.get("headline"),
                "severity": alert.get("severity"),
                "urgency": alert.get("urgency"),
                "areas": alert.get("areas"),
                "category": alert.get("category"),
                "certainty": alert.get("certainty"),
                "event": alert.get("event"),
                "note": alert.get("note"),
                "effective": alert.get("effective"),
                "expires": alert.get("expires"),
                "desc": alert.get("desc"),
                "instruction": alert.get("instruction"),
            }
        )

    return alerts


def map_location(api_response: Dict[str, Any]) -> Dict[str, Any]:
    """Map location data from WeatherAPI.com format to internal format.

    Args:
        api_response: The WeatherAPI.com response data

    Returns:
        Dict containing mapped location data
    """
    if not api_response or "location" not in api_response:
        logger.warning("Invalid or empty API response for location")
        return {}

    location = api_response.get("location", {})

    return {
        "name": location.get("name"),
        "region": location.get("region"),
        "country": location.get("country"),
        "latitude": location.get("lat"),
        "longitude": location.get("lon"),
        "timezone": location.get("tz_id"),
        "localtime": location.get("localtime"),
        "localtime_epoch": location.get("localtime_epoch"),
    }
