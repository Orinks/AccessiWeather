"""Exit handler for AccessiWeather.

This module provides an exit handler that ensures all resources are properly
cleaned up when the application exits.
"""

import logging
import os
import threading
import time
import wx

logger = logging.getLogger(__name__)


class ExitHandler:
    """Exit handler for AccessiWeather."""

    @staticmethod
    def cleanup_threads(threads, stop_events=None, timeout=0.05):
        """Clean up threads.

        Args:
            threads: List of threads to clean up
            stop_events: List of stop events to set (optional)
            timeout: Timeout for joining threads in seconds

        Returns:
            List of threads that could not be joined
        """
        if not threads:
            return []

        # Set stop events if provided
        if stop_events:
            for event in stop_events:
                if event is not None:
                    logger.debug("[EXIT] Setting stop event for thread")
                    event.set()

        # Join threads with timeout
        remaining_threads = []
        for thread in threads:
            if thread is not None and thread.is_alive():
                logger.debug(f"[EXIT] Joining thread: {thread.name}")
                thread.join(timeout)
                if thread.is_alive():
                    logger.warning(f"[EXIT] Thread did not exit: {thread.name}")
                    remaining_threads.append(thread)
                else:
                    logger.debug(f"[EXIT] Thread successfully joined: {thread.name}")

        return remaining_threads

    @staticmethod
    def stop_timers(timers):
        """Stop timers."""
        if not timers:
            return []

        remaining_timers = []
        for timer in timers:
            if timer is not None and timer.IsRunning():
                logger.debug("[EXIT] Stopping timer")
                timer.Stop()
                if timer.IsRunning():
                    logger.warning("[EXIT] Timer did not stop")
                    remaining_timers.append(timer)
                else:
                    logger.debug("[EXIT] Timer successfully stopped")

        return remaining_timers

    @staticmethod
    def destroy_windows(windows):
        """Destroy windows."""
        if not windows:
            return []

        remaining_windows = []
        for window in windows:
            if window is not None:
                try:
                    logger.debug(f"[EXIT] Destroying window: {window}")
                    window.Destroy()
                    logger.debug("[EXIT] Window successfully destroyed")
                except Exception as e:
                    logger.error(f"[EXIT] Error destroying window: {e}")
                    remaining_windows.append(window)

        return remaining_windows

    @staticmethod
    def cleanup_app(app):
        """Clean up an application."""
        if app is None:
            return True

        logger.info("[EXIT] Starting application cleanup")
        success = True

        # Collect timers
        timers = []
        if hasattr(app, 'timer'):
            timers.append(app.timer)
        if hasattr(app, '_discussion_timer'):
            timers.append(app._discussion_timer)

        # Stop timers
        remaining_timers = ExitHandler.stop_timers(timers)
        if remaining_timers:
            logger.warning(f"[EXIT] {len(remaining_timers)} timers could not be stopped")
            success = False

        # Cancel all fetcher threads
        threads = []
        stop_events = []

        fetchers = ['forecast_fetcher', 'alerts_fetcher', 'discussion_fetcher', 'national_forecast_fetcher']
        for fetcher_name in fetchers:
            if hasattr(app, fetcher_name):
                fetcher = getattr(app, fetcher_name)
                logger.debug(f"[EXIT] Cancelling {fetcher_name}")
                try:
                    if hasattr(fetcher, 'cancel'):
                        fetcher.cancel()
                    else:
                        if hasattr(fetcher, 'thread'):
                            threads.append(fetcher.thread)
                        if hasattr(fetcher, '_stop_event'):
                            stop_events.append(fetcher._stop_event)
                except Exception as e:
                    logger.error(f"[EXIT] Error cancelling {fetcher_name}: {e}")

        # Clean up any remaining threads
        if threads:
            remaining_threads = ExitHandler.cleanup_threads(threads, stop_events)
            if remaining_threads:
                logger.warning(f"[EXIT] {len(remaining_threads)} threads could not be joined")
                success = False

        # Destroy taskbar icon
        if hasattr(app, 'taskbar_icon') and app.taskbar_icon:
            try:
                logger.debug("[EXIT] Removing and destroying taskbar icon")
                if hasattr(app.taskbar_icon, 'RemoveIcon'):
                    app.taskbar_icon.RemoveIcon()
                app.taskbar_icon.Destroy()
                app.taskbar_icon = None
                logger.debug("[EXIT] Taskbar icon successfully destroyed")
            except Exception as e:
                logger.error(f"[EXIT] Error destroying taskbar icon: {e}")
                success = False

        # Process pending events
        for _ in range(2):
            wx.SafeYield()
            time.sleep(0.01)

        logger.info("[EXIT] Application cleanup completed")
        return success

    @staticmethod
    def safe_exit(app):
        """Safely exit the application."""
        if app is None:
            return False

        logger.info("[EXIT] Starting safe exit process")
        
        # Clean up the app
        success = ExitHandler.cleanup_app(app)

        # Log all active threads
        active_threads = [t for t in threading.enumerate() if t != threading.current_thread()]
        if active_threads:
            logger.warning(f"[EXIT] Active threads before exit: {len(active_threads)}")
            for thread in active_threads:
                logger.warning(f"[EXIT] Active thread: {thread.name} (daemon: {thread.daemon})")

        # Exit the main loop
        try:
            logger.info("[EXIT] Exiting main loop")
            app.ExitMainLoop()

            def force_exit():
                logger.warning("[EXIT] Application did not exit cleanly, forcing exit")
                os._exit(0)

            # Schedule force exit after a short delay
            exit_timer = threading.Timer(0.5, force_exit)
            exit_timer.daemon = True
            exit_timer.start()

        except Exception as e:
            logger.error(f"[EXIT] Error exiting main loop: {e}")
            success = False

        logger.info("[EXIT] Safe exit process completed")
        return success
