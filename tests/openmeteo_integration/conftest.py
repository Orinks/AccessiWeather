"""Shared fixtures and test data for OpenMeteo integration tests."""

from unittest.mock import MagicMock

import pytest

from accessiweather.api_client import NoaaApiClient
from accessiweather.openmeteo_client import OpenMeteoApiClient
from accessiweather.services.weather_service import WeatherService

# Sample test data
SAMPLE_OPENMETEO_CURRENT_RESPONSE = {
    "latitude": 51.5074,
    "longitude": -0.1278,
    "current": {
        "time": "2024-01-01T12:00",
        "temperature_2m": 15.5,
        "relative_humidity_2m": 70,
        "weather_code": 2,
        "wind_speed_10m": 10.0,
        "wind_direction_10m": 225,
    },
    "current_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
}

SAMPLE_OPENMETEO_FORECAST_RESPONSE = {
    "latitude": 51.5074,
    "longitude": -0.1278,
    "daily": {
        "time": ["2024-01-01", "2024-01-02"],
        "weather_code": [1, 2],
        "temperature_2m_max": [18.0, 20.0],
        "temperature_2m_min": [8.0, 10.0],
        "wind_speed_10m_max": [15.0, 12.0],
        "wind_direction_10m_dominant": [180, 225],
    },
    "daily_units": {
        "temperature_2m_max": "°C",
        "temperature_2m_min": "°C",
        "wind_speed_10m_max": "km/h",
    },
}

SAMPLE_OPENMETEO_HOURLY_RESPONSE = {
    "latitude": 51.5074,
    "longitude": -0.1278,
    "hourly": {
        "time": ["2024-01-01T12:00", "2024-01-01T13:00"],
        "temperature_2m": [15.5, 16.0],
        "weather_code": [2, 1],
        "wind_speed_10m": [10.0, 8.0],
        "is_day": [1, 1],
    },
    "hourly_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
}


@pytest.fixture
def mock_nws_client():
    """Create a mock NWS client."""
    return MagicMock(spec=NoaaApiClient)


@pytest.fixture
def mock_openmeteo_client():
    """Create a mock Open-Meteo client."""
    return MagicMock(spec=OpenMeteoApiClient)


@pytest.fixture
def weather_service_with_openmeteo(mock_nws_client, mock_openmeteo_client):
    """Create a WeatherService with mocked clients."""
    config = {"settings": {"data_source": "auto"}}
    return WeatherService(
        nws_client=mock_nws_client, openmeteo_client=mock_openmeteo_client, config=config
    )
