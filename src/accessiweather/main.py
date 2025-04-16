"""Main entry point for AccessiWeather

This module provides the main entry point for running the application.
"""

# import pathlib # Removed as unused
import json
import logging
import os
import sys
from typing import Optional

from accessiweather.config_utils import get_config_dir
from accessiweather.data_migration import migrate_config_directory
from accessiweather.gui.app import AccessiWeatherApp
from accessiweather.gui.app_factory import create_weather_app

# Use root config for logging setup - Corrected import path
from accessiweather.logging_config import setup_logging as setup_root_logging


def main(config_dir: Optional[str] = None, debug_mode: bool = False, enable_caching: bool = True):
    """Main entry point for the application

    Args:
        config_dir: Configuration directory, defaults to ~/.accessiweather
        debug_mode: Whether to enable debug logging
        enable_caching: Whether to enable API response caching
    """
    # Set up logging using the root config
    log_level = logging.DEBUG if debug_mode else logging.INFO
    setup_root_logging(log_level=log_level)

    # Configure application directory
    config_dir = get_config_dir(config_dir)
    os.makedirs(config_dir, exist_ok=True)

    # Get logger
    logger = logging.getLogger(__name__)
    logger.info(f"Using config directory: {config_dir}")

    # Migrate data from old config directory if needed
    old_config_dir = os.path.expanduser("~/.noaa_weather_app")
    if os.path.exists(old_config_dir):
        logger.info(f"Found old config directory: {old_config_dir}")
        migration_result = migrate_config_directory(old_config_dir, config_dir)
        if migration_result:
            logger.info("Successfully migrated data from old config directory")
        else:
            logger.warning("Failed to migrate data from old config directory")

    # Load configuration
    config_file = os.path.join(config_dir, "config.json")
    config = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {str(e)}")

    # No need to create dependencies here - app_factory handles it

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


if __name__ == "__main__":
    # If run directly, debug_mode defaults to False.
    # Assumes primary execution via cli.py which handles arg parsing.
    sys.exit(main())
