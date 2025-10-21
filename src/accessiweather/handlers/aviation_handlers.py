"""Handlers for aviation weather dialog interactions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import toga

from ..dialogs import AviationDialog

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..app import AccessiWeatherApp


logger = logging.getLogger(__name__)


async def on_view_aviation_pressed(app: AccessiWeatherApp, widget: toga.Widget) -> None:
    """Open the aviation weather dialog."""
    if not getattr(app, "weather_client", None):
        logger.warning("Aviation view requested before weather client initialization.")
        if getattr(app, "main_window", None):
            await app.main_window.info_dialog(
                "Aviation Weather Unavailable",
                "The aviation view is unavailable until the weather client finishes initializing.",
            )
        return

    if getattr(app, "aviation_dialog", None) is None:
        app.aviation_dialog = AviationDialog(app)

    try:
        await app.aviation_dialog.show_and_focus()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to open aviation dialog: %s", exc)
        if getattr(app, "main_window", None):
            await app.main_window.error_dialog(
                "Aviation Dialog Error", f"Failed to open aviation view: {exc}"
            )
