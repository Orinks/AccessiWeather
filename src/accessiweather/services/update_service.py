"""Briefcase-aware update service for AccessiWeather.

This module provides update checking and management functionality specifically
designed to work with Briefcase-packaged applications and GitHub Releases.
"""

import asyncio
import json
import logging
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from .platform_detector import PlatformDetector, PlatformInfo

logger = logging.getLogger(__name__)

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
REPO_OWNER = "Orinks"
REPO_NAME = "AccessiWeather"
RELEASES_URL = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/releases"

# Update channels
UPDATE_CHANNEL_STABLE = "stable"
UPDATE_CHANNEL_DEV = "dev"

# Default settings
DEFAULT_CHECK_INTERVAL_HOURS = 24
DEFAULT_AUTO_CHECK_ENABLED = True
DEFAULT_UPDATE_CHANNEL = UPDATE_CHANNEL_STABLE


class UpdateInfo:
    """Information about an available update."""

    def __init__(
        self,
        version: str,
        download_url: str,
        release_notes: str,
        artifact_name: str,
        file_size: int = 0,
    ):
        self.version = version
        self.download_url = download_url
        self.release_notes = release_notes
        self.artifact_name = artifact_name
        self.file_size = file_size


class BriefcaseUpdateService:
    """Update service for Briefcase-packaged AccessiWeather applications."""

    def __init__(self, app, config_manager):
        """Initialize the update service.

        Args:
            app: The main Toga application instance
            config_manager: Configuration manager for settings

        """
        self.app = app
        self.config_manager = config_manager
        self.platform_detector = PlatformDetector()

        # Update state
        self.update_state_file = self._get_update_state_file()
        self.update_state = self._load_update_state()

        # HTTP client for API requests
        self.http_client = httpx.AsyncClient(
            timeout=30.0, headers={"User-Agent": "AccessiWeather/2.0"}
        )

        # Background check task
        self._check_task: asyncio.Task | None = None
        self._stop_checking = asyncio.Event()

    def _get_update_state_file(self) -> Path:
        """Get the path to the update state file."""
        config_dir = self.config_manager.config_file.parent
        return config_dir / "update_state.json"

    def _load_update_state(self) -> dict[str, Any]:
        """Load update state from file."""
        try:
            if self.update_state_file.exists():
                with open(self.update_state_file) as f:
                    return json.load(f)
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
            self.update_state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.update_state_file, "w") as f:
                json.dump(self.update_state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save update state: {e}")

    async def check_for_updates(self, channel: str | None = None) -> UpdateInfo | None:
        """Check for available updates.

        Args:
            channel: Update channel to check ('stable' or 'dev')

        Returns:
            UpdateInfo if update is available, None otherwise

        """
        if channel is None:
            channel = self.update_state.get("update_channel", DEFAULT_UPDATE_CHANNEL)

        try:
            logger.info(f"Checking for updates on {channel} channel")

            # Get platform information
            platform_info = self.platform_detector.get_platform_info()

            # Check GitHub releases
            update_info = await self._check_github_releases(platform_info, channel)

            # Update last check time
            self.update_state["last_check"] = datetime.now(UTC).isoformat()
            self._save_update_state()

            return update_info

        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            return None

    async def _check_github_releases(
        self, platform_info: PlatformInfo, channel: str
    ) -> UpdateInfo | None:
        """Check GitHub releases for updates.

        Args:
            platform_info: Platform information
            channel: Update channel

        Returns:
            UpdateInfo if update is available

        """
        try:
            # Get releases from GitHub API
            response = await self.http_client.get(RELEASES_URL)
            response.raise_for_status()
            releases = response.json()

            # Get current version
            current_version = self._get_current_version()

            # Find the latest compatible release
            for release in releases:
                if release.get("draft", False):
                    continue

                # Filter by channel
                is_prerelease = release.get("prerelease", False)
                if channel == UPDATE_CHANNEL_STABLE and is_prerelease:
                    continue

                release_version = release["tag_name"].lstrip("v")

                # Check if this is a newer version
                if not self._is_newer_version(current_version, release_version):
                    continue

                # Find appropriate artifact for this platform
                artifact_info = self._find_platform_artifact(release, platform_info)
                if artifact_info:
                    return UpdateInfo(
                        version=release_version,
                        download_url=artifact_info["download_url"],
                        release_notes=release.get("body", ""),
                        artifact_name=artifact_info["name"],
                        file_size=artifact_info.get("size", 0),
                    )

            logger.info("No updates available")
            return None

        except Exception as e:
            logger.error(f"Failed to check GitHub releases: {e}")
            return None

    def _find_platform_artifact(self, release: dict, platform_info: PlatformInfo) -> dict | None:
        """Find the appropriate artifact for the current platform.

        Args:
            release: GitHub release data
            platform_info: Platform information

        Returns:
            Artifact information if found

        """
        assets = release.get("assets", [])

        # Get expected artifact names for this platform
        artifacts = self.platform_detector.get_update_artifacts(release["tag_name"].lstrip("v"))

        # Prefer portable version if we're running portable and can update
        if platform_info.deployment_type == "portable" and platform_info.update_capable:
            preferred_artifact = artifacts.get("portable")
        else:
            preferred_artifact = artifacts.get("installer")

        # Look for the preferred artifact first
        for asset in assets:
            if asset["name"] == preferred_artifact:
                return {
                    "name": asset["name"],
                    "download_url": asset["browser_download_url"],
                    "size": asset["size"],
                }

        # Fallback to any compatible artifact
        for asset in assets:
            asset_name = asset["name"].lower()
            platform_name = platform_info.platform

            # Platform-specific matching
            if platform_name == "windows" and (".msi" in asset_name or ".zip" in asset_name):
                if "windows" in asset_name or "win" in asset_name or "setup" in asset_name:
                    return {
                        "name": asset["name"],
                        "download_url": asset["browser_download_url"],
                        "size": asset["size"],
                    }
            elif platform_name == "macos" and (".dmg" in asset_name or ".zip" in asset_name):
                if "macos" in asset_name or "mac" in asset_name or "darwin" in asset_name:
                    return {
                        "name": asset["name"],
                        "download_url": asset["browser_download_url"],
                        "size": asset["size"],
                    }
            elif platform_name == "linux" and (".deb" in asset_name or ".appimage" in asset_name):
                if "linux" in asset_name or ".deb" in asset_name or ".appimage" in asset_name:
                    return {
                        "name": asset["name"],
                        "download_url": asset["browser_download_url"],
                        "size": asset["size"],
                    }

        return None

    def _get_current_version(self) -> str:
        """Get the current application version."""
        try:
            from accessiweather.version import __version__

            return __version__
        except ImportError:
            logger.warning("Could not import version, using default")
            return "0.0.0"

    def _is_newer_version(self, current: str, new: str) -> bool:
        """Check if new version is newer than current version.

        Args:
            current: Current version string
            new: New version string

        Returns:
            True if new version is newer

        """

        def parse_version(version_str: str) -> tuple:
            # Remove 'v' prefix and split by dots
            clean_version = version_str.lstrip("v").split("-")[0]
            try:
                parts = [int(x) for x in clean_version.split(".")]
                # Ensure we have at least 3 parts
                while len(parts) < 3:
                    parts.append(0)
                return tuple(parts)
            except ValueError:
                return (0, 0, 0)

        current_parts = parse_version(current)
        new_parts = parse_version(new)

        return new_parts > current_parts

    async def download_update(self, update_info: UpdateInfo, progress_callback=None) -> Path | None:
        """Download an update file.

        Args:
            update_info: Information about the update
            progress_callback: Optional callback for progress updates

        Returns:
            Path to downloaded file if successful

        """
        try:
            # Create temporary file for download
            temp_dir = Path(tempfile.gettempdir()) / "accessiweather_updates"
            temp_dir.mkdir(exist_ok=True)

            download_path = temp_dir / update_info.artifact_name

            logger.info(f"Downloading update from {update_info.download_url}")

            async with self.http_client.stream("GET", update_info.download_url) as response:
                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0

                with open(download_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            await progress_callback(progress, downloaded, total_size)

            logger.info(f"Update downloaded to {download_path}")
            return download_path

        except Exception as e:
            logger.error(f"Failed to download update: {e}")
            return None

    async def apply_update(self, update_path: Path) -> bool:
        """Apply a downloaded update.

        Args:
            update_path: Path to the downloaded update file

        Returns:
            True if update was applied successfully

        """
        platform_info = self.platform_detector.get_platform_info()

        if not platform_info.update_capable:
            logger.warning("Auto-update not supported for this deployment type")
            return False

        try:
            if platform_info.deployment_type == "portable":
                return await self._apply_portable_update(update_path, platform_info)
            # For installed versions, we'll show a notification instead
            logger.info("Installed version detected, manual update required")
            return False

        except Exception as e:
            logger.error(f"Failed to apply update: {e}")
            return False

    async def _apply_portable_update(self, update_path: Path, platform_info: PlatformInfo) -> bool:
        """Apply update for portable deployment.

        Args:
            update_path: Path to the downloaded update file
            platform_info: Platform information

        Returns:
            True if update was applied successfully

        """
        try:
            app_dir = platform_info.app_directory
            backup_dir = app_dir.parent / f"{app_dir.name}_backup"

            logger.info(f"Applying portable update to {app_dir}")

            # Create backup of current installation
            if backup_dir.exists():
                import shutil

                shutil.rmtree(backup_dir)

            import shutil

            shutil.copytree(app_dir, backup_dir)

            # Extract update
            if update_path.suffix.lower() == ".zip":
                with zipfile.ZipFile(update_path, "r") as zip_ref:
                    # Extract to temporary directory first
                    temp_extract = app_dir.parent / "temp_update"
                    zip_ref.extractall(temp_extract)

                    # Find the actual app directory in the extracted content
                    extracted_items = list(temp_extract.iterdir())
                    if len(extracted_items) == 1 and extracted_items[0].is_dir():
                        extracted_app_dir = extracted_items[0]
                    else:
                        extracted_app_dir = temp_extract

                    # Replace current app directory
                    shutil.rmtree(app_dir)
                    shutil.move(str(extracted_app_dir), str(app_dir))

                    # Clean up temporary directory
                    if temp_extract.exists():
                        shutil.rmtree(temp_extract)

            logger.info("Portable update applied successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to apply portable update: {e}")
            # Restore backup if update failed
            try:
                if backup_dir.exists():
                    if app_dir.exists():
                        shutil.rmtree(app_dir)
                    shutil.move(str(backup_dir), str(app_dir))
            except Exception as restore_error:
                logger.error(f"Failed to restore backup: {restore_error}")
            return False

    def get_update_settings(self) -> dict[str, Any]:
        """Get current update settings.

        Returns:
            Dictionary of update settings

        """
        return {
            "auto_check_enabled": self.update_state.get(
                "auto_check_enabled", DEFAULT_AUTO_CHECK_ENABLED
            ),
            "check_interval_hours": self.update_state.get(
                "check_interval_hours", DEFAULT_CHECK_INTERVAL_HOURS
            ),
            "update_channel": self.update_state.get("update_channel", DEFAULT_UPDATE_CHANNEL),
            "last_check": self.update_state.get("last_check"),
            "platform_info": self.platform_detector.get_platform_info(),
        }

    def update_settings(self, settings: dict[str, Any]):
        """Update the update settings.

        Args:
            settings: Dictionary of settings to update

        """
        for key, value in settings.items():
            if key in ["auto_check_enabled", "check_interval_hours", "update_channel"]:
                self.update_state[key] = value

        self._save_update_state()

    async def cleanup(self):
        """Clean up resources."""
        if self._check_task and not self._check_task.done():
            self._stop_checking.set()
            try:
                await asyncio.wait_for(self._check_task, timeout=5.0)
            except TimeoutError:
                self._check_task.cancel()

        await self.http_client.aclose()
