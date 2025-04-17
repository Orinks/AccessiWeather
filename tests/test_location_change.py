import time
import unittest
from unittest.mock import MagicMock, patch

# mypy: ignore-errors
import wx

from accessiweather.gui.weather_app import WeatherApp
from accessiweather.services.location_service import LocationService
from accessiweather.services.weather_service import WeatherService
from accessiweather.services.notification_service import NotificationService
from accessiweather.api_client import NoaaApiClient


class TestLocationChange(unittest.TestCase):
    """Test case for verifying location change updates weather data"""

    def setUp(self):
        self.app = wx.App()

        # Setup API client mock for forecast response
        self.ny_forecast = {
            "properties": {
                "periods": [
                    {
                        "name": "Tonight",
                        "temperature": 50,
                        "temperatureUnit": "F",
                        "detailedForecast": "Clear",
                    }
                ]
            }
        }
        self.la_forecast = {
            "properties": {
                "periods": [
                    {
                        "name": "Tonight",
                        "temperature": 70,
                        "temperatureUnit": "F",
                        "detailedForecast": "Sunny",
                    }
                ]
            }
        }

        # Create sample locations
        self.sample_locations = {
            "New York": {"lat": 40.7128, "lon": -74.0060},
            "Los Angeles": {"lat": 34.0522, "lon": -118.2437},
        }

        # Start patchers
        self.api_client_patcher = patch.object(
            NoaaApiClient, '__new__', return_value=MagicMock(spec=NoaaApiClient)
        )
        self.location_service_patcher = patch.object(
            LocationService, '__new__', return_value=MagicMock(spec=LocationService)
        )
        self.notifier_patcher = patch.object(
            NotificationService, '__new__', return_value=MagicMock(spec=NotificationService)
        )
        self.weather_service_patcher = patch.object(
            WeatherService, '__new__', return_value=MagicMock(spec=WeatherService)
        )

        # Start the patchers
        self.api_client_mock = self.api_client_patcher.start()
        self.location_service_mock = self.location_service_patcher.start()
        self.notifier_mock = self.notifier_patcher.start()
        self.weather_service_mock = self.weather_service_patcher.start()

        # Patch get_forecast to return LA forecast if called with LA coordinates
        def get_forecast_side_effect(lat, lon, force_refresh=False):  # noqa: F841
            if abs(lat - 34.0522) < 0.001 and abs(lon + 118.2437) < 0.001:
                return self.la_forecast
            return self.ny_forecast
        self.weather_service_mock.get_forecast.side_effect = get_forecast_side_effect
        # Do not patch get_national_forecast_data; let it return the default MagicMock

        # Setup location manager mock
        self.location_service_mock.get_all_locations.return_value = list(
            self.sample_locations.keys()
        )
        self.location_manager_mock = MagicMock()
        self.location_manager_mock.get_current_location_name.return_value = "New York"
        self.location_manager_mock.get_current_location.return_value = (
            "New York",
            40.7128,
            -74.0060,
        )

        # Create WeatherApp with mocked dependencies
        with patch("wx.CallAfter", side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)):
            with patch.object(WeatherApp, "_check_api_contact_configured"):
                self.frame = WeatherApp(
                    weather_service=self.weather_service_mock,
                    location_service=self.location_manager_mock,
                    api_client=self.api_client_mock,
                    notification_service=self.notifier_mock,
                    config={"skip_api_contact_check": True},
                )

    def tearDown(self):
        # Ensure all threads are properly terminated before destroying the frame
        try:
            # If async fetchers were created, make sure they are stopped
            if hasattr(self.frame, "forecast_fetcher") and self.frame.forecast_fetcher is not None:
                if hasattr(self.frame.forecast_fetcher, "_stop_event"):
                    self.frame.forecast_fetcher._stop_event.set()
            if hasattr(self.frame, "alerts_fetcher") and self.frame.alerts_fetcher is not None:
                if hasattr(self.frame.alerts_fetcher, "_stop_event"):
                    self.frame.alerts_fetcher._stop_event.set()
            if (
                hasattr(self.frame, "discussion_fetcher")
                and self.frame.discussion_fetcher is not None
            ):
                if hasattr(self.frame.discussion_fetcher, "_stop_event"):
                    self.frame.discussion_fetcher._stop_event.set()

            # Small delay to ensure threads can process stop events
            time.sleep(0.1)
        finally:
            # Stop all patchers
            self.api_client_patcher.stop()
            self.location_service_patcher.stop()
            self.notifier_patcher.stop()
            self.weather_service_patcher.stop()

            self.frame.Destroy()
            # Avoid calling MainLoop which can cause access violations
            # during testing when threads are involved

    def test_location_change_updates_forecast(self):
        """Test that changing location updates the forecast"""
        # Before changing location: verify New York is current
        self.assertEqual(self.location_manager_mock.get_current_location_name(), "New York")

        # Simulate selecting Los Angeles
        self.location_manager_mock.get_current_location.return_value = (
            "Los Angeles",
            34.0522,
            -118.2437,
        )

        # Mock the location choice selection
        with patch.object(
            self.frame.location_choice, "GetStringSelection", return_value="Los Angeles"
        ):
            # Trigger the location change event
            self.frame.OnLocationChange(None)

            # Verify location manager was updated
            self.location_manager_mock.set_current_location.assert_called_with("Los Angeles")


if __name__ == "__main__":
    unittest.main()
