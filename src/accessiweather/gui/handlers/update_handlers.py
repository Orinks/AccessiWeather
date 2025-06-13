"""Update handlers for the WeatherApp class

This module contains the update-related handlers for the WeatherApp class.
"""

import logging
import threading

import wx

from accessiweather.gui.update_dialog import UpdateNotificationDialog, UpdateProgressDialog
from accessiweather.services.update_service import UpdateService

from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppUpdateHandlers(WeatherAppHandlerBase):
    """Update handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides update-related event handlers for the WeatherApp class.
    """

    def __init__(self, *args, **kwargs):
        """Initialize update handlers."""
        super().__init__(*args, **kwargs)
        self.update_service = None
        self._init_update_service()

    def _init_update_service(self):
        """Initialize the update service."""
        try:
            # Get config directory from the main app
            config_dir = getattr(self, "_config_dir", None)
            if not config_dir:
                # Fallback to getting it from config path
                import os

                config_path = getattr(self, "_config_path", "")
                if config_path:
                    config_dir = os.path.dirname(config_path)
                else:
                    # Final fallback - use default config directory
                    from accessiweather.config_utils import get_config_dir

                    config_dir = get_config_dir()
                    logger.info(f"Using default config directory for update service: {config_dir}")

            # Initialize update service
            self.update_service = UpdateService(
                config_dir=config_dir,
                notification_callback=self._on_update_available,
                progress_callback=self._on_update_progress,
            )

            # Load settings and start background checking if enabled
            self._load_update_settings()

            logger.info("Update service initialized")

        except Exception as e:
            logger.error(f"Failed to initialize update service: {e}")

    def _load_update_settings(self):
        """Load update settings from config and apply to update service."""
        if not self.update_service:
            return

        try:
            # Get update settings from main config
            settings = self.config.get("settings", {})

            update_settings = {
                "auto_check_enabled": settings.get("auto_update_check_enabled", True),
                "check_interval_hours": settings.get("update_check_interval_hours", 24),
                "update_channel": settings.get("update_channel", "stable"),
            }

            # Update the service settings
            self.update_service.update_settings(update_settings)

            logger.debug(f"Loaded update settings: {update_settings}")

        except Exception as e:
            logger.error(f"Failed to load update settings: {e}")

    def _on_update_available(self, update_info):
        """Handle update available notification.

        Args:
            update_info: UpdateInfo object with details about the available update
        """
        try:
            # Show update notification on main thread
            wx.CallAfter(self._show_update_notification, update_info)
        except Exception as e:
            logger.error(f"Error handling update notification: {e}")

    def _on_update_progress(self, progress):
        """Handle update download progress.

        Args:
            progress: Progress percentage (0-100)
        """
        # This could be used to update a progress dialog if needed
        logger.debug(f"Update progress: {progress}%")

    def _show_update_notification(self, update_info):
        """Show update notification dialog on main thread.

        Args:
            update_info: UpdateInfo object with details about the available update
        """
        try:
            if not self.update_service:
                logger.warning("Update service not available")
                return

            # Create and show update dialog
            dialog = UpdateNotificationDialog(self, update_info, self.update_service)
            result = dialog.ShowModal()

            if result == wx.ID_YES:
                # User chose auto-install and it completed - exit app for update
                logger.info("Update installation started, closing application")
                self.Close(force=True)
            elif result == wx.ID_OK:
                # User chose manual download - browser was opened
                logger.info("User chose manual update download")
            elif result == wx.ID_IGNORE:
                # User chose to skip this version
                logger.info(f"User skipped update version {update_info.version}")
            else:
                # User cancelled or reminded later
                logger.info("User cancelled update or chose to be reminded later")

            dialog.Destroy()

        except Exception as e:
            logger.error(f"Error showing update notification: {e}")

    def OnCheckForUpdates(self, event):
        """Handle manual check for updates menu item.

        Args:
            event: The menu event
        """
        logger.info("OnCheckForUpdates called - starting manual update check")

        if not self.update_service:
            logger.error("Update service is not available")
            wx.MessageBox(
                "Update service is not available.",
                "Update Check Failed",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return

        logger.debug("Update service is available, showing progress dialog")
        # Show progress dialog
        progress_dialog = UpdateProgressDialog(self, "Checking for Updates")
        progress_dialog.Show()

        # Start check in background thread
        def check_updates():
            try:
                logger.info("Background thread: Starting update check")
                update_info = self.update_service.check_for_updates()
                logger.info(f"Background thread: Update check completed, result: {update_info is not None}")
                wx.CallAfter(self._on_manual_check_complete, progress_dialog, update_info)
            except Exception as e:
                logger.error(f"Background thread: Update check failed with error: {e}")
                wx.CallAfter(self._on_manual_check_error, progress_dialog, str(e))

        thread = threading.Thread(target=check_updates, daemon=True)
        thread.start()
        logger.debug("Background update check thread started")

    def _on_manual_check_complete(self, progress_dialog, update_info):
        """Handle manual update check completion.

        Args:
            progress_dialog: The progress dialog to close
            update_info: UpdateInfo object or None if no update available
        """
        try:
            logger.info("Manual update check completed, processing results")
            progress_dialog.Destroy()
            logger.debug("Progress dialog destroyed")

            if update_info:
                logger.info(f"Update available: version {update_info.version}")
                # Show update available dialog
                self._show_update_notification(update_info)
            else:
                logger.info("No update available, showing 'up to date' message")
                # No update available
                wx.MessageBox(
                    "You are running the latest version of AccessiWeather.",
                    "No Updates Available",
                    wx.OK | wx.ICON_INFORMATION,
                    self,
                )
                logger.debug("'No Updates Available' message box displayed")

        except Exception as e:
            logger.error(f"Error handling manual check completion: {e}")

    def _on_manual_check_error(self, progress_dialog, error_message):
        """Handle manual update check error.

        Args:
            progress_dialog: The progress dialog to close
            error_message: Error message string
        """
        try:
            logger.error(f"Manual update check failed: {error_message}")
            progress_dialog.Destroy()
            logger.debug("Progress dialog destroyed after error")

            wx.MessageBox(
                f"Failed to check for updates:\n\n{error_message}",
                "Update Check Failed",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            logger.debug("Error message box displayed")

        except Exception as e:
            logger.error(f"Error handling manual check error: {e}")

    def _update_update_settings(self, new_settings):
        """Update the update service settings when settings change.

        Args:
            new_settings: Dictionary of new settings
        """
        if not self.update_service:
            return

        try:
            # Extract update-related settings
            update_settings = {}

            if "auto_update_check_enabled" in new_settings:
                update_settings["auto_check_enabled"] = new_settings["auto_update_check_enabled"]

            if "update_check_interval_hours" in new_settings:
                update_settings["check_interval_hours"] = new_settings[
                    "update_check_interval_hours"
                ]

            if "update_channel" in new_settings:
                update_settings["update_channel"] = new_settings["update_channel"]

            if update_settings:
                self.update_service.update_settings(update_settings)
                logger.debug(f"Updated update service settings: {update_settings}")

        except Exception as e:
            logger.error(f"Failed to update update service settings: {e}")

    def cleanup_update_service(self):
        """Clean up update service resources."""
        if self.update_service:
            try:
                self.update_service.stop_background_checking()
                logger.info("Update service cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up update service: {e}")
