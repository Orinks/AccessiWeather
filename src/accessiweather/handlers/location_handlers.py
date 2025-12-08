"""Location management event handlers for AccessiWeather."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

import toga

from .. import app_helpers
from ..dialogs import AddLocationDialog
from ..ui_builder import update_tray_icon_tooltip
from .weather_handlers import refresh_weather_data

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..app import AccessiWeatherApp


logger = logging.getLogger(__name__)

# Debounce delay for rapid location switches (in seconds)
# This prevents overwhelming APIs when users scroll through locations quickly
_LOCATION_CHANGE_DEBOUNCE_DELAY = 0.3


def _get_debounce_delay() -> float:
    """Get debounce delay, disabled during tests."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return 0.0
    return _LOCATION_CHANGE_DEBOUNCE_DELAY


# Track pending location change task for debouncing
_pending_location_change: asyncio.Task | None = None


async def on_location_changed(app: AccessiWeatherApp, widget: toga.Selection) -> None:
    """
    Handle location selection change with debouncing.

    When users rapidly switch locations (e.g., scrolling through a dropdown),
    this debounces the API calls to prevent overwhelming the weather services
    and causing screen reader lag.

    Note: Debouncing is disabled during tests (PYTEST_CURRENT_TEST env var).
    """
    global _pending_location_change

    if not widget.value or widget.value == "No locations available":
        return

    selected_location = widget.value

    # In test mode or with zero delay, execute immediately
    debounce_delay = _get_debounce_delay()
    if debounce_delay == 0:
        logger.info("Location changed to: %s", selected_location)
        try:
            app.config_manager.set_current_location(selected_location)
            update_tray_icon_tooltip(app, None)
            await refresh_weather_data(app)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to handle location change: %s", exc)
            app_helpers.update_status(app, f"Error changing location: {exc}")
        return

    logger.debug("Location selection changed to: %s", selected_location)

    # Cancel any pending location change
    if _pending_location_change and not _pending_location_change.done():
        _pending_location_change.cancel()
        logger.debug("Cancelled pending location change due to new selection")

    # Schedule the actual location change after debounce delay
    _pending_location_change = asyncio.create_task(
        _debounced_location_change(app, selected_location)
    )


async def _debounced_location_change(app: AccessiWeatherApp, location_name: str) -> None:
    """Execute location change after debounce delay."""
    try:
        # Wait for debounce period - if cancelled, another selection was made
        await asyncio.sleep(_LOCATION_CHANGE_DEBOUNCE_DELAY)

        logger.info("Location changed to: %s", location_name)

        app.config_manager.set_current_location(location_name)
        update_tray_icon_tooltip(app, None)
        await refresh_weather_data(app)

    except asyncio.CancelledError:
        logger.debug("Location change to %s was superseded", location_name)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to handle location change: %s", exc)
        app_helpers.update_status(app, f"Error changing location: {exc}")


async def on_add_location_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Handle add location button/menu press."""
    logger.info("Add location menu pressed")

    try:
        add_dialog = AddLocationDialog(app, app.config_manager)
        added_location_name = await add_dialog.show_and_wait()

        if added_location_name:
            # Set the newly added location as current so it's selected in the dropdown
            app.config_manager.set_current_location(added_location_name)
            app_helpers.update_location_selection(app)
            await refresh_weather_data(app)
            logger.info("Location added successfully: %s", added_location_name)
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
