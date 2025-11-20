"""Alert-related event handlers for AccessiWeather."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import toga

from .. import app_helpers
from ..alert_details_dialog import AlertDetailsDialog

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..app import AccessiWeatherApp


logger = logging.getLogger(__name__)


async def on_alert_details_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Handle alert details button press."""
    logger.info("Alert details button pressed")

    try:
        await on_view_alert_details(app, widget)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to show alert details: %s", exc)
        if app_helpers.should_show_dialog(app):
            await app.main_window.error_dialog(
                "Alert Details Error", f"Failed to show alert details: {exc}"
            )
        else:
            logger.warning("Alert details error dialog suppressed - window hidden")


def on_alert_selected(app: AccessiWeatherApp, widget: toga.Table) -> None:
    """Enable/disable alert details button based on selection."""
    try:
        if app.alert_details_button:
            has_selection = widget.selection is not None
            app.alert_details_button.enabled = has_selection
            logger.debug("Alert details button %s", "enabled" if has_selection else "disabled")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error handling alert selection: %s", exc)


async def on_view_alert_details(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Handle the View Alert Details button press."""
    try:
        if not app.alerts_table or not app.alerts_table.selection or not app.current_alerts_data:
            if app_helpers.should_show_dialog(app):
                await app.main_window.info_dialog(
                    "No Selection", "Please select an alert from the table first."
                )
            else:
                logger.info("Alert selection error dialog suppressed - window hidden")
            return

        selected_row = app.alerts_table.selection
        alert_id = getattr(selected_row, "alert_id", None)

        if not alert_id:
            sel_event = getattr(selected_row, "event", None)
            sel_severity = getattr(selected_row, "severity", None)
            sel_headline = getattr(selected_row, "headline", None)

            for row in app.alerts_table.data or []:
                if (
                    row.get("event") == sel_event
                    and row.get("severity") == sel_severity
                    and row.get("headline") == sel_headline
                ):
                    alert_id = row.get("alert_id")
                    break

        if not alert_id:
            if app_helpers.should_show_dialog(app):
                await app.main_window.error_dialog(
                    "Error", "Selected alert is no longer available."
                )
            else:
                logger.warning("Alert not found error dialog suppressed - window hidden")
            return

        active_alerts = app.current_alerts_data.get_active_alerts()
        alert = next(
            (item for item in active_alerts if item.get_unique_id() == alert_id),
            None,
        )
        if not alert:
            if app_helpers.should_show_dialog(app):
                await app.main_window.error_dialog(
                    "Error", "Selected alert is no longer available."
                )
            else:
                logger.warning("Alert not found error dialog suppressed - window hidden")
            return

        title = f"Alert Details - {alert.event or 'Weather Alert'}"
        dialog = AlertDetailsDialog(app, title, alert)
        await dialog.show()

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error showing alert details: %s", exc)
        if app_helpers.should_show_dialog(app):
            await app.main_window.error_dialog("Error", f"Failed to show alert details: {exc}")
        else:
            logger.warning("Alert details error dialog suppressed - window hidden")
