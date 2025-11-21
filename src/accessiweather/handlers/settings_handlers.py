"""Settings and discussion dialog event handlers for AccessiWeather."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import toga

from .. import app_helpers
from ..dialogs import SettingsDialog
from ..dialogs.discussion import ForecastDiscussionDialog

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..app import AccessiWeatherApp


logger = logging.getLogger(__name__)


async def on_settings_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Handle settings menu item."""
    logger.info("Settings menu pressed")

    try:
        settings_saved = await show_settings_dialog(app)

        if settings_saved:
            app_helpers.update_location_selection(app)
            try:
                config = app.config_manager.get_config()
                if app._notifier:
                    app._notifier.sound_enabled = bool(
                        getattr(config.settings, "sound_enabled", True)
                    )
                    app._notifier.soundpack = getattr(config.settings, "sound_pack", "default")
                if app.alert_notification_system:
                    alert_settings = config.settings.to_alert_settings()
                    app.alert_notification_system.update_settings(alert_settings)
                logger.info("Settings updated successfully and applied to runtime components")
            except Exception as apply_err:  # pragma: no cover - defensive logging
                logger.warning(
                    "Settings saved but failed to apply to runtime components: %s", apply_err
                )
            logger.info("Settings updated successfully")

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to show settings dialog: %s", exc)
        await app.main_window.error_dialog("Settings Error", f"Failed to open settings: {exc}")


async def show_settings_dialog(app: AccessiWeatherApp) -> bool:
    """Show the settings dialog and return whether settings were saved."""
    settings_dialog = SettingsDialog(app, app.config_manager, app.update_service)
    settings_dialog.show_and_prepare()
    return await settings_dialog


async def on_discussion_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Handle forecast discussion button press."""
    logger.info("Forecast discussion button pressed")

    try:
        if not app.current_weather_data:
            await app.main_window.info_dialog(
                "No Data Available",
                "Please refresh weather data first to view the forecast discussion.",
            )
            return

        discussion_text = app.current_weather_data.discussion
        if not discussion_text or discussion_text.strip() == "":
            await app.main_window.info_dialog(
                "Discussion Not Available",
                "Forecast discussion is not available for this location. "
                "This may occur for locations outside the US or when using backup weather data.",
            )
            return

        location_name = (
            app.current_weather_data.location.name
            if app.current_weather_data.location
            else "Unknown Location"
        )
        dialog = ForecastDiscussionDialog(app, discussion_text, location_name)
        await dialog.show_and_focus()
        logger.info("Forecast discussion dialog shown successfully")

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to show forecast discussion: %s", exc)
        await app.main_window.error_dialog(
            "Discussion Error", f"Failed to show forecast discussion: {exc}"
        )
