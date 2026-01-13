"""Helper utilities for the AccessiWeather application orchestrator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .app import AccessiWeatherApp
    from .models import WeatherData


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
    Handle Escape key press - always minimizes to background.

    Behavior:
    - If a modal dialog is open: don't minimize, let the dialog handle Escape
    - If system tray is available: hide to system tray
    - Otherwise: minimize to taskbar

    Args:
        app: The AccessiWeather application instance

    Returns:
        True if the event was handled, False to propagate

    """
    import toga.constants

    try:
        # Check if any modal dialogs are open
        # Modal dialogs in Toga are tracked via app.windows
        for window in app.windows:
            if window != app.main_window and getattr(window, "visible", False):
                # A dialog is open - don't minimize, let the dialog handle Escape
                logger.debug("Escape pressed with dialog open - not minimizing")
                return False

        # No dialogs open - minimize to background
        system_tray_available = getattr(app, "system_tray_available", False)

        if system_tray_available and getattr(app, "status_icon", None):
            # Hide to system tray
            logger.info("Escape pressed - minimizing to system tray")
            app.main_window.hide()
            app.window_visible = False
            if hasattr(app, "show_hide_command") and hasattr(app.show_hide_command, "text"):
                app.show_hide_command.text = "Show AccessiWeather"
            return True

        # Fallback: minimize to taskbar using WindowState enum
        logger.info("Escape pressed - minimizing to taskbar")
        try:
            app.main_window.state = toga.constants.WindowState.MINIMIZED
        except (AttributeError, NotImplementedError, ValueError):
            logger.warning("Window minimize not supported on this platform")
        return True
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


def _convert_alerts_to_table_data(alerts: Any) -> list[dict[str, str]]:
    """Convert WeatherAlerts to table data format with stable identifiers.

    This is a synchronous helper that mirrors the logic in weather_handlers
    but avoids circular imports by being defined here.
    """
    if not alerts or not getattr(alerts, "has_alerts", lambda: False)():
        return []

    table_data: list[dict[str, str]] = []
    active_alerts = getattr(alerts, "get_active_alerts", lambda: [])()

    for alert in active_alerts[:10]:
        event = getattr(alert, "event", None) or "Weather Alert"
        severity = getattr(alert, "severity", None) or "Unknown"
        headline = getattr(alert, "headline", None) or "No headline available"

        if len(headline) > 80:
            headline = headline[:77] + "..."

        alert_id = (
            getattr(alert, "get_unique_id", lambda: "unknown")()
            if callable(getattr(alert, "get_unique_id", None))
            else "unknown"
        )

        table_data.append(
            {
                "alert_id": alert_id,
                "event": event,
                "severity": severity,
                "headline": headline,
            }
        )

    return table_data


def sync_update_weather_displays(app: AccessiWeatherApp, weather_data: WeatherData) -> None:
    """Synchronously update UI widgets with weather data.

    This function is designed for immediate display during startup when cached
    data is available. It directly sets widget values without async operations
    (no notifications, no WebView updates that may require async context).

    Args:
        app: The AccessiWeather application instance
        weather_data: Weather data to display

    """
    # Skip UI updates if window is hidden to prevent phantom popups on Windows
    if not should_show_dialog(app):
        logger.debug("Skipping sync weather display updates - window is hidden")
        return

    try:
        # Use presenter to format weather data
        presentation = app.presenter.present(weather_data)

        # Update current conditions display (text-based)
        if app.current_conditions_display:
            if presentation.current_conditions:
                current_text = presentation.current_conditions.fallback_text
                trend_lines = presentation.current_conditions.trends
                if trend_lines:
                    current_text += "\n\nTrends:\n" + "\n".join(
                        f"• {trend}" for trend in trend_lines
                    )

                if presentation.status_messages:
                    status_lines = "\n".join(f"• {line}" for line in presentation.status_messages)
                    current_text += f"\n\nStatus:\n{status_lines}"

                # Add source attribution for transparency
                if presentation.source_attribution:
                    attr = presentation.source_attribution
                    if attr.summary_text:
                        current_text += f"\n\n{attr.summary_text}"
                    if attr.incomplete_sections:
                        incomplete = ", ".join(attr.incomplete_sections)
                        current_text += f"\nMissing sections: {incomplete}"

                app.current_conditions_display.value = current_text
            else:
                app.current_conditions_display.value = ""

        # Update forecast display (text-based)
        if app.forecast_display:
            if presentation.forecast:
                app.forecast_display.value = presentation.forecast.fallback_text
            else:
                app.forecast_display.value = ""

        # Update aviation display if present
        aviation_display = getattr(app, "aviation_display", None)
        if aviation_display is not None:
            if presentation.aviation:
                aviation_display.value = presentation.aviation.fallback_text
            else:
                aviation_display.value = ""

        # Update alerts table
        alerts_table_data = _convert_alerts_to_table_data(weather_data.alerts)
        if app.alerts_table:
            app.alerts_table.data = alerts_table_data

        app.current_alerts_data = weather_data.alerts
        if app.alert_details_button:
            app.alert_details_button.enabled = len(alerts_table_data) > 0

        logger.info("Sync weather displays updated successfully (cached data)")

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to sync update weather displays: %s", exc)
        show_error_displays(app, f"Display error: {exc}")


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
    import toga.constants

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
                app.main_window.state = toga.constants.WindowState.MINIMIZED
            except (AttributeError, NotImplementedError, ValueError):
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
