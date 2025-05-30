"""Comprehensive tests for the OpenWeatherMap wrapper.

This module provides tests for all components of the OpenWeatherMap wrapper,
including error handling, rate limiting, caching, and data mapping.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from accessiweather.openweathermap_client import (
    AuthenticationError,
    NotFoundError,
    OpenWeatherMapError,
    RateLimitError,
)
from accessiweather.openweathermap_wrapper import OpenWeatherMapWrapper


class TestOpenWeatherMapWrapperCore(unittest.TestCase):
    """Core tests for the OpenWeatherMap wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key_12345678901234567890"
        self.wrapper = OpenWeatherMapWrapper(
            api_key=self.api_key,
            enable_caching=True,
            cache_ttl=300,
            min_request_interval=0.1,  # Short interval for testing
        )

    def test_wrapper_initialization(self):
        """Test wrapper initialization with various parameters."""
        # Test default initialization
        wrapper = OpenWeatherMapWrapper(api_key=self.api_key)
        self.assertEqual(wrapper.api_key, self.api_key)
        self.assertEqual(wrapper.cache_ttl, 300)
        self.assertEqual(wrapper.min_request_interval, 1.0)
        self.assertEqual(wrapper.max_retries, 3)
        self.assertEqual(wrapper.client.units, "imperial")
        self.assertEqual(wrapper.client.language, "en")

        # Test custom initialization
        wrapper = OpenWeatherMapWrapper(
            api_key=self.api_key,
            enable_caching=True,
            cache_ttl=600,
            min_request_interval=2.0,
            max_retries=5,
            units="metric",
            language="es",
        )
        self.assertTrue(wrapper.enable_caching)
        self.assertEqual(wrapper.cache_ttl, 600)
        self.assertEqual(wrapper.min_request_interval, 2.0)
        self.assertEqual(wrapper.max_retries, 5)
        self.assertEqual(wrapper.client.units, "metric")
        self.assertEqual(wrapper.client.language, "es")

    def test_cache_key_generation(self):
        """Test cache key generation."""
        cache_key = self.wrapper._get_cache_key("current", lat=51.5, lon=-0.1)
        self.assertIn("current", cache_key)
        self.assertIn("51.5", cache_key)
        self.assertIn("-0.1", cache_key)

        # Test with additional parameters
        cache_key = self.wrapper._get_cache_key("forecast", lat=51.5, lon=-0.1, days=7)
        self.assertIn("forecast", cache_key)
        self.assertIn("days=7", cache_key)

    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        # Mock the client to avoid actual API calls
        with patch.object(self.wrapper.client, "get_current_weather") as mock_get:
            mock_get.return_value = {"test": "data"}

            # First call should go through immediately
            start_time = time.time()
            self.wrapper.get_current_conditions(51.5, -0.1)
            first_call_time = time.time() - start_time

            # Second call should be rate limited
            start_time = time.time()
            self.wrapper.get_current_conditions(51.5, -0.1)
            second_call_time = time.time() - start_time

            # Second call should take longer due to rate limiting
            self.assertGreater(second_call_time, first_call_time)

    @patch.object(OpenWeatherMapWrapper, "_cached_request")
    def test_get_current_conditions(self, mock_cached_request):
        """Test getting current weather conditions."""
        # Mock the mapped response
        mock_cached_request.return_value = {
            "location": {"name": "London", "lat": 51.5074, "lon": -0.1278},
            "current": {"temperature": 59.0, "condition": "Clear", "humidity": 65},
        }

        result = self.wrapper.get_current_conditions(51.5074, -0.1278)

        # Check the result
        self.assertIn("location", result)
        self.assertIn("current", result)
        self.assertEqual(result["location"]["name"], "London")
        self.assertEqual(result["current"]["temperature"], 59.0)

        # Check that cached_request was called
        mock_cached_request.assert_called_once()

    @patch.object(OpenWeatherMapWrapper, "_cached_request")
    def test_get_forecast(self, mock_cached_request):
        """Test getting weather forecast."""
        # Mock the mapped response
        mock_cached_request.return_value = {
            "location": {"lat": 51.5074, "lon": -0.1278},
            "forecast": {
                "days": [{"date": "2023-05-22", "high": 72.5, "low": 59.4, "condition": "Sunny"}]
            },
        }

        result = self.wrapper.get_forecast(51.5074, -0.1278, days=3)

        # Check the result
        self.assertIn("location", result)
        self.assertIn("forecast", result)
        self.assertEqual(len(result["forecast"]["days"]), 1)
        self.assertEqual(result["forecast"]["days"][0]["condition"], "Sunny")

        # Check that cached_request was called
        mock_cached_request.assert_called_once()

    @patch.object(OpenWeatherMapWrapper, "_cached_request")
    def test_get_hourly_forecast(self, mock_cached_request):
        """Test getting hourly weather forecast."""
        # Mock the mapped response
        mock_cached_request.return_value = {
            "location": {"lat": 51.5074, "lon": -0.1278},
            "hourly_forecast": {
                "hours": [{"time": "2023-05-22 00:00", "temperature": 61.7, "condition": "Clear"}]
            },
        }

        result = self.wrapper.get_hourly_forecast(51.5074, -0.1278, hours=24)

        # Check the result
        self.assertIn("location", result)
        self.assertIn("hourly_forecast", result)
        self.assertEqual(len(result["hourly_forecast"]["hours"]), 1)
        self.assertEqual(result["hourly_forecast"]["hours"][0]["condition"], "Clear")

        # Check that cached_request was called
        mock_cached_request.assert_called_once()

    @patch.object(OpenWeatherMapWrapper, "_cached_request")
    def test_get_alerts(self, mock_cached_request):
        """Test getting weather alerts."""
        # Mock the mapped response
        mock_cached_request.return_value = [
            {
                "event": "Flood Warning",
                "severity": "Moderate",
                "description": "Flooding is occurring or imminent.",
            }
        ]

        result = self.wrapper.get_alerts(51.5074, -0.1278)

        # Check the result
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["event"], "Flood Warning")

        # Check that cached_request was called
        mock_cached_request.assert_called_once()

    def test_validate_api_key_success(self):
        """Test successful API key validation."""
        with patch.object(self.wrapper.client, "get_current_weather") as mock_get:
            mock_get.return_value = {"test": "data"}

            result = self.wrapper.validate_api_key()
            self.assertTrue(result)

    def test_validate_api_key_failure(self):
        """Test failed API key validation."""
        with patch.object(self.wrapper.client, "get_current_weather") as mock_get:
            mock_get.side_effect = AuthenticationError("Invalid API key")

            result = self.wrapper.validate_api_key()
            self.assertFalse(result)

    def test_validate_api_key_unexpected_error(self):
        """Test API key validation with unexpected error."""
        with patch.object(self.wrapper.client, "get_current_weather") as mock_get:
            mock_get.side_effect = Exception("Unexpected error")

            result = self.wrapper.validate_api_key()
            self.assertFalse(result)


class TestOpenWeatherMapWrapperRetry(unittest.TestCase):
    """Tests for retry logic in OpenWeatherMap wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key_12345678901234567890"
        self.wrapper = OpenWeatherMapWrapper(
            api_key=self.api_key,
            max_retries=2,
            retry_initial_wait=0.01,  # Very short wait for testing
            retry_backoff=2.0,
        )

    def test_retry_on_rate_limit_error(self):
        """Test retry logic on rate limit errors."""
        mock_func = MagicMock()
        mock_func.side_effect = [
            RateLimitError("Rate limit exceeded"),
            RateLimitError("Rate limit exceeded"),
            {"success": True},  # Third attempt succeeds
        ]

        result = self.wrapper._make_request_with_retry(mock_func)
        self.assertEqual(result, {"success": True})
        self.assertEqual(mock_func.call_count, 3)

    def test_retry_exhausted(self):
        """Test retry logic when all attempts fail."""
        mock_func = MagicMock()
        mock_func.side_effect = RateLimitError("Rate limit exceeded")

        with self.assertRaises(RateLimitError):
            self.wrapper._make_request_with_retry(mock_func)

        # Should try max_retries + 1 times (initial + retries)
        self.assertEqual(mock_func.call_count, 3)

    def test_no_retry_on_auth_error(self):
        """Test that authentication errors are not retried."""
        mock_func = MagicMock()
        mock_func.side_effect = AuthenticationError("Invalid API key")

        with self.assertRaises(AuthenticationError):
            self.wrapper._make_request_with_retry(mock_func)

        # Should only try once
        self.assertEqual(mock_func.call_count, 1)

    def test_no_retry_on_not_found_error(self):
        """Test that not found errors are not retried."""
        mock_func = MagicMock()
        mock_func.side_effect = NotFoundError("Location not found")

        with self.assertRaises(NotFoundError):
            self.wrapper._make_request_with_retry(mock_func)

        # Should only try once
        self.assertEqual(mock_func.call_count, 1)


class TestOpenWeatherMapWrapperCaching(unittest.TestCase):
    """Tests for caching functionality in OpenWeatherMap wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key_12345678901234567890"
        self.wrapper = OpenWeatherMapWrapper(
            api_key=self.api_key,
            enable_caching=True,
            cache_ttl=300,
            min_request_interval=0.01,  # Very short for testing
        )

    def test_cache_hit(self):
        """Test cache hit scenario."""
        cache_key = "test_key"
        test_data = {"test": "data"}

        # Mock the cache to return data
        with patch.object(self.wrapper.cache, "get") as mock_get:
            mock_get.return_value = test_data

            mock_func = MagicMock()
            result = self.wrapper._cached_request(cache_key, mock_func)

            self.assertEqual(result, test_data)
            mock_get.assert_called_once_with(cache_key)
            mock_func.assert_not_called()  # Function should not be called on cache hit

    def test_cache_miss(self):
        """Test cache miss scenario."""
        cache_key = "test_key"
        test_data = {"test": "data"}

        # Mock the cache to return None (cache miss)
        with (
            patch.object(self.wrapper.cache, "get") as mock_get,
            patch.object(self.wrapper.cache, "set") as mock_set,
        ):
            mock_get.return_value = None

            mock_func = MagicMock()
            mock_func.return_value = test_data

            result = self.wrapper._cached_request(cache_key, mock_func)

            self.assertEqual(result, test_data)
            mock_get.assert_called_once_with(cache_key)
            mock_func.assert_called_once()
            mock_set.assert_called_once_with(cache_key, test_data, ttl=300)

    def test_cache_disabled(self):
        """Test behavior when caching is disabled."""
        wrapper = OpenWeatherMapWrapper(api_key=self.api_key, enable_caching=False)

        cache_key = "test_key"
        test_data = {"test": "data"}

        mock_func = MagicMock()
        mock_func.return_value = test_data

        result = wrapper._cached_request(cache_key, mock_func)

        self.assertEqual(result, test_data)
        mock_func.assert_called_once()
        self.assertIsNone(wrapper.cache)

    def test_force_refresh_invalidates_cache(self):
        """Test that force refresh invalidates cache."""
        with (
            patch.object(self.wrapper.cache, "invalidate") as mock_invalidate,
            patch.object(self.wrapper.client, "get_current_weather") as mock_get,
        ):
            mock_get.return_value = {"test": "data"}

            self.wrapper.get_current_conditions(51.5, -0.1, force_refresh=True)

            # Cache should be invalidated
            mock_invalidate.assert_called_once()


class TestOpenWeatherMapWrapperEdgeCases(unittest.TestCase):
    """Tests for edge cases in OpenWeatherMap wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.wrapper = OpenWeatherMapWrapper(
            api_key="test_key",
            enable_caching=True,
            cache_ttl=300,
            min_request_interval=0.1,
        )

    @patch.object(OpenWeatherMapWrapper, "_cached_request")
    def test_get_current_conditions_error_handling(self, mock_cached_request):
        """Test current conditions with error handling."""
        mock_cached_request.side_effect = OpenWeatherMapError("API Error")

        with self.assertRaises(OpenWeatherMapError):
            self.wrapper.get_current_conditions(51.5, -0.1)

    @patch.object(OpenWeatherMapWrapper, "_cached_request")
    def test_get_forecast_error_handling(self, mock_cached_request):
        """Test forecast with error handling."""
        mock_cached_request.side_effect = OpenWeatherMapError("API Error")

        with self.assertRaises(OpenWeatherMapError):
            self.wrapper.get_forecast(51.5, -0.1, days=3)

    def test_forecast_days_validation(self):
        """Test forecast days parameter validation."""
        with patch.object(self.wrapper.client, "get_one_call_data") as mock_get:
            mock_get.return_value = {"daily": []}

            # Test maximum days limit (8 for One Call API)
            self.wrapper.get_forecast(51.5, -0.1, days=8)
            mock_get.assert_called_once()

    def test_hourly_forecast_hours_validation(self):
        """Test hourly forecast hours parameter validation."""
        with patch.object(self.wrapper.client, "get_one_call_data") as mock_get:
            mock_get.return_value = {"hourly": []}

            # Test maximum hours limit (48 for One Call API)
            self.wrapper.get_hourly_forecast(51.5, -0.1, hours=48)
            mock_get.assert_called_once()

    def test_wrapper_initialization_with_custom_settings(self):
        """Test wrapper initialization with custom settings."""
        wrapper = OpenWeatherMapWrapper(
            api_key="test_key",
            enable_caching=True,
            cache_ttl=600,
            min_request_interval=1.0,
            max_retries=5,
            units="metric",
            language="fr",
        )
        self.assertTrue(wrapper.enable_caching)
        self.assertEqual(wrapper.cache_ttl, 600)
        self.assertEqual(wrapper.min_request_interval, 1.0)
        self.assertEqual(wrapper.max_retries, 5)
        self.assertEqual(wrapper.client.units, "metric")
        self.assertEqual(wrapper.client.language, "fr")

    def test_coordinate_precision(self):
        """Test handling of coordinate precision."""
        with patch.object(self.wrapper.client, "get_current_weather") as mock_get:
            mock_get.return_value = {"test": "data"}

            # Test with high precision coordinates
            self.wrapper.get_current_conditions(51.507351, -0.127758)

            # Verify coordinates are passed correctly
            mock_get.assert_called_once_with(51.507351, -0.127758)

    def test_negative_coordinates(self):
        """Test handling of negative coordinates."""
        with patch.object(self.wrapper.client, "get_current_weather") as mock_get:
            mock_get.return_value = {"test": "data"}

            # Test with negative coordinates (Southern/Western hemispheres)
            self.wrapper.get_current_conditions(-33.8688, 151.2093)  # Sydney

            # Verify coordinates are passed correctly
            mock_get.assert_called_once_with(-33.8688, 151.2093)


if __name__ == "__main__":
    unittest.main()
