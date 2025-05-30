"""Base handlers for the WeatherApp class

This module contains the base handlers for the WeatherApp class.
"""

import logging

import wx

from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppBaseHandlers(WeatherAppHandlerBase):
    """Base handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides base event handlers for the WeatherApp class.
    """

    def OnKeyDown(self, event):
        """Handle key down events for accessibility

        Args:
            event: Key event
        """
        # Handle key events for accessibility
        key_code = event.GetKeyCode()

        if key_code == wx.WXK_F5:
            # F5 to refresh
            self.OnRefresh(event)
        elif key_code == wx.WXK_ESCAPE:
            # Escape to hide to system tray
            logger.info("Escape key pressed in BaseHandlers, hiding to system tray")
            if hasattr(self, "taskbar_icon") and self.taskbar_icon:
                logger.info("Hiding app to system tray from BaseHandlers")
                self.Hide()
            else:
                event.Skip()
        else:
            # Other key events are handled by WeatherAppSystemHandlers.OnKeyDown
            event.Skip()

    # OnClose is now implemented in WeatherAppSystemHandlers

    # _stop_fetcher_threads is now implemented in WeatherAppSystemHandlers

    # OnRefresh is now implemented in WeatherAppRefreshHandlers
    # OnMinimizeToTray is now implemented in WeatherAppMenuHandlers
