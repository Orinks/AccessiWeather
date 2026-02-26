"""
Configuration utilities for AccessiWeather.

This module provides utilities for handling configuration paths and migration.
"""

import copy
import logging
import os
import platform
import sys
from typing import Any

# Get logger
logger = logging.getLogger(__name__)


def is_portable_mode() -> bool:
    """
    Determine if the application is running in portable mode.

    Portable mode is detected by the presence of a ``config`` directory next to
    the executable (for frozen builds) or next to the current working directory
    (for source runs with ACCESSIWEATHER_FORCE_PORTABLE set).

    The portable ZIP ships with an empty ``config/`` folder pre-created inside
    it. Installed builds do not include this folder, so its presence
    unambiguously signals portable mode — no heuristics required.

    For testing purposes, portable mode can be forced by setting the
    ACCESSIWEATHER_FORCE_PORTABLE environment variable to "1" or "true".

    Returns
    -------
        True if running in portable mode, False otherwise

    """
    # Check for testing override first
    force_portable = os.environ.get("ACCESSIWEATHER_FORCE_PORTABLE", "").lower()
    if force_portable in ("1", "true", "yes"):
        logger.debug("Portable mode forced via ACCESSIWEATHER_FORCE_PORTABLE environment variable")
        return True

    # Running from source — never portable unless forced above
    if not getattr(sys, "frozen", False):
        logger.debug("Not in portable mode: running from source code")
        return False

    # Frozen build: portable mode is signalled by a 'config' folder next to the exe.
    # The portable ZIP ships with this folder pre-created; the installer does not.
    app_dir = os.path.dirname(sys.executable)
    config_marker = os.path.join(app_dir, "config")
    if os.path.isdir(config_marker):
        logger.debug(f"Portable mode detected: config marker found at {config_marker}")
        return True

    logger.debug(f"Not in portable mode: no config marker at {config_marker}")
    return False


def get_config_dir(custom_dir: str | None = None) -> str:
    """
    Get the configuration directory path.

    Args:
    ----
        custom_dir: Custom directory path (optional)

    Returns:
    -------
        Path to the configuration directory

    """
    if custom_dir is not None:
        logger.debug(f"Using custom config directory: {custom_dir}")
        return custom_dir

    # Check if we're running in portable mode
    portable_mode = is_portable_mode()
    logger.debug(f"Portable mode check result: {portable_mode}")

    if portable_mode:
        # Get the directory of the executable or source code
        if getattr(sys, "frozen", False):
            app_dir = os.path.dirname(sys.executable)
        else:
            # When running from source in forced portable mode, use the project root
            # Find the project root by looking for pyproject.toml
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = current_dir
            while project_root != os.path.dirname(project_root):  # Stop at filesystem root
                if os.path.exists(os.path.join(project_root, "pyproject.toml")):
                    break
                project_root = os.path.dirname(project_root)
            app_dir = project_root

        # Use a 'config' directory in the application directory
        config_dir = os.path.join(app_dir, "config")
        logger.info(f"Running in portable mode, using config directory: {config_dir}")
        return config_dir

    # Use %APPDATA% on Windows, ~/.accessiweather on other platforms
    if platform.system() == "Windows":
        # Use %APPDATA%\.accessiweather on Windows
        appdata = os.environ.get("APPDATA")
        if appdata:
            config_dir = os.path.join(appdata, ".accessiweather")
            logger.info(
                f"Running in standard mode on Windows, using config directory: {config_dir}"
            )
            return config_dir

    # Default to ~/.accessiweather for all other cases
    config_dir = os.path.expanduser("~/.accessiweather")
    logger.info(f"Using default config directory: {config_dir}")
    return config_dir


def ensure_config_defaults(config: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure configuration has all required default settings.

    This function adds missing default settings to the configuration
    without performing any migration logic.

    Args:
    ----
        config: Configuration dictionary to update

    Returns:
    -------
        Dict: Configuration dictionary with defaults added

    """
    # Make a deep copy of the config to avoid modifying the original
    updated_config = copy.deepcopy(config)

    # Ensure settings section exists
    if "settings" not in updated_config:
        updated_config["settings"] = {}

    settings = updated_config["settings"]

    # Add data source setting if not present
    if "data_source" not in settings:
        from accessiweather.constants import DEFAULT_DATA_SOURCE

        logger.info(f"Adding default data_source setting: {DEFAULT_DATA_SOURCE}")
        settings["data_source"] = DEFAULT_DATA_SOURCE

    # Add update settings if not present
    from accessiweather.constants import (
        AUTO_UPDATE_CHECK_KEY,
        DEFAULT_AUTO_UPDATE_CHECK,
        DEFAULT_UPDATE_CHANNEL,
        DEFAULT_UPDATE_CHECK_INTERVAL,
        UPDATE_CHANNEL_KEY,
        UPDATE_CHECK_INTERVAL_KEY,
    )

    if AUTO_UPDATE_CHECK_KEY not in settings:
        logger.info(f"Adding default {AUTO_UPDATE_CHECK_KEY} setting: {DEFAULT_AUTO_UPDATE_CHECK}")
        settings[AUTO_UPDATE_CHECK_KEY] = DEFAULT_AUTO_UPDATE_CHECK

    if UPDATE_CHECK_INTERVAL_KEY not in settings:
        logger.info(
            f"Adding default {UPDATE_CHECK_INTERVAL_KEY} setting: {DEFAULT_UPDATE_CHECK_INTERVAL}"
        )
        settings[UPDATE_CHECK_INTERVAL_KEY] = DEFAULT_UPDATE_CHECK_INTERVAL

    if UPDATE_CHANNEL_KEY not in settings:
        logger.info(f"Adding default {UPDATE_CHANNEL_KEY} setting: {DEFAULT_UPDATE_CHANNEL}")
        settings[UPDATE_CHANNEL_KEY] = DEFAULT_UPDATE_CHANNEL

    # Ensure api_keys section exists
    if "api_keys" not in updated_config:
        logger.info("Adding api_keys section to config")
        updated_config["api_keys"] = {}

    # Ensure api_settings section exists
    if "api_settings" not in updated_config:
        logger.info("Adding api_settings section to config")
        updated_config["api_settings"] = {}

    return updated_config
