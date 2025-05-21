"""Tests for the WeatherAPI.com client."""

import os
import unittest
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.weatherapi_client.client import WeatherApiClient
from accessiweather.weatherapi_wrapper import WeatherApiWrapper


class TestWeatherApiClient(unittest.TestCase):
    """Tests for the WeatherAPI.com client."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.client = WeatherApiClient(api_key=self.api_key)

    @patch("httpx.Client")
    def test_get_current_sync(self, mock_client):
        """Test getting current weather."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {"current": {"temp_c": 20}}
        mock_response.raise_for_status.return_value = None

        # Mock the client
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        # Call the method
        result = self.client.get_current_sync("London")

        # Check the result
        self.assertEqual(result, {"current": {"temp_c": 20}})

        # Check the request
        mock_client_instance.get.assert_called_once()
        args, kwargs = mock_client_instance.get.call_args
        self.assertEqual(kwargs["params"]["key"], self.api_key)
        self.assertEqual(kwargs["params"]["q"], "London")


class TestWeatherApiWrapper(unittest.TestCase):
    """Tests for the WeatherAPI.com wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.wrapper = WeatherApiWrapper(api_key=self.api_key)

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_current_conditions(self, mock_request):
        """Test getting current weather conditions."""
        # Mock the response
        mock_request.return_value = {"current": {"temp_c": 20}}

        # Call the method
        result = self.wrapper.get_current_conditions(51.5, -0.1)

        # Check the result - expect the mapped format, not the raw API response
        self.assertEqual(result["temperature_c"], 20)

        # Check the request
        mock_request.assert_called_once()
        args, _ = mock_request.call_args
        self.assertEqual(args[0], "current.json")
        self.assertEqual(args[1]["q"], "51.5,-0.1")

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_forecast(self, mock_request):
        """Test getting weather forecast."""
        # Mock the response
        mock_request.return_value = {"forecast": {"forecastday": []}}

        # Call the method with a string location instead of separate lat/lon
        result = self.wrapper.get_forecast("51.5,-0.1", days=3)

        # Check the result - expect the mapped format, not the raw API response
        self.assertIn("forecast", result)
        self.assertIn("location", result)
        self.assertEqual(result["forecast"], [])  # Empty list after mapping

        # Check the request
        mock_request.assert_called_once()
        args, _ = mock_request.call_args
        self.assertEqual(args[0], "forecast.json")
        self.assertEqual(args[1]["q"], "51.5,-0.1")
        self.assertEqual(args[1]["days"], 3)


@pytest.mark.skipif(
    "WEATHERAPI_KEY" not in os.environ,
    reason="WeatherAPI.com API key not available",
)
class TestWeatherApiIntegration:
    """Integration tests for the WeatherAPI.com client.

    These tests require a valid WeatherAPI.com API key to be set in the
    WEATHERAPI_KEY environment variable.
    """

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = os.environ["WEATHERAPI_KEY"]
        self.client = WeatherApiClient(api_key=self.api_key)
        self.wrapper = WeatherApiWrapper(api_key=self.api_key)

    def test_get_current_sync(self):
        """Test getting current weather."""
        result = self.client.get_current_sync("London")
        assert "current" in result
        assert "temp_c" in result["current"]

    def test_get_forecast_sync(self):
        """Test getting weather forecast."""
        result = self.client.get_forecast_sync("London", days=3)
        assert "forecast" in result
        assert "forecastday" in result["forecast"]
        assert len(result["forecast"]["forecastday"]) == 3

    def test_wrapper_get_current_conditions(self):
        """Test getting current weather conditions using the wrapper."""
        result = self.wrapper.get_current_conditions(51.5, -0.1)
        assert "current" in result
        assert "temp_c" in result["current"]

    def test_wrapper_get_forecast(self):
        """Test getting weather forecast using the wrapper."""
        result = self.wrapper.get_forecast(51.5, -0.1, days=3)
        assert "forecast" in result
        assert "forecastday" in result["forecast"]
        assert len(result["forecast"]["forecastday"]) == 3
