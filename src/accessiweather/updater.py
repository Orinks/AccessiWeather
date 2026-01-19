"""
Auto-update functionality for AccessiWeather.

This module provides automatic update checking and downloading capabilities,
integrating with GitHub Releases for version management.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# GitHub repository information
GITHUB_OWNER = "Orinks"
GITHUB_REPO = "AccessiWeather"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


@dataclass
class UpdateInfo:
    """Information about an available update."""

    version: str
    download_url: str
    release_notes: str
    published_at: str
    is_prerelease: bool
    file_name: str
    file_size: int | None = None


class UpdateChecker:
    """Checks for and downloads application updates from GitHub Releases."""

    def __init__(
        self,
        current_version: str,
        check_prereleases: bool = False,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the update checker.

        Args:
            current_version: The currently installed version string.
            check_prereleases: Whether to include pre-release versions.
            timeout: HTTP request timeout in seconds.

        """
        self.current_version = current_version
        self.check_prereleases = check_prereleases
        self.timeout = timeout
        self._http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": f"AccessiWeather/{self.current_version}",
                },
            )
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    @staticmethod
    def parse_version(version: str) -> tuple[int, ...]:
        """
        Parse a version string into a comparable tuple.

        Args:
            version: Version string (e.g., "1.2.3", "v1.2.3", "1.2.3.dev1").

        Returns:
            Tuple of version components for comparison.

        """
        # Remove 'v' prefix if present
        version = version.lstrip("v")

        # Handle dev/alpha/beta/rc suffixes
        base_version = version.split(".dev")[0].split("a")[0].split("b")[0].split("rc")[0]

        try:
            parts = [int(p) for p in base_version.split(".")]
            # Pad to at least 3 components
            while len(parts) < 3:
                parts.append(0)
            return tuple(parts)
        except ValueError:
            logger.warning(f"Could not parse version: {version}")
            return (0, 0, 0)

    def is_newer_version(self, remote_version: str) -> bool:
        """
        Check if a remote version is newer than the current version.

        Args:
            remote_version: The version string to compare against.

        Returns:
            True if remote_version is newer than current_version.

        """
        current = self.parse_version(self.current_version)
        remote = self.parse_version(remote_version)
        return remote > current

    async def check_for_updates(self) -> UpdateInfo | None:
        """
        Check GitHub Releases for available updates.

        Returns:
            UpdateInfo if an update is available, None otherwise.

        """
        try:
            client = await self._get_client()

            # Fetch latest release
            response = await client.get(GITHUB_API_URL)
            response.raise_for_status()
            release_data = response.json()

            tag_name = release_data.get("tag_name", "")
            remote_version = tag_name.lstrip("v")

            # Check if this is a prerelease and if we should skip it
            is_prerelease = release_data.get("prerelease", False)
            if is_prerelease and not self.check_prereleases:
                logger.info(f"Skipping prerelease version: {remote_version}")
                return None

            # Check if the remote version is newer
            if not self.is_newer_version(remote_version):
                logger.info(f"Current version {self.current_version} is up to date")
                return None

            # Find the appropriate asset for the current platform
            assets = release_data.get("assets", [])
            download_asset = self._find_platform_asset(assets)

            if download_asset is None:
                logger.warning("No suitable download found for current platform")
                return None

            return UpdateInfo(
                version=remote_version,
                download_url=download_asset["browser_download_url"],
                release_notes=release_data.get("body", ""),
                published_at=release_data.get("published_at", ""),
                is_prerelease=is_prerelease,
                file_name=download_asset["name"],
                file_size=download_asset.get("size"),
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error checking for updates: {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Network error checking for updates: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error checking for updates: {e}")
            return None

    def _find_platform_asset(self, assets: list[dict]) -> dict | None:
        """
        Find the appropriate download asset for the current platform.

        Args:
            assets: List of release assets from GitHub API.

        Returns:
            The asset dict for the current platform, or None if not found.

        """
        platform = sys.platform

        # Define platform-specific patterns
        if platform == "win32":
            # Prefer .exe installer, fallback to .zip
            patterns = [".exe", ".msi", ".zip"]
        elif platform == "darwin":
            patterns = [".dmg", ".pkg"]
        else:
            # Linux - no installer support yet
            return None

        for pattern in patterns:
            for asset in assets:
                name = asset.get("name", "").lower()
                if pattern in name:
                    return asset

        return None

    async def download_update(
        self,
        update_info: UpdateInfo,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path | None:
        """
        Download an update to a temporary location.

        Args:
            update_info: Information about the update to download.
            progress_callback: Optional callback(downloaded_bytes, total_bytes).

        Returns:
            Path to the downloaded file, or None if download failed.

        """
        try:
            client = await self._get_client()

            # Create temp file with appropriate extension
            suffix = Path(update_info.file_name).suffix
            fd, temp_path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            temp_file = Path(temp_path)

            logger.info(f"Downloading update to: {temp_file}")

            async with client.stream("GET", update_info.download_url) as response:
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0

                with temp_file.open("wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)

            logger.info(f"Download complete: {temp_file}")
            return temp_file

        except Exception as e:
            logger.error(f"Error downloading update: {e}")
            return None

    @staticmethod
    def install_update(installer_path: Path) -> bool:
        """
        Launch the installer and exit the current application.

        Args:
            installer_path: Path to the downloaded installer.

        Returns:
            True if installer was launched successfully.

        """
        try:
            if sys.platform == "win32":
                # Launch installer and exit
                if installer_path.suffix.lower() == ".exe":
                    subprocess.Popen([str(installer_path)])
                elif installer_path.suffix.lower() == ".msi":
                    subprocess.Popen(["msiexec", "/i", str(installer_path)])
                else:
                    logger.error(f"Unknown installer type: {installer_path.suffix}")
                    return False
            elif sys.platform == "darwin":
                # Open DMG on macOS
                subprocess.Popen(["open", str(installer_path)])
            else:
                logger.error("Automatic installation not supported on this platform")
                return False

            logger.info("Installer launched, application will exit")
            return True

        except Exception as e:
            logger.error(f"Error launching installer: {e}")
            return False


class AutoUpdater:
    """
    High-level auto-update manager that integrates with the application.

    This class provides a simple interface for checking updates on startup
    or periodically, and notifying the user when updates are available.
    """

    def __init__(
        self,
        current_version: str,
        check_on_startup: bool = True,
        check_interval_hours: int = 24,
        check_prereleases: bool = False,
    ) -> None:
        """
        Initialize the auto-updater.

        Args:
            current_version: Current application version.
            check_on_startup: Whether to check for updates on startup.
            check_interval_hours: Hours between automatic update checks.
            check_prereleases: Whether to include pre-release versions.

        """
        self.checker = UpdateChecker(
            current_version=current_version,
            check_prereleases=check_prereleases,
        )
        self.check_on_startup = check_on_startup
        self.check_interval_hours = check_interval_hours
        self._update_callback: Callable[[UpdateInfo], None] | None = None
        self._check_task: asyncio.Task | None = None

    def set_update_callback(self, callback: Callable[[UpdateInfo], None]) -> None:
        """Set callback to be called when an update is available."""
        self._update_callback = callback

    async def start(self) -> None:
        """Start the auto-updater (check on startup if enabled)."""
        if self.check_on_startup:
            await self._check_and_notify()

    async def stop(self) -> None:
        """Stop the auto-updater and clean up resources."""
        if self._check_task is not None:
            self._check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._check_task
        await self.checker.close()

    async def check_now(self) -> UpdateInfo | None:
        """Manually trigger an update check."""
        return await self._check_and_notify()

    async def _check_and_notify(self) -> UpdateInfo | None:
        """Check for updates and notify via callback if available."""
        update_info = await self.checker.check_for_updates()
        if update_info and self._update_callback:
            self._update_callback(update_info)
        return update_info

    async def download_and_install(
        self,
        update_info: UpdateInfo,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> bool:
        """
        Download and install an update.

        Args:
            update_info: The update to install.
            progress_callback: Optional progress callback.

        Returns:
            True if update was downloaded and installer launched.

        """
        installer_path = await self.checker.download_update(update_info, progress_callback)
        if installer_path is None:
            return False

        return self.checker.install_update(installer_path)
