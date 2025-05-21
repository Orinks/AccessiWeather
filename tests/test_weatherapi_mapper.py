"""Tests for the WeatherAPI mapper module."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.weatherapi_mapper import (
    map_alerts,
    map_current_conditions,
    map_forecast,
    map_hourly_forecast,
    map_location,
)

# Sample test data
SAMPLE_CURRENT_DATA = {
    "current": {
        "last_updated_epoch": 1613896210,
        "last_updated": "2021-02-21 08:30",
        "temp_c": 11,
        "temp_f": 51.8,
        "is_day": 1,
        "condition": {
            "text": "Partly cloudy",
            "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png",
            "code": 1003,
        },
        "wind_mph": 3.8,
        "wind_kph": 6.1,
        "wind_degree": 220,
        "wind_dir": "SW",
        "pressure_mb": 1009,
        "pressure_in": 30.3,
        "precip_mm": 0.1,
        "precip_in": 0,
        "humidity": 82,
        "cloud": 75,
        "feelslike_c": 9.5,
        "feelslike_f": 49.2,
        "vis_km": 10,
        "vis_miles": 6,
        "uv": 1,
        "gust_mph": 10.5,
        "gust_kph": 16.9,
    }
}

SAMPLE_FORECAST_DATA = {
    "forecast": {
        "forecastday": [
            {
                "date": "2021-02-21",
                "date_epoch": 1613865600,
                "day": {
                    "maxtemp_c": 12.5,
                    "maxtemp_f": 54.5,
                    "mintemp_c": 6.7,
                    "mintemp_f": 44.1,
                    "avgtemp_c": 9.5,
                    "avgtemp_f": 49.1,
                    "maxwind_mph": 8.9,
                    "maxwind_kph": 14.4,
                    "totalprecip_mm": 0.2,
                    "totalprecip_in": 0.01,
                    "totalsnow_cm": 0,
                    "avgvis_km": 10,
                    "avgvis_miles": 6,
                    "avghumidity": 80,
                    "daily_will_it_rain": 1,
                    "daily_chance_of_rain": "82",
                    "daily_will_it_snow": 0,
                    "daily_chance_of_snow": "0",
                    "condition": {
                        "text": "Patchy rain possible",
                        "icon": "//cdn.weatherapi.com/weather/64x64/day/176.png",
                        "code": 1063,
                    },
                    "uv": 1,
                },
                "astro": {
                    "sunrise": "07:01 AM",
                    "sunset": "05:31 PM",
                    "moonrise": "12:33 PM",
                    "moonset": "03:15 AM",
                    "moon_phase": "First Quarter",
                    "moon_illumination": "50",
                },
                "hour": [
                    {
                        "time_epoch": 1613865600,
                        "time": "2021-02-21 00:00",
                        "temp_c": 8.9,
                        "temp_f": 48,
                        "is_day": 0,
                        "condition": {
                            "text": "Clear",
                            "icon": "//cdn.weatherapi.com/weather/64x64/night/113.png",
                            "code": 1000,
                        },
                        "wind_mph": 4.3,
                        "wind_kph": 6.8,
                        "wind_degree": 225,
                        "wind_dir": "SW",
                        "pressure_mb": 1009,
                        "pressure_in": 30.3,
                        "precip_mm": 0,
                        "precip_in": 0,
                        "humidity": 87,
                        "cloud": 19,
                        "feelslike_c": 7.5,
                        "feelslike_f": 45.5,
                        "windchill_c": 7.5,
                        "windchill_f": 45.5,
                        "heatindex_c": 8.9,
                        "heatindex_f": 48,
                        "dewpoint_c": 6.9,
                        "dewpoint_f": 44.4,
                        "will_it_rain": 0,
                        "chance_of_rain": "0",
                        "will_it_snow": 0,
                        "chance_of_snow": "0",
                        "vis_km": 10,
                        "vis_miles": 6,
                        "gust_mph": 8.5,
                        "gust_kph": 13.7,
                        "uv": 1,
                    }
                ],
            }
        ]
    }
}

SAMPLE_ALERTS_DATA = {
    "alerts": {
        "alert": [
            {
                "headline": "Flood Warning",
                "severity": "Moderate",
                "urgency": "Expected",
                "areas": "County A; County B",
                "category": "Met",
                "certainty": "Likely",
                "event": "Flood",
                "note": "Test note",
                "effective": "2021-02-21T00:00:00Z",
                "expires": "2021-02-22T00:00:00Z",
                "desc": "Flooding is occurring or imminent.",
                "instruction": "Move to higher ground.",
            }
        ]
    }
}

SAMPLE_LOCATION_DATA = {
    "location": {
        "name": "London",
        "region": "City of London, Greater London",
        "country": "United Kingdom",
        "lat": 51.52,
        "lon": -0.11,
        "tz_id": "Europe/London",
        "localtime_epoch": 1613896955,
        "localtime": "2021-02-21 8:42",
    }
}


def test_map_current_conditions():
    """Test mapping current conditions data."""
    result = map_current_conditions(SAMPLE_CURRENT_DATA)

    assert result["temperature"] == 51.8
    assert result["temperature_c"] == 11
    assert result["condition"] == "Partly cloudy"
    assert result["condition_icon"] == "//cdn.weatherapi.com/weather/64x64/day/116.png"
    assert result["condition_code"] == 1003
    assert result["humidity"] == 82
    assert result["wind_speed"] == 3.8
    assert result["wind_direction"] == "SW"
    assert result["pressure"] == 30.3
    assert result["visibility"] == 6
    assert result["uv_index"] == 1


def test_map_forecast():
    """Test mapping forecast data."""
    result = map_forecast(SAMPLE_FORECAST_DATA)

    assert len(result) == 1
    day = result[0]
    assert day["date"] == "2021-02-21"
    assert day["high"] == 54.5
    assert day["low"] == 44.1
    assert day["condition"] == "Patchy rain possible"
    assert day["precipitation_probability"] == "82"
    assert day["snow_probability"] == "0"
    assert day["max_wind_speed"] == 8.9
    assert day["avg_humidity"] == 80
    assert day["uv_index"] == 1


def test_map_hourly_forecast():
    """Test mapping hourly forecast data."""
    result = map_hourly_forecast(SAMPLE_FORECAST_DATA)

    assert len(result) == 1
    hour = result[0]
    assert hour["time"] == "2021-02-21 00:00"
    assert hour["temperature"] == 48
    assert hour["temperature_c"] == 8.9
    assert hour["condition"] == "Clear"
    assert hour["wind_speed"] == 4.3
    assert hour["humidity"] == 87
    assert hour["chance_of_rain"] == "0"
    assert hour["chance_of_snow"] == "0"
    assert hour["visibility"] == 6
    assert hour["uv_index"] == 1


def test_map_alerts():
    """Test mapping alerts data."""
    result = map_alerts(SAMPLE_ALERTS_DATA)

    assert len(result) == 1
    alert = result[0]
    assert alert["headline"] == "Flood Warning"
    assert alert["severity"] == "Moderate"
    assert alert["urgency"] == "Expected"
    assert alert["areas"] == "County A; County B"
    assert alert["event"] == "Flood"
    assert alert["desc"] == "Flooding is occurring or imminent."
    assert alert["instruction"] == "Move to higher ground."


def test_map_location():
    """Test mapping location data."""
    result = map_location(SAMPLE_LOCATION_DATA)

    assert result["name"] == "London"
    assert result["region"] == "City of London, Greater London"
    assert result["country"] == "United Kingdom"
    assert result["latitude"] == 51.52
    assert result["longitude"] == -0.11
    assert result["timezone"] == "Europe/London"
    assert result["localtime"] == "2021-02-21 8:42"


def test_map_current_conditions_empty():
    """Test mapping empty current conditions data."""
    result = map_current_conditions({})
    assert result == {}


def test_map_forecast_empty():
    """Test mapping empty forecast data."""
    result = map_forecast({})
    assert result == []


def test_map_hourly_forecast_empty():
    """Test mapping empty hourly forecast data."""
    result = map_hourly_forecast({})
    assert result == []


def test_map_alerts_empty():
    """Test mapping empty alerts data."""
    result = map_alerts({})
    assert result == []


def test_map_location_empty():
    """Test mapping empty location data."""
    result = map_location({})
    assert result == {}
