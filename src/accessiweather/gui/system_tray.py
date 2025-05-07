"""System tray functionality for AccessiWeather.

This module provides the TaskBarIcon class for system tray integration.
"""

import logging
import os

import wx
import wx.adv

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
        icon_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "resources", "icon.ico"
        )

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
        # Use the menu handler from the frame to create the menu
        menu, items = self.frame.CreateTaskBarMenu()

        # Check if we have debug items
        if len(items) > 4:
            show_hide_item, refresh_item, settings_item, exit_item, *debug_items = items

            # Bind debug menu events if present
            if debug_items:
                test_alerts_item, verify_interval_item = debug_items
                self.Bind(wx.EVT_MENU, self.on_test_alerts, test_alerts_item)
                self.Bind(wx.EVT_MENU, self.on_verify_interval, verify_interval_item)
        else:
            show_hide_item, refresh_item, settings_item, exit_item = items

        # Bind standard menu events
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
        # Use the menu handler from the frame
        self.frame.OnTaskBarShowHide(event)

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
        # Use the menu handler from the frame
        self.frame.OnTaskBarExit(event)

    def on_test_alerts(self, event):
        """Handle test alerts menu item.

        Args:
            event: The event object
        """
        # Call the frame's test_alert_update method
        if hasattr(self.frame, "test_alert_update"):
            self.frame.test_alert_update()
        else:
            logger.error("Frame does not have test_alert_update method")

    def on_verify_interval(self, event):
        """Handle verify interval menu item.

        Args:
            event: The event object
        """
        # Call the frame's verify_alert_interval method
        if hasattr(self.frame, "verify_alert_interval"):
            self.frame.verify_alert_interval()
        else:
            logger.error("Frame does not have verify_alert_interval method")
