"""Comprehensive tests for the OpenWeatherMap API client.

This module provides tests for all components of the OpenWeatherMap client,
including error handling, rate limiting, authentication, and API integration.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

import httpx
import pytest

from accessiweather.openweathermap_client import (
    AuthenticationError,
    NotFoundError,
    OpenWeatherMapClient,
    OpenWeatherMapError,
    RateLimitError,
    ValidationError,
)


class TestOpenWeatherMapClientCore(unittest.TestCase):
    """Core tests for the OpenWeatherMap client."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key_12345678901234567890"
        self.client = OpenWeatherMapClient(
            api_key=self.api_key, timeout=10, units="imperial", language="en"
        )

    def test_client_initialization(self):
        """Test client initialization with various parameters."""
        # Test default initialization
        client = OpenWeatherMapClient(api_key=self.api_key)
        self.assertEqual(client.api_key, self.api_key)
        self.assertEqual(client.timeout, 10.0)
        self.assertEqual(client.units, "imperial")
        self.assertEqual(client.language, "en")

        # Test custom initialization
        client = OpenWeatherMapClient(
            api_key=self.api_key, timeout=15, units="metric", language="es"
        )
        self.assertEqual(client.timeout, 15)
        self.assertEqual(client.units, "metric")
        self.assertEqual(client.language, "es")

    def test_get_base_params(self):
        """Test base parameter generation."""
        params = self.client._get_base_params()
        expected_params = {"appid": self.api_key, "units": "imperial", "lang": "en"}
        self.assertEqual(params, expected_params)

    def test_get_headers(self):
        """Test header generation."""
        headers = self.client._get_headers()
        self.assertIn("User-Agent", headers)
        self.assertEqual(headers["User-Agent"], "AccessiWeather")

    @patch("httpx.Client")
    def test_make_request_success(self, mock_client):
        """Test successful API request."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        result = self.client._make_request("weather", {"lat": 51.5, "lon": -0.1})

        self.assertEqual(result, {"test": "data"})
        mock_client_instance.get.assert_called_once()

    @patch("httpx.Client")
    def test_make_request_authentication_error(self, mock_client):
        """Test authentication error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"cod": 401, "message": "Invalid API key"}

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        with self.assertRaises(AuthenticationError) as context:
            self.client._make_request("weather", {"lat": 51.5, "lon": -0.1})

        self.assertIn("Invalid API key", str(context.exception))
        self.assertEqual(context.exception.status_code, 401)

    @patch("httpx.Client")
    def test_make_request_rate_limit_error(self, mock_client):
        """Test rate limit error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"cod": 429, "message": "Too many requests"}

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        with self.assertRaises(RateLimitError) as context:
            self.client._make_request("weather", {"lat": 51.5, "lon": -0.1})

        self.assertIn("Too many requests", str(context.exception))
        self.assertEqual(context.exception.status_code, 429)

    @patch("httpx.Client")
    def test_make_request_not_found_error(self, mock_client):
        """Test not found error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"cod": "404", "message": "city not found"}

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        with self.assertRaises(NotFoundError) as context:
            self.client._make_request("weather", {"lat": 51.5, "lon": -0.1})

        self.assertIn("city not found", str(context.exception))
        self.assertEqual(context.exception.status_code, 404)

    @patch("httpx.Client")
    def test_make_request_validation_error(self, mock_client):
        """Test validation error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"cod": 400, "message": "Invalid coordinates"}

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        with self.assertRaises(ValidationError) as context:
            self.client._make_request("weather", {"lat": 51.5, "lon": -0.1})

        self.assertIn("Invalid coordinates", str(context.exception))
        self.assertEqual(context.exception.status_code, 400)

    @patch("httpx.Client")
    def test_make_request_server_error(self, mock_client):
        """Test server error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"cod": 500, "message": "Internal server error"}

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        with self.assertRaises(OpenWeatherMapError) as context:
            self.client._make_request("weather", {"lat": 51.5, "lon": -0.1})

        self.assertIn("Internal server error", str(context.exception))
        self.assertEqual(context.exception.status_code, 500)

    @patch("httpx.Client")
    def test_make_request_network_error(self, mock_client):
        """Test network error handling."""
        mock_client_instance = MagicMock()
        mock_client_instance.get.side_effect = httpx.ConnectError("Connection failed")
        mock_client.return_value.__enter__.return_value = mock_client_instance

        with self.assertRaises(OpenWeatherMapError) as context:
            self.client._make_request("weather", {"lat": 51.5, "lon": -0.1})

        self.assertIn("Connection failed", str(context.exception))
        self.assertEqual(context.exception.error_type, OpenWeatherMapError.CONNECTION_ERROR)

    @patch("httpx.Client")
    def test_make_request_timeout_error(self, mock_client):
        """Test timeout error handling."""
        mock_client_instance = MagicMock()
        mock_client_instance.get.side_effect = httpx.TimeoutException("Request timeout")
        mock_client.return_value.__enter__.return_value = mock_client_instance

        with self.assertRaises(OpenWeatherMapError) as context:
            self.client._make_request("weather", {"lat": 51.5, "lon": -0.1})

        self.assertIn("Request timeout", str(context.exception))
        self.assertEqual(context.exception.error_type, OpenWeatherMapError.TIMEOUT_ERROR)


class TestOpenWeatherMapClientAPI(unittest.TestCase):
    """Tests for OpenWeatherMap API methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key_12345678901234567890"
        self.client = OpenWeatherMapClient(api_key=self.api_key)

    @patch.object(OpenWeatherMapClient, "_make_request")
    def test_get_current_weather(self, mock_request):
        """Test getting current weather data."""
        mock_response = {
            "coord": {"lon": -0.1278, "lat": 51.5074},
            "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
            "main": {"temp": 15.0, "feels_like": 14.5, "humidity": 65, "pressure": 1013},
            "wind": {"speed": 3.5, "deg": 180},
            "clouds": {"all": 0},
            "name": "London",
        }
        mock_request.return_value = mock_response

        result = self.client.get_current_weather(51.5074, -0.1278)

        self.assertEqual(result, mock_response)
        mock_request.assert_called_once_with(
            self.client.CURRENT_WEATHER_ENDPOINT, {"lat": 51.5074, "lon": -0.1278}
        )

    @patch.object(OpenWeatherMapClient, "_make_request")
    def test_get_one_call_data(self, mock_request):
        """Test getting One Call API data."""
        mock_response = {
            "lat": 51.5074,
            "lon": -0.1278,
            "current": {"temp": 15.0, "humidity": 65},
            "daily": [{"temp": {"max": 18, "min": 12}}],
            "hourly": [{"temp": 16.0, "humidity": 70}],
        }
        mock_request.return_value = mock_response

        result = self.client.get_one_call_data(51.5074, -0.1278)

        self.assertEqual(result, mock_response)
        mock_request.assert_called_once_with(
            self.client.ONE_CALL_ENDPOINT, {"lat": 51.5074, "lon": -0.1278}
        )

    @patch.object(OpenWeatherMapClient, "_make_request")
    def test_get_one_call_data_with_exclude(self, mock_request):
        """Test getting One Call API data with exclusions."""
        mock_response = {"lat": 51.5074, "lon": -0.1278, "current": {"temp": 15.0, "humidity": 65}}
        mock_request.return_value = mock_response

        result = self.client.get_one_call_data(
            51.5074, -0.1278, exclude="minutely,hourly,daily,alerts"
        )

        self.assertEqual(result, mock_response)
        mock_request.assert_called_once_with(
            self.client.ONE_CALL_ENDPOINT,
            {"lat": 51.5074, "lon": -0.1278, "exclude": "minutely,hourly,daily,alerts"},
        )


class TestOpenWeatherMapIntegration:
    """Integration tests for the OpenWeatherMap client.

    These tests require a valid OpenWeatherMap API key to be set in the
    OPENWEATHERMAP_KEY environment variable.
    """

    def setup_method(self):
        """Set up test fixtures."""
        # Skip if no API key is available
        if "OPENWEATHERMAP_KEY" not in os.environ:
            pytest.skip("OPENWEATHERMAP_KEY environment variable not set")

        self.api_key = os.environ["OPENWEATHERMAP_KEY"]
        self.client = OpenWeatherMapClient(api_key=self.api_key)

    def test_get_current_weather_real_api(self):
        """Test getting current weather from real API."""
        # Use London coordinates
        result = self.client.get_current_weather(51.5074, -0.1278)

        # Verify response structure
        assert "coord" in result
        assert "weather" in result
        assert "main" in result
        assert "name" in result
        assert result["coord"]["lat"] == pytest.approx(51.5074, abs=0.1)
        assert result["coord"]["lon"] == pytest.approx(-0.1278, abs=0.1)

    def test_get_one_call_data_real_api(self):
        """Test getting One Call data from real API."""
        # Use London coordinates
        result = self.client.get_one_call_data(51.5074, -0.1278)

        # Verify response structure
        assert "lat" in result
        assert "lon" in result
        assert "current" in result
        assert "daily" in result
        assert "hourly" in result
        assert result["lat"] == pytest.approx(51.5074, abs=0.1)
        assert result["lon"] == pytest.approx(-0.1278, abs=0.1)

    def test_get_one_call_data_with_exclude_real_api(self):
        """Test getting One Call data with exclusions from real API."""
        # Use London coordinates, exclude minutely and alerts
        result = self.client.get_one_call_data(51.5074, -0.1278, exclude="minutely,alerts")

        # Verify response structure
        assert "lat" in result
        assert "lon" in result
        assert "current" in result
        assert "daily" in result
        assert "hourly" in result
        # These should be excluded
        assert "minutely" not in result
        assert "alerts" not in result

    def test_invalid_coordinates_real_api(self):
        """Test error handling with invalid coordinates."""
        with pytest.raises(ValidationError):
            # Invalid latitude (> 90)
            self.client.get_current_weather(91.0, 0.0)

    def test_invalid_api_key_real_api(self):
        """Test error handling with invalid API key."""
        invalid_client = OpenWeatherMapClient(api_key="invalid_key")

        with pytest.raises(AuthenticationError):
            invalid_client.get_current_weather(51.5074, -0.1278)


class TestOpenWeatherMapErrorHandling(unittest.TestCase):
    """Tests for OpenWeatherMap error handling edge cases."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key_12345678901234567890"
        self.client = OpenWeatherMapClient(api_key=self.api_key)

    @patch("httpx.Client")
    def test_malformed_json_response(self, mock_client):
        """Test handling of malformed JSON response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        with self.assertRaises(OpenWeatherMapError) as context:
            self.client._make_request("weather", {"lat": 51.5, "lon": -0.1})

        self.assertEqual(context.exception.error_type, OpenWeatherMapError.PARSE_ERROR)

    @patch("httpx.Client")
    def test_empty_response(self, mock_client):
        """Test handling of empty response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        result = self.client._make_request("weather", {"lat": 51.5, "lon": -0.1})
        self.assertEqual(result, {})

    @patch("httpx.Client")
    def test_unexpected_status_code(self, mock_client):
        """Test handling of unexpected status codes."""
        mock_response = MagicMock()
        mock_response.status_code = 418  # I'm a teapot
        mock_response.json.return_value = {"message": "I'm a teapot"}

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        with self.assertRaises(OpenWeatherMapError) as context:
            self.client._make_request("weather", {"lat": 51.5, "lon": -0.1})

        self.assertEqual(context.exception.status_code, 418)

    def test_error_string_representation(self):
        """Test error string representation."""
        error = OpenWeatherMapError(
            message="Test error",
            status_code=400,
            error_type=OpenWeatherMapError.VALIDATION_ERROR,
            url="https://api.openweathermap.org/data/2.5/weather",
            error_code="400",
        )

        error_str = str(error)
        self.assertIn("Test error", error_str)
        self.assertIn("Status code: 400", error_str)
        self.assertIn("Error type: validation", error_str)
        self.assertIn("Error code: 400", error_str)
        self.assertIn("URL: https://api.openweathermap.org", error_str)


if __name__ == "__main__":
    unittest.main()
