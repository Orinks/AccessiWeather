# tests/test_settings_dialog.py
"""Tests for the SettingsDialog GUI component"""

import pytest
import wx

# from unittest.mock import patch, MagicMock # Not used yet


# We need a wx App for testing wx components
@pytest.fixture
def wx_app():
    """Create a wx App for testing"""
    app = wx.App()
    yield app


# Import the class we are testing (will fail until created)
try:
    from accessiweather.gui.settings_dialog import SettingsDialog
except ImportError:
    SettingsDialog = None  # Define as None if import fails


@pytest.mark.skipif(SettingsDialog is None, reason="Dialog not implemented")
class TestSettingsDialog:
    """Test suite for the SettingsDialog"""

    @pytest.fixture
    def mock_config(self):
        """Provides a mock configuration dictionary"""
        # Match the keys used in SettingsDialog
        return {
            "api_contact": "initial@example.com",
            "update_interval_minutes": 30,
            "alert_radius_miles": 25,
        }

    def test_settings_dialog_init_reads_config(self, wx_app, mock_config):
        """Test SettingsDialog reads initial values from the passed settings"""
        dialog = None
        try:
            # Pass the mock_config directly as current_settings
            dialog = SettingsDialog(None, current_settings=mock_config.copy())

            # Assertions using actual control names
            assert dialog.api_contact_ctrl.GetValue() == "initial@example.com"
            assert dialog.update_interval_ctrl.GetValue() == 30
            assert dialog.alert_radius_ctrl.GetValue() == 25
            # Remove pytest.fail as assertions are now implemented
        finally:
            if dialog:
                dialog.Destroy()

    def test_settings_dialog_writes_config_on_save(self, wx_app, mock_config):
        """Test SettingsDialog returns updated values via get_settings"""
        dialog = None
        try:
            # Pass the mock_config directly as current_settings
            dialog = SettingsDialog(None, current_settings=mock_config.copy())

            # Simulate changing values using actual control names
            dialog.api_contact_ctrl.SetValue("updated@example.com")
            dialog.update_interval_ctrl.SetValue(60)
            dialog.alert_radius_ctrl.SetValue(50)

            # Simulate clicking OK (which calls EndModal(wx.ID_OK))
            # We don't need to call OnOK directly, just check get_settings
            # after assuming the dialog would have been closed with OK.

            # Assert get_settings returns the updated values
            updated_settings = dialog.get_settings()
            assert updated_settings["api_contact"] == "updated@example.com"
            assert updated_settings["update_interval_minutes"] == 60
            assert updated_settings["alert_radius_miles"] == 50
            # Remove pytest.fail as assertions are now implemented

        finally:
            if dialog:
                dialog.Destroy()
