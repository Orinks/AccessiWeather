"""Update information and version utilities for AccessiWeather.

This module provides classes and utilities for handling update information
and version parsing/comparison.
"""

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
REPO_OWNER = "Orinks"
REPO_NAME = "AccessiWeather"
RELEASES_URL = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/releases"

# GitHub Pages configuration for dev builds
GITHUB_PAGES_URL = "https://orinks.github.io/AccessiWeather/"
DEV_BUILD_BASE_URL = "https://nightly.link/Orinks/AccessiWeather/workflows/build/dev"

# Update channels
UPDATE_CHANNEL_STABLE = "stable"
UPDATE_CHANNEL_DEV = "dev"
VALID_UPDATE_CHANNELS = [UPDATE_CHANNEL_STABLE, UPDATE_CHANNEL_DEV]

# Default settings
DEFAULT_CHECK_INTERVAL_HOURS = 24
DEFAULT_AUTO_CHECK_ENABLED = True
DEFAULT_UPDATE_CHANNEL = UPDATE_CHANNEL_STABLE


class UpdateInfo:
    """Information about an available update."""

    def __init__(
        self,
        version: str,
        release_url: str,
        release_notes: str,
        assets: List[Dict],
        published_date: str,
        is_prerelease: bool = False,
    ):
        self.version = version
        self.release_url = release_url
        self.release_notes = release_notes
        self.assets = assets
        self.published_date = published_date
        self.is_prerelease = is_prerelease

        # Parse assets for installer and portable versions
        self.installer_asset = None
        self.portable_asset = None

        for asset in assets:
            name = asset.get("name", "").lower()
            if "setup" in name and name.endswith(".exe"):
                self.installer_asset = asset
            elif "portable" in name and name.endswith(".zip"):
                self.portable_asset = asset


class VersionUtils:
    """Utilities for version parsing and comparison."""

    @staticmethod
    def parse_version(version_str: str) -> Tuple[List[int], bool]:
        """Parse version string into comparable format.

        Args:
            version_str: Version string (e.g., "0.9.3", "0.9.4-dev")

        Returns:
            Tuple of (version_parts, is_dev)
        """
        # Remove 'v' prefix if present
        version_str = version_str.lstrip("v")

        # Check if it's a dev version
        is_dev = "-dev" in version_str or "dev" in version_str.lower()

        # Extract numeric version parts
        version_clean = re.sub(r"[-.]?(dev|alpha|beta|rc).*$", "", version_str, flags=re.IGNORECASE)

        try:
            parts = [int(x) for x in version_clean.split(".")]
            # Ensure we have at least 3 parts (major.minor.patch)
            while len(parts) < 3:
                parts.append(0)
            return parts, is_dev
        except ValueError:
            logger.warning(f"Could not parse version: {version_str}")
            return [0, 0, 0], is_dev

    @staticmethod
    def is_newer_version(current_version: str, new_version: str, channel: str) -> bool:
        """Check if new_version is newer than current_version.

        Args:
            current_version: Current application version
            new_version: Version to compare against
            channel: Update channel (stable or dev)

        Returns:
            True if new_version is newer
        """
        current_parts, current_is_dev = VersionUtils.parse_version(current_version)
        new_parts, new_is_dev = VersionUtils.parse_version(new_version)

        # For stable channel, ignore dev versions
        if channel == UPDATE_CHANNEL_STABLE and new_is_dev:
            return False

        # Compare version parts
        for i in range(max(len(current_parts), len(new_parts))):
            current_part = current_parts[i] if i < len(current_parts) else 0
            new_part = new_parts[i] if i < len(new_parts) else 0

            if new_part > current_part:
                return True
            elif new_part < current_part:
                return False

        # If versions are equal, dev version is newer than stable
        if current_parts == new_parts:
            return new_is_dev and not current_is_dev

        return False


class UpdateAssetParser:
    """Parser for update assets from GitHub releases."""

    @staticmethod
    def create_dev_assets(dev_version: str) -> List[Dict[str, Any]]:
        """Create dev build assets for a given version.

        Args:
            dev_version: Development version string

        Returns:
            List of asset dictionaries for dev builds
        """
        return [
            {
                "name": f"AccessiWeather-{dev_version}-Setup.exe",
                "browser_download_url": f"{DEV_BUILD_BASE_URL}/windows-installer-{dev_version}.zip",
            },
            {
                "name": f"AccessiWeather-{dev_version}-Portable.zip",
                "browser_download_url": f"{DEV_BUILD_BASE_URL}/windows-portable-{dev_version}.zip",
            },
        ]

    @staticmethod
    def parse_assets(assets: List[Dict]) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
        """Parse assets to find installer and portable versions.

        Args:
            assets: List of asset dictionaries from GitHub API

        Returns:
            Tuple of (installer_asset, portable_asset) or (None, None) if not found
        """
        installer_asset: Dict[str, Any] | None = None
        portable_asset: Dict[str, Any] | None = None

        for asset in assets:
            name = asset.get("name", "").lower()
            if "setup" in name and name.endswith(".exe"):
                installer_asset = asset
            elif "portable" in name and name.endswith(".zip"):
                portable_asset = asset

        return installer_asset, portable_asset
