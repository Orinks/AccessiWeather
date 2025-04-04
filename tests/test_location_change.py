import time
import unittest
from unittest.mock import MagicMock, patch

# mypy: ignore-errors
import wx


class TestLocationChange(unittest.TestCase):
    """Test case for verifying location change updates weather data"""

    def setUp(self):
        self.app = wx.App()

        # Mock dependencies
        self.api_client_mock = MagicMock()
        self.location_manager_mock = MagicMock()
        self.notifier_mock = MagicMock()

        # Create sample locations
        self.sample_locations = {
            "New York": {"lat": 40.7128, "lon": -74.0060},
            "Los Angeles": {"lat": 34.0522, "lon": -118.2437},
        }

        # Setup location manager mock
        self.location_manager_mock.get_all_locations.return_value = list(
            self.sample_locations.keys()
        )
        self.location_manager_mock.get_current_location_name.return_value = (
            "New York"
        )
        self.location_manager_mock.get_current_location.return_value = (
            "New York",
            40.7128,
            -74.0060,
        )

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

        # Import here to avoid circular imports
        from accessiweather.gui.weather_app import WeatherApp

        # Create WeatherApp with mocked dependencies
        with patch(
            "wx.CallAfter",
            side_effect=lambda func, *args, **kwargs: func(*args, **kwargs),
        ):
            self.frame = WeatherApp(
                location_manager=self.location_manager_mock,
                api_client=self.api_client_mock,
                notifier=self.notifier_mock,
            )

    def tearDown(self):
        # Ensure all threads are properly terminated before destroying the
        # frame
        try:
            # If async fetchers were created, make sure they are stopped
            if (
                hasattr(self.frame, "forecast_fetcher")
                and self.frame.forecast_fetcher is not None
            ):
                if hasattr(self.frame.forecast_fetcher, "_stop_event"):
                    self.frame.forecast_fetcher._stop_event.set()
            if (
                hasattr(self.frame, "alerts_fetcher")
                and self.frame.alerts_fetcher is not None
            ):
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
            self.frame.Destroy()
            # Avoid calling MainLoop which can cause access violations
            # during testing when threads are involved

    def test_location_change_updates_forecast(self):
        """Test that changing location updates the forecast"""
        # Set up test hooks for tracking callbacks
        forecast_callback = MagicMock()
        self.frame._testing_forecast_callback = forecast_callback
        self.frame._testing_forecast_error_callback = MagicMock()

        alerts_callback = MagicMock()
        self.frame._testing_alerts_callback = alerts_callback
        self.frame._testing_alerts_error_callback = MagicMock()

        # Before changing location: verify New York is current
        self.assertEqual(
            self.location_manager_mock.get_current_location_name(), "New York"
        )

        # Patch the forecast and alerts fetchers to directly call the success
        # callbacks

        def mock_forecast_fetch(lat, lon, on_success=None, on_error=None):
            # Verify we're getting the LA coordinates
            self.assertAlmostEqual(lat, 34.0522)
            self.assertAlmostEqual(lon, -118.2437)
            # Directly call success callback
            if on_success:
                on_success(self.la_forecast)
            return

        self.frame.forecast_fetcher.fetch = mock_forecast_fetch

        def mock_alerts_fetch(lat, lon, on_success=None, on_error=None):
            # Verify we're getting the LA coordinates
            self.assertAlmostEqual(lat, 34.0522)
            self.assertAlmostEqual(lon, -118.2437)
            # Directly call success callback
            if on_success:
                on_success({"features": []})
            return

        self.frame.alerts_fetcher.fetch = mock_alerts_fetch

        # Simulate selecting Los Angeles
        self.location_manager_mock.get_current_location.return_value = (
            "Los Angeles",
            34.0522,
            -118.2437,
        )

        # Mock the location choice selection
        with patch.object(
            self.frame.location_choice,
            "GetStringSelection",
            return_value="Los Angeles",
        ):
            # Trigger the location change event
            self.frame.OnLocationChange(None)

            # Verify location manager was updated
            self.location_manager_mock.set_current_location.assert_called_with(
                "Los Angeles"
            )

            # Verify test hooks were called with the correct data
            forecast_callback.assert_called_once_with(self.la_forecast)
            alerts_callback.assert_called_once_with({"features": []})


if __name__ == "__main__":
    unittest.main()
