"""Tests for precise location alerts functionality."""

# Import faulthandler setup first to enable faulthandler
from unittest.mock import MagicMock

import unittest
import wx

# Import for side effects (enables faulthandler)
import tests.faulthandler_setup  # noqa: F401
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

    def test_get_alerts_precise_location(self):
        self.mock_api_client.get_point_data = MagicMock(return_value={
            "properties": {
                "county": "https://api.weather.gov/zones/county/NJC015",
                "relativeLocation": {"properties": {"state": "NJ"}}
            }
        })
        self.mock_api_client.get_alerts(40.0, -74.0, precise_location=True)
        self.mock_api_client._make_request.assert_called_with(
            "alerts/active", params={"zone": "NJC015"}, force_refresh=False
        )

    def test_get_alerts_statewide(self):
        self.mock_api_client.get_point_data = MagicMock(return_value={
            "properties": {
                "county": "https://api.weather.gov/zones/county/NJC015",
                "relativeLocation": {"properties": {"state": "NJ"}}
            }
        })
        self.mock_api_client.get_alerts(40.0, -74.0, precise_location=False)
        self.mock_api_client._make_request.assert_called_with(
            "alerts/active", params={"area": "NJ"}, force_refresh=False
        )

    def test_alerts_fetcher_uses_precise_setting(self):
        self.mock_api_client.get_alerts = MagicMock(return_value={"features": []})
        on_success = MagicMock()
        self.mock_alerts_fetcher.fetch(40.0, -74.0, on_success=on_success, precise_location=True)
        import time
        time.sleep(0.1)
        self.mock_api_client.get_alerts.assert_called_with(
            40.0, -74.0, radius=25, precise_location=True
        )
        self.mock_api_client.get_alerts.reset_mock()
        self.mock_alerts_fetcher.fetch(40.0, -74.0, on_success=on_success, precise_location=False)
        time.sleep(0.1)
        self.mock_api_client.get_alerts.assert_called_with(
            40.0, -74.0, radius=25, precise_location=False
        )

    def test_settings_dialog_precise_location_toggle(self):
        frame = wx.Frame(None)
        settings = {
            "update_interval_minutes": 30,
            "alert_radius_miles": 25,
            "api_contact": "test@example.com",
            PRECISE_LOCATION_ALERTS_KEY: True
        }
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
