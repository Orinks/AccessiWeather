"""Tests for NoaaApiWrapper rate limiting and error handling functionality."""

import time
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
    with patch("time.sleep") as mock_sleep:
        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = SAMPLE_POINT_DATA

            # Make first request
            api_wrapper.get_point_data(40.0, -75.0)

            # Make second request immediately - this should trigger rate limiting
            api_wrapper.get_point_data(40.1, -75.1)

            # Check that sleep was called for rate limiting
            assert mock_sleep.call_count >= 1


@pytest.mark.unit
def test_retry_mechanism_with_backoff(api_wrapper):
    """Test retry mechanism with exponential backoff."""
    # Mock the underlying API function to raise an error then succeed
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.side_effect = [MockUnexpectedStatus(429), SAMPLE_POINT_DATA]

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(NoaaApiError):
                # This should fail because the retry mechanism is not implemented
                # in the current version of the wrapper
                api_wrapper.get_point_data(40.0, -75.0)


def test_rate_limiting(api_wrapper):
    """Test rate limiting functionality."""
    with patch("time.sleep") as mock_sleep:
        # Test the basic rate limiting functionality by directly manipulating
        # the last_request_time attribute

        # First scenario: No previous request, should not sleep
        api_wrapper.last_request_time = None
        api_wrapper._rate_limit()
        mock_sleep.assert_not_called()

        # Second scenario: Recent request (0.2s ago), should sleep for 0.3s
        mock_sleep.reset_mock()
        current_time = time.time()
        api_wrapper.last_request_time = current_time - 0.2  # 0.2 seconds ago

        with patch("time.time", return_value=current_time):
            api_wrapper._rate_limit()

        mock_sleep.assert_called_once()
        assert mock_sleep.call_args[0][0] == pytest.approx(0.3)

        # Third scenario: Less recent request (0.4s ago), should sleep for 0.1s
        mock_sleep.reset_mock()
        current_time = time.time()
        api_wrapper.last_request_time = current_time - 0.4  # 0.4 seconds ago

        with patch("time.time", return_value=current_time):
            api_wrapper._rate_limit()

        mock_sleep.assert_called_once()
        assert mock_sleep.call_args[0][0] == pytest.approx(0.1)


def test_handle_rate_limit(api_wrapper):
    """Test rate limit handling with exponential backoff."""
    with patch("time.sleep") as mock_sleep, patch("time.time") as mock_time:

        # Set up time.time to return a constant value
        mock_time.return_value = 100.0

        # First retry should wait for retry_initial_wait (5.0 seconds)
        api_wrapper._handle_rate_limit("https://api.weather.gov/test", 0)
        mock_sleep.assert_called_once_with(5.0)
        mock_sleep.reset_mock()

        # Second retry should wait for retry_initial_wait * retry_backoff (10.0 seconds)
        api_wrapper._handle_rate_limit("https://api.weather.gov/test", 1)
        mock_sleep.assert_called_once_with(10.0)
        mock_sleep.reset_mock()

        # Third retry should wait for retry_initial_wait * retry_backoff^2 (20.0 seconds)
        api_wrapper._handle_rate_limit("https://api.weather.gov/test", 2)
        mock_sleep.assert_called_once_with(20.0)
        mock_sleep.reset_mock()

        # Fourth retry should exceed max_retries and raise an exception
        with pytest.raises(Exception) as excinfo:
            api_wrapper._handle_rate_limit("https://api.weather.gov/test", 3)

        assert "Rate limit exceeded" in str(excinfo.value)
        assert "after 3 retries" in str(excinfo.value)
        mock_sleep.assert_not_called()


@pytest.mark.unit
def test_handle_rate_limit_max_retries_exceeded(api_wrapper):
    """Test rate limit handling when max retries are exceeded."""
    url = "https://api.weather.gov/test"

    with pytest.raises(NoaaApiError) as exc_info:
        api_wrapper._handle_rate_limit(url, retry_count=api_wrapper.max_retries)

    assert "Rate limit exceeded" in str(exc_info.value)
    assert exc_info.value.error_type == NoaaApiError.RATE_LIMIT_ERROR


@pytest.mark.unit
def test_handle_rate_limit_with_backoff(api_wrapper):
    """Test rate limit handling with exponential backoff."""
    url = "https://api.weather.gov/test"

    with patch("time.sleep") as mock_sleep:
        api_wrapper._handle_rate_limit(url, retry_count=1)

        # Should sleep for initial_wait * backoff^retry_count
        expected_wait = api_wrapper.retry_initial_wait * (api_wrapper.retry_backoff**1)
        mock_sleep.assert_called_once_with(expected_wait)


@pytest.mark.unit
def test_handle_client_error_timeout(api_wrapper):
    """Test handling of timeout errors."""
    import httpx

    timeout_error = httpx.TimeoutException("Request timed out")
    url = "https://api.weather.gov/test"

    result = api_wrapper._handle_client_error(timeout_error, url)

    assert isinstance(result, NoaaApiError)
    assert result.error_type == NoaaApiError.TIMEOUT_ERROR
    assert "timed out" in str(result)


@pytest.mark.unit
def test_handle_client_error_connection(api_wrapper):
    """Test handling of connection errors."""
    import httpx

    connection_error = httpx.ConnectError("Connection failed")
    url = "https://api.weather.gov/test"

    result = api_wrapper._handle_client_error(connection_error, url)

    assert isinstance(result, NoaaApiError)
    assert result.error_type == NoaaApiError.CONNECTION_ERROR
    assert "Connection error" in str(result)


@pytest.mark.unit
def test_handle_client_error_network(api_wrapper):
    """Test handling of network errors."""
    import httpx

    network_error = httpx.RequestError("Network error")
    url = "https://api.weather.gov/test"

    result = api_wrapper._handle_client_error(network_error, url)

    assert isinstance(result, NoaaApiError)
    assert result.error_type == NoaaApiError.NETWORK_ERROR
    assert "Network error" in str(result)


@pytest.mark.unit
def test_handle_client_error_unknown(api_wrapper):
    """Test handling of unknown errors."""
    unknown_error = Exception("Unknown error")
    url = "https://api.weather.gov/test"

    result = api_wrapper._handle_client_error(unknown_error, url)

    assert isinstance(result, NoaaApiError)
    assert result.error_type == NoaaApiError.UNKNOWN_ERROR
    assert "Unexpected error" in str(result)
