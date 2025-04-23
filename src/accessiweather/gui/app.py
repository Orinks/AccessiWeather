"""Custom App class for AccessiWeather

This module provides a custom App class that inherits from wx.App and
overrides the OnExit method to perform cleanup operations.
"""

import logging
import wx
import sys

from accessiweather.config_utils import get_config_dir
from accessiweather.logging_config import setup_logging
from accessiweather.utils.thread_manager import stop_all_threads
from .weather_app import WeatherApp
from accessiweather.utils.single_instance import SingleInstanceChecker

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
        # Create single instance checker
        self.instance_checker = SingleInstanceChecker()
        if not self.instance_checker.try_acquire_lock():
            # Another instance is running
            wx.MessageBox(
                "AccessiWeather is already running.",
                "Already Running",
                wx.OK | wx.ICON_INFORMATION
            )
            sys.exit(1)

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
        logging.info("[EXIT] Application exiting. Starting cleanup process...")
        
        # Release single instance lock
        if hasattr(self, 'instance_checker'):
            self.instance_checker.release_lock()

        # Get the top window (WeatherApp frame)
        top_window = self.GetTopWindow()
        if isinstance(top_window, WeatherApp):
            try:
                # Stop all fetcher threads
                if hasattr(top_window, '_stop_fetcher_threads'):
                    logging.info("[EXIT] Stopping fetcher threads...")
                    top_window._stop_fetcher_threads()
                
                # Stop the update timer
                if hasattr(top_window, 'timer') and top_window.timer:
                    logging.info("[EXIT] Stopping update timer...")
                    top_window.timer.Stop()
                
                # Save config
                if hasattr(top_window, '_save_config'):
                    logging.info("[EXIT] Saving configuration...")
                    try:
                        top_window._save_config(show_errors=False)
                    except Exception as e:
                        logging.error(f"[EXIT] Error saving configuration: {e}")
                
                # Cleanup taskbar icon
                if hasattr(top_window, 'taskbar_icon') and top_window.taskbar_icon:
                    logging.info("[EXIT] Cleaning up taskbar icon...")
                    try:
                        top_window.taskbar_icon.RemoveIcon()
                        top_window.taskbar_icon.Destroy()
                        top_window.taskbar_icon = None
                    except Exception as e:
                        logging.error(f"[EXIT] Error cleaning up taskbar icon: {e}")
            except Exception as e:
                logging.error(f"[EXIT] Error during top window cleanup: {e}")

        # Stop all threads using thread manager
        from accessiweather.utils.thread_manager import stop_all_threads
        logging.info("[EXIT] Stopping all remaining threads...")
        remaining_threads = stop_all_threads(timeout=0.1)  # Short timeout for faster exit
        if remaining_threads:
            logging.warning(f"[EXIT] {len(remaining_threads)} threads did not exit cleanly: {remaining_threads}")
        
        # Process any remaining events
        try:
            self.ProcessPendingEvents()
            wx.SafeYield()
        except Exception as e:
            logging.error(f"[EXIT] Error processing final events: {e}")

        total_time = time.time() - exit_start_time
        logging.info(f"[EXIT] Cleanup completed in {total_time:.3f}s. Proceeding with default exit.")
        return super().OnExit() # Ensure the base class method is called
