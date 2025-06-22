"""Tests for system tray functionality.

This module tests the system tray icon functionality including:
- Multiple tray icons prevention
- Proper cleanup and lifecycle management
- Windows version-specific behavior
- Error handling and recovery
"""

import logging
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import wx

from accessiweather.gui.system_tray import TaskBarIcon
from accessiweather.gui.system_tray_modules.icon_manager import TaskBarIconManager


class TestSystemTray(unittest.TestCase):
    """Test cases for system tray functionality."""

    def _get_taskbar_patches(self):
        """Get common patches for TaskBarIcon tests."""
        stack = ExitStack()
        stack.enter_context(patch.object(TaskBarIcon, "set_icon"))
        stack.enter_context(patch.object(TaskBarIcon, "bind_events"))
        stack.enter_context(patch.object(TaskBarIcon, "SetIcon"))
        stack.enter_context(patch.object(TaskBarIcon, "RemoveIcon"))
        stack.enter_context(patch.object(TaskBarIcon, "Destroy"))
        return stack

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
        TaskBarIconManager._instance = None
        TaskBarIconManager._instance_count = 0

    def tearDown(self):
        """Clean up after tests."""
        # Clean up any existing instances
        TaskBarIconManager.cleanup_existing_instance()

        # Destroy the wx.App
        self.app.Destroy()

    def test_single_instance_creation(self):
        """Test that only one TaskBarIcon instance can be created."""
        with (
            patch.object(TaskBarIcon, "set_icon"),
            patch.object(TaskBarIcon, "bind_events"),
            patch.object(TaskBarIcon, "SetIcon"),
            patch.object(TaskBarIcon, "RemoveIcon"),
            patch.object(TaskBarIcon, "Destroy"),
        ):
            # Create first instance
            icon1 = TaskBarIcon(self.frame)
            # Access singleton attributes through the TaskBarIconManager base class
            self.assertEqual(TaskBarIconManager._instance_count, 1)
            self.assertEqual(TaskBarIconManager._instance, icon1)

            # Create second instance - should log warning
            with self.assertLogs(level=logging.WARNING) as log:
                icon2 = TaskBarIcon(self.frame)
                self.assertIn("TaskBarIcon instance already exists", log.output[0])

            self.assertEqual(TaskBarIconManager._instance_count, 2)
            # The class instance should point to the latest one
            self.assertEqual(TaskBarIconManager._instance, icon2)

    def test_cleanup_existing_instance(self):
        """Test cleanup of existing instance before creating new one."""
        with self._get_taskbar_patches():
            # Create first instance
            icon1 = TaskBarIcon(self.frame)

            # Configure the patched methods to return appropriate values
            with (
                patch.object(icon1, "IsOk", return_value=True),
                patch.object(icon1, "RemoveIcon") as mock_remove_icon,
                patch.object(icon1, "Destroy") as mock_destroy,
            ):
                # Cleanup existing instance
                TaskBarIconManager.cleanup_existing_instance()

                # Verify cleanup was called
                mock_remove_icon.assert_called_once()
                mock_destroy.assert_called_once()
                self.assertIsNone(TaskBarIconManager._instance)

    def test_cleanup_method(self):
        """Test the cleanup method properly removes and destroys icon."""
        with self._get_taskbar_patches():
            icon = TaskBarIcon(self.frame)

            # Configure the patched methods to return appropriate values
            with (
                patch.object(icon, "IsOk", return_value=True),
                patch.object(icon, "RemoveIcon") as mock_remove_icon,
                patch.object(icon, "Destroy") as mock_destroy,
            ):
                # Call cleanup
                icon.cleanup()

                # Verify cleanup sequence
                mock_remove_icon.assert_called_once()
                mock_destroy.assert_called_once()
                self.assertTrue(icon._is_destroyed)
                self.assertIsNone(TaskBarIconManager._instance)

    def test_cleanup_when_not_ok(self):
        """Test cleanup when TaskBarIcon is not OK."""
        with self._get_taskbar_patches():
            icon = TaskBarIcon(self.frame)

            # Configure the patched methods to return appropriate values
            with (
                patch.object(icon, "IsOk", return_value=False),
                patch.object(icon, "RemoveIcon") as mock_remove_icon,
                patch.object(icon, "Destroy") as mock_destroy,
            ):
                # Call cleanup
                with self.assertLogs(level=logging.WARNING) as log:
                    icon.cleanup()
                    self.assertIn("TaskBarIcon is not OK", log.output[0])

                # RemoveIcon should not be called, but Destroy should
                mock_remove_icon.assert_not_called()
                mock_destroy.assert_called_once()

    def test_double_cleanup(self):
        """Test that double cleanup is handled gracefully."""
        with self._get_taskbar_patches():
            icon = TaskBarIcon(self.frame)

            # Configure the patched methods to return appropriate values
            with (
                patch.object(icon, "IsOk", return_value=True),
                patch.object(icon, "RemoveIcon") as mock_remove_icon,
                patch.object(icon, "Destroy") as mock_destroy,
            ):
                # First cleanup
                icon.cleanup()

                # Second cleanup should be ignored
                with self.assertLogs(level=logging.DEBUG) as log:
                    icon.cleanup()
                    self.assertIn("TaskBarIcon already cleaned up", log.output[0])

                # Methods should only be called once
                mock_remove_icon.assert_called_once()
                mock_destroy.assert_called_once()

    @patch("accessiweather.gui.system_tray_modules.icon_manager._is_windows_11")
    @patch("accessiweather.gui.system_tray_modules.icon_manager._get_windows_version")
    def test_windows_10_cleanup_delay(self, mock_get_version, mock_is_win11):
        """Test that Windows 10 gets a cleanup delay."""
        # Mock Windows 10
        mock_get_version.return_value = (10, 0, 19041)
        mock_is_win11.return_value = False

        with (
            patch.object(TaskBarIcon, "set_icon"),
            patch.object(TaskBarIcon, "bind_events"),
            patch.object(TaskBarIcon, "SetIcon"),
            patch.object(TaskBarIcon, "RemoveIcon"),
            patch.object(TaskBarIcon, "Destroy"),
            patch("time.sleep") as mock_sleep,
        ):
            icon = TaskBarIcon(self.frame)

            # Configure the patched methods to return appropriate values
            with (
                patch.object(icon, "IsOk", return_value=True),
                patch.object(icon, "RemoveIcon"),
                patch.object(icon, "Destroy"),
            ):
                # Call cleanup
                icon.cleanup()

                # Verify delay was added for Windows 10
                mock_sleep.assert_called_once_with(0.1)

    @patch("accessiweather.gui.system_tray_modules.icon_manager._is_windows_11")
    @patch("accessiweather.gui.system_tray_modules.icon_manager._get_windows_version")
    def test_windows_11_no_cleanup_delay(self, mock_get_version, mock_is_win11):
        """Test that Windows 11 doesn't get a cleanup delay."""
        # Mock Windows 11
        mock_get_version.return_value = (10, 0, 22000)
        mock_is_win11.return_value = True

        with (
            patch.object(TaskBarIcon, "set_icon"),
            patch.object(TaskBarIcon, "bind_events"),
            patch.object(TaskBarIcon, "SetIcon"),
            patch.object(TaskBarIcon, "RemoveIcon"),
            patch.object(TaskBarIcon, "Destroy"),
            patch("time.sleep") as mock_sleep,
        ):
            icon = TaskBarIcon(self.frame)

            # Configure the patched methods to return appropriate values
            with (
                patch.object(icon, "IsOk", return_value=True),
                patch.object(icon, "RemoveIcon"),
                patch.object(icon, "Destroy"),
            ):
                # Call cleanup
                icon.cleanup()

                # Verify no delay for Windows 11
                mock_sleep.assert_not_called()

    def test_accessibility_keyboard_events(self):
        """Test that keyboard accessibility events are properly bound."""
        with self._get_taskbar_patches():
            icon = TaskBarIcon(self.frame)

            # Verify that additional accessibility events are bound
            # These events help with keyboard navigation of the system tray
            self.assertTrue(hasattr(icon, "on_left_click"))
            self.assertTrue(hasattr(icon, "on_right_down"))

    def test_accessibility_event_handling(self):
        """Test that accessibility events are handled properly."""
        with self._get_taskbar_patches():
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
        with self._get_taskbar_patches():
            icon = TaskBarIcon(self.frame)

            # Use patch.object for proper mocking instead of direct assignment
            with (
                patch.object(icon, "CreatePopupMenu", return_value=MagicMock()) as mock_create_menu,
                patch.object(icon, "PopupMenu") as mock_popup_menu,
            ):
                # Test right-click context menu
                mock_event = MagicMock()
                icon.on_right_click(mock_event)

                # Verify menu was created and shown with proper focus
                mock_create_menu.assert_called_once()
                mock_popup_menu.assert_called_once()


if __name__ == "__main__":
    unittest.main()
