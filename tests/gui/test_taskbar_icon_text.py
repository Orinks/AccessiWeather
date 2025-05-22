"""
Tests for the taskbar icon text functionality.
"""

import unittest
from unittest.mock import MagicMock, patch

import wx

from accessiweather.gui.settings_dialog import (
    TASKBAR_ICON_TEXT_ENABLED_KEY,
    TASKBAR_ICON_TEXT_FORMAT_KEY,
)
from accessiweather.gui.system_tray import TaskBarIcon


class TestTaskBarIconText(unittest.TestCase):
    """Test cases for the taskbar icon text functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock wx.App
        self.app = wx.App()

        # Create a mock frame
        self.frame = MagicMock()
        self.frame.config = {
            "settings": {
                TASKBAR_ICON_TEXT_ENABLED_KEY: True,
                TASKBAR_ICON_TEXT_FORMAT_KEY: "{temp}°F {condition}",
            }
        }

        # Create a test weather data dictionary
        self.weather_data = {
            "temp": 72.5,
            "temp_f": 72.5,
            "temp_c": 22.5,
            "condition": "Partly Cloudy",
            "humidity": 45,
            "wind_speed": 10,
            "wind_dir": "NW",
            "pressure": 29.92,
            "location": "New York",
        }

        # Create a TaskBarIcon instance with the mock frame
        with patch("wx.adv.TaskBarIcon"):
            self.taskbar_icon = TaskBarIcon(self.frame)
            self.taskbar_icon.SetIcon = MagicMock()

    def tearDown(self):
        """Clean up after tests."""
        # Destroy the wx.App
        self.app.Destroy()

    def test_update_weather_data(self):
        """Test updating weather data in the taskbar icon."""
        # Call update_weather_data
        self.taskbar_icon.update_weather_data(self.weather_data)

        # Verify that the weather data was stored
        self.assertEqual(self.taskbar_icon.current_weather_data, self.weather_data)

    def test_update_icon_text_enabled(self):
        """Test updating the taskbar icon text when enabled."""
        # Set up the taskbar icon with weather data
        self.taskbar_icon.current_weather_data = self.weather_data

        # Call update_icon_text
        self.taskbar_icon.update_icon_text()

        # Verify that SetIcon was called with the formatted text
        expected_text = "72.5°F Partly Cloudy"
        # Check that the second argument (tooltip text) matches our expected text
        self.assertEqual(self.taskbar_icon.SetIcon.call_args[0][1], expected_text)

    def test_update_icon_text_disabled(self):
        """Test updating the taskbar icon text when disabled."""
        # Set up the taskbar icon with weather data
        self.taskbar_icon.current_weather_data = self.weather_data

        # Disable taskbar icon text
        self.frame.config["settings"][TASKBAR_ICON_TEXT_ENABLED_KEY] = False

        # Call update_icon_text
        self.taskbar_icon.update_icon_text()

        # Verify that SetIcon was called with default text
        self.assertEqual(self.taskbar_icon.SetIcon.call_args[0][1], "AccessiWeather")

    def test_update_icon_text_no_weather_data(self):
        """Test updating the taskbar icon text when no weather data is available."""
        # Set up the taskbar icon with no weather data
        self.taskbar_icon.current_weather_data = {}

        # Call update_icon_text
        self.taskbar_icon.update_icon_text()

        # Verify that SetIcon was not called
        self.taskbar_icon.SetIcon.assert_not_called()

    def test_update_icon_text_custom_format(self):
        """Test updating the taskbar icon text with a custom format string."""
        # Set up the taskbar icon with weather data
        self.taskbar_icon.current_weather_data = self.weather_data

        # Set a custom format string - note: wind_speed now includes the unit
        self.frame.config["settings"][
            TASKBAR_ICON_TEXT_FORMAT_KEY
        ] = "{location}: {temp}°F, {wind_dir} {wind_speed}"

        # Call update_icon_text
        self.taskbar_icon.update_icon_text()

        # Verify that SetIcon was called with the formatted text
        expected_text = "New York: 72.5°F, NW 10.0 mph"
        # Check that the second argument (tooltip text) matches our expected text
        self.assertEqual(self.taskbar_icon.SetIcon.call_args[0][1], expected_text)


if __name__ == "__main__":
    unittest.main()
