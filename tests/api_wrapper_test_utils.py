"""Shared utilities for NoaaApiWrapper tests."""

# Mock the weather_gov_api_client modules
import sys
from unittest.mock import MagicMock

import pytest

# Import the module that will be tested
from accessiweather.api_wrapper import NoaaApiWrapper

# Create mock modules
mock_client = MagicMock()
mock_errors = MagicMock()
mock_default = MagicMock()
mock_models = MagicMock()


# Create UnexpectedStatus class for testing
class MockUnexpectedStatus(Exception):
    def __init__(self, status_code, content=None):
        self.status_code = status_code
        self.content = content
        super().__init__(f"Unexpected status code: {status_code}")


# Assign the mock class to the mock module
mock_errors.UnexpectedStatus = MockUnexpectedStatus


# Create a mock Client class that properly handles headers
class MockClient:
    def __init__(self, base_url=None, headers=None, timeout=None, follow_redirects=None):
        self.base_url = base_url
        # Store headers using the same attribute name as the real Client class
        self._headers = headers or {}
        self.timeout = timeout
        self.follow_redirects = follow_redirects


# Assign the mock class to the mock module
mock_client.Client = MockClient

# Add the mocks to sys.modules
sys.modules["accessiweather.weather_gov_api_client"] = MagicMock()
sys.modules["accessiweather.weather_gov_api_client.client"] = mock_client
sys.modules["accessiweather.weather_gov_api_client.errors"] = mock_errors
sys.modules["accessiweather.weather_gov_api_client.api"] = MagicMock()
sys.modules["accessiweather.weather_gov_api_client.api.default"] = mock_default
sys.modules["accessiweather.weather_gov_api_client.models"] = mock_models

# Sample test data
SAMPLE_POINT_DATA = {
    "properties": {
        "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
        "forecastGridData": "https://api.weather.gov/gridpoints/PHI/31,70",
        "observationStations": "https://api.weather.gov/gridpoints/PHI/31,70/stations",
        "county": "https://api.weather.gov/zones/county/PAC101",
        "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ103",
        "timeZone": "America/New_York",
        "radarStation": "KDIX",
    }
}

SAMPLE_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "number": 1,
                "name": "Today",
                "startTime": "2023-01-01T06:00:00-05:00",
                "endTime": "2023-01-01T18:00:00-05:00",
                "isDaytime": True,
                "temperature": 45,
                "temperatureUnit": "F",
                "windSpeed": "10 mph",
                "windDirection": "NW",
                "icon": "https://api.weather.gov/icons/land/day/few?size=medium",
                "shortForecast": "Mostly Sunny",
                "detailedForecast": "Mostly sunny, with a high near 45.",
            }
        ]
    }
}

SAMPLE_ALERTS_DATA = {
    "features": [
        {
            "id": "https://api.weather.gov/alerts/urn:oid:2.49.0.1.840.0.123456",
            "type": "Feature",
            "properties": {
                "id": "urn:oid:2.49.0.1.840.0.123456",
                "areaDesc": "Test County",
                "geocode": {"FIPS6": ["123456"]},
                "affectedZones": ["https://api.weather.gov/zones/county/TST123"],
                "references": [],
                "sent": "2023-01-01T12:00:00-05:00",
                "effective": "2023-01-01T12:00:00-05:00",
                "onset": "2023-01-01T12:00:00-05:00",
                "expires": "2023-01-01T18:00:00-05:00",
                "ends": "2023-01-01T18:00:00-05:00",
                "status": "Actual",
                "messageType": "Alert",
                "category": "Met",
                "severity": "Minor",
                "certainty": "Likely",
                "urgency": "Expected",
                "event": "Test Warning",
                "sender": "NWS Test Office",
                "senderName": "National Weather Service Test Office",
                "headline": "Test Warning issued for Test County",
                "description": "Test warning description",
                "instruction": "Test instructions",
                "response": "Monitor",
                "parameters": {
                    "NWSheadline": ["Test Warning issued for Test County"],
                    "VTEC": ["/O.NEW.KTST.WW.Y.0001.230101T1700Z-230101T2300Z/"],
                },
            },
        }
    ]
}


# Shared fixtures
@pytest.fixture
def api_wrapper():
    """Create a NoaaApiWrapper instance without caching."""
    return NoaaApiWrapper(
        user_agent="TestClient", contact_info="test@example.com", enable_caching=False
    )


@pytest.fixture
def cached_api_wrapper():
    """Create a NoaaApiWrapper instance with caching enabled."""
    return NoaaApiWrapper(
        user_agent="TestClient", contact_info="test@example.com", enable_caching=True, cache_ttl=300
    )


class PointPropertiesSpec:
    """Spec class for mocking point properties."""

    forecast: str
    forecast_hourly: str
    forecast_grid_data: str
    observation_stations: str
    county: str
    fire_weather_zone: str
    time_zone: str
    radar_station: str
    # Note: 'additional_properties' is intentionally omitted from this spec.


def create_mock_point_properties():
    """Create a mock properties object for point data tests."""
    mock_properties = MagicMock(spec=PointPropertiesSpec)
    mock_properties.forecast = "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
    mock_properties.forecast_hourly = "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly"
    mock_properties.forecast_grid_data = "https://api.weather.gov/gridpoints/PHI/31,70"
    mock_properties.observation_stations = "https://api.weather.gov/gridpoints/PHI/31,70/stations"
    mock_properties.county = "https://api.weather.gov/zones/county/PAC101"
    mock_properties.fire_weather_zone = "https://api.weather.gov/zones/fire/PAZ103"
    mock_properties.time_zone = "America/New_York"
    mock_properties.radar_station = "KDIX"
    return mock_properties


def create_mock_point_response():
    """Create a mock response object for point data tests."""
    mock_response = MagicMock()
    mock_response.properties = create_mock_point_properties()
    return mock_response
