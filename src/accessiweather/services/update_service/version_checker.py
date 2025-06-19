"""Version checking and comparison utilities for AccessiWeather updates.

This module provides functionality to parse version strings and compare
them to determine if updates are available.
"""

import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import requests

from accessiweather.version import __version__
from .update_info import UpdateInfo

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


class VersionChecker:
    """Handles version checking and comparison logic."""

    def __init__(self):
        """Initialize the version checker."""
        pass

    def _parse_version(self, version_str: str) -> Tuple[List[int], bool]:
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

    def _is_newer_version(self, current_version: str, new_version: str, channel: str) -> bool:
        """Check if new_version is newer than current_version.

        Args:
            current_version: Current application version
            new_version: Version to compare against
            channel: Update channel (stable or dev)

        Returns:
            True if new_version is newer
        """
        current_parts, current_is_dev = self._parse_version(current_version)
        new_parts, new_is_dev = self._parse_version(new_version)

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

    def _check_dev_builds(self) -> Optional[UpdateInfo]:
        """Check for dev builds from GitHub Pages.

        Returns:
            UpdateInfo if dev build is available, None otherwise
        """
        try:
            logger.info("Checking for dev builds from GitHub Pages...")

            # Fetch the GitHub Pages content
            response = requests.get(GITHUB_PAGES_URL, timeout=10)
            response.raise_for_status()

            content = response.text
            current_version = __version__

            # Parse dev build information from the HTML
            # Look for the development build section
            import re

            # Extract dev version - look for pattern in span with id="dev-version"
            dev_version_match = re.search(r'<span id="dev-version">([^<]+)</span>', content)
            if not dev_version_match:
                # Fallback: look for any dev version pattern
                dev_version_match = re.search(r"([0-9]+\.[0-9]+\.[0-9]+[^\s<]*-dev)", content)
                if not dev_version_match:
                    logger.info("No dev build version found on GitHub Pages")
                    return None

            dev_version = dev_version_match.group(1).strip()

            # Extract build date - look for span with id="dev-date"
            dev_date_match = re.search(r'<span id="dev-date">([^<]+)</span>', content)
            dev_date = dev_date_match.group(1).strip() if dev_date_match else ""

            # Extract commit hash - look for span with id="dev-commit"
            dev_commit_match = re.search(r'<span id="dev-commit">([a-f0-9]+)', content)
            dev_commit = dev_commit_match.group(1).strip() if dev_commit_match else ""

            # Check if this dev version is newer than current
            if self._is_newer_version(current_version, dev_version, UPDATE_CHANNEL_DEV):
                # Create dev build assets
                dev_assets = [
                    {
                        "name": f"AccessiWeather-{dev_version}-Setup.exe",
                        "browser_download_url": f"{DEV_BUILD_BASE_URL}/windows-installer-{dev_version}.zip",
                    },
                    {
                        "name": f"AccessiWeather-{dev_version}-Portable.zip",
                        "browser_download_url": f"{DEV_BUILD_BASE_URL}/windows-portable-{dev_version}.zip",
                    },
                ]

                return UpdateInfo(
                    version=dev_version,
                    release_url=GITHUB_PAGES_URL,
                    release_notes=f"Development build {dev_version}\nBuilt: {dev_date}\nCommit: {dev_commit[:8] if dev_commit else 'unknown'}",
                    assets=dev_assets,
                    published_date=dev_date,
                    is_prerelease=True,
                )
            else:
                logger.info(f"Dev build {dev_version} is not newer than current {current_version}")
                return None

        except Exception as e:
            logger.error(f"Failed to check dev builds: {e}")
            return None

    def check_for_updates(self, channel: str) -> Optional[UpdateInfo]:
        """Check for available updates.

        Args:
            channel: Update channel to check (stable or dev)

        Returns:
            UpdateInfo if update is available, None otherwise
        """
        try:
            logger.info(f"Checking for updates on {channel} channel...")

            # For dev channel, check GitHub Pages for dev builds
            if channel == UPDATE_CHANNEL_DEV:
                latest_update = self._check_dev_builds()

                if latest_update:
                    logger.info(f"Dev build available: {latest_update.version}")
                else:
                    logger.info("No dev builds available")

                return latest_update

            # For stable channel, check GitHub releases
            response = requests.get(RELEASES_URL, timeout=10)
            response.raise_for_status()

            releases = response.json()

            current_version = __version__
            latest_update = None

            for release in releases:
                release_version = release.get("tag_name", "").lstrip("v")
                is_prerelease = release.get("prerelease", False)

                # Skip drafts
                if release.get("draft", False):
                    continue

                # For stable channel, skip prereleases
                if channel == UPDATE_CHANNEL_STABLE and is_prerelease:
                    continue

                # Check if this version is newer
                if self._is_newer_version(current_version, release_version, channel):
                    latest_update = UpdateInfo(
                        version=release_version,
                        release_url=release.get("html_url", ""),
                        release_notes=release.get("body", ""),
                        assets=release.get("assets", []),
                        published_date=release.get("published_at", ""),
                        is_prerelease=is_prerelease,
                    )
                    break

            if latest_update:
                logger.info(f"Update available: {latest_update.version}")
            else:
                logger.info("No updates available")

            return latest_update

        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            return None
