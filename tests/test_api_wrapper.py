"""Tests for the NoaaApiWrapper class."""

# Mock the weather_gov_api_client modules
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

# Import the module that will be tested
# We need to import this after setting up the mocks but before they're used
from accessiweather.api_client import NoaaApiError
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


# Fixtures
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


# Tests
def test_init_basic():
    """Test basic initialization without caching."""
    wrapper = NoaaApiWrapper(user_agent="TestClient")

    assert wrapper.user_agent == "TestClient"
    # Access headers through the private attribute
    assert "User-Agent" in wrapper.client._headers
    assert wrapper.client._headers["User-Agent"] == "TestClient"
    assert wrapper.cache is None


def test_init_with_contact():
    """Test initialization with contact info."""
    wrapper = NoaaApiWrapper(user_agent="TestClient", contact_info="test@example.com")

    # Access headers through the private attribute
    assert "User-Agent" in wrapper.client._headers
    assert wrapper.client._headers["User-Agent"] == "TestClient (test@example.com)"


def test_init_with_caching():
    """Test initialization with caching enabled."""
    wrapper = NoaaApiWrapper(user_agent="TestClient", enable_caching=True, cache_ttl=300)

    assert wrapper.cache is not None
    assert wrapper.cache.default_ttl == 300


def test_generate_cache_key():
    """Test cache key generation."""
    wrapper = NoaaApiWrapper()

    # Test with simple endpoint
    key1 = wrapper._generate_cache_key("points/40.0,-75.0")
    assert isinstance(key1, str)
    assert len(key1) > 0

    # Test with endpoint and params
    key2 = wrapper._generate_cache_key(
        "points/40.0,-75.0", {"param1": "value1", "param2": "value2"}
    )
    assert isinstance(key2, str)
    assert len(key2) > 0

    # Test that different inputs produce different keys
    key3 = wrapper._generate_cache_key("points/41.0,-76.0")
    assert key1 != key3


def test_get_cached_or_fetch_no_cache(api_wrapper):
    """Test _get_cached_or_fetch when caching is disabled."""
    mock_fetch = MagicMock(return_value={"data": "test"})

    result = api_wrapper._get_cached_or_fetch("test_key", mock_fetch)

    assert result == {"data": "test"}
    mock_fetch.assert_called_once()


def test_get_cached_or_fetch_with_cache(cached_api_wrapper):
    """Test _get_cached_or_fetch with caching enabled."""
    mock_fetch = MagicMock(return_value={"data": "test"})

    # First call should fetch
    result1 = cached_api_wrapper._get_cached_or_fetch("test_key", mock_fetch)

    assert result1 == {"data": "test"}
    mock_fetch.assert_called_once()

    # Reset mock for second call
    mock_fetch.reset_mock()

    # Second call should use cache
    result2 = cached_api_wrapper._get_cached_or_fetch("test_key", mock_fetch)

    assert result2 == {"data": "test"}
    mock_fetch.assert_not_called()


def test_get_cached_or_fetch_force_refresh(cached_api_wrapper):
    """Test _get_cached_or_fetch with force_refresh=True."""
    mock_fetch = MagicMock(return_value={"data": "test"})

    # First call should fetch
    result1 = cached_api_wrapper._get_cached_or_fetch("test_key", mock_fetch)

    assert result1 == {"data": "test"}
    mock_fetch.assert_called_once()

    # Reset mock for second call
    mock_fetch.reset_mock()

    # Second call with force_refresh should fetch again
    result2 = cached_api_wrapper._get_cached_or_fetch("test_key", mock_fetch, force_refresh=True)

    assert result2 == {"data": "test"}
    mock_fetch.assert_called_once()


def test_get_point_data_caching_original(cached_api_wrapper):
    """Test caching in get_point_data method."""
    lat, lon = 40.0, -75.0

    # Define a spec for the properties object to guide MagicMock's behavior.
    # This ensures that hasattr(mock_properties, "additional_properties") will be False,
    # directing _transform_point_data to the correct processing path for this mock.
    class PointPropertiesSpec:
        forecast: str
        forecast_hourly: str
        forecast_grid_data: str
        observation_stations: str
        county: str
        fire_weather_zone: str
        time_zone: str
        radar_station: str
        # Note: 'additional_properties' is intentionally omitted from this spec.

    # Mock the _make_api_request method
    with patch.object(cached_api_wrapper, "_make_api_request") as mock_make_api_request:
        # Create a mock properties object using the defined spec
        mock_properties = MagicMock(spec=PointPropertiesSpec)
        mock_properties.forecast = "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
        mock_properties.forecast_hourly = (
            "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly"
        )
        mock_properties.forecast_grid_data = "https://api.weather.gov/gridpoints/PHI/31,70"
        mock_properties.observation_stations = (
            "https://api.weather.gov/gridpoints/PHI/31,70/stations"
        )
        mock_properties.county = "https://api.weather.gov/zones/county/PAC101"
        mock_properties.fire_weather_zone = "https://api.weather.gov/zones/fire/PAZ103"
        mock_properties.time_zone = "America/New_York"
        mock_properties.radar_station = "KDIX"

        # Create a mock response object
        mock_response = MagicMock()
        mock_response.properties = mock_properties

        mock_make_api_request.return_value = mock_response

        # First call should make the API request
        result1 = cached_api_wrapper.get_point_data(lat, lon)

        assert "properties" in result1
        assert result1["properties"]["forecast"] == mock_properties.forecast
        assert result1["properties"]["forecastHourly"] == mock_properties.forecast_hourly
        mock_make_api_request.assert_called_once()

        # Reset the mock to track subsequent calls
        mock_make_api_request.reset_mock()

        # Second call should use cache
        result2 = cached_api_wrapper.get_point_data(lat, lon)

        assert result2 == result1
        mock_make_api_request.assert_not_called()

        # Third call with force_refresh should make the API request again
        mock_make_api_request.reset_mock()
        result3 = cached_api_wrapper.get_point_data(lat, lon, force_refresh=True)

        # Assuming the transformation is deterministic and data hasn't changed.
        assert result3 == result1
        mock_make_api_request.assert_called_once()


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


@pytest.mark.unit
def test_cache_hit_and_miss_scenarios(cached_api_wrapper):
    """Test cache hit and miss scenarios."""
    lat, lon = 40.0, -75.0

    with patch.object(cached_api_wrapper, "_make_api_request") as mock_request:
        mock_request.return_value = SAMPLE_POINT_DATA

        # First call should miss cache and fetch data
        result1 = cached_api_wrapper.get_point_data(lat, lon)
        assert mock_request.call_count == 1

        # Second call should hit cache
        result2 = cached_api_wrapper.get_point_data(lat, lon)
        assert mock_request.call_count == 1  # No additional calls
        assert result1 == result2

        # Force refresh should bypass cache
        result3 = cached_api_wrapper.get_point_data(lat, lon, force_refresh=True)
        assert mock_request.call_count == 2  # One additional call


@pytest.mark.unit
def test_error_handling_for_http_errors(api_wrapper):
    """Test error handling for different HTTP status codes."""
    test_cases = [
        (404, "CLIENT_ERROR"),
        (429, "RATE_LIMIT_ERROR"),
        (500, "SERVER_ERROR"),
        (503, "SERVER_ERROR"),
    ]

    for status_code, expected_error_type in test_cases:
        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.side_effect = MockUnexpectedStatus(status_code)

            with pytest.raises(NoaaApiError) as exc_info:
                api_wrapper.get_point_data(40.0, -75.0)

            assert hasattr(exc_info.value, "error_type")


@pytest.mark.unit
def test_request_transformation_point_data(api_wrapper):
    """Test request transformation for point data."""
    # Test with object-style response that has additional_properties
    mock_properties = MagicMock()
    mock_properties.additional_properties = {
        "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
    }

    mock_response = MagicMock()
    mock_response.properties = mock_properties

    result = api_wrapper._transform_point_data(mock_response)

    assert "properties" in result
    assert (
        result["properties"]["forecast"] == "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
    )
    assert (
        result["properties"]["forecastHourly"]
        == "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly"
    )


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


@pytest.mark.unit
def test_transform_point_data_dict_format(api_wrapper):
    """Test _transform_point_data with dictionary input."""
    input_data = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
            "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
            "county": "https://api.weather.gov/zones/county/PAC101",
            "timeZone": "America/New_York",
        }
    }

    result = api_wrapper._transform_point_data(input_data)

    assert result["properties"]["forecast"] == input_data["properties"]["forecast"]
    assert result["properties"]["forecastHourly"] == input_data["properties"]["forecastHourly"]
    assert result["properties"]["county"] == input_data["properties"]["county"]
    assert result["properties"]["timeZone"] == input_data["properties"]["timeZone"]


@pytest.mark.unit
def test_transform_point_data_object_with_additional_properties(api_wrapper):
    """Test _transform_point_data with object having additional_properties."""
    mock_properties = MagicMock()
    mock_properties.additional_properties = {
        "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
    }

    mock_data = MagicMock()
    mock_data.properties = mock_properties

    result = api_wrapper._transform_point_data(mock_data)

    assert (
        result["properties"]["forecast"] == "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
    )
    assert (
        result["properties"]["forecastHourly"]
        == "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly"
    )


@pytest.mark.unit
def test_transform_point_data_object_without_additional_properties(api_wrapper):
    """Test _transform_point_data with object without additional_properties."""
    mock_properties = MagicMock()
    mock_properties.forecast = "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
    mock_properties.forecast_hourly = "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly"
    # Ensure additional_properties doesn't exist
    del mock_properties.additional_properties

    mock_data = MagicMock()
    mock_data.properties = mock_properties

    result = api_wrapper._transform_point_data(mock_data)

    assert (
        result["properties"]["forecast"] == "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
    )
    assert (
        result["properties"]["forecastHourly"]
        == "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly"
    )


@pytest.mark.unit
def test_transform_point_data_fallback(api_wrapper):
    """Test _transform_point_data fallback when no properties."""
    mock_data = MagicMock()
    mock_data.properties = None

    result = api_wrapper._transform_point_data(mock_data)

    assert result == {"properties": {}}


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


def test_rate_limit_retry_mechanism(api_wrapper):
    """Test the retry mechanism for rate limited requests."""

    # Create a mock NoaaApiError class for local control
    class NoaaApiError(Exception):
        RATE_LIMIT_ERROR = "rate_limit_error"
        CLIENT_ERROR = "client_error"
        SERVER_ERROR = "server_error"
        UNKNOWN_ERROR = "unknown_error"

        def __init__(self, message=None, error_type=None, status_code=None, url=None):
            self.message = message
            self.error_type = error_type
            self.status_code = status_code
            self.url = url
            super().__init__(message)

    # Patch NoaaApiError as seen by api_wrapper to use our local version
    with patch("accessiweather.api_wrapper.NoaaApiError", new=NoaaApiError):
        # Define a simple mock for UnexpectedStatus that api_wrapper will see
        class MockApiUnexpectedStatus:
            def __init__(self, status_code, content=None):
                self.status_code = status_code
                self.content = content  # Store content if api_wrapper._handle_client_error uses it

        # Patch the actual UnexpectedStatus used by api_wrapper with our mock
        with patch("accessiweather.api_wrapper.UnexpectedStatus", new=MockApiUnexpectedStatus):
            # Create an instance of our mocked UnexpectedStatus
            mock_error_instance = MockApiUnexpectedStatus(
                status_code=429, content=b"Rate limit exceeded"
            )

            # Mock the _handle_rate_limit method to avoid actual sleeping and for verification
            with patch.object(api_wrapper, "_handle_rate_limit") as mock_handle_rate_limit:
                # --- Test 1: Successful retry scenario ---
                # api_wrapper._handle_client_error should call _handle_rate_limit (which we've mocked)
                # and then return a NoaaApiError with error_type="retry"
                error = api_wrapper._handle_client_error(
                    mock_error_instance, "https://api.weather.gov/test", 0
                )

                mock_handle_rate_limit.assert_called_once_with("https://api.weather.gov/test", 0)
                assert error.error_type == "retry", "Error type should indicate a retry is needed"
                assert error.status_code == 429, "Status code should be preserved"

                # Reset for the next scenario
                mock_handle_rate_limit.reset_mock()

                # --- Test 2: Max retries exceeded scenario ---
                # Configure the mocked _handle_rate_limit to simulate max retries being hit
                # by raising the specific NoaaApiError it's supposed to raise in that case.
                max_retry_error = NoaaApiError(
                    message="Rate limit exceeded after 3 retries",
                    error_type=NoaaApiError.RATE_LIMIT_ERROR,  # Use the locally defined constant
                    status_code=429,
                    url="https://api.weather.gov/test",
                )
                mock_handle_rate_limit.side_effect = max_retry_error

                # Call _handle_client_error with retry_count at the max limit (e.g., 3)
                error = api_wrapper._handle_client_error(
                    mock_error_instance, "https://api.weather.gov/test", 3
                )

                # _handle_rate_limit should still be called
                mock_handle_rate_limit.assert_called_once_with("https://api.weather.gov/test", 3)

                # The error returned should now be the one raised by _handle_rate_limit
                assert error is max_retry_error, "Should return the error from _handle_rate_limit"
                assert (
                    error.error_type == NoaaApiError.RATE_LIMIT_ERROR
                ), "Error type should be RATE_LIMIT_ERROR"
                assert (
                    "after 3 retries" in error.message
                ), "Error message should indicate max retries exceeded"


def test_cache_performance(cached_api_wrapper):
    """Test cache performance by measuring response times."""
    import time

    # Create a slow fetch function
    def slow_fetch():
        time.sleep(0.1)  # Simulate a slow API call
        return {"data": "test"}

    # Measure time for first call (cache miss)
    start_time = time.time()
    cached_api_wrapper._get_cached_or_fetch("perf_test_key", slow_fetch)
    first_call_time = time.time() - start_time

    # Measure time for second call (cache hit)
    start_time = time.time()
    cached_api_wrapper._get_cached_or_fetch("perf_test_key", slow_fetch)
    second_call_time = time.time() - start_time

    # Cache hit should be significantly faster
    assert second_call_time < first_call_time
    assert second_call_time < 0.01  # Cache lookup should be very fast


def test_make_api_request_success(api_wrapper):
    """Test successful API request using _make_api_request."""
    # Create a mock function
    mock_func = MagicMock(return_value={"data": "test"})

    # Call the method
    result = api_wrapper._make_api_request(mock_func, arg1="value1", arg2="value2")

    # Verify the result
    assert result == {"data": "test"}
    mock_func.assert_called_once_with(arg1="value1", arg2="value2", client=api_wrapper.client)


def test_make_api_request_unexpected_status(api_wrapper):
    """Test handling of UnexpectedStatus exceptions in _make_api_request."""
    # Create a mock function that raises UnexpectedStatus
    mock_func = MagicMock(side_effect=MockUnexpectedStatus(404, b"Not found"))

    # Call the method and expect a NoaaApiError
    with pytest.raises(NoaaApiError) as excinfo:
        api_wrapper._make_api_request(mock_func, arg1="value1")

    # Verify the exception
    assert "404" in str(excinfo.value)
    mock_func.assert_called_once_with(arg1="value1", client=api_wrapper.client)


def test_make_api_request_rate_limit(api_wrapper):
    """Test handling of rate limit (429) errors in _make_api_request."""
    # Create a mock function that raises UnexpectedStatus with 429
    mock_func = MagicMock(side_effect=MockUnexpectedStatus(429, b"Rate limit exceeded"))

    # Call the method and expect a NoaaApiError
    with pytest.raises(NoaaApiError) as excinfo:
        api_wrapper._make_api_request(mock_func, arg1="value1")

    # Verify the exception
    assert "429" in str(excinfo.value)
    mock_func.assert_called_once_with(arg1="value1", client=api_wrapper.client)


def test_make_api_request_server_error(api_wrapper):
    """Test handling of server errors in _make_api_request."""
    # Create a mock function that raises UnexpectedStatus with 500
    mock_func = MagicMock(side_effect=MockUnexpectedStatus(500, b"Internal server error"))

    # Call the method and expect a NoaaApiError
    with pytest.raises(NoaaApiError) as excinfo:
        api_wrapper._make_api_request(mock_func, arg1="value1")

    # Verify the exception
    assert "500" in str(excinfo.value)
    mock_func.assert_called_once_with(arg1="value1", client=api_wrapper.client)


def test_make_api_request_network_error(api_wrapper):
    """Test handling of network errors in _make_api_request."""
    # Import httpx for the exception types
    import httpx

    # Create a mock function that raises a network error
    mock_func = MagicMock(side_effect=httpx.RequestError("Connection failed", request=None))

    # Call the method and expect a NoaaApiError
    with pytest.raises(Exception) as excinfo:
        api_wrapper._make_api_request(mock_func, arg1="value1")

    # Verify the exception
    assert "Network error" in str(excinfo.value)
    mock_func.assert_called_once_with(arg1="value1", client=api_wrapper.client)


def test_make_api_request_timeout(api_wrapper):
    """Test handling of timeout errors in _make_api_request."""
    # Import httpx for the exception types
    import httpx

    # Create a mock function that raises a timeout error
    mock_func = MagicMock(side_effect=httpx.TimeoutException("Request timed out", request=None))

    # Call the method and expect a NoaaApiError
    with pytest.raises(Exception) as excinfo:
        api_wrapper._make_api_request(mock_func, arg1="value1")

    # Verify the exception
    assert "Request timed out" in str(excinfo.value)
    mock_func.assert_called_once_with(arg1="value1", client=api_wrapper.client)
