"""Custom App class for AccessiWeather

This module provides a custom App class that inherits from wx.App and
overrides the OnExit method to perform cleanup operations.
"""

import logging

import wx

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
        """Called when the application is about to exit

        This method is called after all windows have been destroyed.
        It's a good place to perform final cleanup operations.

        Returns:
            The exit code (0 for success)
        """
        logger.info("Application is exiting, performing final cleanup")

        # Note: By this point, all windows have been destroyed
        # Any cleanup that requires UI elements should be done in the
        # WeatherApp.OnClose method instead

        # Perform any additional cleanup here that doesn't require UI elements
        # For example, closing database connections, network connections, etc.

        # Log the exit
        logger.info("AccessiWeather application exit complete")

        # Call the parent class OnExit
        return super().OnExit()
