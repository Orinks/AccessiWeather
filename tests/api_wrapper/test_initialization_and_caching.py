"""Tests for NoaaApiWrapper initialization and caching functionality."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_wrapper import NoaaApiWrapper
from tests.api_wrapper_test_utils import (
    SAMPLE_POINT_DATA,
    api_wrapper,
    cached_api_wrapper,
    create_mock_point_response,
)


def test_init_basic():
    """Test basic initialization without caching."""
    wrapper = NoaaApiWrapper(user_agent="TestClient")

    assert wrapper.user_agent == "TestClient"
    # Access headers through the private attribute
    assert "User-Agent" in wrapper.client._headers
    assert wrapper.client._headers["User-Agent"] == "TestClient (TestClient)"
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

    # Mock the _make_api_request method
    with patch.object(cached_api_wrapper, "_make_api_request") as mock_make_api_request:
        mock_response = create_mock_point_response()
        mock_make_api_request.return_value = mock_response

        # First call should make the API request
        result1 = cached_api_wrapper.get_point_data(lat, lon)

        assert "properties" in result1
        assert result1["properties"]["forecast"] == mock_response.properties.forecast
        assert result1["properties"]["forecastHourly"] == mock_response.properties.forecast_hourly
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

    lat, lon = 40.0, -75.0

    with patch.object(cached_api_wrapper, "_make_api_request") as mock_request:
        # Simulate a slow API response
        def slow_response(*args, **kwargs):
            time.sleep(0.1)  # 100ms delay
            return SAMPLE_POINT_DATA

        mock_request.side_effect = slow_response

        # First call (cache miss) - should be slow
        start_time = time.time()
        result1 = cached_api_wrapper.get_point_data(lat, lon)
        first_call_time = time.time() - start_time

        # Second call (cache hit) - should be fast
        start_time = time.time()
        result2 = cached_api_wrapper.get_point_data(lat, lon)
        second_call_time = time.time() - start_time

        # Cache hit should be significantly faster
        assert second_call_time < first_call_time / 2
        assert result1 == result2
        assert mock_request.call_count == 1  # Only one actual API call
