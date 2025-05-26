"""Comprehensive tests for the WeatherAPI.com wrapper.

This module provides tests for all components of the WeatherAPI.com wrapper,
including error handling, rate limiting, caching, and data mapping.
"""

import unittest
from unittest.mock import patch

from accessiweather.weatherapi_wrapper import WeatherApiError, WeatherApiWrapper


class TestWeatherApiWrapperCore(unittest.TestCase):
    """Core tests for the WeatherAPI.com wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.wrapper = WeatherApiWrapper(
            api_key=self.api_key,
            enable_caching=True,
            cache_ttl=300,
            min_request_interval=0.1,  # Short interval for testing
        )

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_current_conditions_success(self, mock_request):
        """Test getting current weather conditions successfully."""
        # Mock the response
        mock_response = {
            "location": {
                "name": "London",
                "region": "City of London",
                "country": "United Kingdom",
                "lat": 51.52,
                "lon": -0.11,
                "tz_id": "Europe/London",
                "localtime": "2023-05-22 10:00",
            },
            "current": {
                "temp_c": 18.0,
                "temp_f": 64.4,
                "condition": {
                    "text": "Partly cloudy",
                    "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png",
                    "code": 1003,
                },
                "wind_mph": 5.6,
                "humidity": 72,
                "cloud": 25,
                "feelslike_c": 18.2,
                "uv": 4,
            },
        }
        mock_request.return_value = mock_response

        # Call the method with string location
        result = self.wrapper.get_current_conditions("London")

        # Check the result
        self.assertEqual(result["temperature_c"], 18.0)
        self.assertEqual(result["condition"], "Partly cloudy")
        self.assertEqual(result["wind_speed"], 5.6)
        self.assertEqual(result["humidity"], 72)

        # Check the request
        mock_request.assert_called_once()
        args, _ = mock_request.call_args
        self.assertEqual(args[0], "current.json")
        self.assertEqual(args[1]["q"], "London")

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_current_conditions_with_coordinates(self, mock_request):
        """Test getting current weather conditions with lat/lon coordinates."""
        # Mock the response with all required fields
        mock_response = {
            "location": {"name": "Test Location"},
            "current": {"temp_c": 20.0, "condition": {"text": "Sunny"}},
        }
        mock_request.return_value = mock_response

        # Call the method with coordinates
        self.wrapper.get_current_conditions(51.5, -0.1)

        # Check the request formatting
        mock_request.assert_called_once()
        args, _ = mock_request.call_args
        self.assertEqual(args[0], "current.json")
        self.assertEqual(args[1]["q"], "51.5,-0.1")

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_forecast_success(self, mock_request):
        """Test getting weather forecast successfully."""
        # Mock the response with all required fields
        mock_response = {
            "location": {"name": "London"},
            "current": {"temp_c": 20.0, "condition": {"text": "Sunny"}},
            "forecast": {
                "forecastday": [
                    {
                        "date": "2023-05-22",
                        "day": {
                            "maxtemp_c": 22.5,
                            "maxtemp_f": 72.5,
                            "mintemp_c": 15.2,
                            "mintemp_f": 59.4,
                            "condition": {"text": "Sunny", "code": 1000},
                            "daily_chance_of_rain": "10",
                            "daily_chance_of_snow": "0",
                        },
                    }
                ]
            },
        }
        mock_request.return_value = mock_response

        # Call the method
        result = self.wrapper.get_forecast("London", days=3)

        # Check the result
        self.assertIn("forecast", result)
        self.assertIn("location", result)
        self.assertEqual(len(result["forecast"]), 1)
        self.assertEqual(result["forecast"][0]["date"], "2023-05-22")
        self.assertEqual(result["forecast"][0]["high"], 72.5)
        self.assertEqual(result["forecast"][0]["low"], 59.4)
        self.assertEqual(result["forecast"][0]["condition"], "Sunny")

        # Check the request
        mock_request.assert_called_once()
        args, _ = mock_request.call_args
        self.assertEqual(args[0], "forecast.json")
        self.assertEqual(args[1]["q"], "London")
        self.assertEqual(args[1]["days"], 3)

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_hourly_forecast_success(self, mock_request):
        """Test getting hourly forecast successfully."""
        # Mock the response with all required fields
        mock_response = {
            "location": {"name": "London"},
            "current": {"temp_c": 20.0, "condition": {"text": "Sunny"}},
            "forecast": {
                "forecastday": [
                    {
                        "hour": [
                            {
                                "time": "2023-05-22 00:00",
                                "temp_c": 16.5,
                                "temp_f": 61.7,
                                "condition": {"text": "Clear", "code": 1000},
                                "chance_of_rain": "0",
                                "chance_of_snow": "0",
                            }
                        ]
                    }
                ]
            },
        }
        mock_request.return_value = mock_response

        # Call the method
        result = self.wrapper.get_hourly_forecast("London", days=1)

        # Check the result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["time"], "2023-05-22 00:00")
        self.assertEqual(result[0]["temperature"], 61.7)
        self.assertEqual(result[0]["temperature_c"], 16.5)
        self.assertEqual(result[0]["condition"], "Clear")
        self.assertEqual(result[0]["chance_of_rain"], "0")

        # Check the request
        mock_request.assert_called_once()
        args, _ = mock_request.call_args
        self.assertEqual(args[0], "forecast.json")
        self.assertEqual(args[1]["q"], "London")
        self.assertEqual(args[1]["days"], 1)

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_alerts_success(self, mock_request):
        """Test getting weather alerts successfully."""
        # Mock the response with all required fields
        mock_response = {
            "location": {"name": "London"},
            "current": {"temp_c": 20.0, "condition": {"text": "Sunny"}},
            "forecast": {"forecastday": [{"day": {"condition": {"text": "Sunny"}}}]},
            "alerts": {
                "alert": [
                    {
                        "headline": "Flood Warning",
                        "severity": "Moderate",
                        "urgency": "Expected",
                        "areas": "Test Area",
                        "event": "Flood",
                        "effective": "2023-05-22T00:00:00Z",
                        "expires": "2023-05-23T00:00:00Z",
                        "desc": "Flooding is possible.",
                        "instruction": "Be prepared.",
                    }
                ]
            },
        }
        mock_request.return_value = mock_response

        # Call the method
        result = self.wrapper.get_alerts(51.5, -0.1)

        # Check the result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["headline"], "Flood Warning")
        self.assertEqual(result[0]["severity"], "Moderate")
        self.assertEqual(result[0]["event"], "Flood")
        self.assertEqual(result[0]["desc"], "Flooding is possible.")

        # Check the request
        mock_request.assert_called_once()
        args, _ = mock_request.call_args
        self.assertEqual(args[0], "forecast.json")
        self.assertEqual(args[1]["q"], "51.5,-0.1")
        self.assertEqual(args[1]["alerts"], "yes")

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_search_locations_success(self, mock_request):
        """Test searching for locations successfully."""
        # Mock the response
        mock_response = [
            {
                "id": 1,
                "name": "London",
                "region": "City of London",
                "country": "United Kingdom",
                "lat": 51.52,
                "lon": -0.11,
            }
        ]
        mock_request.return_value = mock_response

        # Call the method
        result = self.wrapper.search_locations("London")

        # Check the result
        self.assertEqual(result, mock_response)

        # Check the request
        mock_request.assert_called_once()
        args, _ = mock_request.call_args
        self.assertEqual(args[0], "search.json")
        self.assertEqual(args[1]["q"], "London")


class TestWeatherApiWrapperErrorHandling(unittest.TestCase):
    """Tests for error handling in the WeatherAPI.com wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.wrapper = WeatherApiWrapper(api_key=self.api_key)

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_api_key_invalid_error(self, mock_make_request):
        """Test handling of invalid API key error."""
        # Mock the _make_request method to raise an API key invalid error
        error = WeatherApiError(
            "API key provided is invalid",
            error_type=WeatherApiError.API_KEY_INVALID,
            error_code=2006,
        )
        mock_make_request.side_effect = error

        # Call the method and expect an error
        with self.assertRaises(WeatherApiError) as context:
            self.wrapper.get_current_conditions("London")

        # Check the error
        self.assertEqual(context.exception.error_type, WeatherApiError.API_KEY_INVALID)
        self.assertIn("API key provided is invalid", str(context.exception))

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_location_not_found_error(self, mock_make_request):
        """Test handling of location not found error."""
        # Mock the _make_request method to raise a location not found error
        error = WeatherApiError(
            "No matching location found.", error_type=WeatherApiError.NOT_FOUND, error_code=1006
        )
        mock_make_request.side_effect = error

        # Call the method and expect an error
        with self.assertRaises(WeatherApiError) as context:
            self.wrapper.get_current_conditions("NonexistentLocation")

        # Check the error
        self.assertEqual(context.exception.error_type, WeatherApiError.NOT_FOUND)
        self.assertIn("No matching location found", str(context.exception))

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_quota_exceeded_error(self, mock_make_request):
        """Test handling of quota exceeded error."""
        # Mock the _make_request method to raise a quota exceeded error
        error = WeatherApiError(
            "API key has exceeded calls per month quota.",
            error_type=WeatherApiError.QUOTA_EXCEEDED,
            error_code=2007,
        )
        mock_make_request.side_effect = error

        # Call the method and expect an error
        with self.assertRaises(WeatherApiError) as context:
            self.wrapper.get_current_conditions("London")

        # Check the error
        self.assertEqual(context.exception.error_type, WeatherApiError.QUOTA_EXCEEDED)
        self.assertIn("exceeded calls per month quota", str(context.exception))

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_server_error(self, mock_make_request):
        """Test handling of server error."""
        # Mock the _make_request method to raise a server error
        error = WeatherApiError(
            "Internal application error.", error_type=WeatherApiError.SERVER_ERROR, error_code=9999
        )
        mock_make_request.side_effect = error

        # Call the method and expect an error
        with self.assertRaises(WeatherApiError) as context:
            self.wrapper.get_current_conditions("London")

        # Check the error
        self.assertEqual(context.exception.error_type, WeatherApiError.SERVER_ERROR)
        self.assertIn("Internal application error", str(context.exception))


class TestWeatherApiWrapperRateLimiting(unittest.TestCase):
    """Tests for rate limiting in the WeatherAPI.com wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.wrapper = WeatherApiWrapper(
            api_key=self.api_key, min_request_interval=0.2  # Short interval for testing
        )

    def test_rate_limit_calculation(self):
        """Test that rate limit calculation works correctly."""
        # Test with a time difference less than the minimum interval
        with patch.object(self.wrapper, "last_request_time", 100.0):
            with patch("time.time", return_value=100.1):
                with patch("time.sleep") as mock_sleep:
                    self.wrapper._rate_limit()
                    mock_sleep.assert_called_once()
                    # Should sleep for approximately 0.1 seconds
                    self.assertAlmostEqual(mock_sleep.call_args[0][0], 0.1, places=1)

    def test_rate_limit_no_wait_needed(self):
        """Test that no wait occurs when sufficient time has passed."""
        # Test with a time difference greater than the minimum interval
        with patch.object(self.wrapper, "last_request_time", 100.0):
            with patch("time.time", return_value=100.5):
                with patch("time.sleep") as mock_sleep:
                    self.wrapper._rate_limit()
                    mock_sleep.assert_not_called()


class TestWeatherApiWrapperCaching(unittest.TestCase):
    """Tests for caching in the WeatherAPI.com wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.wrapper = WeatherApiWrapper(api_key=self.api_key, enable_caching=True, cache_ttl=300)
        # Clear any existing cache
        if hasattr(self.wrapper, "cache"):
            self.wrapper.cache.clear()

    def test_cache_key_generation(self):
        """Test that cache keys are generated correctly."""
        # Test with different endpoints and parameters
        key1 = self.wrapper._get_cache_key("current.json", {"q": "London"})
        key2 = self.wrapper._get_cache_key("current.json", {"q": "Paris"})
        key3 = self.wrapper._get_cache_key("forecast.json", {"q": "London"})

        # Keys should be strings
        self.assertIsInstance(key1, str)

        # Different parameters should generate different keys
        self.assertNotEqual(key1, key2)

        # Different endpoints should generate different keys
        self.assertNotEqual(key1, key3)

    def test_cache_storage_and_retrieval(self):
        """Test direct cache storage and retrieval."""
        if not hasattr(self.wrapper, "cache"):
            self.skipTest("Cache not available")

        # Store something in the cache
        test_key = "test_key"
        test_data = {"test": "data"}
        self.wrapper.cache.set(test_key, test_data)

        # Retrieve it from the cache
        cached_data = self.wrapper.cache.get(test_key)
        self.assertEqual(cached_data, test_data)

        # Check that a non-existent key returns None
        self.assertIsNone(self.wrapper.cache.get("non_existent_key"))


class TestWeatherApiWrapperLocationFormatting(unittest.TestCase):
    """Tests for location formatting in the WeatherAPI.com wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.wrapper = WeatherApiWrapper(api_key=self.api_key)

    def test_format_location_tuple(self):
        """Test formatting location as a tuple."""
        result = self.wrapper._format_location_for_api((51.5, -0.1))
        self.assertEqual(result, "51.5,-0.1")

    def test_format_location_string(self):
        """Test formatting location as a string."""
        result = self.wrapper._format_location_for_api("London")
        self.assertEqual(result, "London")

    def test_format_location_numeric(self):
        """Test formatting location as a numeric value (e.g., ZIP code)."""
        result = self.wrapper._format_location_for_api(10001)
        self.assertEqual(result, "10001")


if __name__ == "__main__":
    unittest.main()
