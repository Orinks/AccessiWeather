"""Exit fix for AccessiWeather.

This module provides fixes for the exit handling in AccessiWeather.
"""

import logging
import os
import threading
import time

import wx

from accessiweather.utils.exit_handler import ExitHandler
from accessiweather.utils.thread_manager import stop_all_threads

logger = logging.getLogger(__name__)


def apply_exit_fixes():
    """Apply exit fixes to the application.

    This function applies fixes to the exit handling in AccessiWeather.
    It should be called during application initialization.
    """
    logger.info("Applying exit fixes")

    # Patch wx.App.OnExit to ensure proper cleanup
    original_on_exit = wx.App.OnExit

    def patched_on_exit(self):
        """Patched OnExit method for wx.App.

        This method ensures that all resources are properly cleaned up
        before the application exits.
        """
        logger.info("[EXIT FIX] Patched OnExit called")

        # Get the app instance
        app = wx.GetApp()

        # Clean up using ExitHandler
        ExitHandler.cleanup_app(app)

        # Stop all threads
        stop_all_threads(timeout=0.1)

        # Log active threads for debugging
        active_threads = [t for t in threading.enumerate() if t != threading.current_thread()]
        if active_threads:
            logger.warning(f"[EXIT FIX] {len(active_threads)} threads still active:")
            for thread in active_threads:
                logger.warning(f"[EXIT FIX]   - {thread.name} (daemon: {thread.daemon})")

        # Schedule a force exit after a delay
        def force_exit():
            logger.warning("[EXIT FIX] Forcing exit")
            os._exit(0)

        # Only start the timer if there are non-daemon threads still running
        non_daemon_threads = [t for t in active_threads if not t.daemon]
        if non_daemon_threads:
            logger.warning(
                f"[EXIT FIX] {len(non_daemon_threads)} non-daemon threads still active, scheduling force exit"
            )
            exit_timer = threading.Timer(1.0, force_exit)
            exit_timer.daemon = True
            exit_timer.start()

        # Call the original OnExit method
        return original_on_exit(self)

    # Apply the patch
    wx.App.OnExit = patched_on_exit

    # Patch WeatherApp.OnClose to ensure proper cleanup
    from accessiweather.gui.weather_app_handlers import WeatherAppHandlers

    # We're completely replacing the method, not calling the original
    # original_on_close = WeatherAppHandlers.OnClose

    def patched_on_close(self, event, force_close=False):
        """Patched OnClose method for WeatherApp.

        This method ensures that all resources are properly cleaned up
        before the window is closed.
        """
        logger.info("[EXIT FIX] Patched OnClose called")

        # If we have a taskbar icon and we're not force closing, just hide the window
        if hasattr(self, "taskbar_icon") and self.taskbar_icon and not force_close:
            logger.debug("[EXIT FIX] Hiding window instead of closing")
            self.Hide()
            try:
                event.Veto()
            except Exception as e:
                logger.warning(f"[EXIT FIX] Could not veto close event: {e}")
            return

        # Stop all fetcher threads
        self._stop_fetcher_threads()

        # Stop the timer
        if hasattr(self, "timer") and self.timer:
            logger.debug("[EXIT FIX] Stopping timer")
            self.timer.Stop()

        # Save configuration
        if hasattr(self, "_save_config"):
            logger.debug("[EXIT FIX] Saving configuration")
            self._save_config(show_errors=False)

        # Destroy taskbar icon
        if hasattr(self, "taskbar_icon") and self.taskbar_icon:
            logger.debug("[EXIT FIX] Destroying taskbar icon")
            try:
                if hasattr(self.taskbar_icon, "RemoveIcon"):
                    self.taskbar_icon.RemoveIcon()
                self.taskbar_icon.Destroy()
                self.taskbar_icon = None
            except Exception as e:
                logger.warning(f"[EXIT FIX] Error destroying taskbar icon: {e}")

        # Process pending events
        for _ in range(2):
            wx.SafeYield()
            time.sleep(0.01)

        # Destroy the window
        logger.info("[EXIT FIX] Destroying window")
        self.Destroy()

        # Get the app instance and exit safely
        app = wx.GetApp()
        if app:
            # Schedule the exit after a short delay to allow the window to be destroyed
            def exit_app():
                logger.info("[EXIT FIX] Exiting application")
                ExitHandler.safe_exit(app)

            wx.CallAfter(exit_app)

    # Apply the patch - using setattr to avoid linter warnings
    setattr(WeatherAppHandlers, "OnClose", patched_on_close)

    logger.info("Exit fixes applied")
