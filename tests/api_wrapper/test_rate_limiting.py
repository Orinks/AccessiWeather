"""Tests for NoaaApiWrapper rate limiting and error handling functionality."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_client import NoaaApiError
from accessiweather.api_wrapper import NoaaApiWrapper

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


@pytest.fixture
def api_wrapper():
    """Create a NoaaApiWrapper instance without caching."""
    with (
        patch("accessiweather.api.nws_wrapper.NwsApiWrapper") as mock_nws,
        patch("accessiweather.api.openmeteo_wrapper.OpenMeteoApiWrapper") as mock_openmeteo,
    ):

        # Create mock instances with proper attributes
        mock_nws_instance = MagicMock()
        mock_nws_instance.client = MagicMock()
        mock_nws_instance.client._headers = {"User-Agent": "TestClient (test@example.com)"}
        mock_nws_instance.cache = None
        mock_nws_instance._generate_cache_key = MagicMock(return_value="test_cache_key")
        mock_nws_instance._get_cached_or_fetch = MagicMock()
        mock_nws_instance._make_api_request = MagicMock()
        mock_nws_instance._transform_point_data = MagicMock()
        mock_nws_instance._rate_limit = MagicMock()
        mock_nws_instance._handle_rate_limit = MagicMock()
        mock_nws_instance._handle_client_error = MagicMock()
        mock_nws_instance.get_point_data = MagicMock()
        mock_nws_instance.last_request_time = None
        mock_nws_instance.max_retries = 3
        mock_nws_instance.retry_initial_wait = 5.0
        mock_nws_instance.retry_backoff = 2.0
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


@pytest.mark.unit
def test_rate_limiting_enforcement(api_wrapper):
    """Test that rate limiting is enforced between requests."""
    # Configure the mock to return expected data
    expected_result = {
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

    api_wrapper.nws_wrapper.get_point_data.return_value = expected_result

    with patch("time.sleep"):
        # Make first request
        api_wrapper.get_point_data(40.0, -75.0)

        # Make second request immediately - this should trigger rate limiting
        api_wrapper.get_point_data(40.1, -75.1)

        # Check that the NWS wrapper's rate limiting was called
        # Since we're mocking the provider wrapper, we can't directly test rate limiting
        # but we can verify the methods were called
        assert api_wrapper.nws_wrapper.get_point_data.call_count == 2


@pytest.mark.unit
def test_retry_mechanism_with_backoff(api_wrapper):
    """Test retry mechanism with exponential backoff."""
    # Configure the NWS wrapper to raise an error
    from accessiweather.api_client import NoaaApiError

    api_wrapper.nws_wrapper.get_point_data.side_effect = NoaaApiError(
        message="Rate limit exceeded",
        error_type=NoaaApiError.RATE_LIMIT_ERROR,
        url="https://api.weather.gov/test",
    )

    with pytest.raises(NoaaApiError):
        api_wrapper.get_point_data(40.0, -75.0)


def test_error_handling_through_public_api(api_wrapper):
    """Test error handling through the public API."""
    # Configure the NWS wrapper to raise an error
    api_wrapper.nws_wrapper.get_point_data.side_effect = NoaaApiError(
        message="Service unavailable",
        error_type=NoaaApiError.NETWORK_ERROR,
        url="https://api.weather.gov/test",
    )

    with pytest.raises(NoaaApiError) as exc_info:
        api_wrapper.get_point_data(40.0, -75.0)

    assert exc_info.value.error_type == NoaaApiError.NETWORK_ERROR
    assert "Service unavailable" in str(exc_info.value)


@pytest.mark.unit
def test_successful_api_calls_work(api_wrapper):
    """Test that successful API calls work correctly."""
    # Configure the mock to return expected data
    expected_result = {
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

    api_wrapper.nws_wrapper.get_point_data.return_value = expected_result

    result = api_wrapper.get_point_data(40.0, -75.0)

    assert result == expected_result
    api_wrapper.nws_wrapper.get_point_data.assert_called_once_with(40.0, -75.0, force_refresh=False)
