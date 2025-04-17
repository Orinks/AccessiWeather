# import time # No longer needed after removing sleep
from unittest.mock import MagicMock, patch

import pytest
import wx
import wx.richtext

# Assuming WeatherApp is importable and fixtures might be needed
# We might need to duplicate or import fixtures from test_gui.py if complex
# For simplicity, let's redefine a minimal mock_components fixture here
# or assume it's available via conftest.py later.
from accessiweather.gui.weather_app import WeatherApp



# Minimal fixture redefinition for standalone use (adapt as needed)
@pytest.fixture
def mock_components_loading():
    """Minimal mock components for loading tests"""
    with (
        patch("accessiweather.api_client.NoaaApiClient") as mock_api_client_class,
        patch("accessiweather.notifications.WeatherNotifier") as mock_notifier_class,
        patch("accessiweather.services.location_service.LocationService") as mock_location_service_class,
    ):

        mock_api_client = MagicMock()
        mock_notifier = MagicMock()
        mock_location_service = MagicMock()
        mock_location_service.get_current_location.return_value = ("Test City", 35.0, -80.0)

        mock_api_client_class.return_value = mock_api_client
        mock_notifier_class.return_value = mock_notifier
        mock_location_service_class.return_value = mock_location_service

        yield {
            "api_client": mock_api_client,
            "notifier": mock_notifier,
            "location_service": mock_location_service,
        }


# Use the base class from test_gui to inherit wx_app fixture
# Note: This class duplicates announcement tests from TestWeatherApp.
# Consider refactoring or removing duplication later.
import unittest
from unittest.mock import MagicMock, patch
import wx
import wx.richtext
from accessiweather.gui.weather_app import WeatherApp

class TestWeatherAppLoadingFeedback(unittest.TestCase):
    @patch("wx.CallAfter")
    def test_ui_state_during_fetch(self, mock_call_after):
        app_ctx = None
        app = None
        try:
            # Ensure a wx.App exists
            if not wx.App.Get():
                app_ctx = wx.App()
            else:
                app_ctx = wx.App.Get()
            # Mock dependencies
            location_manager = MagicMock()
            location_manager.get_current_location.return_value = ("Test City", 35.0, -80.0)
            api_client = MagicMock()
            notifier = MagicMock()
            weather_service = MagicMock()
            with patch.object(WeatherApp, "_check_api_contact_configured", return_value=None):
                with patch("wx.MessageBox", return_value=None):
                    app = WeatherApp(
                        parent=None, # Positional first
                        location_service=location_manager,
                        api_client=api_client,
                        notification_service=notifier,
                        weather_service=weather_service, # Corrected: only one
                    )
                    app.refresh_btn = MagicMock(spec=wx.Button)
                    app.forecast_text = MagicMock(spec=wx.richtext.RichTextCtrl)
                    app.alerts_list = MagicMock(spec=wx.ListCtrl)
                    location = ("Test City", 35.0, -80.0)
                    with patch.object(app.forecast_fetcher, "fetch", return_value=None), \
                         patch.object(app.alerts_fetcher, "fetch", return_value=None):
                        app._FetchWeatherData(location)
                    app.refresh_btn.Disable.assert_called_once()
                    app.forecast_text.SetValue.assert_called()
                    first_call = app.forecast_text.SetValue.call_args_list[0]
                    self.assertEqual(first_call[0][0], "Loading forecast...")
                    app.alerts_list.DeleteAllItems.assert_called_once()
        finally:
            if app:
                app.Destroy()
            if app_ctx and isinstance(app_ctx, wx.App):
                # Pass # Let pytest handle app lifecycle if possible
                pass # Keep for now if needed for unittest runner

    # Moved this method inside the class
    @patch("wx.CallAfter")
    def test_ui_state_on_fetch_success(
        self, mock_call_after, wx_app, mock_components # Removed mock_announce
    ):
        """Test UI elements are updated and enabled on fetch success"""
        app = None
        try:
            # Pass parent=None as the first argument
            app = WeatherApp(
                parent=None, # Positional first
                location_service=mock_components["location_service"],
                api_client=mock_components["api_client"],
                notification_service=mock_components["notifier"], # Corrected key
                weather_service=MagicMock(), # Corrected: single instance
            )
            # Mock UI elements and update methods
            # Correct attribute name
            app.refresh_btn = MagicMock(spec=wx.Button)
            app.forecast_text = MagicMock(spec=wx.richtext.RichTextCtrl)
            # Correct spec
            app.alerts_list = MagicMock(spec=wx.ListCtrl)
            # Mock UIManager methods to check they are called
            app.ui_manager._UpdateForecastDisplay = MagicMock()
            app.ui_manager._UpdateAlertsDisplay = MagicMock()
            # Mock return value for alerts display as it's used in main app
            app.ui_manager._UpdateAlertsDisplay.return_value = [{"event": "Flood Warning"}]

            # Trigger fetch, simulating success in callbacks via fetcher mocks
            location = ("Test City", 35.0, -80.0)
            mock_forecast_data = {
                "properties": {
                    "periods": [{"name": "Today", "detailedForecast": "Sunny"}]
                }
            }
            mock_alerts_data = {"features": [{"properties": {"event": "Flood Warning"}}]}

            with (
                patch.object(
                    app.forecast_fetcher,
                    "fetch",
                    side_effect=lambda lat, lon, on_success, on_error: on_success(
                        mock_forecast_data
                    ),
                ) as mock_f_fetch,
                patch.object(
                    app.alerts_fetcher,
                    "fetch",
                    side_effect=lambda lat, lon, on_success, on_error: on_success(
                        mock_alerts_data
                    ),
                ) as mock_a_fetch,
            ):
                app._FetchWeatherData(location)

                # Check fetchers were called
                mock_f_fetch.assert_called_once()
                mock_a_fetch.assert_called_once()

            # No need for sleep, success handlers are called directly

            # Assertions after success handlers
            app.refresh_btn.Enable.assert_called_once() # Re-enabled
            # Check UIManager methods were called
            app.ui_manager._UpdateForecastDisplay.assert_called_once_with(mock_forecast_data)
            app.ui_manager._UpdateAlertsDisplay.assert_called_once_with(mock_alerts_data)

        finally:
            if app:
                app.Destroy()

if __name__ == "__main__":
    unittest.main()
