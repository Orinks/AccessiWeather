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
            logger.info("Escape key pressed in SystemHandlers, hiding to system tray")
            if hasattr(self, "taskbar_icon") and self.taskbar_icon:
                logger.info("Hiding app to system tray from SystemHandlers")
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

            # Check for force close flag on the instance or parameter
            is_forced_close = force_close
            if hasattr(self, "_force_close"):
                is_forced_close = is_forced_close or self._force_close
                logger.debug("Instance _force_close flag: %s", self._force_close)

            # Get minimize_to_tray setting
            minimize_to_tray = self.config.get("settings", {}).get("minimize_to_tray", True)
            logger.debug("minimize_to_tray setting: %s", minimize_to_tray)

            if (
                minimize_to_tray
                and hasattr(self, "taskbar_icon")
                and self.taskbar_icon
                and not is_forced_close
            ):
                logger.debug("Minimizing to tray instead of closing")

                if hasattr(self, "timer") and self.timer.IsRunning():
                    logger.debug("Stopping timer before hiding")
                    self.timer.Stop()

                self.Hide()

                if hasattr(self, "timer"):  # Check if timer exists before trying to Start
                    logger.debug("Restarting timer after hiding")
                    self.timer.Start()  # Restart after hide, as per original logic

                event.Veto()  # Prevent the window from closing
                logger.debug("Hide/Veto called.")
                return True  # Return True after Veto

            # Proceeding with actual application close
            logger.info("Proceeding with application close")

            # Stop fetchers and timers here, before saving config and destroying UI elements
            self._stop_fetcher_threads()  # Moved here
            logger.debug("Fetcher threads and timers stopped for close.")

            # Save configuration
            logger.debug("Saving configuration before closing")
            self._save_config(show_errors=False)

            # Remove taskbar icon if it exists
            if hasattr(self, "taskbar_icon") and self.taskbar_icon:
                logger.debug("Removing taskbar icon")
                try:
                    # Check if RemoveIcon is available and if the icon is still ok
                    if self.taskbar_icon.IsOk() and hasattr(self.taskbar_icon, "RemoveIcon"):
                        self.taskbar_icon.RemoveIcon()
                    # Check if Destroy is available
                    if hasattr(self.taskbar_icon, "Destroy"):
                        self.taskbar_icon.Destroy()
                except Exception as e:  # Catch specific wx errors if possible
                    logger.error("Error removing taskbar icon: %s", e)
                finally:
                    # Ensure reference is cleared
                    self.taskbar_icon = None

            # Allow the default close behavior to proceed
            event.Skip()
            logger.debug("event.Skip() called, allowing default close.")
            return True  # Return True after Skip to avoid TypeError

        except Exception as e:
            logger.error(f"Error during window close: {e}", exc_info=True)
            # Ensure window closes even if there's an error
            if event:  # Check if event is not None
                event.Skip()  # Allow default closing
            return True  # Return True to avoid TypeError

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
