"""Tests for the WeatherService class with caching."""

from unittest.mock import MagicMock, patch
import unittest
from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.services.weather_service import WeatherService

class TestWeatherServiceCaching(unittest.TestCase):
    """Test suite for WeatherService with caching."""
    def setUp(self):
        # Create a patcher for the WeatherService class
        self.patcher = patch('accessiweather.services.weather_service.WeatherService.__new__',
                             return_value=object.__new__(WeatherService))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

        # Set up a mock API client
        self.mock_api_client = MagicMock(spec=NoaaApiClient)
        self.mock_api_client.get_forecast.return_value = {
            "properties": {"periods": [{"name": "Default", "temperature": 0}]}
        }
        self.mock_api_client.get_alerts.return_value = {"features": []}
        self.mock_api_client.get_discussion.return_value = "Test discussion"
        self.mock_api_client.cache = MagicMock()  # Mock the cache

        # Create the actual WeatherService instance
        self.weather_service = WeatherService(self.mock_api_client)

    def test_get_forecast_with_cache(self):
        self.weather_service.get_forecast(35.0, -80.0)
        self.mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0, force_refresh=False)

    def test_get_forecast_force_refresh(self):
        self.weather_service.get_forecast(35.0, -80.0, force_refresh=True)
        self.mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0, force_refresh=True)

    def test_get_alerts_with_cache(self):
        self.weather_service.get_alerts(35.0, -80.0, radius=25, precise_location=True)
        self.mock_api_client.get_alerts.assert_called_once_with(
            35.0, -80.0, radius=25, precise_location=True, force_refresh=False
        )

    def test_get_alerts_force_refresh(self):
        self.weather_service.get_alerts(35.0, -80.0, radius=25, precise_location=True, force_refresh=True)
        self.mock_api_client.get_alerts.assert_called_once_with(
            35.0, -80.0, radius=25, precise_location=True, force_refresh=True
        )

    def test_get_discussion_with_cache(self):
        self.weather_service.get_discussion(35.0, -80.0)
        self.mock_api_client.get_discussion.assert_called_once_with(35.0, -80.0, force_refresh=False)

    def test_get_discussion_force_refresh(self):
        self.weather_service.get_discussion(35.0, -80.0, force_refresh=True)
        self.mock_api_client.get_discussion.assert_called_once_with(35.0, -80.0, force_refresh=True)

    def test_api_error_handling(self):
        self.mock_api_client.get_forecast.side_effect = ApiClientError("Test error")
        with self.assertRaises(ApiClientError) as exc_info:
            self.weather_service.get_forecast(35.0, -80.0)
        self.assertIn("Test error", str(exc_info.exception))

if __name__ == "__main__":
    unittest.main()
