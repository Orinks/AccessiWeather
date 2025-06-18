"""Shared fixtures and test data for weather service tests."""

from unittest.mock import MagicMock

import pytest

from accessiweather.api_client import NoaaApiClient
from accessiweather.services.weather_service import WeatherService

# Sample test data
SAMPLE_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "name": "Today",
                "temperature": 75,
                "temperatureUnit": "F",
                "shortForecast": "Sunny",
                "detailedForecast": "Sunny with a high near 75.",
            }
        ]
    }
}

SAMPLE_ALERTS_DATA = {
    "features": [
        {
            "properties": {
                "headline": "Test Alert",
                "description": "Test Description",
                "instruction": "Test Instruction",
                "severity": "Moderate",
                "event": "Test Event",
            }
        }
    ]
}

SAMPLE_DISCUSSION_TEXT = """
This is a sample forecast discussion.
Multiple lines of text.
With weather information.
"""

SAMPLE_NATIONAL_DISCUSSION_DATA = {
    "wpc": {
        "short_range_summary": "WPC Short Range Summary",
        "short_range_full": "WPC Full Discussion",
    },
    "spc": {"day1_summary": "SPC Day 1 Summary", "day1_full": "SPC Full Discussion"},
    "attribution": "Data from NOAA/NWS",
}


# Fixture to create a mocked NoaaApiClient
@pytest.fixture
def mock_api_client():
    client = MagicMock(spec=NoaaApiClient)
    # Set default return values
    client.get_forecast.return_value = SAMPLE_FORECAST_DATA
    client.get_alerts.return_value = SAMPLE_ALERTS_DATA
    client.get_discussion.return_value = SAMPLE_DISCUSSION_TEXT
    client.get_national_discussion_summary.return_value = {
        "wpc": {"short_range_summary": "WPC Summary"},
        "spc": {"day1_summary": "SPC Summary"},
    }
    return client


# Fixture to create a WeatherService instance with the mocked client
@pytest.fixture
def weather_service(mock_api_client):
    return WeatherService(mock_api_client)
