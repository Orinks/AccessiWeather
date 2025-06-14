"""Updates package for AccessiWeather.

This package provides functionality for checking, downloading, and installing
application updates from GitHub releases and development builds.
"""

from .update_checker import UpdateChecker, UpdateScheduler
from .update_info import (
    DEFAULT_AUTO_CHECK_ENABLED,
    DEFAULT_CHECK_INTERVAL_HOURS,
    DEFAULT_UPDATE_CHANNEL,
    UPDATE_CHANNEL_DEV,
    UPDATE_CHANNEL_STABLE,
    VALID_UPDATE_CHANNELS,
    UpdateAssetParser,
    UpdateInfo,
    VersionUtils,
)
from .update_installer import UpdateDownloader, UpdateInstaller, UpdateManager

# Re-export the main UpdateService class for backward compatibility
from .update_service import UpdateService

__all__ = [
    "UpdateService",
    "UpdateInfo",
    "UpdateChecker",
    "UpdateScheduler",
    "UpdateDownloader",
    "UpdateInstaller",
    "UpdateManager",
    "VersionUtils",
    "UpdateAssetParser",
    "UPDATE_CHANNEL_STABLE",
    "UPDATE_CHANNEL_DEV",
    "VALID_UPDATE_CHANNELS",
    "DEFAULT_CHECK_INTERVAL_HOURS",
    "DEFAULT_AUTO_CHECK_ENABLED",
    "DEFAULT_UPDATE_CHANNEL",
]
