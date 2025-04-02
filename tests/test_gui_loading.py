# tests/test_gui_loading.py
"""Tests specifically for loading feedback in WeatherApp"""

import pytest
import wx
import wx.richtext
# import time # No longer needed after removing sleep
from unittest.mock import patch, MagicMock

# Assuming WeatherApp is importable and fixtures might be needed
# We might need to duplicate or import fixtures from test_gui.py if complex
# For simplicity, let's redefine a minimal mock_components fixture here
# or assume it's available via conftest.py later.
from accessiweather.gui.weather_app import WeatherApp
from tests.test_gui import TestWeatherApp  # To potentially inherit fixtures


# Minimal fixture redefinition for standalone use (adapt as needed)
@pytest.fixture
def mock_components_loading():
    """Minimal mock components for loading tests"""
    with patch('accessiweather.api_client.NoaaApiClient') \
            as mock_api_client_class, \
         patch('accessiweather.notifications.WeatherNotifier') \
            as mock_notifier_class, \
         patch('accessiweather.location.LocationManager') \
            as mock_location_manager_class:

        mock_api_client = MagicMock()
        mock_notifier = MagicMock()
        mock_location_manager = MagicMock()
        mock_location_manager.get_current_location.return_value = (
            "Test City", 35.0, -80.0
        )

        mock_api_client_class.return_value = mock_api_client
        mock_notifier_class.return_value = mock_notifier
        mock_location_manager_class.return_value = mock_location_manager

        yield {
            'api_client': mock_api_client,
            'notifier': mock_notifier,
            'location_manager': mock_location_manager
        }


# Use the base class from test_gui to inherit wx_app fixture
# Note: This class duplicates announcement tests from TestWeatherApp.
# Consider refactoring or removing duplication later.
class TestWeatherAppLoadingFeedback(TestWeatherApp):
    """Tests specifically for loading feedback and related UI states"""

    # Use the locally defined fixture for components
    @pytest.fixture
    def mock_components(self, mock_components_loading):
        return mock_components_loading

    # Removed duplicated announcement tests as the feature was removed

    # --- Original Loading Feedback Tests (Applying Fixes) ---

    # Removed threading.Thread patch as async fetchers handle threading
    @patch('wx.CallAfter')
    def test_ui_state_during_fetch(
        self, mock_call_after, wx_app, mock_components  # Removed mock_announce
    ):
        """Test UI elements are disabled/show loading during fetch"""
        app = None
        try:
            app = WeatherApp(
                parent=None,
                location_manager=mock_components['location_manager'],
                api_client=mock_components['api_client'],
                notifier=mock_components['notifier']
            )
            # Mock UI elements directly on the instance
            # Correct attribute name
            app.refresh_btn = MagicMock(spec=wx.Button)
            app.forecast_text = MagicMock(spec=wx.richtext.RichTextCtrl)
            # Correct spec to wx.ListCtrl for DeleteAllItems
            app.alerts_list = MagicMock(spec=wx.ListCtrl)

            # Trigger fetch
            location = ("Test City", 35.0, -80.0)
            # Mock the fetcher methods directly to prevent actual calls
            # Assign to _ as mocks are not used directly
            with patch.object(app.forecast_fetcher, 'fetch') as _, \
                 patch.object(app.alerts_fetcher, 'fetch') as _:
                app._FetchWeatherData(location)

            # Assertions immediately after calling _FetchWeatherData
            app.refresh_btn.Disable.assert_called_once()
            # Check forecast text (depends on implementation)
            app.forecast_text.SetValue.assert_called()
            call_args = app.forecast_text.SetValue.call_args[0]
            assert call_args[0] == "Loading forecast..."

            # Check alerts list (depends on implementation)
            # Assert DeleteAllItems was called on the ListCtrl mock
            app.alerts_list.DeleteAllItems.assert_called_once()
            # Or: app.alerts_list.SetString.assert_called_with("Loading...")

            # Check immediate state change only
            # pytest.fail("UI mocking needs refinement.") # Keep failing

        finally:
            if app:
                app.Destroy()

    # Patch the actual fetcher methods and wx.MessageBox
    @patch('wx.MessageBox')  # Mock message box display
    @patch('wx.CallAfter')
    def test_ui_state_on_fetch_error(
        self, mock_call_after, mock_message_box,  # Removed mock_announce
        wx_app, mock_components
    ):
        """Test UI elements are re-enabled/show error on fetch failure"""
        app = None
        try:
            app = WeatherApp(
                parent=None,
                location_manager=mock_components['location_manager'],
                api_client=mock_components['api_client'],
                notifier=mock_components['notifier']
            )
            # Mock UI elements
            # Correct attribute name
            app.refresh_btn = MagicMock(spec=wx.Button)
            app.forecast_text = MagicMock(spec=wx.richtext.RichTextCtrl)
            # Correct spec
            app.alerts_list = MagicMock(spec=wx.ListCtrl)
            # Mock UIManager methods as they are called in error handlers too
            app.ui_manager._UpdateForecastDisplay = MagicMock()
            app.ui_manager._UpdateAlertsDisplay = MagicMock()

            # Trigger fetch, simulating errors in callbacks via fetcher mocks
            location = ("Test City", 35.0, -80.0)
            # Use side_effect on the fetcher mocks to call error handlers
            with patch.object(
                app.forecast_fetcher, 'fetch',
                side_effect=lambda lat, lon, on_success, on_error: on_error("Forecast API Error") # noqa E501
            ) as mock_f_fetch, patch.object(
                app.alerts_fetcher, 'fetch',
                side_effect=lambda lat, lon, on_success, on_error: on_error("Alerts API Error") # noqa E501
            ) as mock_a_fetch:
                app._FetchWeatherData(location)

                # Check fetchers were called
                mock_f_fetch.assert_called_once()
                mock_a_fetch.assert_called_once()

            # No need for sleep, error handlers called directly by side_effect

            # Assertions after error handlers should have run
            app.refresh_btn.Enable.assert_called()  # Re-enabled
            # Check forecast text shows error
            app.forecast_text.SetValue.assert_called()
            assert "Error fetching forecast" in app.forecast_text.SetValue.call_args[0][0] # noqa E501
            # Check alerts list is cleared
            app.alerts_list.DeleteAllItems.assert_called()
            # Check MessageBox was called (at least twice, once for each error)
            assert mock_message_box.call_count >= 2

            # pytest.fail("UI mocking needs refinement.") # Keep failing

        finally:
            if app:
                app.Destroy()

    # Patch the actual fetcher methods
    @patch('wx.CallAfter')
    def test_ui_state_on_fetch_success(
        self, mock_call_after, wx_app, mock_components  # Removed mock_announce
    ):
        """Test UI elements are updated and enabled on fetch success"""
        app = None
        try:
            app = WeatherApp(
                parent=None,
                location_manager=mock_components['location_manager'],
                api_client=mock_components['api_client'],
                notifier=mock_components['notifier']
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
            app.ui_manager._UpdateAlertsDisplay.return_value = [
                {"event": "Flood Warning"}
            ]

            # Trigger fetch, simulating success in callbacks via fetcher mocks
            location = ("Test City", 35.0, -80.0)
            mock_forecast_data = {
                "properties": {"periods": [{"name": "Today", "detailedForecast": "Sunny"}]} # noqa E501
            }
            mock_alerts_data = {
                "features": [{"properties": {"event": "Flood Warning"}}]
            }

            with patch.object(
                app.forecast_fetcher, 'fetch',
                side_effect=lambda lat, lon, on_success, on_error: on_success(mock_forecast_data) # noqa E501
            ) as mock_f_fetch, patch.object(
                app.alerts_fetcher, 'fetch',
                side_effect=lambda lat, lon, on_success, on_error: on_success(mock_alerts_data) # noqa E501
            ) as mock_a_fetch:
                app._FetchWeatherData(location)

                # Check fetchers were called
                mock_f_fetch.assert_called_once()
                mock_a_fetch.assert_called_once()

            # No need for sleep, success handlers are called directly

            # Assertions after success handlers
            app.refresh_btn.Enable.assert_called_once()  # Re-enabled
            # Check UIManager methods were called
            app.ui_manager._UpdateForecastDisplay.assert_called_once_with(
                mock_forecast_data
            )
            app.ui_manager._UpdateAlertsDisplay.assert_called_once_with(
                mock_alerts_data
            )

            # pytest.fail("UI mocking needs refinement.") # Keep failing

        finally:
            if app:
                app.Destroy()