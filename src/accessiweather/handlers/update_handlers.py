"""Application update and system tray event handlers for AccessiWeather."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import toga

from .. import app_helpers
from .settings_handlers import on_settings_pressed
from .weather_handlers import refresh_weather_data

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..app import AccessiWeatherApp


logger = logging.getLogger(__name__)


async def on_about_pressed(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Handle about menu item."""
    formal_name = getattr(app, "formal_name", "AccessiWeather") or "AccessiWeather"
    description = getattr(app, "description", "Simple, accessible weather application") or (
        "Simple, accessible weather application"
    )
    version_value = (
        getattr(app, "version", None) or getattr(app, "__version__", None) or "Unknown version"
    )
    version = str(version_value)

    await app.main_window.info_dialog(
        f"About {formal_name}",
        f"{formal_name} - {description}\n\n"
        "Built with BeeWare/Toga for cross-platform compatibility.\n"
        "Designed with accessibility in mind for screen reader users.\n\n"
        f"Version {version} - Simplified Architecture",
    )


async def on_check_updates_pressed(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Handle check for updates menu item."""
    if not app.update_service:
        await app.main_window.error_dialog(
            "Update Service Unavailable",
            "The update service is not available. Please check your internet connection and try again.",
        )
        return

    try:
        from ..services import sync_update_channel_to_service

        # Sync the update channel before checking for updates
        sync_update_channel_to_service(app.config_manager, app.update_service)

        app_helpers.update_status(app, "Checking for updates...")

        update_info = await app.update_service.check_for_updates()

        if update_info:
            message = (
                f"Update Available: Version {update_info.version}\n\n"
                f"Current version: 2.0\n"
                f"New version: {update_info.version}\n\n"
            )

            if update_info.release_notes:
                message += f"Release Notes:\n{update_info.release_notes[:500]}"
                if len(update_info.release_notes) > 500:
                    message += "..."

            should_download = await app.main_window.question_dialog(
                "Update Available", message + "\n\nWould you like to download this update?"
            )

            if should_download:
                await download_update(app, update_info)
            else:
                app_helpers.update_status(app, "Update check completed")
        else:
            await app.main_window.info_dialog(
                "No Updates Available", "You are running the latest version of AccessiWeather."
            )
            app_helpers.update_status(app, "No updates available")

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Update check failed: %s", exc)
        await app.main_window.error_dialog(
            "Update Check Failed",
            f"Failed to check for updates: {exc}\n\nPlease check your internet connection and try again.",
        )
        app_helpers.update_status(app, "Update check failed")


async def download_update(app: AccessiWeatherApp, update_info: Any) -> None:
    """Download an available update."""
    try:
        app_helpers.update_status(app, f"Downloading update {update_info.version}...")

        downloaded_file = await app.update_service.download_update(update_info)

        if downloaded_file:
            downloaded_path = str(downloaded_file)
            await _handle_update_completion(app, update_info.version, downloaded_path)
            app_helpers.update_status(app, f"Update {update_info.version} downloaded")
        else:
            await app.main_window.error_dialog(
                "Download Failed", "Failed to download the update. Please try again later."
            )
            app_helpers.update_status(app, "Update download failed")

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Update download failed: %s", exc)
        await app.main_window.error_dialog("Download Failed", f"Failed to download update: {exc}")
        app_helpers.update_status(app, "Update download failed")


async def _handle_update_completion(app: AccessiWeatherApp, version: str, file_path: str) -> None:
    """Handle post-download update actions based on platform and installation type."""
    import platform
    from pathlib import Path

    system = platform.system()

    if system == "Windows":
        # Use the app's portable mode flag if available, otherwise try to detect
        is_portable = getattr(app, "_portable_mode", False)
        if not is_portable:
            try:
                from ..config_utils import is_portable_mode

                is_portable = is_portable_mode()
            except Exception:
                is_portable = False

        file_ext = Path(file_path).suffix.lower()

        if is_portable and file_ext == ".zip":
            # Running from portable ZIP, offer to extract or run MSI
            message = (
                f"Update {version} has been downloaded.\n\n"
                f"Location: {file_path}\n\n"
                "You're running from a portable ZIP. Would you like to extract the update "
                "to your current folder?"
            )
            should_extract = await app.main_window.question_dialog("Update Downloaded", message)
            if should_extract:
                await _extract_portable_update(app, file_path)
        elif file_ext == ".msi":
            # MSI installer available, offer to run it
            message = (
                f"Update {version} has been downloaded.\n\n"
                f"Location: {file_path}\n\n"
                "Would you like to run the installer now?"
            )
            should_install = await app.main_window.question_dialog("Update Downloaded", message)
            if should_install:
                await _run_msi_installer(app, file_path)
        else:
            # Fallback for other file types
            await app.main_window.info_dialog(
                "Update Downloaded",
                f"Update {version} has been downloaded successfully.\n\nLocation: {file_path}",
            )
    else:
        # Non-Windows platforms
        await app.main_window.info_dialog(
            "Update Downloaded",
            f"Update {version} has been downloaded successfully.\n\nLocation: {file_path}",
        )


async def _extract_portable_update(app: AccessiWeatherApp, zip_path: str) -> None:
    """Extract portable update from ZIP and restart the application."""
    try:
        if app.update_service:
            app.update_service.schedule_portable_update_and_restart(zip_path)
        else:
            await app.main_window.error_dialog(
                "Update Error", "Update service not available. Please extract manually."
            )
    except Exception as exc:
        logger.error("Failed to extract portable update: %s", exc)
        await app.main_window.error_dialog(
            "Extraction Failed",
            f"Failed to extract the update: {exc}\n\nPlease extract manually from {zip_path}",
        )


async def _run_msi_installer(app: AccessiWeatherApp, msi_path: str) -> None:
    """Run the MSI installer and exit the application."""
    import subprocess

    try:
        # Use /norestart to prevent automatic restart, and /qn for quiet mode
        subprocess.Popen(["msiexec", "/i", msi_path, "/norestart"])
        # Give the installer a moment to start before we exit
        await app.main_window.info_dialog(
            "Installer Starting",
            "The installer is starting. The application will now close to complete the update.",
        )
        # Exit the application to allow the installer to update files
        app.request_exit()
    except Exception as exc:
        logger.error("Failed to run MSI installer: %s", exc)
        await app.main_window.error_dialog(
            "Installer Failed",
            f"Failed to start the installer: {exc}\n\n"
            f'You can manually run: msiexec /i "{msi_path}"',
        )


async def on_window_show(app: AccessiWeatherApp) -> None:
    """Handle window becoming visible and refresh weather data."""
    try:
        logger.info("Main window became visible, refreshing weather data")
        await refresh_weather_data(app)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to refresh weather on window show: %s", exc)


async def on_show_hide_window(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Toggle main window visibility from system tray."""
    try:
        if app.main_window.visible:
            app.main_window.hide()
            if app.status_icon and hasattr(app.show_hide_command, "text"):
                app.show_hide_command.text = "Show AccessiWeather"
            logger.info("Main window hidden to system tray")
        else:
            app.main_window.show()
            if app.status_icon and hasattr(app.show_hide_command, "text"):
                app.show_hide_command.text = "Hide AccessiWeather"
            logger.info("Main window restored from system tray")
            # Trigger refresh when window is shown from tray
            await on_window_show(app)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to toggle window visibility: %s", exc)


async def on_tray_refresh(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Refresh weather data from system tray."""
    try:
        logger.info("Refreshing weather data from system tray")
        await refresh_weather_data(app)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to refresh weather from system tray: %s", exc)


async def on_tray_settings(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Open settings dialog from system tray."""
    try:
        logger.info("Opening settings from system tray")
        await on_settings_pressed(app, widget)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to open settings from system tray: %s", exc)


async def on_tray_exit(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Exit application from system tray."""
    try:
        logger.info("Exiting application from system tray")
        app.request_exit()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to exit from system tray: %s", exc)


async def test_alert_notification(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Test the alert notification system (debug mode only)."""
    try:
        if app.alert_notification_system:
            success = await app.alert_notification_system.test_notification("Severe")
            if success:
                await app.main_window.info_dialog(
                    "Test Alert",
                    "Test alert notification sent successfully! Check your system notifications.",
                )
            else:
                await app.main_window.error_dialog(
                    "Test Alert Failed",
                    "Failed to send test alert notification. Check the logs for details.",
                )
        else:
            await app.main_window.error_dialog(
                "Alert System Error", "Alert notification system is not initialized."
            )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error testing alert notification: %s", exc)
        await app.main_window.error_dialog("Test Error", f"Error testing alert notification: {exc}")


def on_test_notification_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Send a test notification using desktop-notifier."""
    try:
        if app._notifier:
            app._notifier.send_notification(
                title="Test Notification",
                message="This is a test notification from AccessiWeather (Debug Mode)",
                sound_event="notify",
            )
            logger.info("Test notification sent successfully.")
            app_helpers.update_status(app, "Test notification sent.")
        else:
            logger.warning("Notifier not initialized; cannot send test notification")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to send test notification: %s", exc)
        app_helpers.update_status(app, f"Failed to send test notification: {exc}")
