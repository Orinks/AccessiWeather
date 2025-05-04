"""Custom App class for AccessiWeather

This module provides a custom App class that inherits from wx.App and
overrides the OnExit method to perform cleanup operations.
"""

import logging

import wx

from accessiweather.logging_config import setup_logging
from accessiweather.utils.thread_manager import ThreadManager

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
        try:
            logging.info("Application exit initiated")

            # Save any pending configuration changes
            top_window = self.GetTopWindow()
            if isinstance(top_window, WeatherApp) and hasattr(top_window, "_save_config"):
                try:
                    logging.debug("Saving configuration before thread termination")
                    top_window._save_config(show_errors=False)
                except Exception as e:
                    logging.error(f"Error saving configuration: {e}")

            # Stop all background threads
            logging.debug("Stopping all background threads")
            ThreadManager.instance().stop_all_threads(timeout=3.0)  # 3 second timeout

            # Process any remaining events
            try:
                self.ProcessPendingEvents()
            except Exception as e:
                logging.error(f"Error processing pending events: {e}")

            logging.info("Application exit complete")
            return super().OnExit()
        except Exception as e:
            logging.error(f"Error during application exit: {e}")
            return super().OnExit()
