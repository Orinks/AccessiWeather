"""Integration tests for the WeatherAPI.com integration.

This module provides integration tests for the WeatherAPI.com integration,
focusing on the interaction between the WeatherService and WeatherApiWrapper.
"""

import unittest
from unittest.mock import MagicMock, patch

from accessiweather.api_client import NoaaApiClient
from accessiweather.gui.settings_dialog import DATA_SOURCE_WEATHERAPI
from accessiweather.services.weather_service import WeatherService
from accessiweather.weatherapi_wrapper import WeatherApiError, WeatherApiWrapper


class TestWeatherApiIntegration(unittest.TestCase):
    """Integration tests for the WeatherAPI.com integration."""

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

    def test_end_to_end_forecast_flow(self):
        """Test the end-to-end flow of getting forecast data from WeatherAPI.com."""
        # Mock the WeatherAPI.com wrapper response
        mock_forecast = {
            "forecast": [
                {
                    "date": "2023-05-22",
                    "high": 72.5,
                    "low": 59.4,
                    "condition": "Sunny",
                    "precipitation_probability": "10",
                }
            ],
            "location": {"name": "London", "latitude": 51.5, "longitude": -0.1},
        }
        self.weatherapi_wrapper.get_forecast.return_value = mock_forecast

        # Get the forecast
        result = self.service.get_forecast(51.5, -0.1)

        # Check that the WeatherAPI.com wrapper was called with the correct parameters
        self.weatherapi_wrapper.get_forecast.assert_called_once_with(
            "51.5,-0.1", days=7, alerts=True, force_refresh=False
        )

        # Check the result
        self.assertEqual(result, mock_forecast)
        self.assertEqual(result["forecast"][0]["high"], 72.5)
        self.assertEqual(result["forecast"][0]["condition"], "Sunny")

    def test_end_to_end_hourly_forecast_flow(self):
        """Test the end-to-end flow of getting hourly forecast data from WeatherAPI.com."""
        # Mock the WeatherAPI.com wrapper response
        mock_hourly = [
            {
                "time": "2023-05-22 00:00",
                "temperature": 61.7,
                "temperature_c": 16.5,
                "condition": "Clear",
                "chance_of_rain": "0",
            }
        ]
        self.weatherapi_wrapper.get_hourly_forecast.return_value = mock_hourly

        # Get the hourly forecast
        result = self.service.get_hourly_forecast(51.5, -0.1)

        # Check that the WeatherAPI.com wrapper was called with the correct parameters
        self.weatherapi_wrapper.get_hourly_forecast.assert_called_once_with(
            "51.5,-0.1", days=2, force_refresh=False
        )

        # Check the result - service returns {"hourly": [...]}
        expected_result = {"hourly": mock_hourly}
        self.assertEqual(result, expected_result)
        self.assertEqual(result["hourly"][0]["temperature"], 61.7)
        self.assertEqual(result["hourly"][0]["condition"], "Clear")

    def test_end_to_end_alerts_flow(self):
        """Test the end-to-end flow of getting alerts data from WeatherAPI.com."""
        # Mock the WeatherAPI.com wrapper response
        mock_forecast_with_alerts = {
            "forecast": [],
            "alerts": [
                {
                    "headline": "Flood Warning",
                    "severity": "Moderate",
                    "event": "Flood",
                    "desc": "Flooding is possible.",
                    "instruction": "Be prepared.",
                }
            ],
        }
        self.weatherapi_wrapper.get_forecast.return_value = mock_forecast_with_alerts

        # Get the alerts
        result = self.service.get_alerts(51.5, -0.1)

        # Check that the WeatherAPI.com wrapper was called with the correct parameters
        self.weatherapi_wrapper.get_forecast.assert_called_once_with(
            "51.5,-0.1", days=1, alerts=True, force_refresh=False
        )

        # Check the result - service returns {"alerts": [...]}
        expected_result = {"alerts": mock_forecast_with_alerts["alerts"]}
        self.assertEqual(result, expected_result)
        self.assertEqual(result["alerts"][0]["headline"], "Flood Warning")
        self.assertEqual(result["alerts"][0]["severity"], "Moderate")

    def test_error_propagation(self):
        """Test that errors from the WeatherAPI.com wrapper are properly propagated."""
        # Mock the WeatherAPI.com wrapper to raise an error
        error = WeatherApiError(
            "API key provided is invalid",
            error_type=WeatherApiError.API_KEY_INVALID,
            error_code=2006,
        )
        self.weatherapi_wrapper.get_forecast.side_effect = error

        # Try to get the forecast and expect the error to be propagated
        with self.assertRaises(WeatherApiError) as context:
            self.service.get_forecast(51.5, -0.1)

        # Check the error
        self.assertEqual(context.exception.error_type, WeatherApiError.API_KEY_INVALID)
        self.assertIn("API key provided is invalid", str(context.exception))

    def test_concurrent_requests(self):
        """Test that concurrent requests to different endpoints work correctly."""
        # Mock the WeatherAPI.com wrapper responses
        mock_forecast = {"forecast": [{"date": "2023-05-22"}], "location": {"name": "London"}}
        mock_hourly = [{"time": "2023-05-22 00:00"}]
        mock_forecast_with_alerts = {"forecast": [], "alerts": [{"headline": "Flood Warning"}]}

        # Set up different return values for different calls
        self.weatherapi_wrapper.get_forecast.side_effect = [
            mock_forecast,
            mock_forecast_with_alerts,
        ]
        self.weatherapi_wrapper.get_hourly_forecast.return_value = mock_hourly

        # Get all three types of data
        forecast = self.service.get_forecast(51.5, -0.1)
        hourly = self.service.get_hourly_forecast(51.5, -0.1)
        alerts = self.service.get_alerts(51.5, -0.1)

        # Check that wrapper methods were called correctly
        self.assertEqual(
            self.weatherapi_wrapper.get_forecast.call_count, 2
        )  # Called for forecast and alerts
        self.weatherapi_wrapper.get_hourly_forecast.assert_called_once()

        # Check the results
        self.assertEqual(forecast, mock_forecast)
        expected_hourly = {"hourly": mock_hourly}
        self.assertEqual(hourly, expected_hourly)
        expected_alerts = {"alerts": mock_forecast_with_alerts["alerts"]}
        self.assertEqual(alerts, expected_alerts)


class TestWeatherApiErrorHandling(unittest.TestCase):
    """Tests for error handling in the WeatherAPI.com integration."""

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

    def test_api_key_invalid_error_handling(self):
        """Test handling of invalid API key error."""
        # Mock the WeatherAPI.com wrapper to raise an API key invalid error
        error = WeatherApiError(
            "API key provided is invalid",
            error_type=WeatherApiError.API_KEY_INVALID,
            error_code=2006,
        )
        self.weatherapi_wrapper.get_forecast.side_effect = error

        # Try to get the forecast and expect the error to be propagated
        with self.assertRaises(WeatherApiError) as context:
            self.service.get_forecast(51.5, -0.1)

        # Check the error
        self.assertEqual(context.exception.error_type, WeatherApiError.API_KEY_INVALID)

    def test_location_not_found_error_handling(self):
        """Test handling of location not found error."""
        # Mock the WeatherAPI.com wrapper to raise a location not found error
        error = WeatherApiError(
            "No matching location found",
            error_type=WeatherApiError.NOT_FOUND,
            error_code=1006,
        )
        self.weatherapi_wrapper.get_forecast.side_effect = error

        # Try to get the forecast and expect the error to be propagated
        with self.assertRaises(WeatherApiError) as context:
            self.service.get_forecast(51.5, -0.1)

        # Check the error
        self.assertEqual(context.exception.error_type, WeatherApiError.NOT_FOUND)

    def test_quota_exceeded_error_handling(self):
        """Test handling of quota exceeded error."""
        # Mock the WeatherAPI.com wrapper to raise a quota exceeded error
        error = WeatherApiError(
            "API key has exceeded calls per month quota",
            error_type=WeatherApiError.QUOTA_EXCEEDED,
            error_code=2007,
        )
        self.weatherapi_wrapper.get_forecast.side_effect = error

        # Try to get the forecast and expect the error to be propagated
        with self.assertRaises(WeatherApiError) as context:
            self.service.get_forecast(51.5, -0.1)

        # Check the error
        self.assertEqual(context.exception.error_type, WeatherApiError.QUOTA_EXCEEDED)

    def test_server_error_handling(self):
        """Test handling of server error."""
        # Mock the WeatherAPI.com wrapper to raise a server error
        error = WeatherApiError(
            "Internal application error",
            error_type=WeatherApiError.SERVER_ERROR,
            error_code=9999,
        )
        self.weatherapi_wrapper.get_forecast.side_effect = error

        # Try to get the forecast and expect the error to be propagated
        with self.assertRaises(WeatherApiError) as context:
            self.service.get_forecast(51.5, -0.1)

        # Check the error
        self.assertEqual(context.exception.error_type, WeatherApiError.SERVER_ERROR)

    def test_connection_error_handling(self):
        """Test handling of connection error."""
        # Mock the WeatherAPI.com wrapper to raise a connection error
        error = WeatherApiError(
            "Connection error",
            error_type=WeatherApiError.CONNECTION_ERROR,
        )
        self.weatherapi_wrapper.get_forecast.side_effect = error

        # Try to get the forecast and expect the error to be propagated
        with self.assertRaises(WeatherApiError) as context:
            self.service.get_forecast(51.5, -0.1)

        # Check the error
        self.assertEqual(context.exception.error_type, WeatherApiError.CONNECTION_ERROR)


if __name__ == "__main__":
    unittest.main()
