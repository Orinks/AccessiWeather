"""Tests for WeatherAPI location handling."""

import unittest
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.location import LocationManager
from accessiweather.weatherapi_wrapper import WeatherApiWrapper


class TestWeatherApiLocation(unittest.TestCase):
    """Test WeatherAPI location handling."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the geocoding service
        self.geocoding_patcher = patch("accessiweather.location.GeocodingService")
        self.mock_geocoding_class = self.geocoding_patcher.start()
        self.mock_geocoding = MagicMock()
        self.mock_geocoding_class.return_value = self.mock_geocoding

        # Set up default behavior for validate_coordinates
        self.mock_geocoding.validate_coordinates.return_value = True

        # Create a location manager with WeatherAPI data source
        self.location_manager = LocationManager(
            config_dir=None, show_nationwide=True, data_source="weatherapi"
        )

    def tearDown(self):
        """Tear down test fixtures."""
        self.geocoding_patcher.stop()

    def test_add_location_weatherapi(self):
        """Test adding a location with WeatherAPI data source."""
        # Test adding a non-US location (London)
        result = self.location_manager.add_location("London", 51.5074, -0.1278)
        self.assertTrue(result)
        self.assertIn("London", self.location_manager.saved_locations)

        # Verify validate_coordinates was called with us_only=None
        # The method will determine the appropriate validation based on data_source
        self.mock_geocoding.validate_coordinates.assert_called_with(51.5074, -0.1278, us_only=None)

    def test_add_location_nws(self):
        """Test adding a location with NWS data source."""
        # Create a location manager with NWS data source
        nws_location_manager = LocationManager(
            config_dir=None, show_nationwide=True, data_source="nws"
        )

        # Test adding a US location (New York)
        result = nws_location_manager.add_location("New York", 40.7128, -74.0060)
        self.assertTrue(result)
        self.assertIn("New York", nws_location_manager.saved_locations)

        # Verify validate_coordinates was called with us_only=None
        # The method will determine the appropriate validation based on data_source
        self.mock_geocoding.validate_coordinates.assert_called_with(40.7128, -74.0060, us_only=None)

    def test_weatherapi_wrapper_location_formatting(self):
        """Test WeatherAPI wrapper location formatting."""
        with patch("accessiweather.weatherapi_wrapper.WeatherApiClient"):
            wrapper = WeatherApiWrapper(api_key="test_key")

            # Test tuple format
            location = (51.5074, -0.1278)
            formatted = wrapper._format_location_for_api(location)
            self.assertEqual(formatted, "51.5074,-0.1278")

            # Test string format
            location = "London"
            formatted = wrapper._format_location_for_api(location)
            self.assertEqual(formatted, "London")

            # Test ZIP code format
            location = "90210"
            formatted = wrapper._format_location_for_api(location)
            self.assertEqual(formatted, "90210")

            # Test numeric ZIP code
            location = 90210
            formatted = wrapper._format_location_for_api(location)
            self.assertEqual(formatted, "90210")

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_current_conditions_with_different_formats(self, mock_make_request):
        """Test getting current conditions with different location formats."""
        mock_make_request.return_value = {"current": {"temp_c": 20}}

        with patch("accessiweather.weatherapi_wrapper.WeatherApiClient"):
            wrapper = WeatherApiWrapper(api_key="test_key")

            # Test with tuple
            wrapper.get_current_conditions((51.5074, -0.1278))
            mock_make_request.assert_called_with("current.json", {"q": "51.5074,-0.1278"}, False)

            # Test with string
            wrapper.get_current_conditions("London")
            mock_make_request.assert_called_with("current.json", {"q": "London"}, False)

            # Test with ZIP code
            wrapper.get_current_conditions("90210")
            mock_make_request.assert_called_with("current.json", {"q": "90210"}, False)

    @patch("accessiweather.weatherapi_wrapper.WeatherApiWrapper._make_request")
    def test_get_forecast_with_different_formats(self, mock_make_request):
        """Test getting forecast with different location formats."""
        mock_make_request.return_value = {"forecast": {"forecastday": []}}

        with patch("accessiweather.weatherapi_wrapper.WeatherApiClient"):
            wrapper = WeatherApiWrapper(api_key="test_key")

            # Test with tuple
            wrapper.get_forecast((51.5074, -0.1278), days=3)
            mock_make_request.assert_called_with(
                "forecast.json",
                {"q": "51.5074,-0.1278", "days": 3, "aqi": "no", "alerts": "no"},
                False,
            )

            # Test with string
            wrapper.get_forecast("London", days=3)
            mock_make_request.assert_called_with(
                "forecast.json", {"q": "London", "days": 3, "aqi": "no", "alerts": "no"}, False
            )
