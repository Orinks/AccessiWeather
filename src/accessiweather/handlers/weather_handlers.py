"""Weather refresh and presentation event handlers for AccessiWeather."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import toga

from .. import app_helpers
from ..models import WeatherData

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..app import AccessiWeatherApp


logger = logging.getLogger(__name__)


async def on_refresh_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Handle refresh button press."""
    logger.info("Refresh button pressed")
    await refresh_weather_data(app)


async def refresh_weather_data(app: AccessiWeatherApp) -> None:
    """Refresh weather data for the current location."""
    logger.debug("refresh_weather_data called")

    if app.is_updating:
        logger.info("Update already in progress, skipping")
        return

    current_location = app.config_manager.get_current_location()
    if not current_location:
        logger.debug("No current location found")
        app_helpers.update_status(app, "No location selected")
        return

    logger.info("Starting weather data refresh for %s", current_location.name)
    app.is_updating = True
    app_helpers.update_status(app, f"Updating weather for {current_location.name}...")

    try:
        if app.refresh_button:
            app.refresh_button.enabled = False

        logger.debug("About to call weather_client.get_weather_data")
        weather_data = await app.weather_client.get_weather_data(current_location)
        logger.debug("weather_client.get_weather_data completed")

        app.current_weather_data = weather_data

        logger.debug("About to update weather displays")
        presentation = await update_weather_displays(app, weather_data)
        logger.debug("Weather displays updated")

        if presentation and presentation.status_messages:
            app_helpers.update_status(app, presentation.status_messages[-1])
        else:
            app_helpers.update_status(app, f"Weather updated for {current_location.name}")

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to refresh weather data: %s", exc)
        app_helpers.show_error_displays(app, str(exc))
        app_helpers.update_status(app, f"Failed to update weather: {exc}")
    finally:
        app.is_updating = False
        if app.refresh_button:
            app.refresh_button.enabled = True


async def update_weather_displays(app: AccessiWeatherApp, weather_data: WeatherData) -> Any:
    """Update UI widgets with new weather data."""
    try:
        presentation = app.presenter.present(weather_data)

        location_name = weather_data.location.name if weather_data.location else "Unknown"

        if app.current_conditions_display:
            if presentation.current_conditions:
                current_text = presentation.current_conditions.fallback_text
                trend_lines = presentation.current_conditions.trends
                if trend_lines:
                    current_text += "\n\nTrends:\n" + "\n".join(
                        f"• {trend}" for trend in trend_lines
                    )
                
                # Add weather history comparison if enabled
                if app.weather_history_service and weather_data.location and weather_data.current_conditions:
                    try:
                        # Try to get yesterday's comparison
                        comparison = app.weather_history_service.compare_with_yesterday(
                            weather_data.location,
                            weather_data.current_conditions
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
                app.current_conditions_display.value = current_text
            else:
                app.current_conditions_display.value = (
                    f"Current conditions for {location_name}:\nNo current weather data available."
                )

        if app.forecast_display:
            if presentation.forecast:
                app.forecast_display.value = presentation.forecast.fallback_text
            else:
                app.forecast_display.value = (
                    f"Forecast for {location_name}:\nNo forecast data available."
                )

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
                "Enable it in Settings to compare current weather with historical data."
            )
        )
        return

    current_location = app.config_manager.get_current_location()
    if not current_location:
        await app.main_window.dialog(
            toga.InfoDialog(
                "Weather History",
                "No location selected. Please select a location first."
            )
        )
        return

    if not app.current_weather_data or not app.current_weather_data.current_conditions:
        await app.main_window.dialog(
            toga.InfoDialog(
                "Weather History",
                "No current weather data available. Please refresh weather data first."
            )
        )
        return

    try:
        # Fetch historical comparisons
        app_helpers.update_status(app, "Fetching historical weather data...")
        
        yesterday_comp = app.weather_history_service.compare_with_yesterday(
            current_location,
            app.current_weather_data.current_conditions
        )
        
        week_comp = app.weather_history_service.compare_with_last_week(
            current_location,
            app.current_weather_data.current_conditions
        )

        # Build message
        message_parts = [f"Weather History for {current_location.name}\n"]
        
        if yesterday_comp:
            message_parts.append("Yesterday:")
            message_parts.append(yesterday_comp.get_accessible_summary())
            message_parts.append("")
        else:
            message_parts.append("Yesterday: No historical data available")
            message_parts.append("")
        
        if week_comp:
            message_parts.append("Last Week:")
            message_parts.append(week_comp.get_accessible_summary())
        else:
            message_parts.append("Last Week: No historical data available")

        message = "\n".join(message_parts)

        await app.main_window.dialog(
            toga.InfoDialog(
                "Weather History",
                message
            )
        )
        
        app_helpers.update_status(app, "Weather history displayed")

    except Exception as exc:
        logger.error("Failed to fetch weather history: %s", exc)
        await app.main_window.dialog(
            toga.InfoDialog(
                "Weather History Error",
                f"Could not fetch historical weather data: {exc}"
            )
        )
        app_helpers.update_status(app, "Failed to fetch weather history")

