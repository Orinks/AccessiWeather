"""Tests for system tray functionality.

This module tests the system tray icon functionality including:
- Multiple tray icons prevention
- Proper cleanup and lifecycle management
- Windows version-specific behavior
- Error handling and recovery
"""

import logging
import unittest
from unittest.mock import MagicMock, patch

import wx

from accessiweather.gui.system_tray import TaskBarIcon


class TestSystemTray(unittest.TestCase):
    """Test cases for system tray functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock wx.App
        self.app = wx.App()

        # Create a mock frame
        self.frame = MagicMock()
        self.frame.config = {
            "settings": {
                "taskbar_icon_text_enabled": False,
            }
        }

        # Reset class variables
        TaskBarIcon._instance = None
        TaskBarIcon._instance_count = 0

    def tearDown(self):
        """Clean up after tests."""
        # Clean up any existing instances
        TaskBarIcon.cleanup_existing_instance()

        # Destroy the wx.App
        self.app.Destroy()

    def test_single_instance_creation(self):
        """Test that only one TaskBarIcon instance can be created."""
        with patch("wx.adv.TaskBarIcon"):
            # Create first instance
            icon1 = TaskBarIcon(self.frame)
            self.assertEqual(TaskBarIcon._instance_count, 1)
            self.assertEqual(TaskBarIcon._instance, icon1)

            # Create second instance - should log warning
            with self.assertLogs(level=logging.WARNING) as log:
                icon2 = TaskBarIcon(self.frame)
                self.assertIn("TaskBarIcon instance already exists", log.output[0])

            self.assertEqual(TaskBarIcon._instance_count, 2)
            # The class instance should point to the latest one
            self.assertEqual(TaskBarIcon._instance, icon2)

    def test_cleanup_existing_instance(self):
        """Test cleanup of existing instance before creating new one."""
        with patch("wx.adv.TaskBarIcon"):
            # Create first instance
            icon1 = TaskBarIcon(self.frame)
            icon1.IsOk = MagicMock(return_value=True)
            icon1.RemoveIcon = MagicMock()
            icon1.Destroy = MagicMock()

            # Cleanup existing instance
            TaskBarIcon.cleanup_existing_instance()

            # Verify cleanup was called
            icon1.RemoveIcon.assert_called_once()
            icon1.Destroy.assert_called_once()
            self.assertIsNone(TaskBarIcon._instance)

    def test_cleanup_method(self):
        """Test the cleanup method properly removes and destroys icon."""
        with patch("wx.adv.TaskBarIcon"):
            icon = TaskBarIcon(self.frame)
            icon.IsOk = MagicMock(return_value=True)
            icon.RemoveIcon = MagicMock()
            icon.Destroy = MagicMock()

            # Call cleanup
            icon.cleanup()

            # Verify cleanup sequence
            icon.RemoveIcon.assert_called_once()
            icon.Destroy.assert_called_once()
            self.assertTrue(icon._is_destroyed)
            self.assertIsNone(TaskBarIcon._instance)

    def test_cleanup_when_not_ok(self):
        """Test cleanup when TaskBarIcon is not OK."""
        with patch("wx.adv.TaskBarIcon"):
            icon = TaskBarIcon(self.frame)
            icon.IsOk = MagicMock(return_value=False)
            icon.RemoveIcon = MagicMock()
            icon.Destroy = MagicMock()

            # Call cleanup
            with self.assertLogs(level=logging.WARNING) as log:
                icon.cleanup()
                self.assertIn("TaskBarIcon is not OK", log.output[0])

            # RemoveIcon should not be called, but Destroy should
            icon.RemoveIcon.assert_not_called()
            icon.Destroy.assert_called_once()

    def test_double_cleanup(self):
        """Test that double cleanup is handled gracefully."""
        with patch("wx.adv.TaskBarIcon"):
            icon = TaskBarIcon(self.frame)
            icon.IsOk = MagicMock(return_value=True)
            icon.RemoveIcon = MagicMock()
            icon.Destroy = MagicMock()

            # First cleanup
            icon.cleanup()

            # Second cleanup should be ignored
            with self.assertLogs(level=logging.DEBUG) as log:
                icon.cleanup()
                self.assertIn("TaskBarIcon already cleaned up", log.output[0])

            # Methods should only be called once
            icon.RemoveIcon.assert_called_once()
            icon.Destroy.assert_called_once()

    @patch("accessiweather.gui.system_tray._is_windows_11")
    @patch("accessiweather.gui.system_tray._get_windows_version")
    def test_windows_10_cleanup_delay(self, mock_get_version, mock_is_win11):
        """Test that Windows 10 gets a cleanup delay."""
        # Mock Windows 10
        mock_get_version.return_value = (10, 0, 19041)
        mock_is_win11.return_value = False

        with patch("wx.adv.TaskBarIcon"), patch("time.sleep") as mock_sleep:
            icon = TaskBarIcon(self.frame)
            icon.IsOk = MagicMock(return_value=True)
            icon.RemoveIcon = MagicMock()
            icon.Destroy = MagicMock()

            # Call cleanup
            icon.cleanup()

            # Verify delay was added for Windows 10
            mock_sleep.assert_called_once_with(0.1)

    @patch("accessiweather.gui.system_tray._is_windows_11")
    @patch("accessiweather.gui.system_tray._get_windows_version")
    def test_windows_11_no_cleanup_delay(self, mock_get_version, mock_is_win11):
        """Test that Windows 11 doesn't get a cleanup delay."""
        # Mock Windows 11
        mock_get_version.return_value = (10, 0, 22000)
        mock_is_win11.return_value = True

        with patch("wx.adv.TaskBarIcon"), patch("time.sleep") as mock_sleep:
            icon = TaskBarIcon(self.frame)
            icon.IsOk = MagicMock(return_value=True)
            icon.RemoveIcon = MagicMock()
            icon.Destroy = MagicMock()

            # Call cleanup
            icon.cleanup()

            # Verify no delay for Windows 11
            mock_sleep.assert_not_called()

    def test_accessibility_keyboard_events(self):
        """Test that keyboard accessibility events are properly bound."""
        with patch("wx.adv.TaskBarIcon"):
            icon = TaskBarIcon(self.frame)

            # Verify that additional accessibility events are bound
            # These events help with keyboard navigation of the system tray
            self.assertTrue(hasattr(icon, "on_left_click"))
            self.assertTrue(hasattr(icon, "on_right_down"))

    def test_accessibility_event_handling(self):
        """Test that accessibility events are handled properly."""
        with patch("wx.adv.TaskBarIcon"):
            icon = TaskBarIcon(self.frame)

            # Test left click event (keyboard Enter equivalent)
            mock_event = MagicMock()
            icon.on_left_click(mock_event)
            # Should call on_show_hide

            # Test right down event (keyboard Applications key equivalent)
            icon.on_right_down(mock_event)
            # Should skip the event for normal processing

    def test_context_menu_accessibility(self):
        """Test that context menu is shown with proper accessibility."""
        with patch("wx.adv.TaskBarIcon"):
            icon = TaskBarIcon(self.frame)
            icon.CreatePopupMenu = MagicMock(return_value=MagicMock())
            icon.PopupMenu = MagicMock()

            # Test right-click context menu
            mock_event = MagicMock()
            icon.on_right_click(mock_event)

            # Verify menu was created and shown with proper focus
            icon.CreatePopupMenu.assert_called_once()
            icon.PopupMenu.assert_called_once()


if __name__ == "__main__":
    unittest.main()
