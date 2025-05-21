"""Tests for the settings dialog."""

import unittest
from unittest.mock import MagicMock, patch

import wx

from accessiweather.gui.settings_dialog import (
    API_CONTACT_KEY,
    DATA_SOURCE_KEY,
    DATA_SOURCE_NWS,
    DATA_SOURCE_WEATHERAPI,
    WEATHERAPI_KEY,
    SettingsDialog,
)

# Mock response for API key validation
MOCK_VALID_RESPONSE = {
    "location": {"name": "London", "region": "City of London", "country": "UK"},
    "current": {
        "temp_c": 15,
        "condition": {
            "text": "Partly cloudy",
            "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png",
        },
    },
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
            WEATHERAPI_KEY: "",
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
        self.assertEqual(dialog.weatherapi_key_ctrl.GetValue(), "")
        self.assertTrue(dialog.api_contact_ctrl.IsEnabled())
        self.assertFalse(dialog.weatherapi_key_ctrl.IsEnabled())
        self.assertFalse(dialog.signup_link.IsEnabled())
        dialog.Destroy()

    def test_weatherapi_selection(self):
        """Test selecting WeatherAPI.com as the data source."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        dialog.data_source_ctrl.SetSelection(1)  # Select WeatherAPI.com
        dialog._on_data_source_changed(None)  # Simulate selection change
        self.assertFalse(dialog.api_contact_ctrl.IsEnabled())
        self.assertTrue(dialog.weatherapi_key_ctrl.IsEnabled())
        self.assertTrue(dialog.signup_link.IsEnabled())
        dialog.Destroy()

    def test_nws_selection(self):
        """Test selecting NWS as the data source."""
        # Start with WeatherAPI selected
        settings = self.current_settings.copy()
        settings[DATA_SOURCE_KEY] = DATA_SOURCE_WEATHERAPI
        dialog = SettingsDialog(self.frame, settings)
        self.assertEqual(dialog.data_source_ctrl.GetSelection(), 1)  # WeatherAPI selected

        # Switch to NWS
        dialog.data_source_ctrl.SetSelection(0)  # Select NWS
        dialog._on_data_source_changed(None)  # Simulate selection change
        self.assertTrue(dialog.api_contact_ctrl.IsEnabled())
        self.assertFalse(dialog.weatherapi_key_ctrl.IsEnabled())
        self.assertFalse(dialog.signup_link.IsEnabled())
        dialog.Destroy()

    def test_validation_weatherapi_no_key(self):
        """Test validation when WeatherAPI is selected but no key is provided."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        dialog.data_source_ctrl.SetSelection(1)  # Select WeatherAPI.com
        dialog._on_data_source_changed(None)  # Simulate selection change

        # Mock wx.MessageBox to avoid actual dialog
        with patch("wx.MessageBox", return_value=wx.OK):
            dialog._on_ok(None)
            # Dialog should not close (EndModal not called)
            wx.MessageBox.assert_called_once()
        dialog.Destroy()

    def test_validation_weatherapi_with_key(self):
        """Test validation when WeatherAPI is selected and key is provided."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        dialog.data_source_ctrl.SetSelection(1)  # Select WeatherAPI.com
        dialog._on_data_source_changed(None)  # Simulate selection change
        dialog.weatherapi_key_ctrl.SetValue("test_api_key")

        # Mock EndModal to avoid actual dialog closing
        with patch.object(dialog, "EndModal") as mock_end_modal:
            dialog._on_ok(None)
            # Dialog should close with OK result
            mock_end_modal.assert_called_once_with(wx.ID_OK)
        dialog.Destroy()

    def test_get_api_keys(self):
        """Test getting API keys from the dialog."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        dialog.weatherapi_key_ctrl.SetValue("test_api_key")
        api_keys = dialog.get_api_keys()
        self.assertEqual(api_keys[WEATHERAPI_KEY], "test_api_key")
        dialog.Destroy()

    @patch("httpx.Client")
    def test_validate_weatherapi_key_valid(self, mock_client):
        """Test validating a valid WeatherAPI key."""
        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_VALID_RESPONSE

        # Set up mock client
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        # Create dialog and test validation
        dialog = SettingsDialog(self.frame, self.current_settings)
        is_valid, message = dialog._validate_weatherapi_key("test_api_key")

        # Check results
        self.assertTrue(is_valid)
        self.assertEqual(message, "API key is valid")

        # Verify the request was made correctly
        mock_client_instance.get.assert_called_once()
        args, kwargs = mock_client_instance.get.call_args
        self.assertEqual(args[0], "https://api.weatherapi.com/v1/current.json")
        self.assertEqual(kwargs["params"]["key"], "test_api_key")
        self.assertEqual(kwargs["params"]["q"], "London")

        dialog.Destroy()

    @patch("httpx.Client")
    def test_validate_weatherapi_key_invalid(self, mock_client):
        """Test validating an invalid WeatherAPI key."""
        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": {"code": 1002, "message": "API key not provided."}
        }

        # Set up mock client
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        # Create dialog and test validation
        dialog = SettingsDialog(self.frame, self.current_settings)
        is_valid, message = dialog._validate_weatherapi_key("invalid_key")

        # Check results
        self.assertFalse(is_valid)
        self.assertTrue("Authentication error" in message)

        dialog.Destroy()

    @patch("accessiweather.gui.settings_dialog.SettingsDialog._validate_weatherapi_key")
    def test_on_validate_key_button(self, mock_validate):
        """Test the validate button click handler."""
        # Set up mock validation result
        mock_validate.return_value = (True, "API key is valid")

        # Create dialog and set up test
        dialog = SettingsDialog(self.frame, self.current_settings)
        dialog.data_source_ctrl.SetSelection(1)  # Select WeatherAPI.com
        dialog._on_data_source_changed(None)  # Update UI
        dialog.weatherapi_key_ctrl.SetValue("test_api_key")

        # Mock wx.MessageBox to avoid actual dialog
        with patch("wx.MessageBox") as mock_message_box:
            # Simulate button click
            dialog._on_validate_key(None)

            # Verify validation was called
            mock_validate.assert_called_once_with("test_api_key")

            # Verify message box was shown
            mock_message_box.assert_called_once()
            args, kwargs = mock_message_box.call_args
            self.assertTrue("Success" in args[0])

        dialog.Destroy()


if __name__ == "__main__":
    unittest.main()
