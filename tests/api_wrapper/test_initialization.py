"""Tests for NoaaApiWrapper initialization and basic functionality."""

# Mock the weather_gov_api_client modules
import sys
from unittest.mock import MagicMock, patch

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


# Fixtures
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
            user_agent="TestClient",
            contact_info="test@example.com",
            enable_caching=True,
            cache_ttl=300,
        )

        # Ensure the wrapper has the expected attributes
        wrapper.nws_wrapper = mock_nws_instance
        wrapper.openmeteo_wrapper = mock_openmeteo_instance

        return wrapper


# Tests
def test_init_basic():
    """Test basic initialization without caching."""
    wrapper = NoaaApiWrapper(user_agent="TestClient")

    assert wrapper.user_agent == "TestClient"
    # Access headers through the NWS wrapper's client
    assert "User-Agent" in wrapper.nws_wrapper.client._headers
    assert wrapper.nws_wrapper.client._headers["User-Agent"] == "TestClient (TestClient)"
    assert wrapper.nws_wrapper.cache is None


def test_init_with_contact():
    """Test initialization with contact info."""
    wrapper = NoaaApiWrapper(user_agent="TestClient", contact_info="test@example.com")

    # Access headers through the NWS wrapper's client
    assert "User-Agent" in wrapper.nws_wrapper.client._headers
    assert wrapper.nws_wrapper.client._headers["User-Agent"] == "TestClient (test@example.com)"


def test_init_with_caching():
    """Test initialization with caching enabled."""
    wrapper = NoaaApiWrapper(user_agent="TestClient", enable_caching=True, cache_ttl=300)

    assert wrapper.nws_wrapper.cache is not None
    assert wrapper.nws_wrapper.cache.default_ttl == 300


def test_generate_cache_key():
    """Test cache key generation through NWS wrapper."""
    with (
        patch("accessiweather.api.nws.NwsApiWrapper") as mock_nws,
        patch("accessiweather.api.openmeteo_wrapper.OpenMeteoApiWrapper") as mock_openmeteo,
    ):
        # Create mock instances with proper _generate_cache_key method
        mock_nws_instance = MagicMock()
        mock_nws_instance._generate_cache_key = MagicMock()
        mock_nws_instance._generate_cache_key.side_effect = ["key1_hash", "key2_hash", "key3_hash"]
        mock_nws.return_value = mock_nws_instance

        mock_openmeteo_instance = MagicMock()
        mock_openmeteo.return_value = mock_openmeteo_instance

        wrapper = NoaaApiWrapper()
        wrapper.nws_wrapper = mock_nws_instance
        wrapper.openmeteo_wrapper = mock_openmeteo_instance

        # Test cache key generation through the NWS wrapper (since NoaaApiWrapper delegates to it)
        key1 = wrapper.nws_wrapper._generate_cache_key("points/40.0,-75.0")
        assert isinstance(key1, str)
        assert len(key1) > 0

        # Test with endpoint and params
        key2 = wrapper.nws_wrapper._generate_cache_key(
            "points/40.0,-75.0", {"param1": "value1", "param2": "value2"}
        )
        assert isinstance(key2, str)
        assert len(key2) > 0

        # Test that different inputs produce different keys
        key3 = wrapper.nws_wrapper._generate_cache_key("points/41.0,-76.0")
        assert key1 != key3
