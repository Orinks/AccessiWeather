# tests/test_settings_dialog.py
"""Tests for the SettingsDialog GUI component"""

import unittest
import wx

try:
    from accessiweather.gui.settings_dialog import SettingsDialog
except ImportError:
    SettingsDialog = None  # Define as None if import fails

@unittest.skipIf(SettingsDialog is None, "Dialog not implemented")
class TestSettingsDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App()

    @classmethod
    def tearDownClass(cls):
        cls.app.Destroy()

    def setUp(self):
        # Provide a mock configuration dictionary
        self.mock_config = {
            "api_contact": "initial@example.com",
            "update_interval_minutes": 30,
            "alert_radius_miles": 25,
        }

    def tearDown(self):
        if hasattr(self, 'dialog') and self.dialog:
            self.dialog.Destroy()

    def test_settings_dialog_init_reads_config(self):
        self.dialog = SettingsDialog(None, current_settings=self.mock_config.copy())
        self.assertEqual(self.dialog.api_contact_ctrl.GetValue(), "initial@example.com")
        self.assertEqual(self.dialog.update_interval_ctrl.GetValue(), 30)
        self.assertEqual(self.dialog.alert_radius_ctrl.GetValue(), 25)

    def test_settings_dialog_writes_config_on_save(self):
        self.dialog = SettingsDialog(None, current_settings=self.mock_config.copy())
        self.dialog.api_contact_ctrl.SetValue("updated@example.com")
        self.dialog.update_interval_ctrl.SetValue(60)
        self.dialog.alert_radius_ctrl.SetValue(50)
        updated_settings = self.dialog.get_settings()
        self.assertEqual(updated_settings["api_contact"], "updated@example.com")
        self.assertEqual(updated_settings["update_interval_minutes"], 60)
        self.assertEqual(updated_settings["alert_radius_miles"], 50)

if __name__ == "__main__":
    unittest.main()
