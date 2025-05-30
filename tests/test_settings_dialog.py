"""Tests for the settings dialog."""

import unittest
from unittest.mock import MagicMock, patch

import wx

from accessiweather.gui.settings_dialog import (
    API_CONTACT_KEY,
    DATA_SOURCE_KEY,
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


class TestSettingsDialog(unittest.TestCase):
    """Tests for the settings dialog."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = wx.App()
        self.frame = wx.Frame(None)
        self.current_settings = {
            API_CONTACT_KEY: "test@example.com",
            DATA_SOURCE_KEY: DATA_SOURCE_NWS,
            OPENWEATHERMAP_KEY: "",
        }

    def tearDown(self):
        """Tear down test fixtures."""
        self.frame.Destroy()
        self.app.Destroy()

    def test_init(self):
        """Test initialization of the settings dialog."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        self.assertEqual(dialog.data_source_ctrl.GetSelection(), 0)  # NWS selected
        self.assertEqual(dialog.api_contact_ctrl.GetValue(), "test@example.com")
        self.assertEqual(dialog.openweathermap_key_ctrl.GetValue(), "")
        self.assertTrue(dialog.api_contact_ctrl.IsEnabled())
        self.assertFalse(dialog.openweathermap_key_ctrl.IsEnabled())
        self.assertFalse(dialog.signup_link.IsEnabled())
        dialog.Destroy()

    def test_openweathermap_selection(self):
        """Test selecting OpenWeatherMap as the data source."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        dialog.data_source_ctrl.SetSelection(1)  # Select OpenWeatherMap
        dialog._on_data_source_changed(None)  # Simulate selection change
        self.assertFalse(dialog.api_contact_ctrl.IsEnabled())
        self.assertTrue(dialog.openweathermap_key_ctrl.IsEnabled())
        self.assertTrue(dialog.signup_link.IsEnabled())
        dialog.Destroy()

    def test_nws_selection(self):
        """Test selecting NWS as the data source."""
        # Start with OpenWeatherMap selected
        settings = self.current_settings.copy()
        settings[DATA_SOURCE_KEY] = DATA_SOURCE_OPENWEATHERMAP
        dialog = SettingsDialog(self.frame, settings)
        self.assertEqual(dialog.data_source_ctrl.GetSelection(), 1)  # OpenWeatherMap selected

        # Switch to NWS
        dialog.data_source_ctrl.SetSelection(0)  # Select NWS
        dialog._on_data_source_changed(None)  # Simulate selection change
        self.assertTrue(dialog.api_contact_ctrl.IsEnabled())
        self.assertFalse(dialog.openweathermap_key_ctrl.IsEnabled())
        self.assertFalse(dialog.signup_link.IsEnabled())
        dialog.Destroy()

    def test_validation_openweathermap_no_key(self):
        """Test validation when OpenWeatherMap is selected but no key is provided."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        dialog.data_source_ctrl.SetSelection(1)  # Select OpenWeatherMap
        dialog._on_data_source_changed(None)  # Simulate selection change

        # Mock wx.MessageBox to avoid actual dialog
        with patch("wx.MessageBox", return_value=wx.OK):
            dialog._on_ok(None)
            # Dialog should not close (EndModal not called)
            wx.MessageBox.assert_called_once()
        dialog.Destroy()

    def test_validation_openweathermap_with_key(self):
        """Test validation when OpenWeatherMap is selected and key is provided."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        dialog.data_source_ctrl.SetSelection(1)  # Select OpenWeatherMap
        dialog._on_data_source_changed(None)  # Simulate selection change
        dialog.openweathermap_key_ctrl.SetValue("a1b2c3d4e5f6789012345678901234ab")

        # Mock EndModal to avoid actual dialog closing
        with patch.object(dialog, "EndModal") as mock_end_modal:
            dialog._on_ok(None)
            # Dialog should close with OK result
            mock_end_modal.assert_called_once_with(wx.ID_OK)
        dialog.Destroy()

    def test_get_api_keys(self):
        """Test getting API keys from the dialog."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        dialog.openweathermap_key_ctrl.SetValue("a1b2c3d4e5f6789012345678901234ab")
        api_keys = dialog.get_api_keys()
        self.assertEqual(api_keys[OPENWEATHERMAP_KEY], "a1b2c3d4e5f6789012345678901234ab")
        dialog.Destroy()

    @patch("httpx.Client")
    def test_validate_openweathermap_key_valid(self, mock_client):
        """Test validating a valid OpenWeatherMap key."""
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

        # Verify the request was made correctly
        mock_client_instance.get.assert_called_once()
        args, kwargs = mock_client_instance.get.call_args
        self.assertEqual(args[0], "https://api.openweathermap.org/data/2.5/weather")
        self.assertEqual(kwargs["params"]["appid"], "a1b2c3d4e5f6789012345678901234ab")
        self.assertEqual(kwargs["params"]["q"], "London")

        dialog.Destroy()

    @patch("httpx.Client")
    def test_validate_openweathermap_key_invalid(self, mock_client):
        """Test validating an invalid OpenWeatherMap key."""
        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"cod": 401, "message": "Invalid API key"}

        # Set up mock client
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        # Create dialog and test validation
        dialog = SettingsDialog(self.frame, self.current_settings)
        is_valid, message = dialog._validate_openweathermap_key("a1b2c3d4e5f6789012345678901234ab")

        # Check results
        self.assertFalse(is_valid)
        self.assertTrue("Authentication error" in message)

        dialog.Destroy()

    @patch("accessiweather.gui.settings_dialog.SettingsDialog._validate_openweathermap_key")
    def test_on_validate_key_button(self, mock_validate):
        """Test the validate button click handler."""
        # Set up mock validation result
        mock_validate.return_value = (True, "API key is valid")

        # Create dialog and set up test
        dialog = SettingsDialog(self.frame, self.current_settings)
        dialog.data_source_ctrl.SetSelection(1)  # Select OpenWeatherMap
        dialog._on_data_source_changed(None)  # Update UI
        dialog.openweathermap_key_ctrl.SetValue("a1b2c3d4e5f6789012345678901234ab")

        # Mock wx.MessageBox to avoid actual dialog
        with patch("wx.MessageBox") as mock_message_box:
            # Simulate button click
            dialog._on_validate_key(None)

            # Verify validation was called
            mock_validate.assert_called_once_with("a1b2c3d4e5f6789012345678901234ab")

            # Verify message box was shown
            mock_message_box.assert_called_once()
            args, _ = mock_message_box.call_args
            self.assertTrue("Success" in args[0])

        dialog.Destroy()


if __name__ == "__main__":
    unittest.main()
