"""Main entry point for AccessiWeather

This module provides the main entry point for running the application.
"""

import json
import logging
import os
import sys
from typing import Optional

import wx

from accessiweather.config_utils import get_config_dir
from accessiweather.gui.app import AccessiWeatherApp
from accessiweather.gui.app_factory import create_weather_app
from accessiweather.logging_config import setup_logging as setup_root_logging
from accessiweather.utils.single_instance import SingleInstanceChecker

# Add blank line before function definition


def main(
    config_dir: Optional[str] = None,
    debug_mode: bool = False,
    enable_caching: bool = True,
    portable_mode: bool = False,
):
    """Main entry point for the application

    Args:
        config_dir: Configuration directory, defaults to ~/.accessiweather
        debug_mode: Whether to enable debug mode with additional logging and alert testing features
        enable_caching: Whether to enable API response caching
        portable_mode: Whether to run in portable mode (saves config to local directory)
    """
    # Set portable mode environment variable if requested
    if portable_mode:
        os.environ["ACCESSIWEATHER_FORCE_PORTABLE"] = "1"

    # Set up logging using the root config
    log_level = logging.DEBUG if debug_mode else logging.INFO
    setup_root_logging(log_level=log_level)

    # Get logger
    logger = logging.getLogger(__name__)

    # Log the mode we're running in
    if portable_mode:
        logger.info("Running in portable mode")
    else:
        logger.info("Running in standard mode")

    # Create a minimal wx.App instance first
    # This is required for both wx.SingleInstanceChecker and wx.MessageBox
    logger.debug("Creating wx.App instance for single instance checking...")
    temp_app = wx.App(False)

    # Check for existing instance
    instance_checker = SingleInstanceChecker()
    logger.debug("Attempting to acquire single instance lock...")
    if not instance_checker.try_acquire_lock():
        logger.info("Another instance is already running")

        # Show the user-friendly message
        wx.MessageBox(
            "AccessiWeather is already running. Please check your system tray.",
            "AccessiWeather Already Running",
            wx.OK | wx.ICON_INFORMATION,
        )

        # Clean up the temporary app
        temp_app.Destroy()
        return 1

    # If we're continuing with a new instance, destroy the temporary app
    # before creating the real one
    temp_app.Destroy()

    try:
        # Configure application directory
        config_dir = get_config_dir(config_dir)
        os.makedirs(config_dir, exist_ok=True)

        logger.info(f"Using config directory: {config_dir}")

        # Load configuration
        config_file = os.path.join(config_dir, "config.json")
        config = {}
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config: {str(e)}")

        logger.debug("Creating wx.App instance...")  # Added log
        # Create the application using our custom App class
        app = AccessiWeatherApp(False)  # False means don't redirect stdout/stderr

        # Use the app factory to create the WeatherApp with caching enabled
        config_file_path = os.path.join(config_dir, "config.json")
        frame = create_weather_app(
            parent=None,
            config=config,
            config_path=config_file_path,
            enable_caching=enable_caching,
            cache_ttl=300,  # 5 minutes default TTL
            debug_mode=debug_mode,
        )

        # Store a reference to the frame in the app
        app.frame = frame

        frame.Show()

        # Start the main loop
        try:
            logger.info("Entering main loop")
            app.MainLoop()
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            raise
        finally:
            logger.info("Exiting AccessiWeather")
            instance_checker.release_lock()

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        instance_checker.release_lock()
        return 1

    return 0


# Add blank line before if __name__ == "__main__":
if __name__ == "__main__":
    # If run directly, debug_mode defaults to False.
    # Assumes primary execution via cli.py which handles arg parsing.
    sys.exit(main())
