"""Helper utilities for the AccessiWeather application orchestrator."""

from __future__ import annotations

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


def is_escape_key(key: object) -> bool:
    """Return True if the provided key represents the Escape key."""
    key_value = getattr(key, "value", key)
    if not isinstance(key_value, str):
        key_value = str(key_value)

    normalized = key_value.strip().lower()
    if normalized.startswith("<") and normalized.endswith(">"):
        normalized = normalized[1:-1]

    for prefix in ("key.", "vk_"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]

    return normalized in {"escape", "esc"}


def handle_escape_key(app: AccessiWeatherApp) -> bool:
    """
    Handle Escape key press with context awareness.

    Behavior:
    - If a modal dialog is open: close the dialog (don't minimize)
    - If minimize_to_tray is enabled and system tray available: hide to tray
    - If minimize_to_tray is enabled but tray unavailable: minimize to taskbar
    - Otherwise: do nothing (let the event propagate)

    Args:
        app: The AccessiWeather application instance

    Returns:
        True if the event was handled, False to propagate

    """
    try:
        # Check if any modal dialogs are open
        # Modal dialogs in Toga are tracked via app.windows
        for window in app.windows:
            if window != app.main_window and getattr(window, "visible", False):
                # A dialog is open - don't minimize, let the dialog handle Escape
                logger.debug("Escape pressed with dialog open - not minimizing")
                return False

        # No dialogs open - handle minimize behavior
        cfg = app.config_manager.get_config() if app.config_manager else None
        minimize_to_tray = bool(getattr(cfg.settings, "minimize_to_tray", False)) if cfg else False
        system_tray_available = getattr(app, "system_tray_available", False)

        if minimize_to_tray:
            if system_tray_available and getattr(app, "status_icon", None):
                # Hide to system tray
                logger.info("Escape pressed - minimizing to system tray")
                app.main_window.hide()
                app.window_visible = False
                if hasattr(app, "show_hide_command") and hasattr(app.show_hide_command, "text"):
                    app.show_hide_command.text = "Show AccessiWeather"
                return True
            # Fallback: minimize to taskbar
            logger.info("Escape pressed - minimizing to taskbar (tray unavailable)")
            try:
                app.main_window.state = "minimized"
            except (AttributeError, NotImplementedError):
                logger.warning("Window minimize not supported on this platform")
            return True

        # minimize_to_tray not enabled - don't handle
        return False
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error handling Escape key: %s", exc)
        return False


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
    # Only update UI if the window is visible to avoid ghost notifications on Windows
    if app.status_label and should_show_dialog(app):
        app.status_label.text = message
    logger.info("Status: %s", message)


def show_error_displays(app: AccessiWeatherApp, error_message: str) -> None:
    """Populate UI widgets with error text after a failure."""
    import toga
    from toga.style import Pack

    error_text = f"Error loading weather data: {error_message}"

    if app.current_conditions_display:
        app.current_conditions_display.value = error_text

    # Handle new forecast container or legacy forecast_display
    forecast_container = getattr(app, "forecast_container", None)
    if forecast_container is not None:
        # Clear and show error in structured container
        while forecast_container.children:
            forecast_container.remove(forecast_container.children[0])
        error_label = toga.Label(error_text, style=Pack(margin_bottom=5))
        forecast_container.add(error_label)
    elif app.forecast_display:
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
    """
    Implement minimize-to-tray semantics for the main window.

    Handles window close with the following logic:
    - If minimize_to_tray is enabled AND system tray is available: hide to tray
    - If minimize_to_tray is enabled but system tray unavailable: minimize to taskbar
    - Otherwise: exit the application

    Args:
        app: The AccessiWeather application instance
        widget: The widget that triggered the close event

    Returns:
        True to allow the window to close (exit app), False to prevent closing

    """
    try:
        cfg = app.config_manager.get_config() if app.config_manager else None
        minimize_to_tray = bool(getattr(cfg.settings, "minimize_to_tray", False)) if cfg else False
        system_tray_available = getattr(app, "system_tray_available", False)

        if minimize_to_tray:
            if system_tray_available and getattr(app, "status_icon", None):
                # Hide to system tray
                logger.info("Window close requested - minimizing to system tray")
                app.main_window.hide()
                app.window_visible = False
                if hasattr(app, "show_hide_command") and hasattr(app.show_hide_command, "text"):
                    app.show_hide_command.text = "Show AccessiWeather"
                return False
            # Fallback: minimize to taskbar when system tray unavailable
            logger.info("Window close requested - minimizing to taskbar (tray unavailable)")
            try:
                app.main_window.state = "minimized"
            except (AttributeError, NotImplementedError):
                # Some platforms may not support window state
                logger.warning("Window minimize not supported on this platform")
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
