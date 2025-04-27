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
    """Exit handler for AccessiWeather.

    This class provides methods for properly cleaning up resources when the
    application exits, including stopping timers, joining threads, and
    destroying UI elements.
    """

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
                    event.set()

        # Join threads with timeout
        remaining_threads = []
        for thread in threads:
            if thread is not None and thread.is_alive():
                logger.debug(f"[EXIT OPTIMIZATION] Joining thread: {thread.name}")
                thread.join(timeout)
                if thread.is_alive():
                    logger.warning(f"[EXIT OPTIMIZATION] Thread did not exit: {thread.name}")
                    remaining_threads.append(thread)

        return remaining_threads

    @staticmethod
    def stop_timers(timers):
        """Stop timers.

        Args:
            timers: List of timers to stop

        Returns:
            List of timers that could not be stopped
        """
        if not timers:
            return []

        remaining_timers = []
        for timer in timers:
            if timer is not None and timer.IsRunning():
                logger.debug(f"[EXIT OPTIMIZATION] Stopping timer: {timer}")
                timer.Stop()
                if timer.IsRunning():
                    logger.warning(f"[EXIT OPTIMIZATION] Timer did not stop: {timer}")
                    remaining_timers.append(timer)

        return remaining_timers

    @staticmethod
    def destroy_windows(windows):
        """Destroy windows.

        Args:
            windows: List of windows to destroy

        Returns:
            List of windows that could not be destroyed
        """
        if not windows:
            return []

        remaining_windows = []
        for window in windows:
            if window is not None:
                try:
                    logger.debug(f"[EXIT OPTIMIZATION] Destroying window: {window}")
                    window.Destroy()
                except Exception as e:
                    logger.warning(f"[EXIT OPTIMIZATION] Error destroying window: {e}")
                    remaining_windows.append(window)

        return remaining_windows

    @staticmethod
    def cleanup_app(app):
        """Clean up an application.

        This method performs a comprehensive cleanup of an application,
        including stopping timers, joining threads, and destroying windows.

        Args:
            app: The application to clean up

        Returns:
            True if cleanup was successful, False otherwise
        """
        if app is None:
            return True

        success = True

        # Collect timers
        timers = []
        if hasattr(app, "timer"):
            timers.append(app.timer)
        if hasattr(app, "_discussion_timer"):
            timers.append(app._discussion_timer)

        # Stop timers
        remaining_timers = ExitHandler.stop_timers(timers)
        if remaining_timers:
            logger.warning(
                f"[EXIT OPTIMIZATION] {len(remaining_timers)} timers could not be stopped"
            )
            success = False

        # Cancel all fetcher threads using their cancel methods if available
        # Otherwise, collect threads and stop events for manual cleanup
        threads = []
        stop_events = []

        # Forecast fetcher
        if hasattr(app, "forecast_fetcher"):
            if hasattr(app.forecast_fetcher, "cancel"):
                logger.debug("[EXIT OPTIMIZATION] Cancelling forecast fetcher")
                try:
                    app.forecast_fetcher.cancel()
                except Exception as e:
                    logger.error(f"[EXIT OPTIMIZATION] Error cancelling forecast fetcher: {e}")
                    # Fall back to manual cleanup
                    if hasattr(app.forecast_fetcher, "thread"):
                        threads.append(app.forecast_fetcher.thread)
                    if hasattr(app.forecast_fetcher, "_stop_event"):
                        stop_events.append(app.forecast_fetcher._stop_event)
            else:
                # Manual cleanup
                if hasattr(app.forecast_fetcher, "thread"):
                    threads.append(app.forecast_fetcher.thread)
                if hasattr(app.forecast_fetcher, "_stop_event"):
                    stop_events.append(app.forecast_fetcher._stop_event)

        # Alerts fetcher
        if hasattr(app, "alerts_fetcher"):
            if hasattr(app.alerts_fetcher, "cancel"):
                logger.debug("[EXIT OPTIMIZATION] Cancelling alerts fetcher")
                try:
                    app.alerts_fetcher.cancel()
                except Exception as e:
                    logger.error(f"[EXIT OPTIMIZATION] Error cancelling alerts fetcher: {e}")
                    # Fall back to manual cleanup
                    if hasattr(app.alerts_fetcher, "thread"):
                        threads.append(app.alerts_fetcher.thread)
                    if hasattr(app.alerts_fetcher, "_stop_event"):
                        stop_events.append(app.alerts_fetcher._stop_event)
            else:
                # Manual cleanup
                if hasattr(app.alerts_fetcher, "thread"):
                    threads.append(app.alerts_fetcher.thread)
                if hasattr(app.alerts_fetcher, "_stop_event"):
                    stop_events.append(app.alerts_fetcher._stop_event)

        # Discussion fetcher
        if hasattr(app, "discussion_fetcher"):
            if hasattr(app.discussion_fetcher, "cancel"):
                logger.debug("[EXIT OPTIMIZATION] Cancelling discussion fetcher")
                try:
                    app.discussion_fetcher.cancel()
                except Exception as e:
                    logger.error(f"[EXIT OPTIMIZATION] Error cancelling discussion fetcher: {e}")
                    # Fall back to manual cleanup
                    if hasattr(app.discussion_fetcher, "thread"):
                        threads.append(app.discussion_fetcher.thread)
                    if hasattr(app.discussion_fetcher, "_stop_event"):
                        stop_events.append(app.discussion_fetcher._stop_event)
            else:
                # Manual cleanup
                if hasattr(app.discussion_fetcher, "thread"):
                    threads.append(app.discussion_fetcher.thread)
                if hasattr(app.discussion_fetcher, "_stop_event"):
                    stop_events.append(app.discussion_fetcher._stop_event)

        # National forecast fetcher
        if hasattr(app, "national_forecast_fetcher"):
            if hasattr(app.national_forecast_fetcher, "cancel"):
                logger.debug("[EXIT OPTIMIZATION] Cancelling national forecast fetcher")
                try:
                    app.national_forecast_fetcher.cancel()
                except Exception as e:
                    logger.error(
                        f"[EXIT OPTIMIZATION] Error cancelling national forecast fetcher: {e}"
                    )
                    # Fall back to manual cleanup
                    if hasattr(app.national_forecast_fetcher, "thread"):
                        threads.append(app.national_forecast_fetcher.thread)
                    if hasattr(app.national_forecast_fetcher, "_stop_event"):
                        stop_events.append(app.national_forecast_fetcher._stop_event)
            else:
                # Manual cleanup
                if hasattr(app.national_forecast_fetcher, "thread"):
                    threads.append(app.national_forecast_fetcher.thread)
                if hasattr(app.national_forecast_fetcher, "_stop_event"):
                    stop_events.append(app.national_forecast_fetcher._stop_event)

        # Clean up any remaining threads
        if threads:
            remaining_threads = ExitHandler.cleanup_threads(threads, stop_events)
            if remaining_threads:
                logger.warning(
                    f"[EXIT OPTIMIZATION] {len(remaining_threads)} threads could not be joined"
                )
                success = False

        # Destroy taskbar icon
        if hasattr(app, "taskbar_icon") and app.taskbar_icon:
            try:
                logger.debug("[EXIT OPTIMIZATION] Removing and destroying taskbar icon")
                # It's safer to RemoveIcon before Destroy
                if hasattr(app.taskbar_icon, "RemoveIcon"):
                    app.taskbar_icon.RemoveIcon()
                app.taskbar_icon.Destroy()
                app.taskbar_icon = None  # Clear reference
            except Exception as e:
                logger.warning(f"[EXIT OPTIMIZATION] Error destroying taskbar icon: {e}")
                success = False

        # Process pending events - reduced iterations and sleep time
        for _ in range(2):
            wx.SafeYield()
            time.sleep(0.01)

        return success

    @staticmethod
    def safe_exit(app):
        """Safely exit the application.

        This method performs a comprehensive cleanup of the application and
        then exits the main loop.

        Args:
            app: The application to exit

        Returns:
            True if exit was successful, False otherwise
        """
        if app is None:
            return False

        # Clean up the app
        success = ExitHandler.cleanup_app(app)

        # Log all active threads for debugging
        active_threads = [t for t in threading.enumerate() if t != threading.current_thread()]
        if active_threads:
            logger.warning(f"[EXIT OPTIMIZATION] Active threads before exit: {len(active_threads)}")
            for thread in active_threads:
                logger.warning(f"[EXIT OPTIMIZATION]   - {thread.name} (daemon: {thread.daemon})")

        # Exit the main loop
        try:
            logger.info("[EXIT OPTIMIZATION] Exiting main loop")
            app.ExitMainLoop()

            # Force Python to exit if we're still running after a short delay
            def force_exit():
                logger.warning("[EXIT OPTIMIZATION] Application did not exit cleanly, forcing exit")
                os._exit(0)  # Force exit - use with caution

            # Schedule force exit after a shorter delay for faster termination
            exit_timer = threading.Timer(0.5, force_exit)
            exit_timer.daemon = True
            exit_timer.start()

        except Exception as e:
            logger.error(f"[EXIT OPTIMIZATION] Error exiting main loop: {e}")
            success = False

        return success
