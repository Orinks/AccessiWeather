"""Tests for the OpenWeatherMap mapper module."""

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from accessiweather.openweathermap_mapper import (
    map_alerts,
    map_current_conditions,
    map_forecast,
    map_hourly_forecast,
)

# Sample OpenWeatherMap current weather response
SAMPLE_CURRENT_DATA = {
    "coord": {"lon": -0.1278, "lat": 51.5074},
    "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
    "main": {
        "temp": 59.0,
        "feels_like": 58.1,
        "temp_min": 56.3,
        "temp_max": 61.7,
        "pressure": 1013,
        "humidity": 65,
    },
    "visibility": 10000,
    "wind": {"speed": 3.5, "deg": 180, "gust": 5.2},
    "clouds": {"all": 0},
    "dt": 1684766400,
    "sys": {"country": "GB", "sunrise": 1684726800, "sunset": 1684782000},
    "timezone": 3600,
    "name": "London",
}

# Sample OpenWeatherMap One Call forecast response
SAMPLE_FORECAST_DATA = {
    "lat": 51.5074,
    "lon": -0.1278,
    "timezone": "Europe/London",
    "timezone_offset": 3600,
    "current": {"dt": 1684766400, "temp": 59.0, "humidity": 65},
    "daily": [
        {
            "dt": 1684800000,
            "temp": {
                "day": 68.0,
                "min": 52.0,
                "max": 75.2,
                "night": 55.4,
                "eve": 70.7,
                "morn": 54.5,
            },
            "feels_like": {"day": 67.1, "night": 54.3, "eve": 69.8, "morn": 53.6},
            "pressure": 1015,
            "humidity": 60,
            "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
            "clouds": 5,
            "wind_speed": 4.2,
            "wind_deg": 200,
            "wind_gust": 6.8,
            "visibility": 10000,
            "uvi": 6.5,
            "pop": 0.1,
            "rain": {"1h": 0.2},
            "snow": {"1h": 0.0},
        }
    ],
    "hourly": [
        {
            "dt": 1684767600,
            "temp": 61.7,
            "feels_like": 60.8,
            "pressure": 1013,
            "humidity": 70,
            "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
            "clouds": 0,
            "visibility": 10000,
            "wind_speed": 3.8,
            "wind_deg": 185,
            "wind_gust": 5.5,
            "uvi": 5.2,
            "pop": 0.05,
            "rain": {"1h": 0.1},
        }
    ],
    "alerts": [
        {
            "sender_name": "Met Office",
            "event": "Flood Warning",
            "start": 1684800000,
            "end": 1684886400,
            "description": "Flooding is occurring or imminent in the following areas.",
            "tags": ["Flood"],
        }
    ],
}


class TestOpenWeatherMapMapper(unittest.TestCase):
    """Tests for OpenWeatherMap data mapping functions."""

    def test_map_current_conditions(self):
        """Test mapping current conditions data."""
        result = map_current_conditions(SAMPLE_CURRENT_DATA)

        # Check location mapping
        self.assertEqual(result["location"]["name"], "London")
        self.assertEqual(result["location"]["lat"], 51.5074)
        self.assertEqual(result["location"]["lon"], -0.1278)
        self.assertEqual(result["location"]["country"], "GB")
        self.assertEqual(result["location"]["timezone"], 3600)

        # Check current conditions mapping
        self.assertEqual(result["current"]["temperature"], 59.0)
        self.assertEqual(result["current"]["feels_like"], 58.1)
        self.assertEqual(result["current"]["humidity"], 65)
        self.assertEqual(result["current"]["pressure"], 1013)
        self.assertEqual(result["current"]["visibility"], 10000)
        self.assertEqual(result["current"]["condition"], "Clear")
        self.assertEqual(result["current"]["description"], "clear sky")
        self.assertEqual(result["current"]["icon"], "01d")

        # Check wind mapping
        self.assertEqual(result["current"]["wind"]["speed"], 3.5)
        self.assertEqual(result["current"]["wind"]["direction"], 180)
        self.assertEqual(result["current"]["wind"]["gust"], 5.2)

        # Check clouds mapping
        self.assertEqual(result["current"]["clouds"], 0)

        # Check timestamp mapping
        self.assertIn("last_updated", result["current"])

    def test_map_current_conditions_missing_data(self):
        """Test mapping current conditions with missing data."""
        minimal_data = {
            "coord": {"lon": -0.1278, "lat": 51.5074},
            "weather": [{"main": "Clear"}],
            "main": {"temp": 59.0},
            "name": "London",
        }

        result = map_current_conditions(minimal_data)

        # Should handle missing data gracefully
        self.assertEqual(result["location"]["name"], "London")
        self.assertEqual(result["current"]["temperature"], 59.0)
        self.assertEqual(result["current"]["condition"], "Clear")
        self.assertIsNone(result["current"]["feels_like"])
        self.assertIsNone(result["current"]["humidity"])

    def test_map_current_conditions_empty_weather_array(self):
        """Test mapping current conditions with empty weather array."""
        data_with_empty_weather = {
            "coord": {"lon": -0.1278, "lat": 51.5074},
            "weather": [],
            "main": {"temp": 59.0},
            "name": "London",
        }

        result = map_current_conditions(data_with_empty_weather)

        # Should handle empty weather array gracefully
        self.assertEqual(result["current"]["condition"], "Unknown")
        self.assertEqual(result["current"]["description"], "")

    def test_map_forecast(self):
        """Test mapping forecast data."""
        result = map_forecast(SAMPLE_FORECAST_DATA, days=1)

        # Check location mapping
        self.assertEqual(result["location"]["lat"], 51.5074)
        self.assertEqual(result["location"]["lon"], -0.1278)
        self.assertEqual(result["location"]["timezone"], "Europe/London")
        self.assertEqual(result["location"]["timezone_offset"], 3600)

        # Check forecast mapping
        self.assertEqual(len(result["forecast"]["days"]), 1)
        day = result["forecast"]["days"][0]

        self.assertEqual(day["high"], 75.2)
        self.assertEqual(day["low"], 52.0)
        self.assertEqual(day["condition"], "Clear")
        self.assertEqual(day["description"], "clear sky")
        self.assertEqual(day["humidity"], 60)
        self.assertEqual(day["pressure"], 1015)
        self.assertEqual(day["wind_speed"], 4.2)
        self.assertEqual(day["wind_direction"], 200)
        self.assertEqual(day["clouds"], 5)
        self.assertEqual(day["uv_index"], 6.5)
        self.assertEqual(day["pop"], 0.1)
        self.assertEqual(day["rain"], 0.2)
        self.assertEqual(day["snow"], 0.0)

    def test_map_forecast_multiple_days(self):
        """Test mapping forecast data with multiple days."""
        # Create data with multiple days
        multi_day_data = SAMPLE_FORECAST_DATA.copy()
        multi_day_data["daily"] = [SAMPLE_FORECAST_DATA["daily"][0]] * 3

        result = map_forecast(multi_day_data, days=3)

        # Should return all 3 days
        self.assertEqual(len(result["forecast"]["days"]), 3)

    def test_map_forecast_limit_days(self):
        """Test mapping forecast data with day limit."""
        # Create data with multiple days
        multi_day_data = SAMPLE_FORECAST_DATA.copy()
        multi_day_data["daily"] = [SAMPLE_FORECAST_DATA["daily"][0]] * 5

        result = map_forecast(multi_day_data, days=3)

        # Should limit to 3 days
        self.assertEqual(len(result["forecast"]["days"]), 3)

    def test_map_hourly_forecast(self):
        """Test mapping hourly forecast data."""
        result = map_hourly_forecast(SAMPLE_FORECAST_DATA, hours=1)

        # Check location mapping
        self.assertEqual(result["location"]["lat"], 51.5074)
        self.assertEqual(result["location"]["lon"], -0.1278)

        # Check hourly forecast mapping
        self.assertEqual(len(result["hourly_forecast"]["hours"]), 1)
        hour = result["hourly_forecast"]["hours"][0]

        self.assertEqual(hour["temperature"], 61.7)
        self.assertEqual(hour["feels_like"], 60.8)
        self.assertEqual(hour["condition"], "Clear")
        self.assertEqual(hour["description"], "clear sky")
        self.assertEqual(hour["humidity"], 70)
        self.assertEqual(hour["pressure"], 1013)
        self.assertEqual(hour["wind_speed"], 3.8)
        self.assertEqual(hour["wind_direction"], 185)
        self.assertEqual(hour["clouds"], 0)
        self.assertEqual(hour["visibility"], 10000)
        self.assertEqual(hour["uv_index"], 5.2)
        self.assertEqual(hour["pop"], 0.05)
        self.assertEqual(hour["rain"], 0.1)

    def test_map_alerts(self):
        """Test mapping alerts data."""
        result = map_alerts(SAMPLE_FORECAST_DATA)

        # Check alerts mapping
        self.assertEqual(len(result), 1)
        alert = result[0]

        self.assertEqual(alert["sender"], "Met Office")
        self.assertEqual(alert["event"], "Flood Warning")
        self.assertEqual(
            alert["description"], "Flooding is occurring or imminent in the following areas."
        )
        self.assertEqual(alert["tags"], ["Flood"])
        self.assertIn("start", alert)
        self.assertIn("end", alert)

    def test_map_alerts_empty(self):
        """Test mapping empty alerts data."""
        data_without_alerts = {"lat": 51.5074, "lon": -0.1278}
        result = map_alerts(data_without_alerts)
        self.assertEqual(result, [])

    def test_map_current_conditions_error_handling(self):
        """Test error handling in current conditions mapping."""
        with self.assertRaises(ValueError):
            map_current_conditions({})  # Empty data should raise error

    def test_map_forecast_error_handling(self):
        """Test error handling in forecast mapping."""
        with self.assertRaises(ValueError):
            map_forecast({})  # Empty data should raise error

    def test_map_hourly_forecast_error_handling(self):
        """Test error handling in hourly forecast mapping."""
        with self.assertRaises(ValueError):
            map_hourly_forecast({})  # Empty data should raise error


if __name__ == "__main__":
    unittest.main()
