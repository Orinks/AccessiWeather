"""Menu handlers for the WeatherApp class

This module contains the menu-related handlers for the WeatherApp class.
"""

import logging

import wx

from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppMenuHandlers(WeatherAppHandlerBase):
    """Menu handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides menu-related event handlers for the WeatherApp class.
    """

    def CreateTaskBarMenu(self):
        """Create the taskbar popup menu.

        Returns:
            wx.Menu: The popup menu

        """
        menu = wx.Menu()

        # Add menu items
        show_hide_item = menu.Append(wx.ID_ANY, "Show/Hide AccessiWeather")
        menu.AppendSeparator()
        refresh_item = menu.Append(wx.ID_REFRESH, "Refresh Weather")
        settings_item = menu.Append(wx.ID_PREFERENCES, "Settings")

        # Add debug menu items if debug_alerts is enabled
        debug_items = []
        if hasattr(self, "debug_alerts") and self.debug_alerts:
            menu.AppendSeparator()
            debug_menu = wx.Menu()
            test_alerts_item = debug_menu.Append(wx.ID_ANY, "Test Alert Update")
            verify_interval_item = debug_menu.Append(wx.ID_ANY, "Verify Alert Interval")
            menu.AppendSubMenu(debug_menu, "Debug")
            debug_items = [test_alerts_item, verify_interval_item]

        menu.AppendSeparator()
        exit_item = menu.Append(wx.ID_EXIT, "Exit AccessiWeather")

        # Return the menu and items for binding in the TaskBarIcon class
        return menu, (show_hide_item, refresh_item, settings_item, exit_item, *debug_items)

    def OnTaskBarShowHide(self, event):  # event is required by wx
        """Handle show/hide menu item from taskbar.

        Args:
            event: The event object

        """
        if self.IsShown():
            self.Hide()
        else:
            self.Show()
            self.Raise()

    def OnTaskBarExit(self, event):  # event is required by wx
        """Handle exit menu item from taskbar.

        Args:
            event: The event object

        """
        # Call Close with force=True to ensure the app exits
        self.Close(force=True)
