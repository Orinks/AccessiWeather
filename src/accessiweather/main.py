"""Main entry point for AccessiWeather

This module provides the main entry point for running the application.
"""

import wx
import logging
import sys
import os
from typing import Optional
import importlib.util
import pathlib
import json

from accessiweather.gui.weather_app import WeatherApp
from accessiweather.location import LocationManager
from accessiweather.api_client import NoaaApiClient
from accessiweather.notifications import WeatherNotifier
from accessiweather.data_migration import migrate_config_directory


def setup_logging(debug_mode=False):
    """Set up logging for the application
    
    Args:
        debug_mode: Whether to enable debug logging
    """
    # Try to use our enhanced logging config if available
    log_level = logging.DEBUG if debug_mode else logging.INFO
    
    try:
        # First look for logging_config.py in the project root
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "logging_config.py")
        
        if os.path.exists(config_path):
            # Import the logging_config module dynamically
            spec = importlib.util.spec_from_file_location("logging_config", config_path)
            logging_config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(logging_config)
            
            # Use the enhanced logging setup
            log_dir = logging_config.setup_logging(log_level)
            logging.info(f"Using enhanced logging configuration. Log directory: {log_dir}")
            return
    except Exception as e:
        # Fall back to basic logging if there's any error
        print(f"Error loading enhanced logging configuration: {str(e)}")
        pass
    
    # Fall back to basic logging configuration
    config_dir = os.path.expanduser("~/.accessiweather")
    os.makedirs(config_dir, exist_ok=True)
    log_file = os.path.join(config_dir, "app.log")
    
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )
    logging.info(f"Using basic logging configuration. Log file: {log_file}")


def main(config_dir: Optional[str] = None, debug_mode: bool = False):
    """Main entry point for the application
    
    Args:
        config_dir: Configuration directory, defaults to ~/.accessiweather
        debug_mode: Whether to enable debug logging
    """
    # Set up logging
    setup_logging(debug_mode)
    
    # Configure application directory
    if config_dir is None:
        config_dir = os.path.expanduser("~/.accessiweather")
        
    os.makedirs(config_dir, exist_ok=True)
    
    # Get logger
    logger = logging.getLogger(__name__)
    logger.info(f"Starting AccessiWeather using config directory: {config_dir}")
    
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
            with open(config_file, 'r') as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {str(e)}")
    
    # Create dependencies
    location_manager = LocationManager(config_dir=config_dir)
    
    # Create API client with settings
    api_settings = config.get("api_settings", {})
    api_client = NoaaApiClient(
        user_agent="AccessiWeather",
        contact_info=api_settings.get("contact_info")
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
        config=config
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


if __name__ == "__main__":
    sys.exit(main())
