"""System tray functionality for AccessiWeather.

This module provides the TaskBarIcon class for system tray integration.
"""

import logging
import os
from typing import Optional

import wx
import wx.adv

from accessiweather.config_utils import get_config_dir

logger = logging.getLogger(__name__)


class TaskBarIcon(wx.adv.TaskBarIcon):
    """System tray icon for AccessiWeather."""

    def __init__(self, frame):
        """Initialize the TaskBarIcon.

        Args:
            frame: The main application frame (WeatherApp)
        """
        # Ensure we have a wx.App instance before initializing
        if not wx.App.Get():
            logger.warning("No wx.App instance found when creating TaskBarIcon. Creating one.")
            self._app = wx.App()
        else:
            self._app = wx.App.Get()

        super().__init__()
        self.frame = frame

        # Set the icon
        self.set_icon()

        # Bind events
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.on_left_dclick)
        self.Bind(wx.adv.EVT_TASKBAR_RIGHT_UP, self.on_right_click)

    def set_icon(self):
        """Set the taskbar icon."""
        # Try to load the icon from the application's resources
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "resources", "icon.ico")

        if not os.path.exists(icon_path):
            # If the icon doesn't exist, use a default icon
            icon = wx.Icon(wx.ArtProvider.GetIcon(wx.ART_INFORMATION))
        else:
            icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ICO)

        self.SetIcon(icon, "AccessiWeather")

    def on_left_dclick(self, event):
        """Handle left double-click event.

        Args:
            event: The event object
        """
        self.on_show_hide(event)

    def on_right_click(self, event):
        """Handle right-click event.

        Args:
            event: The event object
        """
        # Create and show the popup menu
        menu = self.CreatePopupMenu()
        if menu:
            self.PopupMenu(menu)
            menu.Destroy()

    def CreatePopupMenu(self):
        """Create the popup menu.

        Returns:
            wx.Menu: The popup menu
        """
        menu = wx.Menu()

        # Add menu items
        show_hide_item = menu.Append(wx.ID_ANY, "Show/Hide AccessiWeather")
        menu.AppendSeparator()
        refresh_item = menu.Append(wx.ID_REFRESH, "Refresh Weather")
        settings_item = menu.Append(wx.ID_PREFERENCES, "Settings")
        menu.AppendSeparator()
        exit_item = menu.Append(wx.ID_EXIT, "Exit AccessiWeather")

        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_show_hide, show_hide_item)
        self.Bind(wx.EVT_MENU, self.on_refresh, refresh_item)
        self.Bind(wx.EVT_MENU, self.on_settings, settings_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)

        return menu

    def on_show_hide(self, event):
        """Handle show/hide menu item.

        Args:
            event: The event object
        """
        if self.frame.IsShown():
            self.frame.Hide()
        else:
            self.frame.Show()
            self.frame.Raise()

    def on_refresh(self, event):
        """Handle refresh menu item.

        Args:
            event: The event object
        """
        # Call the frame's OnRefresh method
        self.frame.OnRefresh(event)

    def on_settings(self, event):
        """Handle settings menu item.

        Args:
            event: The event object
        """
        # Call the frame's OnSettings method
        self.frame.OnSettings(event)

    def on_exit(self, event):
        """Handle exit menu item.

        Args:
            event: The event object
        """
        # Call the frame's Close method with force=True
        self.frame.Close(force=True)
