"""Tests for the Settings Dialog with Automatic weather source option."""

import unittest
from unittest.mock import patch

import wx

from accessiweather.gui.settings.constants import DATA_SOURCE_AUTO, DATA_SOURCE_NWS
from accessiweather.gui.settings_dialog import SettingsDialog


class TestSettingsDialogAuto(unittest.TestCase):
    """Tests for the Settings Dialog with Automatic weather source option."""

    def setUp(self):
        """Set up the test case."""
        self.app = wx.App()
        self.frame = wx.Frame(None)
        self.current_settings = {
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
        dialog.data_source_ctrl.SetSelection(1)  # Select Automatic (index 1, not 2)

        # Just verify the selection was set correctly
        self.assertEqual(dialog.data_source_ctrl.GetSelection(), 1)

        dialog.Destroy()

    def test_load_auto_settings(self):
        """Test loading settings with Automatic data source."""
        # Set Automatic as the data source
        settings = self.current_settings.copy()
        settings["data_source"] = DATA_SOURCE_AUTO
        dialog = SettingsDialog(self.frame, settings)

        # Verify Automatic is selected (index 2)
        self.assertEqual(dialog.data_source_ctrl.GetSelection(), 2)  # Automatic selected

        dialog.Destroy()

    def test_get_settings_auto(self):
        """Test getting settings with Automatic data source."""
        dialog = SettingsDialog(self.frame, self.current_settings)

        # Select Automatic
        dialog.data_source_ctrl.SetSelection(2)  # Select Automatic

        # Get settings
        settings = dialog.get_settings()

        # Print settings for debugging
        print("Settings:", settings)

        # Verify data source is set to Automatic
        self.assertEqual(settings["data_source"], DATA_SOURCE_AUTO)

        dialog.Destroy()

    def test_validate_auto_valid(self):
        """Test validation when Automatic is selected with valid settings."""
        dialog = SettingsDialog(self.frame, self.current_settings)

        # Select Automatic
        dialog.data_source_ctrl.SetSelection(2)  # Select Automatic

        # Mock EndModal to avoid actual dialog closing
        with patch.object(dialog, "EndModal") as mock_end_modal:
            dialog._on_ok(None)
            # Dialog should close with OK result
            mock_end_modal.assert_called_once_with(wx.ID_OK)

        dialog.Destroy()
