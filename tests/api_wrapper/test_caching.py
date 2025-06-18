"""Tests for NoaaApiWrapper caching functionality."""

import time
from unittest.mock import MagicMock, patch

import pytest

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
        patch("accessiweather.api.nws_wrapper.NwsApiWrapper") as mock_nws,
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


def test_get_cached_or_fetch_no_cache(api_wrapper):
    """Test _get_cached_or_fetch when caching is disabled through NWS wrapper."""
    mock_fetch = MagicMock(return_value={"data": "test"})

    # Test through the NWS wrapper since NoaaApiWrapper delegates to it
    result = api_wrapper.nws_wrapper._get_cached_or_fetch("test_key", mock_fetch)

    assert result == {"data": "test"}
    mock_fetch.assert_called_once()


def test_get_cached_or_fetch_with_cache(cached_api_wrapper):
    """Test _get_cached_or_fetch with caching enabled through NWS wrapper."""
    mock_fetch = MagicMock(return_value={"data": "test"})

    # First call should fetch
    result1 = cached_api_wrapper.nws_wrapper._get_cached_or_fetch("test_key", mock_fetch)

    assert result1 == {"data": "test"}
    mock_fetch.assert_called_once()

    # Reset mock for second call
    mock_fetch.reset_mock()

    # Second call should use cache
    result2 = cached_api_wrapper.nws_wrapper._get_cached_or_fetch("test_key", mock_fetch)

    assert result2 == {"data": "test"}
    mock_fetch.assert_not_called()


def test_get_cached_or_fetch_force_refresh(cached_api_wrapper):
    """Test _get_cached_or_fetch with force_refresh=True through NWS wrapper."""
    mock_fetch = MagicMock(return_value={"data": "test"})

    # First call should fetch
    result1 = cached_api_wrapper.nws_wrapper._get_cached_or_fetch("test_key", mock_fetch)

    assert result1 == {"data": "test"}
    mock_fetch.assert_called_once()

    # Reset mock for second call
    mock_fetch.reset_mock()

    # Second call with force_refresh should fetch again
    result2 = cached_api_wrapper.nws_wrapper._get_cached_or_fetch(
        "test_key", mock_fetch, force_refresh=True
    )

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
