"""Update service for AccessiWeather.

This module provides functionality to check for application updates
from GitHub releases and handle update notifications.
"""

import json
import logging
import os
import re
import subprocess
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from accessiweather.version import __version__

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


class UpdateService:
    """Service for checking and managing application updates."""

    def __init__(self, config_dir: str, notification_callback=None, progress_callback=None):
        """Initialize the update service.

        Args:
            config_dir: Directory to store update-related configuration
            notification_callback: Callback function for update notifications
            progress_callback: Callback function for download progress updates
        """
        self.config_dir = config_dir
        self.notification_callback = notification_callback
        self.progress_callback = progress_callback

        # Ensure config directory exists
        os.makedirs(config_dir, exist_ok=True)

        # Update state file
        self.update_state_file = os.path.join(config_dir, "update_state.json")

        # Load update state
        self.update_state = self._load_update_state()

        # Background check thread
        self._check_thread: Optional[threading.Thread] = None
        self._stop_checking = threading.Event()

    def _load_update_state(self) -> Dict[str, Any]:
        """Load update state from file."""
        try:
            if os.path.exists(self.update_state_file):
                with open(self.update_state_file, "r") as f:
                    loaded_state: Dict[str, Any] = json.load(f)
                    return loaded_state
        except Exception as e:
            logger.error(f"Failed to load update state: {e}")

        return {
            "last_check": None,
            "last_notified_version": None,
            "auto_check_enabled": DEFAULT_AUTO_CHECK_ENABLED,
            "check_interval_hours": DEFAULT_CHECK_INTERVAL_HOURS,
            "update_channel": DEFAULT_UPDATE_CHANNEL,
        }

    def _save_update_state(self):
        """Save update state to file."""
        try:
            with open(self.update_state_file, "w") as f:
                json.dump(self.update_state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save update state: {e}")

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

    def check_for_updates(self, channel: Optional[str] = None) -> Optional[UpdateInfo]:
        """Check for available updates.

        Args:
            channel: Update channel to check (stable or dev)

        Returns:
            UpdateInfo if update is available, None otherwise
        """
        if channel is None:
            channel = self.update_state.get("update_channel", DEFAULT_UPDATE_CHANNEL)

        try:
            logger.info(f"Checking for updates on {channel} channel...")

            # For dev channel, check GitHub Pages for dev builds
            if channel == UPDATE_CHANNEL_DEV:
                latest_update = self._check_dev_builds()

                # Update last check time
                self.update_state["last_check"] = datetime.now(timezone.utc).isoformat()
                self._save_update_state()

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

            # Update last check time
            self.update_state["last_check"] = datetime.now(timezone.utc).isoformat()
            self._save_update_state()

            if latest_update:
                logger.info(f"Update available: {latest_update.version}")
            else:
                logger.info("No updates available")

            return latest_update

        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            return None

    def should_check_for_updates(self) -> bool:
        """Check if it's time to check for updates based on interval."""
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

    def start_background_checking(self):
        """Start background thread for automatic update checking."""
        if self._check_thread and self._check_thread.is_alive():
            return

        self._stop_checking.clear()
        self._check_thread = threading.Thread(target=self._background_check_loop, daemon=True)
        self._check_thread.start()
        logger.info("Started background update checking")

    def stop_background_checking(self):
        """Stop background update checking."""
        self._stop_checking.set()
        if self._check_thread:
            self._check_thread.join(timeout=5)
        logger.info("Stopped background update checking")

    def _background_check_loop(self):
        """Background loop for checking updates."""
        while not self._stop_checking.is_set():
            try:
                if self.should_check_for_updates():
                    update_info = self.check_for_updates()

                    if update_info and self.notification_callback:
                        # Only notify if we haven't already notified for this version
                        last_notified = self.update_state.get("last_notified_version")
                        if last_notified != update_info.version:
                            self.notification_callback(update_info)
                            self.update_state["last_notified_version"] = update_info.version
                            self._save_update_state()

                # Wait for 1 hour before next check
                self._stop_checking.wait(3600)

            except Exception as e:
                logger.error(f"Error in background update check: {e}")
                # Wait before retrying
                self._stop_checking.wait(3600)

    def download_and_install_update(
        self, update_info: UpdateInfo, install_type: str = "installer"
    ) -> bool:
        """Download and install an update.

        Args:
            update_info: Information about the update to install
            install_type: Type of installation ("installer" or "portable")

        Returns:
            True if successful, False otherwise
        """
        try:
            # Select appropriate asset
            asset = None
            if install_type == "installer" and update_info.installer_asset:
                asset = update_info.installer_asset
            elif install_type == "portable" and update_info.portable_asset:
                asset = update_info.portable_asset

            if not asset:
                logger.error(f"No {install_type} asset found for update")
                return False

            download_url = asset.get("browser_download_url")
            if not download_url:
                logger.error("No download URL found for asset")
                return False

            # Download the file
            filename = asset.get("name", f"update_{update_info.version}")
            temp_dir = tempfile.gettempdir()
            download_path = os.path.join(temp_dir, filename)

            logger.info(f"Downloading update from {download_url}")

            response = requests.get(download_url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(download_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Report progress
                        if self.progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            try:
                                self.progress_callback(progress)
                            except Exception as e:
                                logger.warning(f"Progress callback failed: {e}")

            logger.info(f"Download completed: {download_path}")

            # Install the update
            if install_type == "installer":
                return self._install_update(download_path)
            else:
                # For portable, just notify user where file is downloaded
                logger.info(f"Portable update downloaded to: {download_path}")
                return True

        except Exception as e:
            logger.error(f"Failed to download/install update: {e}")
            return False

    def _install_update(self, installer_path: str) -> bool:
        """Install update using the downloaded installer.

        Args:
            installer_path: Path to the downloaded installer

        Returns:
            True if installation started successfully
        """
        try:
            # Run installer with silent install flags
            # The installer will handle the update process
            subprocess.Popen([installer_path, "/SILENT"], shell=True)
            logger.info(f"Started installer: {installer_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to start installer: {e}")
            return False

    def get_settings(self) -> Dict:
        """Get current update settings."""
        return {
            "auto_check_enabled": self.update_state.get(
                "auto_check_enabled", DEFAULT_AUTO_CHECK_ENABLED
            ),
            "check_interval_hours": self.update_state.get(
                "check_interval_hours", DEFAULT_CHECK_INTERVAL_HOURS
            ),
            "update_channel": self.update_state.get("update_channel", DEFAULT_UPDATE_CHANNEL),
        }

    def update_settings(self, settings: Dict):
        """Update settings and save to file."""
        self.update_state.update(settings)
        self._save_update_state()

        # Restart background checking if settings changed
        if settings.get("auto_check_enabled", False):
            self.start_background_checking()
        else:
            self.stop_background_checking()
