"""System handlers for the WeatherApp class

This module contains the system-related handlers for the WeatherApp class.
"""

import logging

import wx

from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppSystemHandlers(WeatherAppHandlerBase):
    """System handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides system-related event handlers for the WeatherApp class.
    """

    def OnMinimize(self, event):
        """Handle window minimize event"""
        logger.debug("OnMinimize called")
        if event.IsIconized():
            # Window is being minimized
            logger.debug("Window is being minimized, hiding to tray")
            self.Hide()
            event.Skip()
        else:
            # Window is being restored
            event.Skip()

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

    def OnClose(self, event, force_close=False):
        """Handle window close event.

        Args:
            event: The close event
            force_close: If True, force the window to close instead of minimizing
        """
        try:
            logger.debug("OnClose called with force_close=%s", force_close)

            # Stop all fetcher threads first to avoid deadlocks
            self._stop_fetcher_threads()
            logger.debug("Fetcher threads stop requested.")

            # Check for force close flag on the instance or parameter
            if hasattr(self, "_force_close"):
                force_close = force_close or self._force_close
                logger.debug("Instance _force_close flag: %s", self._force_close)

            # Get minimize_to_tray setting
            minimize_to_tray = self.config.get("settings", {}).get("minimize_to_tray", True)
            logger.debug("minimize_to_tray setting: %s", minimize_to_tray)

            # If minimize_to_tray is enabled, we have a taskbar icon, and we're not force closing
            if (
                minimize_to_tray
                and hasattr(self, "taskbar_icon")
                and self.taskbar_icon
                and not force_close
            ):
                logger.debug("Minimizing to tray instead of closing")

                # Stop the timer when hiding to prevent unnecessary updates
                if hasattr(self, "timer") and self.timer.IsRunning():
                    logger.debug("Stopping timer before hiding")
                    self.timer.Stop()

                # Hide the window
                self.Hide()

                # Show notification if configured
                if self.taskbar_icon:
                    # Create a popup menu for the taskbar icon if it doesn't exist
                    logger.debug("Showing notification about minimizing to tray")
                    # We could show a balloon notification here, but it's not necessary
                    # and might be annoying to users

                # Prevent the default close behavior
                event.Veto()

                # Restart the timer after hiding to continue background updates
                if hasattr(self, "timer"):
                    logger.debug("Restarting timer after hiding")
                    self.timer.Start()

                logger.debug("Hide/Veto called.")
                return

            # Actually closing the application
            logger.info("Proceeding with application close")

            # Stop timers
            if hasattr(self, "timer") and self.timer.IsRunning():
                logger.debug("Stopping main timer for force close")
                self.timer.Stop()

            # Alerts timer has been removed in favor of unified update mechanism

            # Save configuration
            logger.debug("Saving configuration before closing")
            self._save_config(show_errors=False)

            # Remove taskbar icon if it exists
            if hasattr(self, "taskbar_icon") and self.taskbar_icon:
                logger.debug("Removing taskbar icon")
                try:
                    if hasattr(self.taskbar_icon, "RemoveIcon"):
                        self.taskbar_icon.RemoveIcon()
                    self.taskbar_icon.Destroy()
                except Exception as e:
                    logger.error("Error removing taskbar icon: %s", e)

            # Allow the close event to proceed
            event.Skip()

            # Proceed with destroying the window to trigger App.OnExit cleanup
            logger.info("Initiating shutdown by calling self.Destroy()...")
            self.Destroy()
            logger.info("self.Destroy() called. App.OnExit should now handle cleanup.")

            # Now it's safe to set taskbar_icon to None after all operations are complete
            if hasattr(self, "taskbar_icon"):
                self.taskbar_icon = None

        except Exception as e:
            logger.error(f"Error during window close: {e}", exc_info=True)
            # Ensure window closes even if there's an error
            event.Skip()
            self.Destroy()

    def _stop_fetcher_threads(self):
        """Stop all fetcher threads"""
        try:
            logger.debug("Stopping fetcher threads")
            # Stop all fetcher threads
            for fetcher_attr in [
                "forecast_fetcher",
                "alerts_fetcher",
                "discussion_fetcher",
                "current_conditions_fetcher",
                "hourly_forecast_fetcher",
                "national_forecast_fetcher",
            ]:
                if hasattr(self, fetcher_attr):
                    fetcher = getattr(self, fetcher_attr)
                    if fetcher and hasattr(fetcher, "stop"):
                        logger.debug(f"Stopping {fetcher_attr}")
                        fetcher.stop()

            # Stop timers
            if hasattr(self, "timer") and self.timer.IsRunning():
                logger.debug("Stopping timer")
                self.timer.Stop()

            # Alerts timer has been removed in favor of unified update mechanism

        except Exception as e:
            logger.error("Error stopping fetcher threads: %s", e, exc_info=True)
