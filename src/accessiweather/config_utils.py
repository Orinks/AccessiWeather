"""Configuration utilities for AccessiWeather

This module provides utilities for handling configuration paths and migration.
"""

import logging
import os
import platform
import sys
from typing import Any, Dict, Optional

# Get logger
logger = logging.getLogger(__name__)


def is_portable_mode() -> bool:
    """Determine if the application is running in portable mode

    Portable mode is detected by checking if the executable is running from a
    non-standard location (not Program Files) and if the directory is writable.

    Returns:
        True if running in portable mode, False otherwise
    """
    # If running from source code, not portable
    if not getattr(sys, "frozen", False):
        return False

    # Get the directory of the executable
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    # Check if we're running from Program Files (standard installation)
    program_files = os.environ.get("PROGRAMFILES", "Program Files")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "Program Files (x86)")

    # If we're in Program Files, we're not portable
    if program_files in app_dir or program_files_x86 in app_dir:
        return False

    # Check if the directory is writable (portable installations should be)
    try:
        test_file = os.path.join(app_dir, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except (IOError, PermissionError):
        # If we can't write to the directory, assume it's not portable
        return False


def get_config_dir(custom_dir: Optional[str] = None) -> str:
    """Get the configuration directory path

    Args:
        custom_dir: Custom directory path (optional)

    Returns:
        Path to the configuration directory
    """
    if custom_dir is not None:
        return custom_dir

    # Check if we're running in portable mode
    if is_portable_mode():
        # Get the directory of the executable
        if getattr(sys, "frozen", False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))

        # Use a 'config' directory in the application directory
        config_dir = os.path.join(app_dir, "config")
        logger.info(f"Running in portable mode, using config directory: {config_dir}")
        return config_dir

    # Use %APPDATA% on Windows, ~/.accessiweather on other platforms
    if platform.system() == "Windows":
        # Use %APPDATA%\.accessiweather on Windows
        appdata = os.environ.get("APPDATA")
        if appdata:
            return os.path.join(appdata, ".accessiweather")

    # Default to ~/.accessiweather for all other cases
    return os.path.expanduser("~/.accessiweather")


def ensure_config_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure configuration has all required default settings

    This function adds missing default settings to the configuration
    without performing any migration logic.

    Args:
        config: Configuration dictionary to update

    Returns:
        Dict: Configuration dictionary with defaults added
    """
    # Make a copy of the config to avoid modifying the original
    updated_config = config.copy()

    # Ensure settings section exists
    if "settings" not in updated_config:
        updated_config["settings"] = {}

    settings = updated_config["settings"]

    # Add data source setting if not present
    if "data_source" not in settings:
        from accessiweather.gui.settings_dialog import DEFAULT_DATA_SOURCE

        logger.info(f"Adding default data_source setting: {DEFAULT_DATA_SOURCE}")
        settings["data_source"] = DEFAULT_DATA_SOURCE

    # Ensure api_keys section exists
    if "api_keys" not in updated_config:
        logger.info("Adding api_keys section to config")
        updated_config["api_keys"] = {}

    api_keys = updated_config["api_keys"]

    # Add default OpenWeatherMap key if not present
    if "openweathermap" not in api_keys:
        logger.info("Adding default OpenWeatherMap key to config")
        api_keys["openweathermap"] = ""

    return updated_config
