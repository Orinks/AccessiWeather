"""Location management event handlers for AccessiWeather."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import toga

from .. import app_helpers
from ..dialogs import AddLocationDialog
from .weather_handlers import refresh_weather_data

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..app import AccessiWeatherApp


logger = logging.getLogger(__name__)


async def on_location_changed(app: AccessiWeatherApp, widget: toga.Selection) -> None:
    """Handle location selection change."""
    if not widget.value or widget.value == "No locations available":
        return

    logger.info("Location changed to: %s", widget.value)

    try:
        app.config_manager.set_current_location(widget.value)
        await refresh_weather_data(app)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to handle location change: %s", exc)
        app_helpers.update_status(app, f"Error changing location: {exc}")


async def on_add_location_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Handle add location button/menu press."""
    logger.info("Add location menu pressed")

    try:
        add_dialog = AddLocationDialog(app, app.config_manager)
        location_added = await add_dialog.show_and_wait()

        if location_added:
            app_helpers.update_location_selection(app)
            await refresh_weather_data(app)
            logger.info("Location added successfully")
        else:
            logger.info("Add location cancelled")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to show add location dialog: %s", exc)
        await app.main_window.error_dialog(
            "Add Location Error", f"Failed to open add location dialog: {exc}"
        )


async def on_remove_location_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Handle remove location button press."""
    logger.info("Remove location button pressed")

    try:
        if not app.location_selection or not app.location_selection.value:
            await app.main_window.info_dialog(
                "No Selection", "Please select a location to remove from the dropdown."
            )
            return

        selected_location = app.location_selection.value

        location_names = app.config_manager.get_location_names()
        if len(location_names) <= 1:
            await app.main_window.info_dialog(
                "Cannot Remove",
                "You cannot remove the last location. At least one location must remain.",
            )
            return

        confirmed = await show_remove_confirmation_dialog(app, selected_location)
        if not confirmed:
            logger.info("Location removal cancelled")
            return

        app.config_manager.remove_location(selected_location)
        logger.info("Location removed: %s", selected_location)

        app_helpers.update_location_selection(app)
        await refresh_weather_data(app)

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to remove location: %s", exc)
        await app.main_window.error_dialog(
            "Remove Location Error", f"Failed to remove location: {exc}"
        )


async def show_remove_confirmation_dialog(app: AccessiWeatherApp, location_name: str) -> bool:
    """Show confirmation dialog before removing a location."""
    try:
        return await app.main_window.question_dialog(
            "Remove Location",
            f"Are you sure you want to remove '{location_name}' from your locations?",
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to show remove confirmation dialog: %s", exc)
        await app.main_window.info_dialog(
            "Confirmation Error",
            "Unable to show confirmation dialog. Location removal cancelled for safety.",
        )
        return False
