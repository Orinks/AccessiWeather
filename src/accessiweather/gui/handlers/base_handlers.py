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
            logger.debug("Escape key pressed, hiding to system tray")
            if hasattr(self, "taskbar_icon") and self.taskbar_icon:
                self.Hide()
            else:
                event.Skip()
        else:
            event.Skip()

    def OnClose(self, event, force_close=False):  # event is required by wx
        """Handle window close event.

        Args:
            event: The close event
            force_close: Whether to force the window to close
        """
        logger.info("OnClose called with force_close=%s", force_close)

        # Check for force close flag on the instance or parameter
        force_close = force_close or getattr(self, "_force_close", False)
        logger.debug("Final force_close value: %s", force_close)

        # Stop all fetcher threads first
        logger.info("Stopping fetcher threads...")
        self._stop_fetcher_threads()

        # If we're not force closing and have a taskbar icon, just hide
        if not force_close and hasattr(self, "taskbar_icon") and self.taskbar_icon:
            logger.debug("Hiding window instead of closing")
            # Stop the timer when hiding
            if hasattr(self, "timer") and self.timer.IsRunning():
                logger.debug("Stopping timer before hiding")
                self.timer.Stop()
            self.Hide()
            event.Veto()
            # Restart timer after hiding
            if hasattr(self, "timer"):
                logger.debug("Restarting timer after hiding")
                self.timer.Start()
            return

        # Force closing - clean up resources
        logger.info("Proceeding with force close cleanup")

        # Stop timer
        if hasattr(self, "timer") and self.timer.IsRunning():
            logger.debug("Stopping timer")
            self.timer.Stop()

        # Remove taskbar icon
        if hasattr(self, "taskbar_icon") and self.taskbar_icon:
            logger.debug("Removing taskbar icon")
            try:
                if hasattr(self.taskbar_icon, "RemoveIcon"):
                    self.taskbar_icon.RemoveIcon()
                self.taskbar_icon.Destroy()
                self.taskbar_icon = None
            except Exception as e:
                logger.error("Error removing taskbar icon: %s", e)

        # Save config
        if hasattr(self, "_save_config"):
            logger.debug("Saving configuration")
            try:
                self._save_config()
            except Exception as e:
                logger.error("Error saving config: %s", e)

        # Destroy the window
        logger.info("Destroying window")
        self.Destroy()

    def _stop_fetcher_threads(self):
        """Stop all fetcher threads directly."""
        logger.debug("Stopping all fetcher threads")
        try:
            # Stop forecast fetcher
            if hasattr(self, "forecast_fetcher"):
                logger.debug("Stopping forecast fetcher")
                if hasattr(self.forecast_fetcher, "cancel"):
                    self.forecast_fetcher.cancel()
                if hasattr(self.forecast_fetcher, "_stop_event"):
                    self.forecast_fetcher._stop_event.set()

            # Stop alerts fetcher
            if hasattr(self, "alerts_fetcher"):
                logger.debug("Stopping alerts fetcher")
                if hasattr(self.alerts_fetcher, "cancel"):
                    self.alerts_fetcher.cancel()
                if hasattr(self.alerts_fetcher, "_stop_event"):
                    self.alerts_fetcher._stop_event.set()

            # Stop discussion fetcher
            if hasattr(self, "discussion_fetcher"):
                logger.debug("Stopping discussion fetcher")
                if hasattr(self.discussion_fetcher, "cancel"):
                    self.discussion_fetcher.cancel()
                if hasattr(self.discussion_fetcher, "_stop_event"):
                    self.discussion_fetcher._stop_event.set()

            # Stop national forecast fetcher
            if hasattr(self, "national_forecast_fetcher"):
                logger.debug("Stopping national forecast fetcher")
                if hasattr(self.national_forecast_fetcher, "cancel"):
                    self.national_forecast_fetcher.cancel()
                if hasattr(self.national_forecast_fetcher, "_stop_event"):
                    self.national_forecast_fetcher._stop_event.set()

            # Stop timers
            if hasattr(self, "timer") and self.timer.IsRunning():
                logger.debug("Stopping main timer")
                self.timer.Stop()

            if hasattr(self, "alerts_timer") and self.alerts_timer.IsRunning():
                logger.debug("Stopping alerts timer")
                self.alerts_timer.Stop()

        except Exception as e:
            logger.error("Error stopping fetcher threads: %s", e, exc_info=True)

    def OnRefresh(self, event):  # event is required by wx
        """Handle refresh button click

        Args:
            event: Button event
        """
        # Trigger weather data update
        self.UpdateWeatherData()

    def OnMinimizeToTray(self, event):  # event is required by wx
        """Handle minimize to tray button click

        Args:
            event: Button event
        """
        logger.debug("Minimizing to tray")
        self.Hide()
