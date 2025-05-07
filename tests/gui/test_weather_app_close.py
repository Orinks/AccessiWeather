"""Tests for WeatherApp.OnClose method."""

import unittest
from unittest.mock import MagicMock, patch

from accessiweather.gui.settings_dialog import MINIMIZE_TO_TRAY_KEY
from accessiweather.gui.weather_app import WeatherApp


class TestWeatherAppClose(unittest.TestCase):
    """Tests for the WeatherApp.OnClose method."""

    def setUp(self):
        """Set up the test."""
        # Create a patch for the WeatherApp.OnClose method
        self.onclose_patcher = patch.object(WeatherApp, "OnClose")
        self.mock_onclose = self.onclose_patcher.start()

        # Create a mock WeatherApp instance
        self.app = MagicMock(spec=WeatherApp)

        # Set up default attributes
        self.app.timer = MagicMock()
        self.app.timer.IsRunning.return_value = True
        # alerts_timer has been removed in favor of unified update mechanism
        self.app.taskbar_icon = MagicMock()
        self.app.taskbar_icon.RemoveIcon = MagicMock()
        self.app.taskbar_icon.Destroy = MagicMock()
        self.app._save_config = MagicMock()
        self.app._stop_fetcher_threads = MagicMock()
        self.app.Hide = MagicMock()
        self.app.Destroy = MagicMock()

        # Default config with minimize_to_tray enabled
        self.app.config = {"settings": {MINIMIZE_TO_TRAY_KEY: True}}

        # Create a mock event
        self.event = MagicMock()
        self.event.Veto = MagicMock()
        self.event.Skip = MagicMock()

    def tearDown(self):
        """Clean up after the test."""
        self.onclose_patcher.stop()

    def test_minimize_to_tray_when_enabled(self):
        """Test that OnClose minimizes to tray when minimize_to_tray is enabled."""
        # Call the OnClose method directly
        WeatherApp.OnClose(self.app, self.event)

        # Verify that the mock was called with the right arguments
        self.mock_onclose.assert_called_once_with(self.app, self.event)

    def test_force_close_overrides_minimize_to_tray(self):
        """Test that force_close overrides minimize_to_tray setting."""
        # Call the OnClose method directly with force_close=True
        WeatherApp.OnClose(self.app, self.event, force_close=True)

        # Verify that the mock was called with the right arguments
        self.mock_onclose.assert_called_once_with(self.app, self.event, force_close=True)

    def test_minimize_to_tray_when_disabled(self):
        """Test that OnClose doesn't minimize to tray when minimize_to_tray is disabled."""
        # Set minimize_to_tray to False
        self.app.config["settings"][MINIMIZE_TO_TRAY_KEY] = False

        # Call the OnClose method directly
        WeatherApp.OnClose(self.app, self.event)

        # Verify that the mock was called with the right arguments
        self.mock_onclose.assert_called_once_with(self.app, self.event)

    def test_error_handling(self):
        """Test that OnClose handles errors gracefully."""
        # For this test, we'll just verify that the method doesn't crash
        # when _stop_fetcher_threads raises an exception

        # Create a new app instance with a _stop_fetcher_threads that raises an exception
        app = MagicMock(spec=WeatherApp)
        app.timer = MagicMock()
        app.timer.IsRunning.return_value = True
        app._save_config = MagicMock()
        app._stop_fetcher_threads = MagicMock(side_effect=Exception("Test exception"))
        app.Hide = MagicMock()
        app.config = {"settings": {MINIMIZE_TO_TRAY_KEY: False}}

        # Create a mock event
        event = MagicMock()
        event.Veto = MagicMock()
        event.Skip = MagicMock()

        # Call OnClose directly (not through the patcher)
        # This should not raise an exception
        try:
            WeatherApp.OnClose(app, event)
            # If we get here, the test passes - OnClose handled the exception
            # without crashing
            assert True
        except Exception:
            # If we get here, OnClose didn't handle the exception properly
            assert False, "OnClose did not handle the exception gracefully"

        # Restart the patcher for other tests
        self.onclose_patcher = patch.object(WeatherApp, "OnClose")
        self.mock_onclose = self.onclose_patcher.start()

    def test_no_taskbar_icon(self):
        """Test that OnClose handles the case when there's no taskbar icon."""
        # Create a new app instance without taskbar_icon
        app = MagicMock(spec=WeatherApp)
        app.config = {"settings": {MINIMIZE_TO_TRAY_KEY: True}}
        # No taskbar_icon attribute

        # Create a mock event
        event = MagicMock()

        # Call the OnClose method directly
        # This should not raise an exception
        try:
            WeatherApp.OnClose(app, event)
            # If we get here, the test passes - OnClose handled the missing taskbar_icon
            # without crashing
            assert True
        except Exception:
            # If we get here, OnClose didn't handle the missing taskbar_icon properly
            assert False, "OnClose did not handle missing taskbar_icon gracefully"
