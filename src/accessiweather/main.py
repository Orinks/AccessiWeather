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

from accessiweather.gui import WeatherApp
from accessiweather.location import LocationManager


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
    
    # Create location manager with config directory
    location_manager = LocationManager(config_dir=config_dir)
    
    # Create the application
    app = wx.App(False)
    frame = WeatherApp(None)
    frame.location_manager = location_manager  # Use the configured location manager
    
    # Now that location manager is set, update the UI
    frame.UpdateLocationDropdown()
    frame.UpdateWeatherData()
    
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
