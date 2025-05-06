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
        # Stop the patcher to use the real method
        self.onclose_patcher.stop()

        # Call the real OnClose method
        WeatherApp.OnClose(self.app, self.event)

        # Verify that Hide was called
        self.app.Hide.assert_called_once()

        # Verify that Veto was called to prevent default close behavior
        self.event.Veto.assert_called_once()

        # Verify that Destroy was not called
        self.app.Destroy.assert_not_called()

        # Verify that timer was stopped and restarted
        self.app.timer.Stop.assert_called_once()
        self.app.timer.Start.assert_called_once()

        # Restart the patcher for other tests
        self.onclose_patcher = patch.object(WeatherApp, "OnClose")
        self.mock_onclose = self.onclose_patcher.start()

    def test_force_close_overrides_minimize_to_tray(self):
        """Test that force_close overrides minimize_to_tray setting."""
        # Stop the patcher to use the real method
        self.onclose_patcher.stop()

        # Save a reference to the taskbar_icon before it might be set to None
        taskbar_icon = self.app.taskbar_icon

        # Call the real OnClose method with force_close=True
        WeatherApp.OnClose(self.app, self.event, force_close=True)

        # Verify that Hide was not called
        self.app.Hide.assert_not_called()

        # Verify that Veto was not called
        self.event.Veto.assert_not_called()

        # Verify that Skip was called to allow default close behavior
        self.event.Skip.assert_called_once()

        # Verify that Destroy was called
        self.app.Destroy.assert_called_once()

        # Verify that timer was stopped
        self.app.timer.Stop.assert_called_once()

        # alerts_timer has been removed in favor of unified update mechanism

        # Verify that taskbar_icon was removed and destroyed
        # Use the saved reference to avoid NoneType errors
        taskbar_icon.RemoveIcon.assert_called_once()
        taskbar_icon.Destroy.assert_called_once()

        # Verify that config was saved
        self.app._save_config.assert_called_once()

        # Restart the patcher for other tests
        self.onclose_patcher = patch.object(WeatherApp, "OnClose")
        self.mock_onclose = self.onclose_patcher.start()

    def test_minimize_to_tray_when_disabled(self):
        """Test that OnClose doesn't minimize to tray when minimize_to_tray is disabled."""
        # Stop the patcher to use the real method
        self.onclose_patcher.stop()

        # Set minimize_to_tray to False
        self.app.config["settings"][MINIMIZE_TO_TRAY_KEY] = False

        # Save a reference to the taskbar_icon before it might be set to None
        taskbar_icon = self.app.taskbar_icon

        # Call the real OnClose method
        WeatherApp.OnClose(self.app, self.event)

        # Verify that Hide was not called
        self.app.Hide.assert_not_called()

        # Verify that Veto was not called
        self.event.Veto.assert_not_called()

        # Verify that Skip was called to allow default close behavior
        self.event.Skip.assert_called_once()

        # Verify that Destroy was called
        self.app.Destroy.assert_called_once()

        # Verify that timer was stopped
        self.app.timer.Stop.assert_called_once()

        # alerts_timer has been removed in favor of unified update mechanism

        # Verify that taskbar_icon was removed and destroyed
        # Use the saved reference to avoid NoneType errors
        taskbar_icon.RemoveIcon.assert_called_once()
        taskbar_icon.Destroy.assert_called_once()

        # Verify that config was saved
        self.app._save_config.assert_called_once()

        # Restart the patcher for other tests
        self.onclose_patcher = patch.object(WeatherApp, "OnClose")
        self.mock_onclose = self.onclose_patcher.start()

    def test_error_handling(self):
        """Test that OnClose handles errors gracefully."""
        # Stop the patcher to use the real method
        self.onclose_patcher.stop()

        # Make _stop_fetcher_threads raise an exception
        self.app._stop_fetcher_threads.side_effect = Exception("Test exception")

        # Call the real OnClose method
        WeatherApp.OnClose(self.app, self.event)

        # Verify that Skip was called to allow default close behavior
        self.event.Skip.assert_called_once()

        # Verify that Destroy was called
        self.app.Destroy.assert_called_once()

        # Restart the patcher for other tests
        self.onclose_patcher = patch.object(WeatherApp, "OnClose")
        self.mock_onclose = self.onclose_patcher.start()

    def test_no_taskbar_icon(self):
        """Test that OnClose handles the case when there's no taskbar icon."""
        # Stop the patcher to use the real method
        self.onclose_patcher.stop()

        # Create a new app instance without taskbar_icon
        app = MagicMock(spec=WeatherApp)
        app.timer = MagicMock()
        app.timer.IsRunning.return_value = True
        # alerts_timer has been removed in favor of unified update mechanism
        app._save_config = MagicMock()
        app._stop_fetcher_threads = MagicMock()
        app.Hide = MagicMock()
        app.Destroy = MagicMock()
        app.config = {"settings": {MINIMIZE_TO_TRAY_KEY: True}}

        # No taskbar_icon attribute

        # Create a mock event
        event = MagicMock()
        event.Veto = MagicMock()
        event.Skip = MagicMock()

        # Call the real OnClose method
        WeatherApp.OnClose(app, event)

        # Verify that Hide was not called (since there's no taskbar icon)
        app.Hide.assert_not_called()

        # Verify that Veto was not called
        event.Veto.assert_not_called()

        # Verify that Skip was called to allow default close behavior
        event.Skip.assert_called_once()

        # Verify that Destroy was called
        app.Destroy.assert_called_once()

        # Verify that timer was stopped
        app.timer.Stop.assert_called_once()
        # alerts_timer has been removed in favor of unified update mechanism

        # Verify that config was saved
        app._save_config.assert_called_once()

        # Restart the patcher for other tests
        self.onclose_patcher = patch.object(WeatherApp, "OnClose")
        self.mock_onclose = self.onclose_patcher.start()
