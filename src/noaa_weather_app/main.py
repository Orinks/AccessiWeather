"""Main entry point for NOAA Weather App

This module provides the main entry point for running the application.
"""

import wx
import logging
import sys
import os
from typing import Optional

from noaa_weather_app.gui import WeatherApp
from noaa_weather_app.location import LocationManager


def setup_logging(config_dir: Optional[str] = None):
    """Set up logging for the application
    
    Args:
        config_dir: Configuration directory, defaults to ~/.noaa_weather_app
    """
    if config_dir is None:
        config_dir = os.path.expanduser("~/.noaa_weather_app")
    
    os.makedirs(config_dir, exist_ok=True)
    log_file = os.path.join(config_dir, "app.log")
    
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )


def main(config_dir: Optional[str] = None):
    """Main entry point for the application
    
    Args:
        config_dir: Configuration directory, defaults to ~/.noaa_weather_app
    """
    # Set up logging
    if config_dir is None:
        config_dir = os.path.expanduser("~/.noaa_weather_app")
        
    os.makedirs(config_dir, exist_ok=True)
    setup_logging(config_dir)
    
    # Get logger
    logger = logging.getLogger(__name__)
    logger.info(f"Starting NOAA Weather App using config directory: {config_dir}")
    
    # Create location manager with config directory
    location_manager = LocationManager(config_dir=config_dir)
    
    # Create the application
    app = wx.App(False)
    frame = WeatherApp(None)
    frame.location_manager = location_manager  # Use the configured location manager
    frame.Show()
    
    # Start the main loop
    try:
        logger.info("Entering main loop")
        app.MainLoop()
    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}")
        raise
    finally:
        logger.info("Exiting NOAA Weather App")


if __name__ == "__main__":
    sys.exit(main())
