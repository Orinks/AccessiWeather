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

        This method handles the window close event, either by minimizing to the system tray
        or by proceeding with the actual application close. It ensures proper cleanup of
        resources in all cases.

        Args:
            event: The close event
            force_close: If True, force the window to close instead of minimizing

        Returns:
            bool: True to indicate successful handling of the event
        """
        close_successful = True
        logger.debug("OnClose called with force_close=%s", force_close)

        try:
            # Check for force close flag on the instance or parameter
            is_forced_close = force_close
            if hasattr(self, "_force_close"):
                is_forced_close = is_forced_close or self._force_close
                logger.debug("Instance _force_close flag: %s", self._force_close)

            # Get minimize_to_tray setting
            minimize_to_tray = self.config.get("settings", {}).get("minimize_to_tray", True)
            logger.debug("minimize_to_tray setting: %s", minimize_to_tray)

            # Check if we should minimize to tray instead of closing
            if (
                minimize_to_tray
                and hasattr(self, "taskbar_icon")
                and self.taskbar_icon
                and not is_forced_close
            ):
                logger.debug("Minimizing to tray instead of closing")

                try:
                    # Stop timer before hiding if it's running
                    if hasattr(self, "timer") and self.timer.IsRunning():
                        logger.debug("Stopping timer before hiding")
                        self.timer.Stop()

                    # Hide the window
                    self.Hide()

                    # Restart timer after hiding
                    if hasattr(self, "timer"):
                        logger.debug("Restarting timer after hiding")
                        self.timer.Start()

                    # Prevent the window from closing
                    event.Veto()
                    logger.debug("Window hidden and close event vetoed")
                    return True
                except Exception as e:
                    logger.error(f"Error during minimize to tray: {e}", exc_info=True)
                    close_successful = False
                    # If minimizing fails, proceed with normal close

            # Proceeding with actual application close
            logger.info("Proceeding with application close")

            try:
                # Stop fetchers and timers
                logger.debug("Stopping fetcher threads and timers")
                self._stop_fetcher_threads()
                logger.debug("Fetcher threads and timers stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping fetcher threads: {e}", exc_info=True)
                close_successful = False
                # Continue with close process even if thread stopping fails

            try:
                # Save configuration
                logger.debug("Saving configuration before closing")
                self._save_config(show_errors=False)
                logger.debug("Configuration saved successfully")
            except Exception as e:
                logger.error(f"Error saving configuration during close: {e}", exc_info=True)
                close_successful = False
                # Continue with close process even if config save fails

            try:
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
                    except Exception as e:
                        logger.error(f"Error removing taskbar icon: {e}", exc_info=True)
                        close_successful = False
                    finally:
                        # Always ensure reference is cleared
                        self.taskbar_icon = None
            except Exception as e:
                logger.error(f"Unexpected error handling taskbar icon: {e}", exc_info=True)
                close_successful = False
                # Continue with close process even if taskbar icon cleanup fails

            # Log close status
            if close_successful:
                logger.info("Application close process completed successfully")
            else:
                logger.warning("Application close process completed with some errors")

            # Always allow the default close behavior to proceed
            event.Skip()
            logger.debug("Default close behavior allowed to proceed")
            return True

        except Exception as e:
            logger.error(f"Unexpected error during window close: {e}", exc_info=True)
            # Ensure window closes even if there's an error
            if event:
                event.Skip()
            return True

    def _stop_fetcher_threads(self):
        """Stop all fetcher threads and timers.

        This method ensures all fetcher threads and timers are properly stopped
        during application shutdown. It handles each fetcher independently to
        ensure that failures in one don't prevent others from being stopped.
        """
        fetcher_errors = []

        logger.debug("Beginning fetcher thread shutdown sequence")

        # List of all fetcher attributes to check
        fetcher_attrs = [
            "forecast_fetcher",
            "alerts_fetcher",
            "discussion_fetcher",
            "current_conditions_fetcher",
            "hourly_forecast_fetcher",
            "national_forecast_fetcher",
        ]

        # Stop each fetcher independently
        for fetcher_attr in fetcher_attrs:
            try:
                if hasattr(self, fetcher_attr):
                    fetcher = getattr(self, fetcher_attr)
                    if fetcher and hasattr(fetcher, "stop"):
                        logger.debug(f"Stopping {fetcher_attr}")
                        fetcher.stop()
                        logger.debug(f"{fetcher_attr} stopped successfully")
                    else:
                        logger.debug(f"{fetcher_attr} exists but has no stop method or is None")
                else:
                    logger.debug(f"{fetcher_attr} not found in instance")
            except Exception as e:
                error_msg = f"Error stopping {fetcher_attr}: {e}"
                logger.error(error_msg, exc_info=True)
                fetcher_errors.append(error_msg)
                # Continue with other fetchers even if this one fails

        # Stop timer separately from fetchers
        try:
            if hasattr(self, "timer"):
                if self.timer.IsRunning():
                    logger.debug("Stopping main timer")
                    self.timer.Stop()
                    logger.debug("Main timer stopped successfully")
                else:
                    logger.debug("Main timer exists but is not running")
            else:
                logger.debug("No main timer found in instance")
        except Exception as e:
            error_msg = f"Error stopping main timer: {e}"
            logger.error(error_msg, exc_info=True)
            fetcher_errors.append(error_msg)

        # Log summary of fetcher shutdown
        if fetcher_errors:
            logger.warning(f"Completed fetcher shutdown with {len(fetcher_errors)} errors")
        else:
            logger.debug("All fetchers and timers stopped successfully")
