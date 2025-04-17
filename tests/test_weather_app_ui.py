import wx
import unittest
import time
from wx import UIActionSimulator
from accessiweather.gui.weather_app import WeatherApp

def wait_for(condition_func, timeout=5.0, poll_interval=0.05):
    """Utility: Wait for a condition to be True or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        if condition_func():
            return True
        wx.Yield()
        time.sleep(poll_interval)
    return False

class TestWeatherAppUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App(False)

    @classmethod
    def tearDownClass(cls):
        cls.app.Destroy()

    def test_nationwide_forecast_display(self):
        from unittest.mock import MagicMock
        frame = WeatherApp(
            parent=None,
            weather_service=MagicMock(),
            location_service=MagicMock(),
            notification_service=MagicMock(),
            api_client=MagicMock(),
            config={
                "locations": {"Nationwide": (39.8283, -98.5795)},
                "current": "Nationwide",
                "settings": {"update_interval_minutes": 30, "alert_radius": 25, "precise_location_alerts": True},
                "api_settings": {"api_contact": "test@example.com"},
            },
        )
        frame.Show()
        sim = UIActionSimulator()

        # Wait for the UI to be ready
        wx.Yield()
        time.sleep(0.2)

        # Find the index of 'Nationwide' in the location dropdown
        idx = frame.location_choice.FindString("Nationwide")
        self.assertNotEqual(idx, wx.NOT_FOUND, "Nationwide must be in the location dropdown")
        frame.location_choice.SetSelection(idx)
        wx.PostEvent(frame.location_choice, wx.CommandEvent(wx.EVT_CHOICE.typeId, frame.location_choice.GetId()))
        wx.Yield()
        time.sleep(0.2)

        # Simulate clicking the Refresh button to trigger forecast update
        btn_pos = frame.refresh_btn.GetScreenPosition()
        btn_size = frame.refresh_btn.GetSize()
        sim.MouseMove(btn_pos.x + btn_size.x // 2, btn_pos.y + btn_size.y // 2)
        sim.MouseClick()
        wx.Yield()
        time.sleep(0.5)

        # Wait for forecast text to update (should mention 'National' or 'Nationwide')
        def forecast_updated():
            val = frame.forecast_text.GetValue()
            return ("National" in val or "Nationwide" in val) and "No forecast" not in val

        self.assertTrue(wait_for(forecast_updated, timeout=5), "Forecast text did not update for Nationwide")

        # Accessibility: Ensure forecast_text label is set correctly
        self.assertIn("Forecast Content", frame.forecast_text.GetLabel(), "Forecast text control should have accessible label")

        frame.Destroy()

if __name__ == "__main__":
    unittest.main()
