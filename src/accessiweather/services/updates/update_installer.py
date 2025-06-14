"""Update installation functionality for AccessiWeather.

This module provides functionality to download and install updates
from GitHub releases and development builds.
"""

import logging
import os
import subprocess
import tempfile
from typing import Callable, Optional

import requests

from .update_info import UpdateInfo

logger = logging.getLogger(__name__)


class UpdateDownloader:
    """Downloader for update files."""

    def __init__(self, progress_callback: Optional[Callable[[float], None]] = None):
        """Initialize the update downloader.

        Args:
            progress_callback: Optional callback function for download progress updates
        """
        self.progress_callback = progress_callback

    def download_update(
        self, update_info: UpdateInfo, install_type: str = "installer"
    ) -> Optional[str]:
        """Download an update file.

        Args:
            update_info: Information about the update to download
            install_type: Type of installation ("installer" or "portable")

        Returns:
            Path to downloaded file if successful, None otherwise
        """
        try:
            # Select appropriate asset
            asset = self._select_asset(update_info, install_type)
            if not asset:
                logger.error(f"No {install_type} asset found for update")
                return None

            download_url = asset.get("browser_download_url")
            if not download_url:
                logger.error("No download URL found for asset")
                return None

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
            return download_path

        except Exception as e:
            logger.error(f"Failed to download update: {e}")
            return None

    def _select_asset(self, update_info: UpdateInfo, install_type: str) -> Optional[dict]:
        """Select the appropriate asset for the installation type.

        Args:
            update_info: Information about the update
            install_type: Type of installation ("installer" or "portable")

        Returns:
            Asset dictionary if found, None otherwise
        """
        if install_type == "installer" and update_info.installer_asset:
            return update_info.installer_asset
        elif install_type == "portable" and update_info.portable_asset:
            return update_info.portable_asset
        return None


class UpdateInstaller:
    """Installer for update files."""

    def __init__(self):
        """Initialize the update installer."""
        pass

    def install_update(self, installer_path: str) -> bool:
        """Install update using the downloaded installer.

        Args:
            installer_path: Path to the downloaded installer

        Returns:
            True if installation started successfully, False otherwise
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

    def handle_portable_update(self, download_path: str) -> bool:
        """Handle portable update (just log the download location).

        Args:
            download_path: Path to the downloaded portable update

        Returns:
            True (portable updates don't need installation)
        """
        logger.info(f"Portable update downloaded to: {download_path}")
        return True


class UpdateManager:
    """Manager that coordinates downloading and installing updates."""

    def __init__(self, progress_callback: Optional[Callable[[float], None]] = None):
        """Initialize the update manager.

        Args:
            progress_callback: Optional callback function for download progress updates
        """
        self.downloader = UpdateDownloader(progress_callback)
        self.installer = UpdateInstaller()

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
            # Download the update file
            download_path = self.downloader.download_update(update_info, install_type)
            if not download_path:
                return False

            # Install the update based on type
            if install_type == "installer":
                return self.installer.install_update(download_path)
            else:
                # For portable, just notify user where file is downloaded
                return self.installer.handle_portable_update(download_path)

        except Exception as e:
            logger.error(f"Failed to download/install update: {e}")
            return False

    def download_only(
        self, update_info: UpdateInfo, install_type: str = "installer"
    ) -> Optional[str]:
        """Download an update without installing it.

        Args:
            update_info: Information about the update to download
            install_type: Type of installation ("installer" or "portable")

        Returns:
            Path to downloaded file if successful, None otherwise
        """
        return self.downloader.download_update(update_info, install_type)

    def install_from_path(self, installer_path: str) -> bool:
        """Install an update from a local file path.

        Args:
            installer_path: Path to the installer file

        Returns:
            True if installation started successfully, False otherwise
        """
        return self.installer.install_update(installer_path)
