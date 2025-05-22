"""Additional tests to boost WeatherAPI coverage to 80%+.

This module contains targeted tests to cover specific lines and edge cases
that are missing from the main test suite.
"""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from accessiweather.weatherapi_client.client import WeatherApiClient
from accessiweather.weatherapi_wrapper import WeatherApiError, WeatherApiWrapper


class TestWeatherApiClientAsync(unittest.TestCase):
    """Tests for async operations in WeatherAPI client."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = WeatherApiClient(api_key="test_key")

    @patch("httpx.AsyncClient")
    async def test_async_request_success(self, mock_async_client):
        """Test successful async request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"test": "data"}
        mock_response.raise_for_status.return_value = None

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        result = await self.client._request("current.json", {"q": "London"})
        self.assertEqual(result, {"test": "data"})

    @patch("httpx.AsyncClient")
    async def test_async_request_empty_response(self, mock_async_client):
        """Test async request with empty response."""
        mock_response = MagicMock()
        mock_response.json.return_value = None
        mock_response.raise_for_status.return_value = None

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        result = await self.client._request("current.json", {"q": "London"})
        self.assertEqual(result, {})

    @patch("httpx.Client")
    def test_sync_request_empty_response(self, mock_client):
        """Test sync request with empty response."""
        mock_response = MagicMock()
        mock_response.json.return_value = None
        mock_response.raise_for_status.return_value = None

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        result = self.client._request_sync("current.json", {"q": "London"})
        self.assertEqual(result, {})

    def test_get_current_async(self):
        """Test async current weather method."""
        with patch.object(self.client, "_request") as mock_request:
            mock_request.return_value = {"current": {"temp_c": 20}}

            # Run async method
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self.client.get_current("London"))
                self.assertEqual(result, {"current": {"temp_c": 20}})
            finally:
                loop.close()

    def test_get_forecast_async(self):
        """Test async forecast method."""
        with patch.object(self.client, "_request") as mock_request:
            mock_request.return_value = {"forecast": {"forecastday": []}}

            # Run async method
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self.client.get_forecast("London", days=3))
                self.assertEqual(result, {"forecast": {"forecastday": []}})
            finally:
                loop.close()


class TestWeatherApiWrapperEdgeCases(unittest.TestCase):
    """Tests for edge cases in WeatherAPI wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.wrapper = WeatherApiWrapper(
            api_key="test_key",
            enable_caching=True,
            cache_ttl=300,
            min_request_interval=0.1,
        )

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_forecast_with_alerts_and_aqi(self, mock_request):
        """Test forecast with alerts and AQI enabled."""
        mock_request.return_value = {
            "forecast": {"forecastday": []},
            "location": {"name": "London"},
            "alerts": {"alert": []},
        }

        result = self.wrapper.get_forecast("London", days=3, aqi=True, alerts=True)

        mock_request.assert_called_once_with(
            "forecast.json",
            {"q": "London", "days": 3, "aqi": "yes", "alerts": "yes"},
            False,
        )
        self.assertIn("forecast", result)
        self.assertIn("location", result)
        self.assertIn("alerts", result)

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_hourly_forecast_with_multiple_days(self, mock_request):
        """Test hourly forecast with multiple days."""
        mock_request.return_value = {
            "forecast": {"forecastday": [{"hour": []}]},
        }

        result = self.wrapper.get_hourly_forecast("London", days=3)

        mock_request.assert_called_once_with(
            "forecast.json",
            {"q": "London", "days": 3, "aqi": "no", "alerts": "no"},
            False,
        )
        self.assertIsInstance(result, list)

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_search_locations_success(self, mock_request):
        """Test successful location search."""
        mock_request.return_value = [
            {"name": "London", "country": "United Kingdom"},
            {"name": "London", "country": "Canada"},
        ]

        result = self.wrapper.search_locations("London")

        # The search_locations method calls with force_refresh=True by default
        mock_request.assert_called_once_with("search.json", {"q": "London"}, force_refresh=True)
        self.assertEqual(len(result), 2)
        # Check that result is a list of dictionaries
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], dict)

    def test_format_location_for_api_edge_cases(self):
        """Test location formatting edge cases."""
        # Test with very precise coordinates
        result = self.wrapper._format_location_for_api((51.123456789, -0.987654321))
        self.assertEqual(result, "51.123456789,-0.987654321")

        # Test with string that's already formatted
        result = self.wrapper._format_location_for_api("51.5,-0.1")
        self.assertEqual(result, "51.5,-0.1")

        # Test with city name
        result = self.wrapper._format_location_for_api("New York")
        self.assertEqual(result, "New York")

    @patch("time.time")
    @patch("time.sleep")
    def test_rate_limit_with_wait(self, mock_sleep, mock_time):
        """Test rate limiting when wait is needed."""
        # Set up time to require waiting
        mock_time.side_effect = [100.0, 100.4]  # 0.4 seconds passed, need to wait 0.1 more
        self.wrapper.last_request_time = 100.0

        self.wrapper._rate_limit()

        mock_sleep.assert_called_once()
        # Should sleep for approximately 0.1 seconds (0.5 - 0.4)
        sleep_time = mock_sleep.call_args[0][0]
        self.assertAlmostEqual(sleep_time, 0.1, places=1)

    def test_cache_key_generation_edge_cases(self):
        """Test cache key generation with various inputs."""
        # Test with complex parameters
        key1 = self.wrapper._get_cache_key(
            "forecast.json", {"q": "London", "days": 7, "aqi": "yes", "alerts": "yes"}
        )

        key2 = self.wrapper._get_cache_key(
            "forecast.json", {"q": "London", "days": 7, "aqi": "no", "alerts": "no"}
        )

        # Keys should be different for different parameters
        self.assertNotEqual(key1, key2)

        # Same parameters should generate same key
        key3 = self.wrapper._get_cache_key(
            "forecast.json", {"q": "London", "days": 7, "aqi": "yes", "alerts": "yes"}
        )
        self.assertEqual(key1, key3)


class TestWeatherApiWrapperErrorRecovery(unittest.TestCase):
    """Tests for error recovery paths in WeatherAPI wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.wrapper = WeatherApiWrapper(
            api_key="test_key",
            enable_caching=False,  # Disable caching for these tests
            min_request_interval=0.01,
        )

    def test_wrapper_initialization_with_caching_disabled(self):
        """Test wrapper initialization with caching disabled."""
        wrapper = WeatherApiWrapper(api_key="test_key", enable_caching=False)
        self.assertFalse(wrapper.enable_caching)
        self.assertIsNone(wrapper.cache)

    def test_wrapper_initialization_with_custom_settings(self):
        """Test wrapper initialization with custom settings."""
        wrapper = WeatherApiWrapper(
            api_key="test_key",
            enable_caching=True,
            cache_ttl=600,
            min_request_interval=1.0,
            max_retries=5,
        )
        self.assertTrue(wrapper.enable_caching)
        self.assertEqual(wrapper.cache_ttl, 600)
        self.assertEqual(wrapper.min_request_interval, 1.0)
        self.assertEqual(wrapper.max_retries, 5)

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_current_conditions_error_handling(self, mock_request):
        """Test current conditions with error handling."""
        mock_request.side_effect = WeatherApiError("API Error")

        with self.assertRaises(WeatherApiError):
            self.wrapper.get_current_conditions("London")

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_forecast_error_handling(self, mock_request):
        """Test forecast with error handling."""
        mock_request.side_effect = WeatherApiError("API Error")

        with self.assertRaises(WeatherApiError):
            self.wrapper.get_forecast("London")

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_hourly_forecast_error_handling(self, mock_request):
        """Test hourly forecast with error handling."""
        mock_request.side_effect = WeatherApiError("API Error")

        with self.assertRaises(WeatherApiError):
            self.wrapper.get_hourly_forecast("London")

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_search_locations_error_handling(self, mock_request):
        """Test search locations with error handling."""
        mock_request.side_effect = WeatherApiError("API Error")

        with self.assertRaises(WeatherApiError):
            self.wrapper.search_locations("London")

    def test_cache_operations_when_disabled(self):
        """Test cache operations when caching is disabled."""
        # Cache should be disabled for this wrapper instance
        self.assertFalse(self.wrapper.enable_caching)
        self.assertIsNone(self.wrapper.cache)

        # These operations should not raise errors even with caching disabled
        key = self.wrapper._get_cache_key("test.json", {"q": "test"})
        self.assertIsInstance(key, str)

        # Cache should be None when disabled
        self.assertIsNone(self.wrapper.cache)


class TestWeatherApiWrapperAdditionalCoverage(unittest.TestCase):
    """Additional tests to improve coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.wrapper = WeatherApiWrapper(api_key="test_key", enable_caching=True)

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_alerts_method(self, mock_request):
        """Test the get_alerts method."""
        mock_request.return_value = {"alerts": {"alert": [{"headline": "Test Alert"}]}}

        result = self.wrapper.get_alerts(51.5, -0.1)

        mock_request.assert_called_once_with(
            "forecast.json",
            {"q": "51.5,-0.1", "days": 1, "aqi": "no", "alerts": "yes"},
            False,
        )
        self.assertIsInstance(result, list)

    def test_format_location_edge_cases(self):
        """Test location formatting with edge cases."""
        # Test with tuple
        result = self.wrapper._format_location_for_api((51.5, -0.1))
        self.assertEqual(result, "51.5,-0.1")

        # Test with string coordinates
        result = self.wrapper._format_location_for_api("51.5,-0.1")
        self.assertEqual(result, "51.5,-0.1")

        # Test with city name
        result = self.wrapper._format_location_for_api("London")
        self.assertEqual(result, "London")

    @patch("time.time")
    def test_rate_limit_no_wait_needed(self, mock_time):
        """Test rate limiting when no wait is needed."""
        # Set up time so no wait is needed
        mock_time.return_value = 100.0
        self.wrapper.last_request_time = 99.0  # More than 0.5 seconds ago

        # This should not sleep
        with patch("time.sleep") as mock_sleep:
            self.wrapper._rate_limit()
            mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
