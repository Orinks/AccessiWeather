"""Helper utilities for the AccessiWeather application orchestrator."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .app import AccessiWeatherApp


logger = logging.getLogger(__name__)


def is_delete_key(key: object) -> bool:
    """Return True if the provided key represents the Delete key."""
    key_value = getattr(key, "value", key)
    if not isinstance(key_value, str):
        key_value = str(key_value)

    normalized = key_value.strip().lower()
    if normalized.startswith("<") and normalized.endswith(">"):
        normalized = normalized[1:-1]

    for prefix in ("key.", "vk_"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]

    return normalized in {"delete", "del"}


async def play_startup_sound(app: AccessiWeatherApp) -> None:
    """Play the application startup sound if enabled."""
    try:
        if not app.config_manager:
            logger.debug("Config manager unavailable; skipping startup sound")
            return

        config = app.config_manager.get_config()
        current_soundpack = getattr(config.settings, "sound_pack", "default")
        sound_enabled = getattr(config.settings, "sound_enabled", True)

        if sound_enabled:
            from .notifications.sound_player import play_startup_sound as _play_startup

            _play_startup(current_soundpack)
            logger.info("Played startup sound from pack: %s", current_soundpack)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to play startup sound: %s", exc)


def play_exit_sound(app: AccessiWeatherApp) -> None:
    """Play the application exit sound if enabled."""
    try:
        if not app.config_manager:
            logger.debug("Config manager unavailable; skipping exit sound")
            return

        config = app.config_manager.get_config()
        current_soundpack = getattr(config.settings, "sound_pack", "default")
        sound_enabled = getattr(config.settings, "sound_enabled", True)

        if sound_enabled:
            from .notifications.sound_player import play_exit_sound as _play_exit

            _play_exit(current_soundpack)
            logger.info("Played exit sound from pack: %s", current_soundpack)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("Failed to play exit sound: %s", exc)


def get_location_choices(app: AccessiWeatherApp) -> list[str]:
    """Return the list of available location names for selection widgets."""
    try:
        location_names = app.config_manager.get_location_names()
        return location_names if location_names else ["No locations available"]
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to get location choices: %s", exc)
        return ["Error loading locations"]


def update_location_selection(app: AccessiWeatherApp) -> None:
    """Refresh the location selection widget to reflect stored locations."""
    try:
        if not app.location_selection:
            return

        location_names = get_location_choices(app)
        app.location_selection.items = location_names

        current_location = app.config_manager.get_current_location()
        if current_location and current_location.name in location_names:
            app.location_selection.value = current_location.name
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to update location selection: %s", exc)


def update_status(app: AccessiWeatherApp, message: str) -> None:
    """Update the status label and log the message."""
    logger.info("Status: %s", message)

    # IMPORTANT: Do NOT update UI when window is hidden to prevent phantom popups on Windows
    # The WinForms backend can show the window if we modify widgets while hidden
    if not app.status_label:
        return

    if not should_show_dialog(app):
        logger.debug("Skipping status UI update - window is hidden")
        return

    try:
        app.status_label.text = message
    except Exception as exc:
        logger.debug("Failed to update status label: %s", exc)


def show_error_displays(app: AccessiWeatherApp, error_message: str) -> None:
    """Populate UI widgets with error text after a failure."""
    # Do NOT update UI when window is hidden to prevent phantom popups on Windows
    if not should_show_dialog(app):
        logger.debug("Skipping error display UI update - window is hidden")
        return

    error_text = f"Error loading weather data: {error_message}"

    if app.current_conditions_display:
        app.current_conditions_display.value = error_text

    if app.forecast_display:
        app.forecast_display.value = error_text

    if app.alerts_table:
        app.alerts_table.data = [
            {
                "alert_id": "error",
                "event": "Error",
                "severity": "N/A",
                "headline": "No alerts available due to error",
            }
        ]
        app.current_alerts_data = None

    if app.alert_details_button:
        app.alert_details_button.enabled = False


def should_show_dialog(app: AccessiWeatherApp) -> bool:
    """Check if dialogs should be shown (window is visible)."""
    try:
        if not hasattr(app, "main_window") or not app.main_window:
            return False
        # If window is hidden/minimized to tray, don't show intrusive dialogs
        return getattr(app.main_window, "visible", True)
    except Exception:
        # If we can't determine visibility, assume visible to avoid breaking user-initiated actions
        return True


def show_error_dialog(app: AccessiWeatherApp, title: str, message: str) -> None:
    """Show an error dialog, falling back to logging if window is hidden."""
    try:
        if should_show_dialog(app):
            app.main_window.error_dialog(title, message)
        else:
            # Window is hidden/minimized - log instead of showing intrusive dialog
            logger.warning("%s: %s (dialog suppressed - window hidden)", title, message)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to show error dialog: %s", exc)
        logger.error("Original error - %s: %s", title, message)


def handle_window_close(app: AccessiWeatherApp, widget) -> bool:
    """Implement minimize-to-tray semantics for the main window."""
    try:
        cfg = app.config_manager.get_config() if app.config_manager else None
        minimize_to_tray = bool(getattr(cfg.settings, "minimize_to_tray", False)) if cfg else False

        if minimize_to_tray and getattr(app, "status_icon", None):
            logger.info("Window close requested - minimizing to system tray")
            app.main_window.hide()
            if hasattr(app, "show_hide_command") and hasattr(app.show_hide_command, "text"):
                app.show_hide_command.text = "Show AccessiWeather"
            return False

        logger.info("Close requested - exiting application")
        return True
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error handling window close: %s", exc)
        return True


def handle_exit(app: AccessiWeatherApp) -> bool:
    """Perform shutdown cleanup and signal whether the app may exit."""
    try:
        logger.info("Application exit requested - performing cleanup")

        try:
            if getattr(app, "update_task", None) and not app.update_task.done():
                logger.info("Cancelling background update task")
                app.update_task.cancel()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug("Background task cancel error (non-fatal): %s", exc)

        # Close httpx client to prevent resource leaks
        try:
            weather_client = getattr(app, "weather_client", None)
            if weather_client:
                logger.debug("Closing weather client HTTP connections")
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(weather_client.close())
                else:
                    asyncio.run(weather_client.close())
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug("Weather client close error (non-fatal): %s", exc)

        play_exit_sound(app)

        if getattr(app, "single_instance_manager", None):
            try:
                logger.debug("Releasing single instance lock")
                app.single_instance_manager.release_lock()
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.debug("Single instance lock release error (non-fatal): %s", exc)

        logger.info("Application cleanup completed successfully")
        return True
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error during application exit cleanup: %s", exc)
        return True
