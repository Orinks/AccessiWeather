"""Tests for the WeatherAppSystemHandlers.OnClose method."""

import unittest
from unittest.mock import MagicMock, patch

from accessiweather.gui.handlers.system_handlers import WeatherAppSystemHandlers


class TestWeatherAppSystemHandlersClose(unittest.TestCase):
    """Tests for the WeatherAppSystemHandlers.OnClose method."""

    def setUp(self):
        """Set up the test."""
        # Create a mock WeatherAppSystemHandlers instance
        self.handlers = MagicMock(spec=WeatherAppSystemHandlers)

        # Set up default attributes
        self.handlers.config = {"settings": {"minimize_to_tray": True}}
        self.handlers.timer = MagicMock()
        self.handlers._force_close = False

        # Set up the _stop_fetcher_threads method
        self.handlers._stop_fetcher_threads = MagicMock()

        # Set up the _save_config method
        self.handlers._save_config = MagicMock()

    def test_onclose_minimize_to_tray(self):
        """Test that OnClose minimizes to tray when minimize_to_tray is True."""
        # Create a mock event
        event = MagicMock()

        # Set up taskbar_icon
        self.handlers.taskbar_icon = MagicMock()

        # Call the method under test
        with patch("accessiweather.gui.handlers.system_handlers.logger"):
            result = WeatherAppSystemHandlers.OnClose(self.handlers, event)

        # Verify that the window was hidden
        self.handlers.Hide.assert_called_once()

        # Verify that the timer was stopped and restarted
        self.handlers.timer.Stop.assert_called_once()
        self.handlers.timer.Start.assert_called_once()

        # Verify that the event was vetoed
        event.Veto.assert_called_once()

        # Verify that the method returned True
        self.assertTrue(result)

        # Verify that _stop_fetcher_threads was not called
        self.handlers._stop_fetcher_threads.assert_not_called()

    def test_onclose_force_close(self):
        """Test that OnClose forces close when force_close is True."""
        # Create a mock event
        event = MagicMock()

        # Set force_close to True
        self.handlers._force_close = True

        # Call the method under test
        with patch("accessiweather.gui.handlers.system_handlers.logger"):
            result = WeatherAppSystemHandlers.OnClose(self.handlers, event)

        # Verify that the window was not hidden
        self.handlers.Hide.assert_not_called()

        # Verify that _stop_fetcher_threads was called
        self.handlers._stop_fetcher_threads.assert_called_once()

        # Verify that _save_config was called
        self.handlers._save_config.assert_called_once_with(show_errors=False)

        # Verify that the event was not vetoed
        event.Veto.assert_not_called()

        # Verify that event.Skip() was called
        event.Skip.assert_called_once()

        # Verify that the method returned True
        self.assertTrue(result)

    def test_onclose_no_minimize_to_tray(self):
        """Test that OnClose forces close when minimize_to_tray is False."""
        # Create a mock event
        event = MagicMock()

        # Set minimize_to_tray to False
        self.handlers.config = {"settings": {"minimize_to_tray": False}}

        # Call the method under test
        with patch("accessiweather.gui.handlers.system_handlers.logger"):
            result = WeatherAppSystemHandlers.OnClose(self.handlers, event)

        # Verify that the window was not hidden
        self.handlers.Hide.assert_not_called()

        # Verify that _stop_fetcher_threads was called
        self.handlers._stop_fetcher_threads.assert_called_once()

        # Verify that _save_config was called
        self.handlers._save_config.assert_called_once_with(show_errors=False)

        # Verify that the event was not vetoed
        event.Veto.assert_not_called()

        # Verify that event.Skip() was called
        event.Skip.assert_called_once()

        # Verify that the method returned True
        self.assertTrue(result)

    def test_onclose_no_taskbar_icon(self):
        """Test that OnClose handles the case when there's no taskbar icon."""
        # Create a mock event
        event = MagicMock()

        # Set taskbar_icon to None
        self.handlers.taskbar_icon = None

        # Call the method under test
        with patch("accessiweather.gui.handlers.system_handlers.logger"):
            result = WeatherAppSystemHandlers.OnClose(self.handlers, event)

        # Verify that _stop_fetcher_threads was called
        self.handlers._stop_fetcher_threads.assert_called_once()

        # Verify that _save_config was called
        self.handlers._save_config.assert_called_once_with(show_errors=False)

        # Verify that the event was not vetoed
        event.Veto.assert_not_called()

        # Verify that event.Skip() was called
        event.Skip.assert_called_once()

        # Verify that the method returned True
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
