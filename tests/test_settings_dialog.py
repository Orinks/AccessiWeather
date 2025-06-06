"""Tests for the settings dialog."""

import unittest
from unittest.mock import patch

import wx

from accessiweather.gui.settings_dialog import (
    DATA_SOURCE_AUTO,
    DATA_SOURCE_KEY,
    DATA_SOURCE_NWS,
    SettingsDialog,
)


class TestSettingsDialog(unittest.TestCase):
    """Tests for the settings dialog."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = wx.App()
        self.frame = wx.Frame(None)
        self.current_settings = {
            DATA_SOURCE_KEY: DATA_SOURCE_NWS,
        }

    def tearDown(self):
        """Tear down test fixtures."""
        self.frame.Destroy()
        self.app.Destroy()

    def test_init(self):
        """Test initialization of the settings dialog."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        self.assertEqual(dialog.data_source_ctrl.GetSelection(), 0)  # NWS selected
        dialog.Destroy()

    def test_auto_selection(self):
        """Test selecting Automatic as the data source."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        dialog.data_source_ctrl.SetSelection(1)  # Select Automatic
        # Just verify the selection was set correctly
        self.assertEqual(dialog.data_source_ctrl.GetSelection(), 1)
        dialog.Destroy()

    def test_nws_selection(self):
        """Test selecting NWS as the data source."""
        # Start with Automatic selected
        settings = self.current_settings.copy()
        settings[DATA_SOURCE_KEY] = DATA_SOURCE_AUTO
        dialog = SettingsDialog(self.frame, settings)
        self.assertEqual(dialog.data_source_ctrl.GetSelection(), 2)  # Automatic selected

        # Switch to NWS
        dialog.data_source_ctrl.SetSelection(0)  # Select NWS
        # Just verify the selection was set correctly
        self.assertEqual(dialog.data_source_ctrl.GetSelection(), 0)
        dialog.Destroy()

    def test_validation_nws_valid(self):
        """Test validation when NWS is selected with valid settings."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        dialog.data_source_ctrl.SetSelection(0)  # Select NWS

        # Mock EndModal to avoid actual dialog closing
        with patch.object(dialog, "EndModal") as mock_end_modal:
            dialog._on_ok(None)
            # Dialog should close with OK result
            mock_end_modal.assert_called_once_with(wx.ID_OK)
        dialog.Destroy()

    def test_get_api_keys(self):
        """Test getting API keys from the dialog."""
        dialog = SettingsDialog(self.frame, self.current_settings)
        api_keys = dialog.get_api_keys()
        # Currently returns empty dict since no API keys are configured in UI
        self.assertEqual(api_keys, {})
        dialog.Destroy()


if __name__ == "__main__":
    unittest.main()
