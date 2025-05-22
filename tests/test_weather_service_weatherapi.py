"""Tests for the WeatherService with WeatherAPI.com integration.

This module provides tests for the WeatherService class when using
WeatherAPI.com as the data source.
"""

import unittest
from unittest.mock import MagicMock, patch

from accessiweather.api_client import NoaaApiClient
from accessiweather.gui.settings_dialog import (
    DATA_SOURCE_AUTO,
    DATA_SOURCE_NWS,
    DATA_SOURCE_WEATHERAPI,
)
from accessiweather.services.weather_service import ConfigurationError, WeatherService
from accessiweather.weatherapi_wrapper import WeatherApiError, WeatherApiWrapper


class TestWeatherServiceWithWeatherApi(unittest.TestCase):
    """Tests for the WeatherService with WeatherAPI.com integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.nws_client = MagicMock(spec=NoaaApiClient)
        self.weatherapi_wrapper = MagicMock(spec=WeatherApiWrapper)
        self.config = {
            "settings": {"data_source": DATA_SOURCE_WEATHERAPI},
            "api_keys": {"weatherapi": "test_key"},
        }
        self.service = WeatherService(
            nws_client=self.nws_client,
            weatherapi_wrapper=self.weatherapi_wrapper,
            config=self.config,
        )

    def test_get_data_source_weatherapi(self):
        """Test that the data source is correctly set to WeatherAPI.com."""
        self.assertEqual(self.service._get_data_source(), DATA_SOURCE_WEATHERAPI)

    def test_check_weatherapi_key_success(self):
        """Test that the WeatherAPI.com key is correctly retrieved."""
        # Ensure the key is in the correct location in the config
        self.service.config = {
            "settings": {"data_source": DATA_SOURCE_WEATHERAPI},
            "api_keys": {"weatherapi": "test_key"},
        }
        key = self.service._check_weatherapi_key()
        self.assertEqual(key, "test_key")

    def test_check_weatherapi_key_missing(self):
        """Test that an error is raised when the WeatherAPI.com key is missing."""
        # Remove the API key from the config but keep the correct structure
        self.service.config = {"settings": {"data_source": DATA_SOURCE_WEATHERAPI}}
        with self.assertRaises(ConfigurationError):
            self.service._check_weatherapi_key()

    def test_is_weatherapi_available_true(self):
        """Test that WeatherAPI.com is reported as available when configured."""
        # Ensure the config has the correct structure
        self.service.config = {
            "settings": {"data_source": DATA_SOURCE_WEATHERAPI},
            "api_keys": {"weatherapi": "test_key"},
        }
        self.assertTrue(self.service._is_weatherapi_available())

    def test_is_weatherapi_available_false_no_wrapper(self):
        """Test that WeatherAPI.com is reported as unavailable when wrapper is missing."""
        # Ensure the config has the correct structure but remove the wrapper
        self.service.config = {
            "settings": {"data_source": DATA_SOURCE_WEATHERAPI},
            "api_keys": {"weatherapi": "test_key"},
        }
        self.service.weatherapi_wrapper = None
        with self.assertRaises(ConfigurationError):
            self.service._is_weatherapi_available()

    def test_is_weatherapi_available_false_no_data_source(self):
        """Test that WeatherAPI.com is reported as unavailable when data source is not set to WeatherAPI."""
        # Set the config with a different data source
        self.service.config = {
            "settings": {"data_source": DATA_SOURCE_NWS},
            "api_keys": {"weatherapi": "test_key"},
        }
        # The method should return False when data source is not WeatherAPI
        self.assertFalse(self.service._is_weatherapi_available())

    def test_should_use_weatherapi_explicit(self):
        """Test that WeatherAPI.com is used when explicitly selected."""
        # Ensure the wrapper is properly initialized and API key is set
        self.service.config = {
            "settings": {"data_source": DATA_SOURCE_WEATHERAPI},
            "api_keys": {"weatherapi": "test_key"},
        }
        self.service.weatherapi_wrapper = MagicMock(spec=WeatherApiWrapper)
        self.assertTrue(self.service._should_use_weatherapi(51.5, -0.1))

    def test_should_use_weatherapi_auto_non_us(self):
        """Test that WeatherAPI.com is used in auto mode for non-US locations."""
        self.service.config = {
            "settings": {"data_source": DATA_SOURCE_AUTO},
            "api_keys": {"weatherapi": "test_key"},
        }
        self.service.weatherapi_wrapper = MagicMock(spec=WeatherApiWrapper)
        # Mock _is_location_in_us to return False for non-US location
        with patch.object(self.service, "_is_location_in_us", return_value=False):
            self.assertTrue(self.service._should_use_weatherapi(51.5, -0.1))

    def test_should_use_weatherapi_auto_us(self):
        """Test that NWS is used in auto mode for US locations."""
        self.service.config = {
            "settings": {"data_source": DATA_SOURCE_AUTO},
            "api_keys": {"weatherapi": "test_key"},
        }
        self.service.weatherapi_wrapper = MagicMock(spec=WeatherApiWrapper)
        # Mock _is_location_in_us to return True for US location
        with patch.object(self.service, "_is_location_in_us", return_value=True):
            self.assertFalse(self.service._should_use_weatherapi(37.7, -122.4))

    def test_should_use_weatherapi_nws(self):
        """Test that NWS is used when explicitly selected."""
        self.service.config = {
            "settings": {"data_source": DATA_SOURCE_NWS},
            "api_keys": {"weatherapi": "test_key"},
        }
        self.service.weatherapi_wrapper = MagicMock(spec=WeatherApiWrapper)
        self.assertFalse(self.service._should_use_weatherapi(51.5, -0.1))

    def test_get_forecast_weatherapi(self):
        """Test getting forecast data from WeatherAPI.com."""
        # Mock the WeatherAPI.com wrapper response
        mock_forecast = {
            "forecast": [
                {
                    "date": "2023-05-22",
                    "high": 72.5,
                    "low": 59.4,
                    "condition": "Sunny",
                }
            ],
            "location": {"name": "London"},
        }
        self.weatherapi_wrapper.get_forecast.return_value = mock_forecast

        # Mock _should_use_weatherapi to return True
        with patch.object(self.service, "_should_use_weatherapi", return_value=True):
            result = self.service.get_forecast(51.5, -0.1)

        # Check that the WeatherAPI.com wrapper was called
        self.weatherapi_wrapper.get_forecast.assert_called_once_with(
            "51.5,-0.1", days=7, alerts=True, force_refresh=False
        )

        # Check the result
        self.assertEqual(result, mock_forecast)

    def test_get_forecast_nws(self):
        """Test getting forecast data from NWS when WeatherAPI.com is not used."""
        # Mock the NWS client response
        mock_forecast = {"forecast": ["day1", "day2"], "location": {"name": "New York"}}
        self.nws_client.get_forecast.return_value = mock_forecast

        # Mock _should_use_weatherapi to return False
        with patch.object(self.service, "_should_use_weatherapi", return_value=False):
            result = self.service.get_forecast(40.7, -74.0)

        # Check that the NWS client was called
        self.nws_client.get_forecast.assert_called_once_with(40.7, -74.0, force_refresh=False)

        # Check the result
        self.assertEqual(result, mock_forecast)

    def test_get_hourly_forecast_weatherapi(self):
        """Test getting hourly forecast data from WeatherAPI.com."""
        # Mock the WeatherAPI.com wrapper response
        mock_hourly = [
            {
                "time": "2023-05-22 00:00",
                "temperature": 61.7,
                "condition": "Clear",
            }
        ]
        self.weatherapi_wrapper.get_hourly_forecast.return_value = mock_hourly

        # Mock _should_use_weatherapi to return True
        with patch.object(self.service, "_should_use_weatherapi", return_value=True):
            result = self.service.get_hourly_forecast(51.5, -0.1)

        # Check that the WeatherAPI.com wrapper was called
        self.weatherapi_wrapper.get_hourly_forecast.assert_called_once_with(
            "51.5,-0.1", days=2, force_refresh=False
        )

        # Check the result
        self.assertEqual(result, mock_hourly)

    def test_get_hourly_forecast_nws(self):
        """Test getting hourly forecast data from NWS when WeatherAPI.com is not used."""
        # Mock the NWS client response
        mock_hourly = [{"time": "2023-05-22 00:00", "temperature": 65}]
        self.nws_client.get_hourly_forecast.return_value = mock_hourly

        # Mock _should_use_weatherapi to return False
        with patch.object(self.service, "_should_use_weatherapi", return_value=False):
            result = self.service.get_hourly_forecast(40.7, -74.0)

        # Check that the NWS client was called
        self.nws_client.get_hourly_forecast.assert_called_once_with(
            40.7, -74.0, force_refresh=False
        )

        # Check the result
        self.assertEqual(result, mock_hourly)

    def test_get_alerts_weatherapi(self):
        """Test getting alerts data from WeatherAPI.com."""
        # Mock the WeatherAPI.com wrapper response
        mock_forecast_with_alerts = {
            "forecast": [],
            "alerts": [
                {
                    "headline": "Flood Warning",
                    "severity": "Moderate",
                    "event": "Flood",
                }
            ],
        }
        self.weatherapi_wrapper.get_forecast.return_value = mock_forecast_with_alerts

        # Mock _should_use_weatherapi to return True
        with patch.object(self.service, "_should_use_weatherapi", return_value=True):
            result = self.service.get_alerts(51.5, -0.1)

        # Check that the WeatherAPI.com wrapper was called
        self.weatherapi_wrapper.get_forecast.assert_called_once_with(
            "51.5,-0.1", days=1, alerts=True, force_refresh=False
        )

        # Check the result - service returns {"alerts": [...]}
        expected_result = {"alerts": mock_forecast_with_alerts["alerts"]}
        self.assertEqual(result, expected_result)

    def test_get_alerts_nws(self):
        """Test getting alerts data from NWS when WeatherAPI.com is not used."""
        # Mock the NWS client response
        mock_alerts = {"features": [{"properties": {"headline": "Severe Thunderstorm Warning"}}]}
        self.nws_client.get_alerts.return_value = mock_alerts

        # Mock _should_use_weatherapi to return False
        with patch.object(self.service, "_should_use_weatherapi", return_value=False):
            result = self.service.get_alerts(40.7, -74.0)

        # Check that the NWS client was called
        self.nws_client.get_alerts.assert_called_once_with(
            40.7, -74.0, radius=None, precise_location=None, force_refresh=False
        )

        # Check the result
        self.assertEqual(result, mock_alerts)

    def test_get_discussion_always_uses_nws(self):
        """Test that getting discussion data always uses NWS even with WeatherAPI.com selected."""
        # Mock the NWS client response
        mock_discussion = "This is a test discussion."
        self.nws_client.get_discussion.return_value = mock_discussion

        # Even with WeatherAPI.com selected, discussions should come from NWS
        result = self.service.get_discussion(51.5, -0.1)

        # Check that the NWS client was called
        self.nws_client.get_discussion.assert_called_once_with(51.5, -0.1, force_refresh=False)

        # Check the result
        self.assertEqual(result, mock_discussion)

    def test_get_forecast_weatherapi_error(self):
        """Test handling of WeatherAPI.com errors when getting forecast data."""
        # Mock the WeatherAPI.com wrapper to raise an error
        error = WeatherApiError("API Error", error_type=WeatherApiError.API_KEY_INVALID)
        self.weatherapi_wrapper.get_forecast.side_effect = error

        # Mock _should_use_weatherapi to return True
        with patch.object(self.service, "_should_use_weatherapi", return_value=True):
            with self.assertRaises(WeatherApiError):
                self.service.get_forecast(51.5, -0.1)

    def test_get_stations_not_supported_with_weatherapi(self):
        """Test that getting stations data is not supported with WeatherAPI.com."""
        # Mock _should_use_weatherapi to return True
        with patch.object(self.service, "_should_use_weatherapi", return_value=True):
            with self.assertRaises(ConfigurationError):
                self.service.get_stations(51.5, -0.1)

    def test_get_stations_nws(self):
        """Test getting stations data from NWS when WeatherAPI.com is not used."""
        # Mock the NWS client response
        mock_stations = {"features": [{"properties": {"stationIdentifier": "KNYC"}}]}
        self.nws_client.get_stations.return_value = mock_stations

        # Mock _should_use_weatherapi to return False
        with patch.object(self.service, "_should_use_weatherapi", return_value=False):
            result = self.service.get_stations(40.7, -74.0)

        # Check that the NWS client was called
        self.nws_client.get_stations.assert_called_once_with(40.7, -74.0, force_refresh=False)

        # Check the result
        self.assertEqual(result, mock_stations)


class TestWeatherServiceWithoutWeatherApi(unittest.TestCase):
    """Tests for the WeatherService without WeatherAPI.com integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.nws_client = MagicMock(spec=NoaaApiClient)
        self.config = {"data_source": DATA_SOURCE_NWS}
        self.service = WeatherService(
            nws_client=self.nws_client,
            weatherapi_wrapper=None,
            config=self.config,
        )

    def test_is_weatherapi_available_false(self):
        """Test that WeatherAPI.com is reported as unavailable when not configured."""
        self.assertFalse(self.service._is_weatherapi_available())

    def test_should_use_weatherapi_false(self):
        """Test that WeatherAPI.com is not used when not available."""
        self.assertFalse(self.service._should_use_weatherapi(51.5, -0.1))

    def test_get_forecast_always_uses_nws(self):
        """Test that getting forecast data always uses NWS when WeatherAPI.com is not available."""
        # Mock the NWS client response
        mock_forecast = {"forecast": ["day1", "day2"], "location": {"name": "London"}}
        self.nws_client.get_forecast.return_value = mock_forecast

        # Even with WeatherAPI.com selected in config, NWS should be used when wrapper is not available
        self.service.config = {"data_source": DATA_SOURCE_WEATHERAPI}
        result = self.service.get_forecast(51.5, -0.1)

        # Check that the NWS client was called
        self.nws_client.get_forecast.assert_called_once_with(51.5, -0.1, force_refresh=False)

        # Check the result
        self.assertEqual(result, mock_forecast)


if __name__ == "__main__":
    unittest.main()
