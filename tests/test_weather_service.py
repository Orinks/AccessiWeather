"""Tests for the WeatherService class."""

from unittest.mock import MagicMock, patch
import unittest
from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.services.weather_service import WeatherService


class TestWeatherService(unittest.TestCase):
    """Test suite for WeatherService."""
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

        # Create the actual WeatherService instance
        self.weather_service = WeatherService(self.mock_api_client)

    def test_get_national_forecast_data_success(self):
        sample_data = {"outlook": "Sunny", "hazards": "None"}
        self.mock_api_client.get_national_forecast_data.return_value = sample_data
        result = self.weather_service.get_national_forecast_data()
        self.assertEqual(result, sample_data)
        self.mock_api_client.get_national_forecast_data.assert_called_once_with(force_refresh=False)

    def test_get_national_forecast_data_error(self):
        self.mock_api_client.get_national_forecast_data.side_effect = Exception("API failure")
        with self.assertRaises(ApiClientError) as exc_info:
            self.weather_service.get_national_forecast_data()
        self.assertIn("Unable to retrieve nationwide forecast data", str(exc_info.exception))
        self.assertIn("API failure", str(exc_info.exception))

    def test_init(self):
        service = WeatherService(self.mock_api_client)
        self.assertEqual(service.api_client, self.mock_api_client)

    def test_get_forecast(self):
        expected_forecast = {"properties": {"periods": [{"name": "Today", "temperature": 75}]}}
        self.mock_api_client.get_forecast.return_value = expected_forecast
        result = self.weather_service.get_forecast(35.0, -80.0)
        self.assertEqual(result, expected_forecast)
        self.mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0, force_refresh=False)

    def test_get_forecast_error(self):
        self.mock_api_client.get_forecast.side_effect = Exception("Test error")
        with self.assertRaises(ApiClientError) as exc_info:
            self.weather_service.get_forecast(35.0, -80.0)
        self.assertIn("Unable to retrieve forecast data", str(exc_info.exception))
        self.assertIn("Test error", str(exc_info.exception))
        self.mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0, force_refresh=False)

    def test_get_alerts(self):
        expected_alerts = {
            "features": [
                {"properties": {"headline": "Test Alert", "description": "Test Description"}}
            ]
        }
        self.mock_api_client.get_alerts.return_value = expected_alerts
        result = self.weather_service.get_alerts(35.0, -80.0, radius=25, precise_location=True)
        self.assertEqual(result, expected_alerts)
        self.mock_api_client.get_alerts.assert_called_once_with(
            35.0, -80.0, radius=25, precise_location=True, force_refresh=False
        )

    def test_get_alerts_error(self):
        self.mock_api_client.get_alerts.side_effect = Exception("Test error")
        with self.assertRaises(ApiClientError) as exc_info:
            self.weather_service.get_alerts(35.0, -80.0, radius=25, precise_location=True)
        self.assertIn("Unable to retrieve alerts data", str(exc_info.exception))
        self.assertIn("Test error", str(exc_info.exception))
        self.mock_api_client.get_alerts.assert_called_once_with(
            35.0, -80.0, radius=25, precise_location=True, force_refresh=False
        )

    def test_get_discussion(self):
        self.mock_api_client.get_discussion.return_value = "Some discussion"
        result = self.weather_service.get_discussion(35.0, -80.0)
        self.assertEqual(result, "Some discussion")
        self.mock_api_client.get_discussion.assert_called_once_with(
            35.0, -80.0, force_refresh=False
        )

    def test_get_discussion_none(self):
        self.mock_api_client.get_discussion.return_value = None
        result = self.weather_service.get_discussion(35.0, -80.0)
        self.assertIsNone(result)
        self.mock_api_client.get_discussion.assert_called_once_with(
            35.0, -80.0, force_refresh=False
        )

    def test_get_discussion_error(self):
        self.mock_api_client.get_discussion.side_effect = Exception("Test error")
        with self.assertRaises(ApiClientError) as exc_info:
            self.weather_service.get_discussion(35.0, -80.0)
        self.assertIn("Unable to retrieve discussion data", str(exc_info.exception))
        self.assertIn("Test error", str(exc_info.exception))
        self.mock_api_client.get_discussion.assert_called_once_with(
            35.0, -80.0, force_refresh=False
        )

    def test_process_alerts(self):
        alerts_data = {
            "features": [
                {
                    "id": "alert-1",
                    "properties": {
                        "headline": "Test Alert 1",
                        "description": "Test Description 1",
                        "instruction": "Test Instruction 1",
                        "severity": "Moderate",
                        "event": "Test Event 1",
                        "effective": "2023-01-01T00:00:00Z",
                        "expires": "2023-01-02T00:00:00Z",
                        "status": "Actual",
                        "messageType": "Alert",
                        "areaDesc": "Test Area 1",
                    },
                },
                {
                    "id": "alert-2",
                    "properties": {
                        "headline": "Test Alert 2",
                        "description": "Test Description 2",
                        "severity": "Severe",
                        "event": "Test Event 2",
                    },
                },
            ]
        }
        result = self.weather_service.process_alerts(alerts_data)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "alert-1")
        self.assertEqual(result[0]["headline"], "Test Alert 1")
        self.assertEqual(result[0]["description"], "Test Description 1")
        self.assertEqual(result[0]["instruction"], "Test Instruction 1")
        self.assertEqual(result[0]["severity"], "Moderate")
        self.assertEqual(result[0]["event"], "Test Event 1")
        self.assertEqual(result[0]["effective"], "2023-01-01T00:00:00Z")
        self.assertEqual(result[0]["expires"], "2023-01-02T00:00:00Z")
        self.assertEqual(result[0]["status"], "Actual")
        self.assertEqual(result[0]["messageType"], "Alert")
        self.assertEqual(result[0]["areaDesc"], "Test Area 1")
        self.assertEqual(result[1]["id"], "alert-2")
        self.assertEqual(result[1]["headline"], "Test Alert 2")
        self.assertEqual(result[1]["description"], "Test Description 2")
        self.assertEqual(result[1]["instruction"], "")  # Default value
        self.assertEqual(result[1]["severity"], "Severe")
        self.assertEqual(result[1]["event"], "Test Event 2")
        self.assertEqual(result[1]["areaDesc"], "Unknown Area")  # Default value

    def test_process_alerts_empty(self):
        alerts_data: dict = {"features": []}
        result = self.weather_service.process_alerts(alerts_data)
        self.assertEqual(result, [])

    def test_process_alerts_missing_features(self):
        alerts_data: dict = {}
        result = self.weather_service.process_alerts(alerts_data)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
