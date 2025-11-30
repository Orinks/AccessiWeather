"""Tests for API base wrapper functionality."""

import time
from unittest.mock import Mock, patch

import httpx
import pytest

from accessiweather.api.base_wrapper import BaseApiWrapper
from accessiweather.api_client import NoaaApiError


class ConcreteApiWrapper(BaseApiWrapper):
    """Concrete implementation of BaseApiWrapper for testing."""

    def get_current_conditions(self, lat: float, lon: float, **kwargs):
        """Get test current conditions."""
        return {"temperature": 72, "conditions": "sunny"}

    def get_forecast(self, lat: float, lon: float, **kwargs):
        """Get test forecast."""
        return {"forecast": "partly cloudy"}

    def get_hourly_forecast(self, lat: float, lon: float, **kwargs):
        """Get test hourly forecast."""
        return {"hourly": ["hour1", "hour2"]}


class TestBaseApiWrapper:
    """Test suite for BaseApiWrapper class."""

    def test_initialization_default_values(self):
        """Test wrapper initialization with default values."""
        wrapper = ConcreteApiWrapper()
        assert wrapper.user_agent == "AccessiWeather"
        assert wrapper.contact_info == "AccessiWeather"  # Defaults to user_agent
        assert wrapper.cache is None  # Caching disabled by default
        assert wrapper.min_request_interval == 0.5
        assert wrapper.max_retries == 3

    def test_initialization_custom_values(self):
        """Test wrapper initialization with custom values."""
        wrapper = ConcreteApiWrapper(
            user_agent="TestAgent/1.0",
            contact_info="test@example.com",
            enable_caching=True,
            cache_ttl=600,
            min_request_interval=1.0,
            max_retries=5,
        )
        assert wrapper.user_agent == "TestAgent/1.0"
        assert wrapper.contact_info == "test@example.com"
        assert wrapper.cache is not None
        assert wrapper.min_request_interval == 1.0
        assert wrapper.max_retries == 5

    def test_caching_enabled(self):
        """Test that caching is properly enabled."""
        wrapper = ConcreteApiWrapper(enable_caching=True, cache_ttl=10)
        assert wrapper.cache is not None

    def test_caching_disabled(self):
        """Test that caching is disabled by default."""
        wrapper = ConcreteApiWrapper(enable_caching=False)
        assert wrapper.cache is None

    def test_cache_key_generation(self):
        """Test cache key generation from endpoint and parameters."""
        wrapper = ConcreteApiWrapper(enable_caching=True)

        endpoint = "weather"
        params = {"lat": 40.7128, "lon": -74.0060}

        # Generate cache key
        cache_key = wrapper._generate_cache_key(endpoint, params)

        # Verify it's a hash
        assert isinstance(cache_key, str)
        assert len(cache_key) == 64  # SHA256 produces 64 hex characters

        # Verify same endpoint/params produces same key
        cache_key2 = wrapper._generate_cache_key(endpoint, params)
        assert cache_key == cache_key2

        # Verify different params produces different key
        params2 = {"lat": 41.0, "lon": -73.0}
        cache_key3 = wrapper._generate_cache_key(endpoint, params2)
        assert cache_key != cache_key3

    def test_rate_limiting_enforcement(self):
        """Test that rate limiting enforces minimum request interval."""
        wrapper = ConcreteApiWrapper(min_request_interval=0.02)

        # Make first request
        start_time = time.time()
        wrapper._rate_limit()

        # Make second request immediately
        wrapper._rate_limit()
        elapsed = time.time() - start_time

        # Should have waited at least min_request_interval
        assert elapsed >= 0.02

    def test_rate_limit_thread_safety(self):
        """Test that rate limiting is thread-safe."""
        wrapper = ConcreteApiWrapper(min_request_interval=0.02)

        import threading

        results = []

        def make_request():
            start = time.time()
            wrapper._rate_limit()
            elapsed = time.time() - start
            results.append(elapsed)

        # Run multiple threads
        threads = [threading.Thread(target=make_request) for _ in range(3)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # At least some threads should have waited
        assert any(r >= 0.02 for r in results)

    def test_fetch_url_success(self):
        """Test successful URL fetch."""
        wrapper = ConcreteApiWrapper()

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"temperature": 72}

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            result = wrapper._fetch_url("https://api.test.com/weather")
            assert result["temperature"] == 72

    def test_fetch_url_with_headers(self):
        """Test URL fetch with custom headers."""
        wrapper = ConcreteApiWrapper(user_agent="TestAgent", contact_info="test@example.com")

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"temperature": 72}

        with patch("httpx.Client") as mock_client:
            mock_get = mock_client.return_value.__enter__.return_value.get
            mock_get.return_value = mock_response

            custom_headers = {"X-Custom": "value"}
            wrapper._fetch_url("https://api.test.com/weather", headers=custom_headers)

            # Check that headers were merged
            call_args = mock_get.call_args
            headers = call_args[1]["headers"]
            assert "User-Agent" in headers
            assert headers["User-Agent"] == "TestAgent (test@example.com)"
            assert headers["X-Custom"] == "value"

    def test_fetch_url_http_error_404(self):
        """Test handling of 404 HTTP error."""
        wrapper = ConcreteApiWrapper()

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("httpx.Client") as mock_client:
            mock_get = mock_client.return_value.__enter__.return_value.get
            mock_get.return_value = mock_response
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not found", request=Mock(), response=mock_response
            )

            with pytest.raises(NoaaApiError) as exc_info:
                wrapper._fetch_url("https://api.test.com/notfound")

            assert exc_info.value.error_type == NoaaApiError.HTTP_ERROR
            assert exc_info.value.status_code == 404

    def test_fetch_url_rate_limit_retry(self):
        """Test retry logic for 429 rate limit errors."""
        wrapper = ConcreteApiWrapper(max_retries=2, retry_initial_wait=0.01, retry_backoff=1.5)

        # First two calls return 429, third succeeds
        mock_response_429 = Mock(spec=httpx.Response)
        mock_response_429.status_code = 429

        mock_response_200 = Mock(spec=httpx.Response)
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"temperature": 72}

        call_count = [0]

        def get_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                mock_response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Rate limited", request=Mock(), response=mock_response_429
                )
                return mock_response_429
            return mock_response_200

        with (
            patch("httpx.Client") as mock_client,
            patch("accessiweather.api.base_wrapper.time.sleep"),
        ):
            mock_client.return_value.__enter__.return_value.get.side_effect = get_side_effect

            result = wrapper._fetch_url("https://api.test.com/weather")
            assert result["temperature"] == 72
            assert call_count[0] == 3  # Two retries, then success

    def test_fetch_url_rate_limit_max_retries_exceeded(self):
        """Test that max retries raises error."""
        wrapper = ConcreteApiWrapper(max_retries=2, retry_initial_wait=0.01)

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=Mock(), response=mock_response
        )

        with (
            patch("httpx.Client") as mock_client,
            patch("accessiweather.api.base_wrapper.time.sleep"),
        ):
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            with pytest.raises(NoaaApiError) as exc_info:
                wrapper._fetch_url("https://api.test.com/weather")

            assert exc_info.value.error_type == NoaaApiError.RATE_LIMIT_ERROR

    def test_fetch_url_network_error(self):
        """Test handling of network errors."""
        wrapper = ConcreteApiWrapper()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = httpx.RequestError(
                "Connection failed"
            )

            with pytest.raises(NoaaApiError) as exc_info:
                wrapper._fetch_url("https://api.test.com/error")

            assert exc_info.value.error_type == NoaaApiError.NETWORK_ERROR

    def test_fetch_url_unexpected_error(self):
        """Test handling of unexpected errors."""
        wrapper = ConcreteApiWrapper()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = ValueError(
                "Unexpected error"
            )

            with pytest.raises(NoaaApiError) as exc_info:
                wrapper._fetch_url("https://api.test.com/error")

            assert exc_info.value.error_type == NoaaApiError.UNKNOWN_ERROR

    def test_get_cached_or_fetch_no_cache(self):
        """Test _get_cached_or_fetch when caching is disabled."""
        wrapper = ConcreteApiWrapper(enable_caching=False)

        fetch_count = [0]

        def fetch_func():
            fetch_count[0] += 1
            return {"data": fetch_count[0]}

        # Should call fetch_func both times since caching is disabled
        result1 = wrapper._get_cached_or_fetch("key1", fetch_func)
        result2 = wrapper._get_cached_or_fetch("key1", fetch_func)

        assert result1["data"] == 1
        assert result2["data"] == 2
        assert fetch_count[0] == 2

    def test_get_cached_or_fetch_with_cache(self):
        """Test _get_cached_or_fetch when caching is enabled."""
        wrapper = ConcreteApiWrapper(enable_caching=True, cache_ttl=10)

        fetch_count = [0]

        def fetch_func():
            fetch_count[0] += 1
            return {"data": fetch_count[0]}

        # First call should fetch
        result1 = wrapper._get_cached_or_fetch("key1", fetch_func)
        assert result1["data"] == 1
        assert fetch_count[0] == 1

        # Second call should use cache
        result2 = wrapper._get_cached_or_fetch("key1", fetch_func)
        assert result2["data"] == 1  # Same data
        assert fetch_count[0] == 1  # No additional fetch

    def test_get_cached_or_fetch_force_refresh(self):
        """Test _get_cached_or_fetch with force_refresh."""
        wrapper = ConcreteApiWrapper(enable_caching=True, cache_ttl=10)

        fetch_count = [0]

        def fetch_func():
            fetch_count[0] += 1
            return {"data": fetch_count[0]}

        # First call
        result1 = wrapper._get_cached_or_fetch("key1", fetch_func)
        assert result1["data"] == 1

        # Force refresh should bypass cache
        result2 = wrapper._get_cached_or_fetch("key1", fetch_func, force_refresh=True)
        assert result2["data"] == 2
        assert fetch_count[0] == 2

    def test_abstract_methods_must_be_implemented(self):
        """Test that abstract methods must be implemented by subclasses."""
        # This should work since ConcreteApiWrapper implements all abstract methods
        wrapper = ConcreteApiWrapper()
        assert wrapper.get_current_conditions(40.7, -74.0) is not None
        assert wrapper.get_forecast(40.7, -74.0) is not None
        assert wrapper.get_hourly_forecast(40.7, -74.0) is not None
