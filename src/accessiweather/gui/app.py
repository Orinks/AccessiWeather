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
        """Clean up resources when the application exits.

        This method ensures all resources are properly released during application exit,
        including saving configuration and stopping background threads.

        Returns:
            The result of the parent OnExit method
        """
        logging.info("Application exit initiated")
        exit_successful = True

        try:
            # Save any pending configuration changes
            try:
                top_window = self.GetTopWindow()
                if isinstance(top_window, WeatherApp) and hasattr(top_window, "_save_config"):
                    logging.debug("Saving configuration before thread termination")
                    top_window._save_config(show_errors=False)
                    logging.debug("Configuration saved successfully")
                else:
                    logging.debug(
                        "No WeatherApp instance found or no _save_config method available"
                    )
            except Exception as e:
                logging.error(f"Error saving configuration during exit: {e}", exc_info=True)
                exit_successful = False
                # Continue with exit process even if config save fails

            # Stop all background threads
            try:
                logging.debug("Stopping all background threads")
                remaining_threads = ThreadManager.instance().stop_all_threads(
                    timeout=3.0
                )  # 3 second timeout
                if remaining_threads:
                    logging.warning(f"Some threads did not stop cleanly: {remaining_threads}")
                    exit_successful = False
                else:
                    logging.debug("All threads stopped successfully")
            except Exception as e:
                logging.error(f"Error stopping threads during exit: {e}", exc_info=True)
                exit_successful = False
                # Continue with exit process even if thread stopping fails

            # Process any remaining events
            try:
                logging.debug("Processing any pending events")
                self.ProcessPendingEvents()
                logging.debug("Pending events processed")
            except Exception as e:
                logging.error(f"Error processing pending events during exit: {e}", exc_info=True)
                exit_successful = False
                # Continue with exit process even if event processing fails
        except Exception as e:
            logging.error(f"Unexpected error during application exit: {e}", exc_info=True)
            exit_successful = False
        finally:
            # Always log exit status and call parent's OnExit
            if exit_successful:
                logging.info("Application exit completed successfully")
            else:
                logging.warning("Application exit completed with some errors")

            # Always call parent's OnExit to ensure proper cleanup
            return super().OnExit()
