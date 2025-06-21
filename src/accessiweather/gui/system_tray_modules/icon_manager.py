"""System tray icon management functionality.

This module provides core system tray icon management including:
- Windows version compatibility handling
- Icon lifecycle management
- Instance tracking and cleanup
"""

import logging
import os
import platform
import time
from typing import Optional

import wx
import wx.adv

logger = logging.getLogger(__name__)


def _get_windows_version():
    """Get Windows version information for system tray compatibility.

    Returns:
        tuple: (major_version, minor_version, build_number) or None if not Windows

    """
    try:
        if platform.system() != "Windows":
            return None

        # Get Windows version
        version = platform.version().split(".")
        if len(version) >= 3:
            return (int(version[0]), int(version[1]), int(version[2]))
        return None
    except Exception as e:
        logger.warning(f"Could not determine Windows version: {e}")
        return None


def _is_windows_11():
    """Check if running on Windows 11.

    Returns:
        bool: True if Windows 11, False otherwise

    """
    version = _get_windows_version()
    if version is None:
        return False

    # Windows 11 is build 22000 and above
    major, minor, build = version
    return major >= 10 and build >= 22000


class TaskBarIconManager:
    """Core system tray icon management functionality.

    This mixin expects the following methods to be provided by the implementing class:
    - SetIcon(icon, tooltip)
    - IsOk() -> bool
    - RemoveIcon()
    - Destroy()
    """

    # These methods must be implemented by the class that uses this mixin (wx.adv.TaskBarIcon)
    def SetIcon(self, icon, tooltip):
        """Set the taskbar icon. Must be implemented by wx.adv.TaskBarIcon."""
        raise NotImplementedError("SetIcon must be implemented by wx.adv.TaskBarIcon")

    def IsOk(self) -> bool:
        """Check if the taskbar icon is OK. Must be implemented by wx.adv.TaskBarIcon."""
        raise NotImplementedError("IsOk must be implemented by wx.adv.TaskBarIcon")

    def RemoveIcon(self):
        """Remove the taskbar icon. Must be implemented by wx.adv.TaskBarIcon."""
        raise NotImplementedError("RemoveIcon must be implemented by wx.adv.TaskBarIcon")

    def Destroy(self):
        """Destroy the taskbar icon. Must be implemented by wx.adv.TaskBarIcon."""
        raise NotImplementedError("Destroy must be implemented by wx.adv.TaskBarIcon")

    # Class variable to track if an instance already exists
    _instance: Optional["TaskBarIconManager"] = None
    _instance_count = 0

    def __init__(self):
        """Initialize the TaskBarIconManager."""
        # Check if we already have an instance
        if TaskBarIconManager._instance is not None:
            logger.warning(
                "TaskBarIcon instance already exists. This may cause multiple tray icons."
            )

        # Ensure we have a wx.App instance
        app = wx.App.Get()
        if not app:
            raise RuntimeError("No wx.App instance found. TaskBarIcon requires an active wx.App.")

        # Track this instance
        TaskBarIconManager._instance = self
        TaskBarIconManager._instance_count += 1
        logger.debug(f"Creating TaskBarIcon instance #{TaskBarIconManager._instance_count}")

        self._is_destroyed = False

    def set_icon(self, tooltip_text=None):
        """Set the taskbar icon.

        Args:
            tooltip_text: Optional text to display in the taskbar icon tooltip.
                          If None, uses the default "AccessiWeather".

        """
        # Try to load the icon from the application's resources
        icon_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "..", "resources", "icon.ico"
        )

        if not os.path.exists(icon_path):
            # If the icon doesn't exist, use a default icon
            icon = wx.Icon(wx.ArtProvider.GetIcon(wx.ART_INFORMATION))
        else:
            icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ICO)

        # Use the provided tooltip text or default to "AccessiWeather"
        tooltip = tooltip_text if tooltip_text else "AccessiWeather"
        self.SetIcon(icon, tooltip)

    def cleanup(self):
        """Properly cleanup the TaskBarIcon to prevent multiple icons."""
        if self._is_destroyed:
            logger.debug("TaskBarIcon already cleaned up")
            return

        logger.debug("Cleaning up TaskBarIcon")

        # Check Windows version for compatibility
        windows_version = _get_windows_version()
        is_win11 = _is_windows_11()
        logger.debug(f"Windows version: {windows_version}, Windows 11: {is_win11}")

        try:
            # First, remove the icon from the system tray
            if self.IsOk():
                logger.debug("Removing icon from system tray")
                self.RemoveIcon()

                # On Windows 10, sometimes we need a small delay for proper cleanup
                if not is_win11:
                    time.sleep(0.1)  # 100ms delay for Windows 10

            else:
                logger.warning("TaskBarIcon is not OK, cannot remove icon")
        except Exception as e:
            logger.error(f"Error removing taskbar icon: {e}", exc_info=True)

        try:
            # Then destroy the TaskBarIcon object
            logger.debug("Destroying TaskBarIcon object")
            self.Destroy()
        except Exception as e:
            logger.error(f"Error destroying taskbar icon: {e}", exc_info=True)
        finally:
            # Mark as destroyed and clear class reference
            self._is_destroyed = True
            if TaskBarIconManager._instance is self:
                TaskBarIconManager._instance = None
            logger.debug("TaskBarIcon cleanup completed")

    @classmethod
    def get_instance(cls):
        """Get the current TaskBarIcon instance if it exists."""
        return cls._instance

    @classmethod
    def cleanup_existing_instance(cls):
        """Cleanup any existing TaskBarIcon instance."""
        if cls._instance is not None:
            logger.debug("Cleaning up existing TaskBarIcon instance")
            cls._instance.cleanup()
