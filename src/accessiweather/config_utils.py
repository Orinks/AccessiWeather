"""
Configuration utilities for AccessiWeather.

This module provides utilities for handling configuration paths and migration.
"""

import copy
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Any

# Get logger
logger = logging.getLogger(__name__)

_PORTABLE_MARKER_FILE = ".portable"


def _is_program_files_path(app_dir: Path) -> bool:
    """Return True when app_dir is under Program Files on Windows."""
    if platform.system() != "Windows":
        return False

    app_dir_norm = os.path.normcase(str(app_dir.resolve()))
    roots = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)")]
    for root in roots:
        if not root:
            continue
        root_norm = os.path.normcase(os.path.normpath(root))
        if app_dir_norm.startswith(root_norm + os.sep) or app_dir_norm == root_norm:
            return True
    return False


def _has_windows_uninstall_entry(executable_path: Path) -> bool:
    """Best-effort check for an uninstall registry entry for this install."""
    if platform.system() != "Windows":
        return False

    try:
        import winreg
    except Exception:
        return False

    exe_norm = os.path.normcase(str(executable_path.resolve()))
    app_dir_norm = os.path.normcase(str(executable_path.parent.resolve()))
    uninstall_roots = (
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
        r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    )

    for root in uninstall_roots:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, root) as uninstall_key:
                subkey_count, _, _ = winreg.QueryInfoKey(uninstall_key)
                for idx in range(subkey_count):
                    try:
                        subkey_name = winreg.EnumKey(uninstall_key, idx)
                        with winreg.OpenKey(uninstall_key, subkey_name) as subkey:
                            values = {}
                            value_count = winreg.QueryInfoKey(subkey)[1]
                            for v_idx in range(value_count):
                                try:
                                    name, value, _ = winreg.EnumValue(subkey, v_idx)
                                    values[name] = value
                                except OSError:
                                    continue

                            display_name = str(values.get("DisplayName", "")).lower()
                            install_location = os.path.normcase(
                                str(values.get("InstallLocation", ""))
                            )
                            display_icon = os.path.normcase(str(values.get("DisplayIcon", "")))

                            if (
                                "accessiweather" not in display_name
                                and "accessiweather" not in subkey_name.lower()
                            ):
                                continue

                            if display_icon and exe_norm in display_icon:
                                return True
                            if install_location and (
                                app_dir_norm.startswith(install_location)
                                or install_location.startswith(app_dir_norm)
                            ):
                                return True
                    except OSError:
                        continue
        except OSError:
            continue

    return False


def is_portable_mode() -> bool:
    """
    Determine if the application is running in portable mode.

    Portable mode is detected with explicit, conservative signals for frozen
    builds:

    - Preferred marker: a ``.portable`` file next to the executable.
    - Installed indicators (Program Files path / uninstall registry entry)
      override ambiguous markers.
    - Back-compat fallback: when explicit marker is absent, a neighboring
      ``config`` folder is only considered when no installed indicators are
      present.

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

    executable_path = Path(sys.executable)
    app_dir = executable_path.parent

    # Installed context should always win over marker ambiguity.
    installed_by_path = _is_program_files_path(app_dir)
    installed_by_registry = _has_windows_uninstall_entry(executable_path)
    if installed_by_path or installed_by_registry:
        logger.debug(
            "Not in portable mode: installed indicators detected "
            f"(path={installed_by_path}, registry={installed_by_registry})"
        )
        return False

    portable_marker = app_dir / _PORTABLE_MARKER_FILE
    if portable_marker.is_file():
        logger.debug(f"Portable mode detected: marker file found at {portable_marker}")
        return True

    # Conservative fallback for older portable builds.
    config_marker = app_dir / "config"
    if config_marker.is_dir():
        logger.debug(f"Portable mode detected using legacy config folder marker at {config_marker}")
        return True

    logger.debug(
        f"Not in portable mode: no marker file ({portable_marker}) or legacy config marker "
        f"({config_marker})"
    )
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
