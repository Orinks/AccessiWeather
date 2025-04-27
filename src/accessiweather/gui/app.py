"""Custom App class for AccessiWeather

This module provides a custom App class that inherits from wx.App and
overrides the OnExit method to perform cleanup operations.
"""

import logging

import wx

from accessiweather.logging_config import setup_logging
from accessiweather.utils.thread_manager import stop_all_threads

from .weather_app import WeatherApp

# Setup logging
setup_logging()

logger = logging.getLogger(__name__)


class AccessiWeatherApp(wx.App):
    """Custom App class for AccessiWeather"""

    def __init__(self, redirect=False, filename=None, useBestVisual=False, clearSigInt=True):
        """Initialize the application

        Args:
            redirect: Whether to redirect stdout/stderr to a window
            filename: If redirect is True, redirect to this file
            useBestVisual: Whether to use the best visual on systems that support it
            clearSigInt: Whether to catch SIGINT or not
        """
        super().__init__(redirect, filename, useBestVisual, clearSigInt)
        self.frame = None  # Will store a reference to the main frame
        logger.debug("AccessiWeatherApp initialized")

    def OnInit(self):
        """Called when the application is initialized

        Returns:
            True to continue processing, False to exit
        """
        logger.debug("AccessiWeatherApp.OnInit called")
        return super().OnInit()

    def OnExit(self):
        """Clean up resources when the application exits."""
        import time

        exit_start_time = time.time()
        logging.info("[EXIT OPTIMIZATION] Application exiting. Starting cleanup process...")

        # --- Save Configuration ---
        config_start_time = time.time()
        config_save_thread = None
        top_window = self.GetTopWindow()
        if isinstance(top_window, WeatherApp):
            try:
                # Try to save config asynchronously if the method exists
                if hasattr(top_window, "_save_config_async"):
                    logging.debug("[EXIT OPTIMIZATION] Using asynchronous config save...")
                    config_save_thread = top_window._save_config_async()
                else:
                    # Fall back to synchronous save
                    logging.debug(
                        "[EXIT OPTIMIZATION] Asynchronous save not available, using synchronous save..."
                    )
                    top_window._save_config(show_errors=False)

                config_time = time.time() - config_start_time
                logging.debug(
                    f"[EXIT OPTIMIZATION] Configuration save initiated in {config_time:.3f}s"
                )
            except Exception as e:
                config_time = time.time() - config_start_time
                logging.error(
                    f"[EXIT OPTIMIZATION] Error saving configuration after {config_time:.3f}s: {e}",
                    exc_info=True,
                )
        else:
            logging.warning("Could not find WeatherApp window to save configuration.")
        # --- End Save Configuration ---

        # --- Stop All Threads ---
        threads_start_time = time.time()
        logging.debug("[EXIT OPTIMIZATION] Stopping all registered threads...")

        # Use a much shorter timeout for faster exit
        remaining_threads = stop_all_threads(timeout=0.02)

        threads_time = time.time() - threads_start_time
        if remaining_threads:
            logging.warning(
                f"[EXIT OPTIMIZATION] Thread cleanup took {threads_time:.3f}s. {len(remaining_threads)} threads did not exit cleanly: {remaining_threads}"
            )
        else:
            logging.debug(
                f"[EXIT OPTIMIZATION] Thread cleanup completed in {threads_time:.3f}s. All threads stopped successfully."
            )
        # --- End Stop All Threads ---

        # --- Wait for Config Save (if async) ---
        if config_save_thread and config_save_thread.is_alive():
            wait_start = time.time()
            logging.debug("[EXIT OPTIMIZATION] Waiting for async config save to complete...")
            # Very short timeout since we don't want to block exit for too long
            # Reduced timeout for config save thread
            config_save_thread.join(0.05)
            wait_time = time.time() - wait_start
            if config_save_thread.is_alive():
                logging.warning(
                    f"[EXIT OPTIMIZATION] Config save thread still running after {wait_time:.3f}s wait, continuing with exit anyway"
                )
            else:
                logging.debug(
                    f"[EXIT OPTIMIZATION] Config save thread completed in {wait_time:.3f}s"
                )
        # --- End Wait for Config Save ---

        # --- Process any pending events ---
        wx_start = time.time()
        try:
            # Process any remaining events to avoid error messages during exit
            self.ProcessPendingEvents()
            wx_time = time.time() - wx_start
            logging.debug(f"[EXIT OPTIMIZATION] Final event processing completed in {wx_time:.3f}s")
        except Exception as e:
            wx_time = time.time() - wx_start
            logging.error(
                f"[EXIT OPTIMIZATION] Error in final event processing after {wx_time:.3f}s: {e}"
            )
        # --- End Process Events ---

        # Allow the default exit procedure to continue
        total_time = time.time() - exit_start_time
        logging.info(
            f"[EXIT OPTIMIZATION] Cleanup completed in {total_time:.3f}s. Proceeding with default exit."
        )
        return super().OnExit()  # Ensure the base class method is called
