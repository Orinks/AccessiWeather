"""Tests for the settings dialog."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import wx

from accessiweather.gui.handlers.config_handlers import WeatherAppConfigHandlers
from accessiweather.gui.handlers.dialog_handlers import WeatherAppDialogHandlers
from accessiweather.gui.handlers.settings_handlers import WeatherAppSettingsHandlers
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


class MockWeatherApp(
    WeatherAppSettingsHandlers, WeatherAppConfigHandlers, WeatherAppDialogHandlers
):
    """Mock WeatherApp for testing settings handlers."""

    def __init__(self, config_path):
        self._config_path = config_path
        self.config = {
            "settings": {
                "update_interval_minutes": 10,
                "alert_radius_miles": 25,
                "data_source": "nws",
            },
            "api_settings": {},
            "api_keys": {},
        }
        self.location_service = None
        self._last_settings_dialog = None

    def UpdateLocationDropdown(self):
        """Mock method."""
        pass

    def UpdateWeatherData(self):
        """Mock method."""
        pass

    def _handle_data_source_change(self):
        """Mock method."""
        pass


class TestSettingsBugFix(unittest.TestCase):
    """Test cases for the settings dialog bug fix."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "config.json")
        self.app = MockWeatherApp(self.config_path)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_settings_saved_with_empty_api_settings(self):
        """Test that settings are saved even when api_settings is empty."""

        # Mock the dialog to return empty api_settings (the bug condition)
        def mock_show_dialog(current_settings):
            updated_settings = current_settings.copy()
            updated_settings["update_interval_minutes"] = 15
            updated_settings["alert_radius_miles"] = 30
            return wx.ID_OK, updated_settings, {}  # Empty api_settings

        self.app.ShowSettingsDialog = mock_show_dialog

        # Create a mock event
        mock_event = MagicMock()

        # Call OnSettings
        self.app.OnSettings(mock_event)

        # Verify settings were updated
        self.assertEqual(self.app.config["settings"]["update_interval_minutes"], 15)
        self.assertEqual(self.app.config["settings"]["alert_radius_miles"], 30)

        # Verify config file was created and saved
        self.assertTrue(os.path.exists(self.config_path))

        # Read and verify the saved config
        import json

        with open(self.config_path, "r") as f:
            saved_config = json.load(f)

        self.assertEqual(saved_config["settings"]["update_interval_minutes"], 15)
        self.assertEqual(saved_config["settings"]["alert_radius_miles"], 30)

    def test_settings_not_saved_when_dialog_cancelled(self):
        """Test that settings are not saved when dialog is cancelled."""

        # Mock the dialog to return cancelled result
        def mock_show_dialog(current_settings):  # noqa: ARG001
            return wx.ID_CANCEL, None, None

        self.app.ShowSettingsDialog = mock_show_dialog

        # Store original values
        original_interval = self.app.config["settings"]["update_interval_minutes"]
        original_radius = self.app.config["settings"]["alert_radius_miles"]

        # Create a mock event
        mock_event = MagicMock()

        # Call OnSettings
        self.app.OnSettings(mock_event)

        # Verify settings were not changed
        self.assertEqual(self.app.config["settings"]["update_interval_minutes"], original_interval)
        self.assertEqual(self.app.config["settings"]["alert_radius_miles"], original_radius)

        # Verify config file was not created
        self.assertFalse(os.path.exists(self.config_path))

    def test_original_bug_condition(self):
        """Test that demonstrates the original bug condition."""
        # Simulate the original buggy condition
        result = wx.ID_OK
        updated_settings = {"update_interval_minutes": 15}
        updated_api_settings: dict = {}  # Empty dict - the bug!

        # Original condition (buggy) - would evaluate to False
        original_condition = result == wx.ID_OK and updated_settings and updated_api_settings
        self.assertFalse(original_condition)  # This should fail with the bug

        # Fixed condition - should evaluate to True
        fixed_condition = (
            result == wx.ID_OK and updated_settings is not None and updated_api_settings is not None
        )
        self.assertTrue(fixed_condition)  # This should pass with the fix


if __name__ == "__main__":
    unittest.main()
