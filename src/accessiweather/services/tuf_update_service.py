"""TUF-enabled update service for AccessiWeather.

This module provides secure update functionality using The Update Framework (TUF)
with fallback to GitHub releases for development and testing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Try to import TUF components
try:
    from tufup.client import Client as TUFClient

    TUF_AVAILABLE = True
    logger.info("TUF (tufup) is available")
except ImportError as e:
    TUF_AVAILABLE = False
    logger.warning(f"TUF (tufup) not available - falling back to GitHub releases: {e}")


@dataclass
class UpdateInfo:
    """Information about an available update."""

    version: str
    download_url: str
    artifact_name: str
    release_notes: str
    is_prerelease: bool = False
    file_size: int | None = None
    checksum: str | None = None


@dataclass
class UpdateSettings:
    """Update service settings."""

    method: str = "github"  # "tuf" or "github"
    channel: str = "stable"  # "stable" or "dev"
    auto_check: bool = True
    check_interval_hours: int = 24
    repo_owner: str = "joshuakitchen"
    repo_name: str = "accessiweather"
    tuf_repo_url: str = "https://updates.accessiweather.app"


class TUFUpdateService:
    """Simple, clean update service with TUF support."""

    def __init__(self, app_name: str = "AccessiWeather", config_dir: Path | None = None):
        """Initialize the update service.

        Args:
            app_name: Name of the application
            config_dir: Directory for storing update configuration

        """
        self.app_name = app_name
        self.config_dir = config_dir or Path.home() / f".{app_name.lower()}"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Settings file
        self.settings_file = self.config_dir / "update_settings.json"
        self.settings = self._load_settings()

        # TUF client (initialized on demand)
        self._tuf_client: TUFClient | None = None
        self._tuf_initialized = False

        # HTTP client for GitHub API
        self._http_client = httpx.AsyncClient(
            timeout=30.0, headers={"User-Agent": f"{app_name}/1.0"}
        )

        logger.info(f"Update service initialized for {app_name}")
        logger.info(f"TUF available: {TUF_AVAILABLE}")
        logger.info(f"Current method: {self.settings.method}")

    @property
    def tuf_available(self) -> bool:
        """Check if TUF is available."""
        return TUF_AVAILABLE

    @property
    def current_method(self) -> str:
        """Get the current update method."""
        return self.settings.method

    def _load_settings(self) -> UpdateSettings:
        """Load settings from file or create defaults."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file) as f:
                    data = json.load(f)
                    return UpdateSettings(**data)
        except Exception as e:
            logger.warning(f"Failed to load settings: {e}")

        # Return defaults
        settings = UpdateSettings()
        # Use TUF if available, otherwise GitHub
        if TUF_AVAILABLE:
            settings.method = "tuf"

        self._save_settings(settings)
        return settings

    def _save_settings(self, settings: UpdateSettings) -> None:
        """Save settings to file."""
        try:
            with open(self.settings_file, "w") as f:
                json.dump(settings.__dict__, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def update_settings(self, **kwargs) -> None:
        """Update settings."""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)

        self._save_settings(self.settings)
        logger.info(f"Settings updated: {kwargs}")

    def get_settings_dict(self) -> dict[str, Any]:
        """Get settings as dictionary."""
        return {
            "method": self.settings.method,
            "channel": self.settings.channel,
            "auto_check": self.settings.auto_check,
            "check_interval_hours": self.settings.check_interval_hours,
            "tuf_available": TUF_AVAILABLE,
            "platform": {
                "system": platform.system(),
                "machine": platform.machine(),
                "python_version": platform.python_version(),
            },
        }

    async def check_for_updates(self, method: str | None = None) -> UpdateInfo | None:
        """Check for available updates.

        Args:
            method: Update method to use ("tuf" or "github"). Uses settings default if None.

        Returns:
            UpdateInfo if update available, None otherwise

        """
        check_method = method or self.settings.method

        logger.info(f"Checking for updates using method: {check_method}")

        try:
            if check_method == "tuf" and TUF_AVAILABLE:
                return await self._check_tuf_updates()
            return await self._check_github_updates()
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return None

    async def _check_tuf_updates(self) -> UpdateInfo | None:
        """Check for updates using TUF."""
        if not TUF_AVAILABLE:
            logger.warning("TUF not available")
            return None

        try:
            # Initialize TUF client if needed
            if not self._tuf_initialized:
                await self._init_tuf_client()

            if not self._tuf_client:
                logger.warning("TUF client not initialized")
                return None

            # Check for updates using TUF client
            logger.info("Checking TUF repository for updates...")

            # Use the tufup client to check for updates
            # The pre parameter can be used for pre-release channels
            pre_release = None if self.settings.channel == "stable" else self.settings.channel

            new_update = self._tuf_client.check_for_updates(pre=pre_release)

            if new_update:
                logger.info(f"TUF update found: {new_update}")

                # Convert tufup update info to our UpdateInfo format
                return UpdateInfo(
                    version=str(new_update.version),
                    download_url="",  # TUF handles downloads internally
                    artifact_name=f"{self.app_name}-{new_update.version}.tar.gz",
                    release_notes=getattr(new_update, "custom", {}).get("release_notes", ""),
                    is_prerelease=(pre_release is not None),
                )
            logger.info("No TUF updates available")
            return None

        except Exception as e:
            logger.error(f"TUF update check failed: {e}")
            return None

    async def _check_github_updates(self) -> UpdateInfo | None:
        """Check for updates using GitHub releases."""
        try:
            url = f"https://api.github.com/repos/{self.settings.repo_owner}/{self.settings.repo_name}/releases"

            # Add channel filter
            if self.settings.channel == "stable":
                url += "?per_page=10"  # Get recent releases
            else:
                url += "?per_page=20"  # Include prereleases

            logger.info(f"Checking GitHub releases: {url}")

            response = await self._http_client.get(url)
            response.raise_for_status()

            releases = response.json()

            # Filter releases based on channel
            for release in releases:
                if self.settings.channel == "stable" and release.get("prerelease", False):
                    continue

                # Find appropriate asset for current platform
                asset = self._find_platform_asset(release.get("assets", []))
                if not asset:
                    continue

                # Check if this is a newer version (simplified check)
                version = release["tag_name"].lstrip("v")

                return UpdateInfo(
                    version=version,
                    download_url=asset["browser_download_url"],
                    artifact_name=asset["name"],
                    release_notes=release.get("body", ""),
                    is_prerelease=release.get("prerelease", False),
                    file_size=asset.get("size"),
                )

            logger.info("No GitHub updates available")
            return None

        except Exception as e:
            logger.error(f"GitHub update check failed: {e}")
            return None

    def _find_platform_asset(self, assets: list) -> dict | None:
        """Find the appropriate asset for the current platform."""
        system = platform.system().lower()

        # Platform-specific patterns
        patterns = []
        if system == "windows":
            patterns = ["windows", "win", ".exe", ".msi"]
        elif system == "linux":
            patterns = ["linux", ".tar.gz", ".deb", ".rpm"]
        elif system == "darwin":
            patterns = ["macos", "darwin", ".dmg", ".pkg"]

        # Look for matching assets
        for asset in assets:
            name = asset["name"].lower()
            if any(pattern in name for pattern in patterns):
                return asset

        # Fallback to first asset
        return assets[0] if assets else None

    async def _init_tuf_client(self) -> bool:
        """Initialize TUF client."""
        if not TUF_AVAILABLE:
            return False

        try:
            # Create TUF directories
            tuf_dir = self.config_dir / "tuf"
            metadata_dir = tuf_dir / "metadata"
            targets_dir = tuf_dir / "targets"

            metadata_dir.mkdir(parents=True, exist_ok=True)
            targets_dir.mkdir(parents=True, exist_ok=True)

            # Try to copy root metadata from app bundle
            root_path = metadata_dir / "root.json"
            if not root_path.exists() and not self._copy_root_metadata(root_path):
                logger.warning("Could not find root.json - TUF client may not work properly")

            # Initialize TUF client with proper parameters
            self._tuf_client = TUFClient(
                app_name=self.app_name,
                app_install_dir=self.config_dir / "install",  # Where updates will be installed
                current_version="1.0.0",  # Current app version
                metadata_dir=metadata_dir,
                metadata_base_url=self.settings.tuf_repo_url,
                target_dir=targets_dir,
                target_base_url=self.settings.tuf_repo_url,
                refresh_required=False,
            )

            self._tuf_initialized = True
            logger.info("TUF client initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize TUF client: {e}")
            return False

    def _copy_root_metadata(self, dest_path: Path) -> bool:
        """Copy root.json from app bundle."""
        try:
            # Possible locations for root.json
            possible_locations = [
                Path(__file__).parent.parent / "resources" / "root.json",
                Path(__file__).parent.parent.parent.parent / "resources" / "root.json",
                Path(__file__).parent / "resources" / "root.json",
            ]

            for source_path in possible_locations:
                if source_path.exists():
                    import shutil

                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, dest_path)
                    logger.info(f"Copied root metadata from {source_path}")
                    return True

            logger.warning("Could not find root.json in app bundle")
            return False

        except Exception as e:
            logger.error(f"Failed to copy root metadata: {e}")
            return False

    async def download_update(
        self, update_info: UpdateInfo, dest_dir: Path | None = None
    ) -> Path | None:
        """Download an update.

        Args:
            update_info: Information about the update to download
            dest_dir: Destination directory (uses temp dir if None)

        Returns:
            Path to downloaded file, or None if failed

        """
        try:
            if dest_dir is None:
                dest_dir = Path(tempfile.gettempdir()) / "accessiweather_updates"

            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file = dest_dir / update_info.artifact_name

            logger.info(f"Downloading update to {dest_file}")

            async with self._http_client.stream("GET", update_info.download_url) as response:
                response.raise_for_status()

                with open(dest_file, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)

            logger.info(f"Update downloaded successfully: {dest_file}")
            return dest_file

        except Exception as e:
            logger.error(f"Failed to download update: {e}")
            return None

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            await self._http_client.aclose()
            logger.info("Update service cleaned up")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            # Try to close the HTTP client if it exists
            if hasattr(self, "_http_client") and self._http_client:
                asyncio.create_task(self._http_client.aclose())
        except Exception:
            pass  # Ignore errors during cleanup
