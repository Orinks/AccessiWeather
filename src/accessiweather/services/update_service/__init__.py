"""Update service for AccessiWeather.

This module provides functionality to check for application updates
from GitHub releases and handle update notifications.

This module has been refactored for better maintainability. The functionality
is now split across multiple focused modules.
"""

import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .download_manager import DownloadManager
from .update_info import UpdateInfo
from .version_checker import VersionChecker

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_CHECK_INTERVAL_HOURS = 24
DEFAULT_AUTO_CHECK_ENABLED = True
DEFAULT_UPDATE_CHANNEL = "stable"


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

        # Initialize specialized managers
        self.version_checker = VersionChecker()
        self.download_manager = DownloadManager(progress_callback)

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

    def check_for_updates(self, channel: Optional[str] = None) -> Optional[UpdateInfo]:
        """Check for available updates.

        Args:
            channel: Update channel to check (stable or dev)

        Returns:
            UpdateInfo if update is available, None otherwise
        """
        if channel is None:
            channel = self.update_state.get("update_channel", DEFAULT_UPDATE_CHANNEL)

        latest_update = self.version_checker.check_for_updates(channel)

        # Update last check time
        self.update_state["last_check"] = datetime.now(timezone.utc).isoformat()
        self._save_update_state()

        return latest_update

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
        return self.download_manager.download_and_install_update(update_info, install_type)

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


__all__ = ["UpdateService", "UpdateInfo"]
