"""Main module for AccessiWeather.

This module provides the main entry point and initialization.
"""

import json
import logging
import os
from typing import Optional

import wx

from accessiweather.api_client import NoaaApiClient
from accessiweather.data_migration import migrate_config_directory
from accessiweather.gui.weather_app import WeatherApp
from accessiweather.location import LocationManager
from accessiweather.logging_config import setup_logging
from accessiweather.notifications import WeatherNotifier


def run_app(config_dir: Optional[str] = None, debug_mode: bool = False) -> None:
    """Run the AccessiWeather application.

    Args:
        config_dir: Optional configuration directory path
        debug_mode: Enable debug logging if True
    """
    # Set up logging using the root config
    log_level = logging.DEBUG if debug_mode else logging.INFO
    setup_logging(log_level=log_level)

    # Configure application directory
    if config_dir is None:
        config_dir = os.path.expanduser("~/.accessiweather")

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

    # Create dependencies
    location_manager = LocationManager(config_dir=config_dir)

    # Create API client with settings
    api_settings = config.get("api_settings", {})
    api_client = NoaaApiClient(
        user_agent="AccessiWeather",
        contact_info=api_settings.get("contact_info"),
    )

    # Create notifier
    notifier = WeatherNotifier()

    # Create the application
    app = wx.App(False)
    frame = WeatherApp(
        parent=None,
        location_manager=location_manager,
        api_client=api_client,
        notifier=notifier,
        config=config,
    )

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
