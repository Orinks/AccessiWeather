"""Utility functions for system tray functionality."""

import logging
import os
import platform

import wx

logger = logging.getLogger(__name__)


def get_windows_version():
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


def is_windows_11():
    """Check if running on Windows 11.

    Returns:
        bool: True if Windows 11, False otherwise
    """
    version = get_windows_version()
    if version is None:
        return False

    # Windows 11 is build 22000 and above
    major, minor, build = version
    return major >= 10 and build >= 22000


def load_tray_icon():
    """Load the system tray icon.

    Returns:
        wx.Icon: The loaded icon or a default icon if loading fails
    """
    # Try to load the icon from the application's resources
    icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "resources", "icon.ico")

    if not os.path.exists(icon_path):
        # If the icon doesn't exist, use a default icon
        return wx.Icon(wx.ArtProvider.GetIcon(wx.ART_INFORMATION))
    else:
        return wx.Icon(icon_path, wx.BITMAP_TYPE_ICO)


def cleanup_taskbar_icon(taskbar_icon):
    """Properly cleanup a TaskBarIcon to prevent multiple icons.

    Args:
        taskbar_icon: The TaskBarIcon instance to cleanup
    """
    if getattr(taskbar_icon, "_is_destroyed", False):
        logger.debug("TaskBarIcon already cleaned up")
        return

    logger.debug("Cleaning up TaskBarIcon")

    # Check Windows version for compatibility
    windows_version = get_windows_version()
    is_win11 = is_windows_11()
    logger.debug(f"Windows version: {windows_version}, Windows 11: {is_win11}")

    try:
        # First, remove the icon from the system tray
        if taskbar_icon.IsOk():
            logger.debug("Removing icon from system tray")
            taskbar_icon.RemoveIcon()

            # On Windows 10, sometimes we need a small delay for proper cleanup
            if not is_win11:
                import time

                time.sleep(0.1)  # 100ms delay for Windows 10

        else:
            logger.warning("TaskBarIcon is not OK, cannot remove icon")
    except Exception as e:
        logger.error(f"Error removing taskbar icon: {e}", exc_info=True)

    try:
        # Then destroy the TaskBarIcon object
        logger.debug("Destroying TaskBarIcon object")
        taskbar_icon.Destroy()
    except Exception as e:
        logger.error(f"Error destroying taskbar icon: {e}", exc_info=True)
    finally:
        # Mark as destroyed
        taskbar_icon._is_destroyed = True
        logger.debug("TaskBarIcon cleanup completed")
