"""Weather refresh and presentation event handlers for AccessiWeather."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import toga

from .. import app_helpers
from ..dialogs.weather_history_dialog import WeatherHistoryDialog
from ..models import WeatherData
from ..performance.timer import timed_async

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..app import AccessiWeatherApp


logger = logging.getLogger(__name__)


async def on_refresh_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Handle refresh button press."""
    logger.info("Refresh button pressed")
    await refresh_weather_data(app)


@timed_async("UI.refresh_weather_data")
async def refresh_weather_data(app: AccessiWeatherApp) -> None:
    """Refresh weather data for the current location."""
    logger.debug("refresh_weather_data called")

    if app.is_updating:
        logger.info("Update already in progress, skipping")
        return

    current_location = app.config_manager.get_current_location()
    if not current_location:
        logger.debug("No current location found")
        return

    logger.info("Starting weather data refresh for %s", current_location.name)
    app.is_updating = True
    window_visible = app_helpers.should_show_dialog(app)

    try:
        # Only update button state if window is visible
        if app.refresh_button and window_visible:
            app.refresh_button.enabled = False

        # OPTIMIZATION: Try to load cached data first for immediate feedback
        # This allows the UI to populate instantly while the fresh data is being fetched
        logger.debug("Checking for cached weather data")
        cached_data = app.weather_client.get_cached_weather(current_location)
        if cached_data:
            logger.info("Found cached data, updating display immediately")
            app.current_weather_data = cached_data
            await update_weather_displays(app, cached_data)
            # Indicate that an update is still in progress
            if app.status_label:
                app_helpers.update_status(app, f"Updating weather for {current_location.name}...")

        logger.debug("About to call weather_client.get_weather_data")
        weather_data = await app.weather_client.get_weather_data(current_location)
        logger.debug("weather_client.get_weather_data completed")

        app.current_weather_data = weather_data

        logger.debug("About to update weather displays")
        await update_weather_displays(app, weather_data)
        logger.debug("Weather displays updated")

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to refresh weather data: %s", exc)
        app_helpers.show_error_displays(app, str(exc))
    finally:
        app.is_updating = False
        # Only update button state if window is visible
        if app.refresh_button and window_visible:
            app.refresh_button.enabled = True


@timed_async("UI.update_displays")
async def update_weather_displays(app: AccessiWeatherApp, weather_data: WeatherData) -> Any:
    """Update UI widgets with new weather data."""
    # CRITICAL: Do NOT update UI when window is hidden to prevent phantom popups on Windows
    if not app_helpers.should_show_dialog(app):
        logger.debug("Skipping weather display updates - window is hidden")
        return None

    try:
        presentation = app.presenter.present(weather_data)

        if app.current_conditions_display:
            if presentation.current_conditions:
                current_text = presentation.current_conditions.fallback_text
                trend_lines = presentation.current_conditions.trends
                if trend_lines:
                    current_text += "\n\nTrends:\n" + "\n".join(
                        f"• {trend}" for trend in trend_lines
                    )

                # Add weather history comparison if enabled
                if (
                    app.weather_history_service
                    and weather_data.location
                    and weather_data.current_conditions
                ):
                    try:
                        # Try to get yesterday's comparison
                        comparison = app.weather_history_service.compare_with_yesterday(
                            weather_data.location, weather_data.current_conditions
                        )
                        if comparison:
                            history_text = comparison.get_accessible_summary()
                            current_text += f"\n\nHistory:\n• {history_text}"
                            logger.debug("Added weather history comparison to display")
                    except Exception as hist_exc:
                        logger.debug(f"Could not fetch weather history: {hist_exc}")

                if presentation.status_messages:
                    status_lines = "\n".join(f"• {line}" for line in presentation.status_messages)
                    current_text += f"\n\nStatus:\n{status_lines}"
                if presentation.air_quality:
                    aq_lines: list[str] = []
                    if presentation.air_quality.summary:
                        aq_lines.append(f"• {presentation.air_quality.summary}")
                    if presentation.air_quality.guidance:
                        aq_lines.append(f"• Advice: {presentation.air_quality.guidance}")
                    if presentation.air_quality.updated_at:
                        aq_lines.append(f"• {presentation.air_quality.updated_at}")
                    if presentation.air_quality.sources:
                        aq_lines.append("• Sources: " + ", ".join(presentation.air_quality.sources))
                    if aq_lines:
                        current_text += "\n\nAir quality update:\n" + "\n".join(aq_lines)
                app.current_conditions_display.value = current_text
            else:
                # Avoid inventing "no data" messages when the API simply omitted a section.
                app.current_conditions_display.value = ""

        if app.forecast_display:
            if presentation.forecast:
                app.forecast_display.value = presentation.forecast.fallback_text
            else:
                app.forecast_display.value = ""

        aviation_display = getattr(app, "aviation_display", None)
        if aviation_display is not None:
            if presentation.aviation:
                aviation_display.value = presentation.aviation.fallback_text
            else:
                aviation_display.value = ""

        alerts_table_data = convert_alerts_to_table_data(weather_data.alerts)
        if app.alerts_table:
            app.alerts_table.data = alerts_table_data

        app.current_alerts_data = weather_data.alerts
        if app.alert_details_button:
            app.alert_details_button.enabled = len(alerts_table_data) > 0

        await notify_new_alerts(app, weather_data.alerts)

        logger.info("Weather displays updated successfully")
        return presentation

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to update weather displays: %s", exc)
        app_helpers.show_error_displays(app, f"Display error: {exc}")
        return None


def convert_alerts_to_table_data(alerts: Any) -> list[dict[str, str]]:
    """Convert WeatherAlerts to table data format with stable identifiers."""
    if not alerts or not alerts.has_alerts():
        return []

    table_data: list[dict[str, str]] = []
    active_alerts = alerts.get_active_alerts()

    for alert in active_alerts[:10]:
        event = alert.event or "Weather Alert"
        severity = alert.severity or "Unknown"
        headline = alert.headline or "No headline available"

        if len(headline) > 80:
            headline = headline[:77] + "..."

        table_data.append(
            {
                "alert_id": alert.get_unique_id(),
                "event": event,
                "severity": severity,
                "headline": headline,
            }
        )

    return table_data


async def notify_new_alerts(app: AccessiWeatherApp, alerts: Any) -> None:
    """Send system notifications for new or changed alerts."""
    if not alerts or not alerts.has_alerts():
        return

    try:
        if app.alert_notification_system:
            notifications_sent = await app.alert_notification_system.process_and_notify(alerts)
            if notifications_sent > 0:
                logger.info("Sent %s alert notifications", notifications_sent)
        else:
            logger.warning("Alert notification system not initialized")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to process alert notifications: %s", exc)
        try:
            active_alerts = alerts.get_active_alerts()
            for alert in active_alerts[:1]:
                if alert.severity and alert.severity.lower() in ["extreme", "severe"]:
                    title = alert.event or "Weather Alert"
                    message = alert.headline or "A new weather alert has been issued."
                    if app._notifier:
                        app._notifier.send_notification(title=title, message=message)
                        logger.info("Fallback notification sent: %s", title)
                    break
        except Exception as fallback_error:  # pragma: no cover - defensive logging
            logger.error("Fallback notification also failed: %s", fallback_error)


async def on_view_weather_history(app: AccessiWeatherApp, widget: toga.Widget) -> None:
    """Show weather history comparison dialog."""
    logger.info("View weather history pressed")

    if not app.weather_history_service:
        await app.main_window.dialog(
            toga.InfoDialog(
                "Weather History",
                "Weather history comparison is currently disabled. "
                "Enable it in Settings to compare current weather with historical data.",
            )
        )
        return

    current_location = app.config_manager.get_current_location()
    if not current_location:
        await app.main_window.dialog(
            toga.InfoDialog(
                "Weather History", "No location selected. Please select a location first."
            )
        )
        return

    if not app.current_weather_data or not app.current_weather_data.current_conditions:
        await app.main_window.dialog(
            toga.InfoDialog(
                "Weather History",
                "No current weather data available. Please refresh weather data first.",
            )
        )
        return

    try:
        # Fetch historical comparisons
        app_helpers.update_status(app, "Fetching historical weather data...")

        yesterday_comp = app.weather_history_service.compare_with_yesterday(
            current_location, app.current_weather_data.current_conditions
        )

        week_comp = app.weather_history_service.compare_with_last_week(
            current_location, app.current_weather_data.current_conditions
        )

        sections: list[tuple[str, str]] = []

        if yesterday_comp:
            sections.append(("Yesterday", yesterday_comp.get_accessible_summary()))
        else:
            sections.append(("Yesterday", "No historical data available."))

        if week_comp:
            sections.append(("Last Week", week_comp.get_accessible_summary()))
        else:
            sections.append(("Last Week", "No historical data available."))

        dialog = WeatherHistoryDialog(app, current_location.name, sections)
        await dialog.show_and_focus()

        app_helpers.update_status(app, "Weather history dialog opened")

    except Exception as exc:
        logger.error("Failed to fetch weather history: %s", exc)
        await app.main_window.dialog(
            toga.InfoDialog(
                "Weather History Error", f"Could not fetch historical weather data: {exc}"
            )
        )
        app_helpers.update_status(app, "Failed to fetch weather history")
