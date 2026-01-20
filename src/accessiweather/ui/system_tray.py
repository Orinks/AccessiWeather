"""
System tray icon implementation for AccessiWeather.

This module provides a TaskBarIcon-based system tray icon that allows
the application to minimize to the system tray and provides a context
menu for common operations.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import wx
import wx.adv

if TYPE_CHECKING:
    from ..app import AccessiWeatherApp

logger = logging.getLogger(__name__)


class SystemTrayIcon(wx.adv.TaskBarIcon):
    """
    System tray icon for AccessiWeather.

    Provides:
    - Tray icon with tooltip showing app name/status
    - Left-click to show/restore the main window
    - Right-click context menu with Show/Quit options
    """

    def __init__(self, app: AccessiWeatherApp):
        """
        Initialize the system tray icon.

        Args:
            app: The AccessiWeather application instance

        """
        super().__init__()
        self.app = app
        self._icon_set = False
        self._cached_icon = None  # Cache the icon to avoid reloading

        # Set up the tray icon
        self._setup_icon()

        # Bind events
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self._on_left_click)
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self._on_left_click)
        self.Bind(wx.adv.EVT_TASKBAR_RIGHT_DOWN, self._on_right_click)

    def _setup_icon(self) -> None:
        """Set up the tray icon image."""
        icon = self._load_icon()
        if icon and icon.IsOk():
            self._cached_icon = icon  # Cache the icon
            self.SetIcon(icon, "AccessiWeather")
            self._icon_set = True
            logger.debug("System tray icon set successfully")
        else:
            logger.warning("Failed to set system tray icon")

    def _load_icon(self) -> wx.Icon | None:
        """
        Load the application icon for the tray.

        Returns:
            wx.Icon instance or None if loading fails

        """
        # Try multiple icon paths
        icon_paths = self._get_icon_paths()

        for icon_path in icon_paths:
            if icon_path.exists():
                try:
                    if icon_path.suffix.lower() == ".ico":
                        icon = wx.Icon(str(icon_path), wx.BITMAP_TYPE_ICO)
                    else:
                        icon = wx.Icon(str(icon_path), wx.BITMAP_TYPE_PNG)

                    if icon.IsOk():
                        logger.debug(f"Loaded tray icon from: {icon_path}")
                        return icon
                except Exception as e:
                    logger.debug(f"Failed to load icon from {icon_path}: {e}")

        # Fall back to a default icon
        return self._create_default_icon()

    def _get_icon_paths(self) -> list[Path]:
        """
        Get potential icon file paths.

        Returns:
            List of Path objects to try for the icon

        """
        paths = []

        # Get the app resource directory
        if getattr(sys, "frozen", False):
            # Running as compiled executable
            base_path = Path(sys.executable).parent
            paths.append(base_path / "app.ico")
            paths.append(base_path / "resources" / "app.ico")
        else:
            # Running as script
            module_path = Path(__file__).parent.parent
            paths.append(module_path / "resources" / "app.ico")
            paths.append(module_path / "resources" / "app_32.png")
            paths.append(module_path / "resources" / "app_16.png")

        return paths

    def _create_default_icon(self) -> wx.Icon:
        """
        Create a simple default icon if no icon file is found.

        Returns:
            A simple colored icon

        """
        # Create a 16x16 bitmap with a simple design
        bitmap = wx.Bitmap(16, 16)
        dc = wx.MemoryDC(bitmap)
        dc.SetBackground(wx.Brush(wx.Colour(70, 130, 180)))  # Steel blue
        dc.Clear()
        dc.SetPen(wx.Pen(wx.WHITE, 1))
        dc.SetBrush(wx.Brush(wx.WHITE))
        # Draw a simple "W" for weather
        dc.DrawText("W", 3, 1)
        dc.SelectObject(wx.NullBitmap)

        icon = wx.Icon()
        icon.CopyFromBitmap(bitmap)
        return icon

    def _on_left_click(self, event: wx.adv.TaskBarIconEvent) -> None:
        """Handle left-click on tray icon to show/restore the main window."""
        self.show_main_window()

    def _on_right_click(self, event: wx.adv.TaskBarIconEvent) -> None:
        """Handle right-click on tray icon to show context menu."""
        menu = self._create_popup_menu()
        self.PopupMenu(menu)
        menu.Destroy()

    def _create_popup_menu(self) -> wx.Menu:
        """
        Create the context menu for the tray icon.

        Returns:
            wx.Menu with Show and Quit options

        """
        menu = wx.Menu()

        # Show/Restore item
        show_item = menu.Append(wx.ID_ANY, "&Show AccessiWeather")
        self.Bind(wx.EVT_MENU, self._on_show_menu, show_item)

        menu.AppendSeparator()

        # Quit item
        quit_item = menu.Append(wx.ID_EXIT, "&Quit")
        self.Bind(wx.EVT_MENU, self._on_quit_menu, quit_item)

        return menu

    def _on_show_menu(self, event: wx.CommandEvent) -> None:
        """Handle Show menu item click."""
        self.show_main_window()

    def _on_quit_menu(self, event: wx.CommandEvent) -> None:
        """Handle Quit menu item click."""
        self.app.request_exit()

    def show_main_window(self) -> None:
        """Show and restore the main window."""
        if self.app.main_window:
            frame = self.app.main_window.widget.control
            frame.Show(True)
            frame.Iconize(False)  # Restore if minimized
            frame.Raise()  # Bring to front
            if sys.platform == "darwin":
                # macOS needs RequestUserAttention instead of SetFocus
                frame.RequestUserAttention()
            else:
                frame.SetFocus()
            logger.debug("Main window restored from tray")

    def update_tooltip(self, text: str) -> None:
        """
        Update the tray icon tooltip text.

        Args:
            text: The new tooltip text

        """
        if self._icon_set and self._cached_icon and self._cached_icon.IsOk():
            self.SetIcon(self._cached_icon, text)
            logger.debug(f"Tray tooltip updated: {text}")
