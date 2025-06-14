"""Update checking functionality for AccessiWeather.

This module provides functionality to check for updates from GitHub releases
and GitHub Pages for development builds.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

import requests

from accessiweather.version import __version__

from .update_info import (
    GITHUB_PAGES_URL,
    RELEASES_URL,
    UPDATE_CHANNEL_DEV,
    UPDATE_CHANNEL_STABLE,
    UpdateAssetParser,
    UpdateInfo,
    VersionUtils,
)

logger = logging.getLogger(__name__)


class UpdateChecker:
    """Checker for application updates from various sources."""

    def __init__(self):
        """Initialize the update checker."""
        self.version_utils = VersionUtils()
        self.asset_parser = UpdateAssetParser()

    def check_for_updates(self, channel: str) -> Optional[UpdateInfo]:
        """Check for available updates on the specified channel.

        Args:
            channel: Update channel to check (stable or dev)

        Returns:
            UpdateInfo if update is available, None otherwise
        """
        try:
            logger.info(f"Checking for updates on {channel} channel...")

            # For dev channel, check GitHub Pages for dev builds
            if channel == UPDATE_CHANNEL_DEV:
                return self._check_dev_builds()

            # For stable channel, check GitHub releases
            return self._check_stable_releases(channel)

        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            return None

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
            dev_version, dev_date, dev_commit = self._parse_dev_build_info(content)

            if not dev_version:
                logger.info("No dev build version found on GitHub Pages")
                return None

            # Check if this dev version is newer than current
            if self.version_utils.is_newer_version(
                current_version, dev_version, UPDATE_CHANNEL_DEV
            ):
                # Create dev build assets
                dev_assets = self.asset_parser.create_dev_assets(dev_version)

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

    def _check_stable_releases(self, channel: str) -> Optional[UpdateInfo]:
        """Check for stable releases from GitHub API.

        Args:
            channel: Update channel (should be stable)

        Returns:
            UpdateInfo if update is available, None otherwise
        """
        try:
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
                if self.version_utils.is_newer_version(current_version, release_version, channel):
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
            logger.error(f"Failed to check stable releases: {e}")
            return None

    def _parse_dev_build_info(self, content: str) -> tuple[str, str, str]:
        """Parse dev build information from GitHub Pages HTML content.

        Args:
            content: HTML content from GitHub Pages

        Returns:
            Tuple of (dev_version, dev_date, dev_commit)
        """
        dev_version = ""
        dev_date = ""
        dev_commit = ""

        # Extract dev version - look for pattern in span with id="dev-version"
        dev_version_match = re.search(r'<span id="dev-version">([^<]+)</span>', content)
        if not dev_version_match:
            # Fallback: look for any dev version pattern
            dev_version_match = re.search(r"([0-9]+\.[0-9]+\.[0-9]+[^\s<]*-dev)", content)

        if dev_version_match:
            dev_version = dev_version_match.group(1).strip()

        # Extract build date - look for span with id="dev-date"
        dev_date_match = re.search(r'<span id="dev-date">([^<]+)</span>', content)
        if dev_date_match:
            dev_date = dev_date_match.group(1).strip()

        # Extract commit hash - look for span with id="dev-commit"
        dev_commit_match = re.search(r'<span id="dev-commit">([a-f0-9]+)', content)
        if dev_commit_match:
            dev_commit = dev_commit_match.group(1).strip()

        return dev_version, dev_date, dev_commit


class UpdateScheduler:
    """Scheduler for determining when to check for updates."""

    def __init__(self, update_state: dict):
        """Initialize the update scheduler.

        Args:
            update_state: Dictionary containing update state information
        """
        self.update_state = update_state

    def should_check_for_updates(self) -> bool:
        """Check if it's time to check for updates based on interval.

        Returns:
            True if updates should be checked, False otherwise
        """
        from datetime import timedelta

        from .update_info import DEFAULT_AUTO_CHECK_ENABLED, DEFAULT_CHECK_INTERVAL_HOURS

        if not self.update_state.get("auto_check_enabled", DEFAULT_AUTO_CHECK_ENABLED):
            return False

        last_check_str = self.update_state.get("last_check")
        if not last_check_str:
            return True

        try:
            last_check = datetime.fromisoformat(last_check_str.replace("Z", "+00:00"))
            interval_hours = self.update_state.get(
                "check_interval_hours", DEFAULT_CHECK_INTERVAL_HOURS
            )
            next_check = last_check + timedelta(hours=interval_hours)

            return datetime.now(timezone.utc) >= next_check
        except Exception as e:
            logger.error(f"Error checking update interval: {e}")
            return True

    def update_last_check_time(self) -> str:
        """Update and return the current time as ISO format string.

        Returns:
            Current time in ISO format
        """
        current_time = datetime.now(timezone.utc).isoformat()
        self.update_state["last_check"] = current_time
        return current_time
