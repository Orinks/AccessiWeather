"""Shared fixtures and test data for API wrapper tests."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_wrapper import NoaaApiWrapper

# Common test coordinates
TEST_LAT = 40.0
TEST_LON = -75.0

# Sample point data
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

# Sample forecast data
SAMPLE_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "number": 1,
                "name": "Tonight",
                "temperature": 45,
                "temperatureUnit": "F",
                "windSpeed": "5 mph",
                "windDirection": "NW",
                "shortForecast": "Clear",
                "detailedForecast": "Clear skies tonight.",
            }
        ]
    }
}

# Sample hourly forecast data
SAMPLE_HOURLY_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "number": 1,
                "startTime": "2024-01-15T18:00:00-05:00",
                "temperature": 45,
                "temperatureUnit": "F",
                "windSpeed": "5 mph",
                "windDirection": "NW",
                "shortForecast": "Clear",
            }
        ]
    }
}

# Sample alerts response data
SAMPLE_ALERTS_DATA = {
    "features": [
        {
            "id": "alert1",
            "properties": {"headline": "Test Alert", "description": "Test alert description"},
        }
    ]
}

# Common URLs used in testing
ALERTS_URL_COUNTY = "https://api.weather.gov/alerts/active?zone=PAC101"
FORECAST_URL = "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
HOURLY_FORECAST_URL = "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly"


# Create UnexpectedStatus class for testing
class MockUnexpectedStatus(Exception):
    def __init__(self, status_code, content=None):
        self.status_code = status_code
        self.content = content
        super().__init__(f"Unexpected status code: {status_code}")


@pytest.fixture
def api_wrapper():
    """Create a NoaaApiWrapper instance without caching."""
    with (
        patch("accessiweather.api.nws.NwsApiWrapper") as mock_nws,
        patch("accessiweather.api.openmeteo_wrapper.OpenMeteoApiWrapper") as mock_openmeteo,
    ):
        # Create mock instances with proper attributes
        mock_nws_instance = MagicMock()
        mock_nws_instance.client = MagicMock()
        mock_nws_instance.client._headers = {"User-Agent": "TestClient (test@example.com)"}
        mock_nws_instance.cache = None
        mock_nws_instance._generate_cache_key = MagicMock(return_value="test_cache_key")
        mock_nws_instance._get_cached_or_fetch = MagicMock(return_value={"data": "test"})
        mock_nws_instance._make_api_request = MagicMock()
        mock_nws_instance._transform_point_data = MagicMock()
        mock_nws_instance._rate_limit = MagicMock()
        mock_nws_instance._handle_rate_limit = MagicMock()
        mock_nws_instance._handle_client_error = MagicMock()
        mock_nws_instance.get_point_data = MagicMock(return_value=SAMPLE_POINT_DATA)
        mock_nws_instance.last_request_time = None
        mock_nws_instance.max_retries = 3
        mock_nws_instance.retry_initial_wait = 5.0
        mock_nws_instance.retry_backoff = 2.0

        # Configure method return values with sample data
        mock_nws_instance.get_alerts = MagicMock(return_value=SAMPLE_ALERTS_DATA)
        mock_nws_instance.get_forecast = MagicMock(return_value=SAMPLE_FORECAST_DATA)
        mock_nws_instance.get_hourly_forecast = MagicMock(return_value=SAMPLE_HOURLY_FORECAST_DATA)
        mock_nws_instance.identify_location_type = MagicMock(return_value=("county", "PAC101"))

        mock_nws.return_value = mock_nws_instance

        mock_openmeteo_instance = MagicMock()
        mock_openmeteo.return_value = mock_openmeteo_instance

        wrapper = NoaaApiWrapper(
            user_agent="TestClient", contact_info="test@example.com", enable_caching=False
        )

        # Ensure the wrapper has the expected attributes
        wrapper.nws_wrapper = mock_nws_instance
        wrapper.openmeteo_wrapper = mock_openmeteo_instance

        return wrapper


@pytest.fixture
def cached_api_wrapper():
    """Create a NoaaApiWrapper instance with caching enabled."""
    with (
        patch("accessiweather.api.nws.NwsApiWrapper") as mock_nws,
        patch("accessiweather.api.openmeteo_wrapper.OpenMeteoApiWrapper") as mock_openmeteo,
    ):
        # Create mock cache
        mock_cache = MagicMock()
        mock_cache.default_ttl = 300

        # Create mock instances with proper attributes
        mock_nws_instance = MagicMock()
        mock_nws_instance.client = MagicMock()
        mock_nws_instance.client._headers = {"User-Agent": "TestClient (test@example.com)"}
        mock_nws_instance.cache = mock_cache
        mock_nws_instance._generate_cache_key = MagicMock(return_value="test_cache_key")
        mock_nws_instance._get_cached_or_fetch = MagicMock(return_value={"data": "test"})
        mock_nws_instance._make_api_request = MagicMock()
        mock_nws_instance._transform_point_data = MagicMock()
        mock_nws_instance._rate_limit = MagicMock()
        mock_nws_instance._handle_rate_limit = MagicMock()
        mock_nws_instance._handle_client_error = MagicMock()
        mock_nws_instance.get_point_data = MagicMock(return_value=SAMPLE_POINT_DATA)
        mock_nws_instance.last_request_time = None
        mock_nws_instance.max_retries = 3
        mock_nws_instance.retry_initial_wait = 5.0
        mock_nws_instance.retry_backoff = 2.0

        # Configure method return values with sample data
        mock_nws_instance.get_alerts = MagicMock(return_value=SAMPLE_ALERTS_DATA)
        mock_nws_instance.get_forecast = MagicMock(return_value=SAMPLE_FORECAST_DATA)
        mock_nws_instance.get_hourly_forecast = MagicMock(return_value=SAMPLE_HOURLY_FORECAST_DATA)
        mock_nws_instance.identify_location_type = MagicMock(return_value=("county", "PAC101"))

        mock_nws.return_value = mock_nws_instance

        mock_openmeteo_instance = MagicMock()
        mock_openmeteo.return_value = mock_openmeteo_instance

        wrapper = NoaaApiWrapper(
            user_agent="TestClient",
            contact_info="test@example.com",
            enable_caching=True,
            cache_ttl=300,
        )

        # Ensure the wrapper has the expected attributes
        wrapper.nws_wrapper = mock_nws_instance
        wrapper.openmeteo_wrapper = mock_openmeteo_instance

        return wrapper
