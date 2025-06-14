"""Main update service class that combines all update functionality.

This module provides the main UpdateService class that orchestrates
update checking, downloading, and installation.
"""

import json
import logging
import os
import threading
from typing import Any, Callable, Dict, Optional

from .update_checker import UpdateChecker, UpdateScheduler
from .update_info import (
    DEFAULT_AUTO_CHECK_ENABLED,
    DEFAULT_CHECK_INTERVAL_HOURS,
    DEFAULT_UPDATE_CHANNEL,
    UpdateInfo,
)
from .update_installer import UpdateManager

logger = logging.getLogger(__name__)


class UpdateService:
    """Service for checking and managing application updates."""

    def __init__(
        self,
        config_dir: str,
        notification_callback: Optional[Callable[[UpdateInfo], None]] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ):
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

        # Initialize components
        self.checker = UpdateChecker()
        self.scheduler = UpdateScheduler(self.update_state)
        self.manager = UpdateManager(progress_callback)

        # Background check thread
        self._check_thread: Optional[threading.Thread] = None
        self._stop_checking = threading.Event()

    def _load_update_state(self) -> Dict[str, Any]:
        """Load update state from file.

        Returns:
            Dictionary containing update state
        """
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

    def check_for_updates(self, channel: Optional[str] = None) -> Optional[UpdateInfo]:
        """Check for available updates.

        Args:
            channel: Update channel to check (stable or dev)

        Returns:
            UpdateInfo if update is available, None otherwise
        """
        if channel is None:
            channel = self.update_state.get("update_channel", DEFAULT_UPDATE_CHANNEL)

        # Check for updates using the checker
        update_info = self.checker.check_for_updates(channel)

        # Update last check time
        self.scheduler.update_last_check_time()
        self._save_update_state()

        return update_info

    def should_check_for_updates(self) -> bool:
        """Check if it's time to check for updates based on interval.

        Returns:
            True if updates should be checked, False otherwise
        """
        return self.scheduler.should_check_for_updates()

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
        return self.manager.download_and_install_update(update_info, install_type)

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

    def get_settings(self) -> Dict[str, Any]:
        """Get current update settings.

        Returns:
            Dictionary containing current update settings
        """
        return {
            "auto_check_enabled": self.update_state.get(
                "auto_check_enabled", DEFAULT_AUTO_CHECK_ENABLED
            ),
            "check_interval_hours": self.update_state.get(
                "check_interval_hours", DEFAULT_CHECK_INTERVAL_HOURS
            ),
            "update_channel": self.update_state.get("update_channel", DEFAULT_UPDATE_CHANNEL),
        }

    def update_settings(self, settings: Dict[str, Any]):
        """Update settings and save to file.

        Args:
            settings: Dictionary of settings to update
        """
        self.update_state.update(settings)
        self._save_update_state()

        # Restart background checking if settings changed
        if settings.get("auto_check_enabled", False):
            self.start_background_checking()
        else:
            self.stop_background_checking()

    # Backward compatibility methods
    def _parse_version(self, version_str: str):
        """Parse version string (backward compatibility method)."""
        from .update_info import VersionUtils

        return VersionUtils.parse_version(version_str)

    def _is_newer_version(self, current_version: str, new_version: str, channel: str) -> bool:
        """Check if version is newer (backward compatibility method)."""
        from .update_info import VersionUtils

        return VersionUtils.is_newer_version(current_version, new_version, channel)

    def _check_dev_builds(self):
        """Check dev builds (backward compatibility method)."""
        return self.checker._check_dev_builds()

    def _install_update(self, installer_path: str) -> bool:
        """Install update (backward compatibility method)."""
        return self.manager.install_from_path(installer_path)
