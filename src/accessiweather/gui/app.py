"""Custom App class for AccessiWeather

This module provides a custom App class that inherits from wx.App and
overrides the OnExit method to perform cleanup operations.
"""

import logging
import wx

from accessiweather.config_utils import get_config_dir
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
        logging.info("Application exiting. Cleaning up...")
        
        # --- Save Configuration ---
        top_window = self.GetTopWindow()
        if isinstance(top_window, WeatherApp):
            try:
                logging.debug("Attempting to save configuration from App.OnExit...")
                top_window._save_config() # Call the main window's save method
                logging.debug("Configuration saved successfully from App.OnExit.")
            except Exception as e:
                logging.error(f"Error saving configuration during exit: {e}", exc_info=True)
        else:
            logging.warning("Could not find WeatherApp window to save configuration.")
        # --- End Save Configuration ---
        
        # Stop any remaining threads
        logging.debug("Attempting to stop all registered threads.")
        remaining_threads = stop_all_threads(timeout=1.0) # Use the global stop function
        if remaining_threads:
            logging.warning(f"The following threads did not exit cleanly: {remaining_threads}")
        else:
            logging.debug("All registered threads stopped successfully.")

        # Allow the default exit procedure to continue
        logging.info("Cleanup complete. Proceeding with default exit.")
        return super().OnExit() # Ensure the base class method is called
