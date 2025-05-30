"""Tests for OpenWeatherMap configuration schema changes."""

import unittest
from unittest.mock import MagicMock, patch

import wx

from accessiweather.gui.settings_dialog import (
    DATA_SOURCE_NWS,
    DATA_SOURCE_OPENWEATHERMAP,
    OPENWEATHERMAP_KEY,
    SettingsDialog,
)

# Mock response for OpenWeatherMap API key validation
MOCK_VALID_OWM_RESPONSE = {
    "coord": {"lon": -0.1257, "lat": 51.5085},
    "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
    "main": {"temp": 15.0, "feels_like": 14.5, "temp_min": 12.0, "temp_max": 18.0},
    "name": "London",
}


class TestOpenWeatherMapConfiguration(unittest.TestCase):
    """Tests for OpenWeatherMap configuration schema changes."""

    def setUp(self):
        """Set up the test case."""
        self.app = wx.App()
        self.frame = wx.Frame(None)
        self.current_settings = {
            "api_contact": "test@example.com",
            "update_interval": 15,
            "alert_radius": 25,
            "precise_location_alerts": True,
            "show_nationwide_location": True,
            "auto_refresh_national": True,
            "data_source": DATA_SOURCE_NWS,
            "openweathermap": "",
            "minimize_on_startup": False,
            "minimize_to_tray": True,
            "cache_enabled": True,
            "cache_ttl": 300,
        }

    def tearDown(self):
        """Clean up after the test case."""
        self.frame.Destroy()
        self.app.Destroy()

    def test_openweathermap_constants_exist(self):
        """Test that OpenWeatherMap constants are defined."""
        # These should exist after migration from WeatherAPI
        self.assertEqual(DATA_SOURCE_OPENWEATHERMAP, "openweathermap")
        self.assertEqual(OPENWEATHERMAP_KEY, "openweathermap")

    def test_data_source_options_include_openweathermap(self):
        """Test that data source options include OpenWeatherMap."""
        dialog = SettingsDialog(self.frame, self.current_settings)

        # Check that OpenWeatherMap is available as an option
        choices = [
            dialog.data_source_ctrl.GetString(i) for i in range(dialog.data_source_ctrl.GetCount())
        ]
        self.assertIn("OpenWeatherMap", choices)
        self.assertNotIn("WeatherAPI.com", choices)  # Should be removed

        dialog.Destroy()

    def test_openweathermap_selection_enables_key_field(self):
        """Test selecting OpenWeatherMap enables the API key field."""
        dialog = SettingsDialog(self.frame, self.current_settings)

        # Find OpenWeatherMap option index
        owm_index = None
        for i in range(dialog.data_source_ctrl.GetCount()):
            if "OpenWeatherMap" in dialog.data_source_ctrl.GetString(i):
                owm_index = i
                break

        self.assertIsNotNone(owm_index, "OpenWeatherMap option not found")

        # Select OpenWeatherMap
        dialog.data_source_ctrl.SetSelection(owm_index)
        dialog._on_data_source_changed(None)

        # Check that OpenWeatherMap key field is enabled
        self.assertTrue(dialog.openweathermap_key_ctrl.IsEnabled())
        self.assertFalse(dialog.api_contact_ctrl.IsEnabled())
        self.assertTrue(dialog.validate_key_btn.IsEnabled())

        dialog.Destroy()

    def test_openweathermap_api_key_validation_format(self):
        """Test OpenWeatherMap API key format validation (32-char hex)."""
        dialog = SettingsDialog(self.frame, self.current_settings)

        # Test valid 32-character hexadecimal string
        valid_key = "a1b2c3d4e5f6789012345678901234ab"
        self.assertTrue(dialog._is_valid_openweathermap_key_format(valid_key))

        # Test invalid formats
        invalid_keys = [
            "",  # Empty
            "short",  # Too short
            "a1b2c3d4e5f6789012345678901234abcd",  # Too long (33 chars)
            "g1b2c3d4e5f6789012345678901234ab",  # Invalid hex character 'g'
            "A1B2C3D4E5F6789012345678901234AB",  # Uppercase (should be lowercase)
            "a1b2c3d4-e5f6-7890-1234-5678901234ab",  # Contains hyphens
        ]

        for invalid_key in invalid_keys:
            with self.subTest(key=invalid_key):
                self.assertFalse(dialog._is_valid_openweathermap_key_format(invalid_key))

        dialog.Destroy()

    @patch("httpx.Client")
    def test_validate_openweathermap_key_valid(self, mock_client):
        """Test validating a valid OpenWeatherMap API key."""
        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_VALID_OWM_RESPONSE

        # Set up mock client
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        # Create dialog and test validation
        dialog = SettingsDialog(self.frame, self.current_settings)
        is_valid, message = dialog._validate_openweathermap_key("a1b2c3d4e5f6789012345678901234ab")

        # Check results
        self.assertTrue(is_valid)
        self.assertEqual(message, "API key is valid")

        # Verify the correct OpenWeatherMap endpoint was called
        mock_client_instance.get.assert_called_once()
        call_args = mock_client_instance.get.call_args
        self.assertIn("api.openweathermap.org", call_args[0][0])

        dialog.Destroy()

    def test_validate_openweathermap_key_invalid_format(self):
        """Test validating an invalid OpenWeatherMap API key format."""
        # Create dialog and test validation with invalid format
        dialog = SettingsDialog(self.frame, self.current_settings)
        is_valid, message = dialog._validate_openweathermap_key("invalid_key_format")

        # Check results - should fail format validation before API call
        self.assertFalse(is_valid)
        self.assertIn("32-character hexadecimal string", message)

        dialog.Destroy()

    @patch("httpx.Client")
    def test_validate_openweathermap_key_invalid_api_response(self, mock_client):
        """Test validating a properly formatted but invalid OpenWeatherMap API key."""
        # Set up mock response for 401 Unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"cod": 401, "message": "Invalid API key"}

        # Set up mock client
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        # Create dialog and test validation with properly formatted but invalid key
        dialog = SettingsDialog(self.frame, self.current_settings)
        is_valid, message = dialog._validate_openweathermap_key("a1b2c3d4e5f6789012345678901234ab")

        # Check results
        self.assertFalse(is_valid)
        self.assertIn("Invalid API key", message)

        dialog.Destroy()

    def test_openweathermap_signup_link_updated(self):
        """Test that signup link points to OpenWeatherMap."""
        dialog = SettingsDialog(self.frame, self.current_settings)

        # Check that signup link points to OpenWeatherMap
        signup_url = dialog.signup_link.GetURL()
        self.assertIn("openweathermap.org", signup_url.lower())
        self.assertNotIn("weatherapi.com", signup_url.lower())

        dialog.Destroy()

    def test_validation_openweathermap_no_key(self):
        """Test validation when OpenWeatherMap is selected but no key is provided."""
        dialog = SettingsDialog(self.frame, self.current_settings)

        # Find and select OpenWeatherMap option
        owm_index = None
        for i in range(dialog.data_source_ctrl.GetCount()):
            if "OpenWeatherMap" in dialog.data_source_ctrl.GetString(i):
                owm_index = i
                break

        dialog.data_source_ctrl.SetSelection(owm_index)
        dialog._on_data_source_changed(None)

        # Mock wx.MessageBox to avoid actual dialog
        with patch("wx.MessageBox", return_value=wx.OK):
            dialog._on_ok(None)
            # Dialog should not close (EndModal not called)
            wx.MessageBox.assert_called_once()

        dialog.Destroy()

    def test_automatic_option_requires_openweathermap_key(self):
        """Test that Automatic option requires OpenWeatherMap key for non-US locations."""
        dialog = SettingsDialog(self.frame, self.current_settings)

        # Find and select Automatic option
        auto_index = None
        for i in range(dialog.data_source_ctrl.GetCount()):
            if "Automatic" in dialog.data_source_ctrl.GetString(i):
                auto_index = i
                break

        dialog.data_source_ctrl.SetSelection(auto_index)
        dialog._on_data_source_changed(None)

        # Both fields should be enabled for Automatic
        self.assertTrue(dialog.api_contact_ctrl.IsEnabled())
        self.assertTrue(dialog.openweathermap_key_ctrl.IsEnabled())

        # Test validation without OpenWeatherMap key
        dialog.api_contact_ctrl.SetValue("test@example.com")
        dialog.openweathermap_key_ctrl.SetValue("")

        with patch("wx.MessageBox", return_value=wx.OK):
            dialog._on_ok(None)
            wx.MessageBox.assert_called_once()
            call_args = wx.MessageBox.call_args[0]
            self.assertIn("OpenWeatherMap", call_args[0])

        dialog.Destroy()


if __name__ == "__main__":
    unittest.main()
