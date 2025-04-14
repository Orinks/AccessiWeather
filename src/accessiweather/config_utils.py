"""Configuration utilities for AccessiWeather

This module provides utilities for handling configuration paths.
"""

import os
import platform
from typing import Optional


def get_config_dir(custom_dir: Optional[str] = None) -> str:
    """Get the configuration directory path

    Args:
        custom_dir: Custom directory path (optional)

    Returns:
        Path to the configuration directory
    """
    if custom_dir is not None:
        return custom_dir

    # Use %APPDATA% on Windows, ~/.accessiweather on other platforms
    if platform.system() == "Windows":
        # Use %APPDATA%\.accessiweather on Windows
        appdata = os.environ.get("APPDATA")
        if appdata:
            return os.path.join(appdata, ".accessiweather")

    # Default to ~/.accessiweather for all other cases
    return os.path.expanduser("~/.accessiweather")
