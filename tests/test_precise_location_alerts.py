"""Tests for precise location alerts functionality."""

# Import faulthandler setup first to enable faulthandler
<<<<<<< Updated upstream
=======


>>>>>>> Stashed changes
import json
import os
from unittest.mock import MagicMock, patch

import unittest
import wx
<<<<<<< Updated upstream

import tests.faulthandler_setup
=======
from unittest.mock import MagicMock
>>>>>>> Stashed changes
from accessiweather.api_client import NoaaApiClient
from accessiweather.gui.async_fetchers import AlertsFetcher
from accessiweather.gui.settings_dialog import PRECISE_LOCATION_ALERTS_KEY

class TestPreciseLocationAlerts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App() if not wx.GetApp() else wx.GetApp()

    def setUp(self):
        self.mock_api_client = NoaaApiClient(user_agent="TestClient")
        self.mock_api_client._make_request = MagicMock()
        self.mock_api_client.identify_location_type = MagicMock(return_value=("county", "NJC015"))
        self.mock_alerts_fetcher = AlertsFetcher(self.mock_api_client)

    def test_identify_location_type(self):
        location_type, location_id = self.mock_api_client.identify_location_type(40.0, -74.0)
        self.assertEqual(location_type, "county")
        self.assertEqual(location_id, "NJC015")
        self.mock_api_client.identify_location_type.assert_called_once_with(40.0, -74.0)

<<<<<<< Updated upstream
@pytest.fixture
def mock_alerts_fetcher(mock_api_client):
    """Create a mock alerts fetcher for testing."""
    fetcher = AlertsFetcher(mock_api_client)
    return fetcher


def test_identify_location_type(mock_api_client):
    """Test that the API client correctly identifies location types."""
    # We already mocked identify_location_type in the fixture to return ("county", "NJC015")
    # so we just need to call it and verify the result
    location_type, location_id = mock_api_client.identify_location_type(40.0, -74.0)

    # Verify the result
    assert location_type == "county"
    assert location_id == "NJC015"

    # Verify the method was called with the correct parameters
    mock_api_client.identify_location_type.assert_called_once_with(40.0, -74.0)


def test_get_alerts_precise_location(mock_api_client):
    """Test getting alerts with precise location setting."""
    # Set up the mock
    mock_api_client.get_point_data = MagicMock(
        return_value={
            "properties": {
                "county": "https://api.weather.gov/zones/county/NJC015",
                "relativeLocation": {"properties": {"state": "NJ"}},
            }
        }
    )

    # Call get_alerts with precise_location=True
    mock_api_client.get_alerts(40.0, -74.0, precise_location=True)

    # Verify the API was called with the correct parameters
    mock_api_client._make_request.assert_called_with("alerts/active", params={"zone": "NJC015"})


def test_get_alerts_statewide(mock_api_client):
    """Test getting alerts with statewide setting."""
    # Set up the mock
    mock_api_client.get_point_data = MagicMock(
        return_value={
            "properties": {
                "county": "https://api.weather.gov/zones/county/NJC015",
                "relativeLocation": {"properties": {"state": "NJ"}},
=======
    def test_get_alerts_precise_location(self):
        self.mock_api_client.get_point_data = MagicMock(return_value={
            "properties": {
                "county": "https://api.weather.gov/zones/county/NJC015",
                "relativeLocation": {"properties": {"state": "NJ"}}
            }
        })
        self.mock_api_client.get_alerts(40.0, -74.0, precise_location=True)
        self.mock_api_client._make_request.assert_called_with(
            "alerts/active", params={"zone": "NJC015"}
        )

    def test_get_alerts_statewide(self):
        self.mock_api_client.get_point_data = MagicMock(return_value={
            "properties": {
                "county": "https://api.weather.gov/zones/county/NJC015",
                "relativeLocation": {"properties": {"state": "NJ"}}
>>>>>>> Stashed changes
            }
        })
        self.mock_api_client.get_alerts(40.0, -74.0, precise_location=False)
        self.mock_api_client._make_request.assert_called_with(
            "alerts/active", params={"area": "NJ"}
        )

    def test_alerts_fetcher_uses_precise_setting(self):
        self.mock_api_client.get_alerts = MagicMock(return_value={"features": []})
        on_success = MagicMock()
        self.mock_alerts_fetcher.fetch(40.0, -74.0, on_success=on_success, precise_location=True)
        import time
        time.sleep(0.1)
        self.mock_api_client.get_alerts.assert_called_with(40.0, -74.0, radius=25, precise_location=True)
        self.mock_api_client.get_alerts.reset_mock()
        self.mock_alerts_fetcher.fetch(40.0, -74.0, on_success=on_success, precise_location=False)
        time.sleep(0.1)
        self.mock_api_client.get_alerts.assert_called_with(40.0, -74.0, radius=25, precise_location=False)

    def test_settings_dialog_precise_location_toggle(self):
        frame = wx.Frame(None)
        settings = {
            "update_interval_minutes": 30,
            "alert_radius_miles": 25,
            "api_contact": "test@example.com",
            PRECISE_LOCATION_ALERTS_KEY: True
        }
<<<<<<< Updated upstream
    )

    # Call get_alerts with precise_location=False
    mock_api_client.get_alerts(40.0, -74.0, precise_location=False)

    # Verify the API was called with the correct parameters
    mock_api_client._make_request.assert_called_with("alerts/active", params={"area": "NJ"})


def test_alerts_fetcher_uses_precise_setting(mock_alerts_fetcher, mock_api_client):
    """Test that the alerts fetcher passes the precise location setting to the API client."""
    # Mock the API client's get_alerts method
    mock_api_client.get_alerts = MagicMock(return_value={"features": []})

    # Create a mock success callback
    on_success = MagicMock()

    # Call fetch with precise_location=True
    mock_alerts_fetcher.fetch(40.0, -74.0, on_success=on_success, precise_location=True)

    # Wait for the thread to complete
    import time

    time.sleep(0.1)

    # Verify the API client was called with precise_location=True
    mock_api_client.get_alerts.assert_called_with(40.0, -74.0, radius=25, precise_location=True)

    # Reset the mock
    mock_api_client.get_alerts.reset_mock()

    # Call fetch with precise_location=False
    mock_alerts_fetcher.fetch(40.0, -74.0, on_success=on_success, precise_location=False)

    # Wait for the thread to complete
    time.sleep(0.1)

    # Verify the API client was called with precise_location=False
    mock_api_client.get_alerts.assert_called_with(40.0, -74.0, radius=25, precise_location=False)


@pytest.mark.skipif(not wx.GetApp(), reason="Requires wxPython app")
def test_settings_dialog_precise_location_toggle():
    """Test that the settings dialog includes the precise location toggle."""
    # Create a wx.App if one doesn't exist
    app = wx.App.Get()
    if not app:
        app = wx.App()

    # Create a parent frame
    frame = wx.Frame(None)

    # Create settings with the precise location setting
    settings = {
        "update_interval_minutes": 30,
        "alert_radius_miles": 25,
        "api_contact": "test@example.com",
        PRECISE_LOCATION_ALERTS_KEY: True,
    }

    # Create the dialog
    from accessiweather.gui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(frame, settings)

    # Check that the precise location control exists and has the correct value
    assert hasattr(dialog, "precise_alerts_ctrl")
    assert dialog.precise_alerts_ctrl.GetValue() is True

    # Change the value
    dialog.precise_alerts_ctrl.SetValue(False)

    # Get the settings and verify the change
    new_settings = dialog.get_settings()
    assert new_settings[PRECISE_LOCATION_ALERTS_KEY] is False

    # Clean up
    # Hide the window first
    wx.CallAfter(dialog.Hide)
    wx.SafeYield()
    # Then destroy it
    wx.CallAfter(dialog.Destroy)
    wx.SafeYield()

    # Hide the window first
    wx.CallAfter(frame.Hide)
    wx.SafeYield()
    # Then destroy it
    wx.CallAfter(frame.Destroy)
    wx.SafeYield()
=======
        from accessiweather.gui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(frame, settings)
        self.assertTrue(hasattr(dialog, "precise_alerts_ctrl"))
        self.assertTrue(dialog.precise_alerts_ctrl.GetValue())
        dialog.precise_alerts_ctrl.SetValue(False)
        new_settings = dialog.get_settings()
        self.assertFalse(new_settings[PRECISE_LOCATION_ALERTS_KEY])
        wx.CallAfter(dialog.Hide)
        wx.SafeYield()
        wx.CallAfter(dialog.Destroy)
        wx.SafeYield()
        wx.CallAfter(frame.Hide)
        wx.SafeYield()
        wx.CallAfter(frame.Destroy)
        wx.SafeYield()

if __name__ == "__main__":
    unittest.main()
>>>>>>> Stashed changes
