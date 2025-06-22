"""Tests for the taskbar icon text functionality."""

import unittest
from unittest.mock import MagicMock, patch

import wx

from accessiweather.gui.settings.constants import (
    TASKBAR_ICON_DYNAMIC_ENABLED_KEY,
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
                TASKBAR_ICON_TEXT_FORMAT_KEY: "{location} {temp} {condition}",
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
        with (
            patch(
                "accessiweather.gui.system_tray_modules.wx.adv.TaskBarIcon.__init__",
                return_value=None,
            ),
            patch(
                "accessiweather.gui.system_tray_modules.icon_manager.TaskBarIconManager.__init__",
                return_value=None,
            ),
            patch("accessiweather.gui.system_tray.TaskBarIcon.set_icon"),
            patch("accessiweather.gui.system_tray.TaskBarIcon.bind_events"),
        ):
            self.taskbar_icon = TaskBarIcon(self.frame)
            # Use patch.object to properly mock the SetIcon method
            self.set_icon_patcher = patch.object(self.taskbar_icon, "SetIcon")
            self.mock_set_icon = self.set_icon_patcher.start()
            self.addCleanup(self.set_icon_patcher.stop)

            # Initialize the weather formatter attributes that would normally be set by __init__
            from accessiweather.dynamic_format_manager import DynamicFormatManager
            from accessiweather.format_string_parser import FormatStringParser

            self.taskbar_icon.format_parser = FormatStringParser()
            self.taskbar_icon.dynamic_format_manager = DynamicFormatManager()
            self.taskbar_icon.current_weather_data = {}
            self.taskbar_icon.current_alerts_data = None

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

    @patch("wx.ArtProvider.GetIcon")
    @patch("wx.Icon")
    def test_update_icon_text_enabled(self, mock_icon, mock_get_icon):
        """Test updating the taskbar icon text when enabled."""
        # Mock the icon creation to avoid wx.App issues
        mock_get_icon.return_value = MagicMock()
        mock_icon.return_value = MagicMock()

        # Set up the taskbar icon with weather data
        self.taskbar_icon.current_weather_data = self.weather_data

        # Call update_icon_text
        self.taskbar_icon.update_icon_text()

        # Verify that SetIcon was called with the formatted text
        # Test data has temp: 72.5°F which is not a whole number, so decimal is preserved
        # New enhanced format includes humidity
        expected_text = "New York 72.5°F Partly Cloudy • 45%"
        # Check that the second argument (tooltip text) matches our expected text
        self.assertEqual(self.mock_set_icon.call_args[0][1], expected_text)

    @patch("wx.ArtProvider.GetIcon")
    @patch("wx.Icon")
    def test_update_icon_text_disabled(self, mock_icon, mock_get_icon):
        """Test updating the taskbar icon text when disabled."""
        # Mock the icon creation to avoid wx.App issues
        mock_get_icon.return_value = MagicMock()
        mock_icon.return_value = MagicMock()

        # Set up the taskbar icon with weather data
        self.taskbar_icon.current_weather_data = self.weather_data

        # Disable taskbar icon text
        self.frame.config["settings"][TASKBAR_ICON_TEXT_ENABLED_KEY] = False

        # Call update_icon_text
        self.taskbar_icon.update_icon_text()

        # Verify that SetIcon was called with default text
        self.assertEqual(self.mock_set_icon.call_args[0][1], "AccessiWeather")

    def test_update_icon_text_no_weather_data(self):
        """Test updating the taskbar icon text when no weather data is available."""
        # Set up the taskbar icon with no weather data
        self.taskbar_icon.current_weather_data = {}

        # Call update_icon_text
        self.taskbar_icon.update_icon_text()

        # Verify that SetIcon was not called
        self.mock_set_icon.assert_not_called()

    @patch("wx.ArtProvider.GetIcon")
    @patch("wx.Icon")
    def test_update_icon_text_custom_format(self, mock_icon, mock_get_icon):
        """Test updating the taskbar icon text with a custom format string."""
        # Mock the icon creation to avoid wx.App issues
        mock_get_icon.return_value = MagicMock()
        mock_icon.return_value = MagicMock()

        # Set up the taskbar icon with weather data
        self.taskbar_icon.current_weather_data = self.weather_data

        # Set a custom format string - note: wind_speed now includes the unit
        self.frame.config["settings"][TASKBAR_ICON_TEXT_FORMAT_KEY] = (
            "{location}: {temp}, {wind_dir} {wind_speed}"
        )

        # Disable dynamic formatting to use the custom format string
        self.frame.config["settings"][TASKBAR_ICON_DYNAMIC_ENABLED_KEY] = False

        # Call update_icon_text
        self.taskbar_icon.update_icon_text()

        # Verify that SetIcon was called with the formatted text
        # Test data has temp: 72.5°F which is not a whole number, so decimal is preserved
        expected_text = "New York: 72.5°F, NW 10.0 mph"
        # Check that the second argument (tooltip text) matches our expected text
        self.assertEqual(self.mock_set_icon.call_args[0][1], expected_text)


if __name__ == "__main__":
    unittest.main()
