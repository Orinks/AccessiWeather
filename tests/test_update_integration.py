"""Integration tests for the auto-updater functionality."""

import tempfile
import unittest
from unittest.mock import Mock, patch

import wx

from accessiweather.gui.update_dialog import UpdateNotificationDialog
from accessiweather.services.update_service import UpdateInfo, UpdateService


class TestUpdateIntegration(unittest.TestCase):
    """Integration tests for update functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = wx.App()
        self.temp_dir = tempfile.mkdtemp()

        # Create a mock parent window
        self.parent = wx.Frame(None, title="Test Parent")

        # Create update service
        self.update_service = UpdateService(
            config_dir=self.temp_dir, notification_callback=Mock(), progress_callback=Mock()
        )

        # Create sample update info
        self.update_info = UpdateInfo(
            version="1.0.0",
            release_url="https://github.com/Orinks/AccessiWeather/releases/tag/v1.0.0",
            release_notes="Test release with new features and bug fixes.",
            assets=[
                {
                    "name": "AccessiWeather-1.0.0-Setup.exe",
                    "browser_download_url": "https://github.com/Orinks/AccessiWeather/releases/download/v1.0.0/AccessiWeather-1.0.0-Setup.exe",
                },
                {
                    "name": "AccessiWeather-1.0.0-Portable.zip",
                    "browser_download_url": "https://github.com/Orinks/AccessiWeather/releases/download/v1.0.0/AccessiWeather-1.0.0-Portable.zip",
                },
            ],
            published_date="2024-01-01T00:00:00Z",
            is_prerelease=False,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        self.update_service.stop_background_checking()
        self.parent.Destroy()
        self.app.Destroy()

        # Clean up temp directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_update_dialog_creation(self):
        """Test that update dialog can be created successfully."""
        dialog = UpdateNotificationDialog(self.parent, self.update_info, self.update_service)

        # Check that dialog was created
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.update_info, self.update_info)
        self.assertEqual(dialog.update_service, self.update_service)

        # Check that UI elements exist
        self.assertIsNotNone(dialog.notes_ctrl)
        self.assertIsNotNone(dialog.install_button)
        self.assertIsNotNone(dialog.cancel_button)

        dialog.Destroy()

    def test_update_dialog_with_auto_install_disabled(self):
        """Test update dialog when auto-install is disabled."""
        # Disable auto-install in service settings
        self.update_service.update_settings({"auto_install_enabled": False})

        dialog = UpdateNotificationDialog(self.parent, self.update_info, self.update_service)

        # Should not have auto-install radio button
        self.assertIsNone(dialog.auto_install_radio)

        # Should have manual download radio button
        self.assertIsNotNone(dialog.manual_download_radio)
        self.assertTrue(dialog.manual_download_radio.GetValue())

        dialog.Destroy()

    def test_update_dialog_with_auto_install_enabled(self):
        """Test update dialog when auto-install is enabled."""
        # Enable auto-install in service settings
        self.update_service.update_settings({"auto_install_enabled": True})

        dialog = UpdateNotificationDialog(self.parent, self.update_info, self.update_service)

        # Should have auto-install radio button
        self.assertIsNotNone(dialog.auto_install_radio)
        self.assertTrue(dialog.auto_install_radio.GetValue())

        # Should have manual download radio button
        self.assertIsNotNone(dialog.manual_download_radio)
        self.assertFalse(dialog.manual_download_radio.GetValue())

        dialog.Destroy()

    def test_update_dialog_release_notes_display(self):
        """Test that release notes are displayed correctly."""
        dialog = UpdateNotificationDialog(self.parent, self.update_info, self.update_service)

        # Check that release notes are displayed
        notes_text = dialog.notes_ctrl.GetValue()
        self.assertEqual(notes_text, self.update_info.release_notes)

        dialog.Destroy()

    def test_update_dialog_version_display(self):
        """Test that version information is displayed correctly."""
        dialog = UpdateNotificationDialog(self.parent, self.update_info, self.update_service)

        # Check dialog title contains version
        title = dialog.GetTitle()
        self.assertIn(self.update_info.version, title)

        dialog.Destroy()

    @patch("webbrowser.open")
    def test_manual_download_opens_browser(self, mock_browser_open):
        """Test that manual download opens the browser."""
        dialog = UpdateNotificationDialog(self.parent, self.update_info, self.update_service)

        # Ensure manual download is selected
        dialog.manual_download_radio.SetValue(True)

        # Mock EndModal to prevent modal dialog issues in tests
        with patch.object(dialog, "EndModal") as mock_end_modal:
            # Simulate clicking install button
            event = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED)
            dialog.OnInstallUpdate(event)

            # Check that browser was opened with correct URL
            mock_browser_open.assert_called_once_with(self.update_info.release_url)
            mock_end_modal.assert_called_once_with(wx.ID_OK)

        dialog.Destroy()

    def test_skip_version_functionality(self):
        """Test skip version functionality."""
        dialog = UpdateNotificationDialog(self.parent, self.update_info, self.update_service)

        # Simulate clicking skip version button
        event = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED)

        # Mock ShowModal to prevent actual dialog display
        with patch.object(dialog, "EndModal") as mock_end_modal:
            dialog.OnSkipVersion(event)
            mock_end_modal.assert_called_once_with(wx.ID_IGNORE)

        # Check that version was marked as notified
        self.assertEqual(
            self.update_service.update_state["last_notified_version"], self.update_info.version
        )

        dialog.Destroy()

    def test_remind_later_functionality(self):
        """Test remind later functionality."""
        dialog = UpdateNotificationDialog(self.parent, self.update_info, self.update_service)

        # Store original last_notified_version
        original_notified = self.update_service.update_state.get("last_notified_version")

        # Simulate clicking remind later button
        event = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED)

        # Mock ShowModal to prevent actual dialog display
        with patch.object(dialog, "EndModal") as mock_end_modal:
            dialog.OnRemindLater(event)
            mock_end_modal.assert_called_once_with(wx.ID_CANCEL)

        # Check that last_notified_version was not changed
        self.assertEqual(
            self.update_service.update_state.get("last_notified_version"), original_notified
        )

        dialog.Destroy()

    def test_update_service_settings_integration(self):
        """Test that update service settings work correctly."""
        # Test initial settings
        settings = self.update_service.get_settings()
        self.assertIn("auto_check_enabled", settings)
        self.assertIn("check_interval_hours", settings)
        self.assertIn("update_channel", settings)
        self.assertIn("auto_install_enabled", settings)

        # Test updating settings
        new_settings = {
            "auto_check_enabled": False,
            "check_interval_hours": 48,
            "update_channel": "dev",
            "auto_install_enabled": True,
        }

        self.update_service.update_settings(new_settings)

        # Verify settings were updated
        updated_settings = self.update_service.get_settings()
        for key, value in new_settings.items():
            self.assertEqual(updated_settings[key], value)

    def test_background_checking_control(self):
        """Test background checking start/stop functionality."""
        # Initially should not be running
        self.assertIsNone(self.update_service._check_thread)

        # Start background checking
        self.update_service.start_background_checking()

        # Should now have a thread
        self.assertIsNotNone(self.update_service._check_thread)

        # Stop background checking
        self.update_service.stop_background_checking()

        # Thread should be stopped
        if self.update_service._check_thread:
            self.assertFalse(self.update_service._check_thread.is_alive())


if __name__ == "__main__":
    unittest.main()
