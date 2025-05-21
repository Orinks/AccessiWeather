"""Tests for the Settings Dialog with Automatic weather source option."""

import unittest
from unittest.mock import patch

import wx

from accessiweather.gui.settings_dialog import DATA_SOURCE_AUTO, DATA_SOURCE_NWS, SettingsDialog


class TestSettingsDialogAuto(unittest.TestCase):
    """Tests for the Settings Dialog with Automatic weather source option."""

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
            "weatherapi": "",
            "minimize_on_startup": False,
            "minimize_to_tray": True,
            "cache_enabled": True,
            "cache_ttl": 300,
        }

    def tearDown(self):
        """Clean up after the test case."""
        self.frame.Destroy()
        self.app.Destroy()

    def test_auto_selection(self):
        """Test selecting Automatic as the data source."""
        # Start with NWS selected
        settings = self.current_settings.copy()
        settings["data_source"] = DATA_SOURCE_NWS
        dialog = SettingsDialog(self.frame, settings)
        self.assertEqual(dialog.data_source_ctrl.GetSelection(), 0)  # NWS selected

        # Switch to Automatic
        dialog.data_source_ctrl.SetSelection(2)  # Select Automatic
        dialog._on_data_source_changed(None)  # Simulate selection change

        # Both NWS and WeatherAPI fields should be enabled for Automatic
        self.assertTrue(dialog.api_contact_ctrl.IsEnabled())
        self.assertTrue(dialog.weatherapi_key_ctrl.IsEnabled())
        self.assertTrue(dialog.validate_key_btn.IsEnabled())
        self.assertTrue(dialog.signup_link.IsEnabled())

        dialog.Destroy()

    def test_load_auto_settings(self):
        """Test loading settings with Automatic data source."""
        # Set Automatic as the data source
        settings = self.current_settings.copy()
        settings["data_source"] = DATA_SOURCE_AUTO
        dialog = SettingsDialog(self.frame, settings)

        # Verify Automatic is selected
        self.assertEqual(dialog.data_source_ctrl.GetSelection(), 2)  # Automatic selected

        # Both NWS and WeatherAPI fields should be enabled
        self.assertTrue(dialog.api_contact_ctrl.IsEnabled())
        self.assertTrue(dialog.weatherapi_key_ctrl.IsEnabled())
        self.assertTrue(dialog.validate_key_btn.IsEnabled())
        self.assertTrue(dialog.signup_link.IsEnabled())

        dialog.Destroy()

    def test_get_settings_auto(self):
        """Test getting settings with Automatic data source."""
        dialog = SettingsDialog(self.frame, self.current_settings)

        # Select Automatic
        dialog.data_source_ctrl.SetSelection(2)  # Select Automatic

        # Set some values
        dialog.api_contact_ctrl.SetValue("auto_test@example.com")
        dialog.weatherapi_key_ctrl.SetValue("auto_test_key")

        # Get settings
        settings = dialog.get_settings()

        # Print settings for debugging
        print("Settings:", settings)

        # Verify data source is set to Automatic
        # The API contact and WeatherAPI key are handled separately in the dialog's _on_ok method
        # and are not directly included in the settings dictionary returned by get_settings
        self.assertEqual(settings["data_source"], DATA_SOURCE_AUTO)

        dialog.Destroy()

    def test_validate_auto_missing_weatherapi_key(self):
        """Test validation when Automatic is selected but WeatherAPI key is missing."""
        dialog = SettingsDialog(self.frame, self.current_settings)

        # Select Automatic
        dialog.data_source_ctrl.SetSelection(2)  # Select Automatic

        # Set NWS contact but leave WeatherAPI key empty
        dialog.api_contact_ctrl.SetValue("auto_test@example.com")
        dialog.weatherapi_key_ctrl.SetValue("")

        # Mock wx.MessageBox to capture the message
        with patch("wx.MessageBox") as mock_message_box:
            # Trigger validation
            dialog._on_ok(None)

            # Verify error message
            mock_message_box.assert_called_once()
            args = mock_message_box.call_args[0]  # Get positional arguments
            self.assertIn("WeatherAPI.com API key is required for the Automatic option", args[0])

        dialog.Destroy()
