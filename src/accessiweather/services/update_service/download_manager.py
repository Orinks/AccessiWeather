"""Download and installation manager for AccessiWeather updates.

This module handles downloading update files and managing the installation process.
"""

import logging
import os
import subprocess
import tempfile

import requests

from .update_info import UpdateInfo

logger = logging.getLogger(__name__)


class DownloadManager:
    """Handles downloading and installing updates."""

    def __init__(self, progress_callback=None):
        """Initialize the download manager.

        Args:
            progress_callback: Optional callback function for download progress updates
        """
        self.progress_callback = progress_callback

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
