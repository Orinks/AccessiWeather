"""Event handler implementations for AccessiWeather."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import toga

from .alert_details_dialog import AlertDetailsDialog
from .dialogs import AddLocationDialog, SettingsDialog
from .dialogs.discussion import ForecastDiscussionDialog
from .models import WeatherData

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from .app import AccessiWeatherApp


logger = logging.getLogger(__name__)


# Location management handlers -------------------------------------------------


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
        app._update_status(f"Error changing location: {exc}")


async def on_add_location_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Handle add location button/menu press."""
    logger.info("Add location menu pressed")

    try:
        add_dialog = AddLocationDialog(app, app.config_manager)
        location_added = await add_dialog.show_and_wait()

        if location_added:
            app._update_location_selection()
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

        app._update_location_selection()
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


# Weather and refresh handlers -------------------------------------------------


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
        app._update_status("No location selected")
        return

    logger.info("Starting weather data refresh for %s", current_location.name)
    app.is_updating = True
    app._update_status(f"Updating weather for {current_location.name}...")

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
            app._update_status(presentation.status_messages[-1])
        else:
            app._update_status(f"Weather updated for {current_location.name}")

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to refresh weather data: %s", exc)
        app._show_error_displays(str(exc))
        app._update_status(f"Failed to update weather: {exc}")
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
        app._show_error_displays(f"Display error: {exc}")
        return None


def convert_alerts_to_table_data(alerts: Any) -> list:
    """Convert WeatherAlerts to table data format."""
    if not alerts or not alerts.has_alerts():
        return []

    table_data = []
    active_alerts = alerts.get_active_alerts()

    for alert in active_alerts[:10]:
        event = alert.event or "Weather Alert"
        severity = alert.severity or "Unknown"
        headline = alert.headline or "No headline available"

        if len(headline) > 80:
            headline = headline[:77] + "..."

        table_data.append((event, severity, headline))

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


# Settings and dialog handlers -------------------------------------------------


async def on_settings_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Handle settings menu item."""
    logger.info("Settings menu pressed")

    try:
        settings_saved = await show_settings_dialog(app)

        if settings_saved:
            app._update_location_selection()
            try:
                config = app.config_manager.get_config()
                if app._notifier:
                    app._notifier.sound_enabled = bool(
                        getattr(config.settings, "sound_enabled", True)
                    )
                    app._notifier.soundpack = getattr(config.settings, "sound_pack", "default")
                if app.alert_notification_system:
                    alert_settings = config.settings.to_alert_settings()
                    audio_settings = config.settings.to_alert_audio_settings()
                    app.alert_notification_system.update_settings(
                        alert_settings, audio_settings=audio_settings
                    )
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


# Alert handlers ---------------------------------------------------------------


async def on_alert_details_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Handle alert details button press."""
    logger.info("Alert details button pressed")

    try:
        await on_view_alert_details(app, widget)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to show alert details: %s", exc)
        await app.main_window.error_dialog(
            "Alert Details Error", f"Failed to show alert details: {exc}"
        )


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
            await app.main_window.info_dialog(
                "No Selection", "Please select an alert from the table first."
            )
            return

        selected_row = app.alerts_table.selection
        try:
            alert_index = app.alerts_table.data.index(selected_row)
        except ValueError:
            await app.main_window.error_dialog("Error", "Selected alert is no longer available.")
            return

        active_alerts = app.current_alerts_data.get_active_alerts()
        if alert_index >= len(active_alerts):
            await app.main_window.error_dialog("Error", "Selected alert is no longer available.")
            return

        alert = active_alerts[alert_index]

        title = f"Alert Details - {alert.event or 'Weather Alert'}"
        dialog = AlertDetailsDialog(app, title, alert)
        await dialog.show()

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error showing alert details: %s", exc)
        await app.main_window.error_dialog("Error", f"Failed to show alert details: {exc}")


# Update handlers --------------------------------------------------------------


async def on_about_pressed(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Handle about menu item."""
    await app.main_window.info_dialog(
        "About AccessiWeather",
        "AccessiWeather - Simple, accessible weather application\n\n"
        "Built with BeeWare/Toga for cross-platform compatibility.\n"
        "Designed with accessibility in mind for screen reader users.\n\n"
        "Version 2.0 - Simplified Architecture",
    )


async def on_check_updates_pressed(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Handle check for updates menu item."""
    if not app.update_service:
        await app.main_window.error_dialog(
            "Update Service Unavailable",
            "The update service is not available. Please check your internet connection and try again.",
        )
        return

    try:
        app._update_status("Checking for updates...")

        update_info = await app.update_service.check_for_updates()

        if update_info:
            message = (
                f"Update Available: Version {update_info.version}\n\n"
                f"Current version: 2.0\n"
                f"New version: {update_info.version}\n\n"
            )

            if update_info.release_notes:
                message += f"Release Notes:\n{update_info.release_notes[:500]}"
                if len(update_info.release_notes) > 500:
                    message += "..."

            should_download = await app.main_window.question_dialog(
                "Update Available", message + "\n\nWould you like to download this update?"
            )

            if should_download:
                await download_update(app, update_info)
            else:
                app._update_status("Update check completed")
        else:
            await app.main_window.info_dialog(
                "No Updates Available", "You are running the latest version of AccessiWeather."
            )
            app._update_status("No updates available")

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Update check failed: %s", exc)
        await app.main_window.error_dialog(
            "Update Check Failed",
            f"Failed to check for updates: {exc}\n\nPlease check your internet connection and try again.",
        )
        app._update_status("Update check failed")


async def download_update(app: AccessiWeatherApp, update_info: Any) -> None:
    """Download an available update."""
    try:
        app._update_status(f"Downloading update {update_info.version}...")

        downloaded_file = await app.update_service.download_update(update_info)

        if downloaded_file:
            downloaded_path = str(downloaded_file)
            await app.main_window.info_dialog(
                "Update Downloaded",
                f"Update {update_info.version} has been downloaded successfully.\n\n"
                f"Location: {downloaded_path}\n\n"
                "Please close the application and run the installer to complete the update.",
            )
            app._update_status(f"Update {update_info.version} downloaded")
        else:
            await app.main_window.error_dialog(
                "Download Failed", "Failed to download the update. Please try again later."
            )
            app._update_status("Update download failed")

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Update download failed: %s", exc)
        await app.main_window.error_dialog("Download Failed", f"Failed to download update: {exc}")
        app._update_status("Update download failed")


# System tray handlers ---------------------------------------------------------


async def on_show_hide_window(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Toggle main window visibility from system tray."""
    try:
        if app.main_window.visible:
            app.main_window.hide()
            if app.status_icon and hasattr(app.show_hide_command, "text"):
                app.show_hide_command.text = "Show AccessiWeather"
            logger.info("Main window hidden to system tray")
        else:
            app.main_window.show()
            if app.status_icon and hasattr(app.show_hide_command, "text"):
                app.show_hide_command.text = "Hide AccessiWeather"
            logger.info("Main window restored from system tray")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to toggle window visibility: %s", exc)


async def on_tray_refresh(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Refresh weather data from system tray."""
    try:
        logger.info("Refreshing weather data from system tray")
        await refresh_weather_data(app)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to refresh weather from system tray: %s", exc)


async def on_tray_settings(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Open settings dialog from system tray."""
    try:
        logger.info("Opening settings from system tray")
        await on_settings_pressed(app, widget)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to open settings from system tray: %s", exc)


async def on_tray_exit(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Exit application from system tray."""
    try:
        logger.info("Exiting application from system tray")
        app.request_exit()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to exit from system tray: %s", exc)


# Test and utility handlers ----------------------------------------------------


async def test_alert_notification(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Test the alert notification system (debug mode only)."""
    try:
        if app.alert_notification_system:
            success = await app.alert_notification_system.test_notification("Severe")
            if success:
                await app.main_window.info_dialog(
                    "Test Alert",
                    "Test alert notification sent successfully! Check your system notifications.",
                )
            else:
                await app.main_window.error_dialog(
                    "Test Alert Failed",
                    "Failed to send test alert notification. Check the logs for details.",
                )
        else:
            await app.main_window.error_dialog(
                "Alert System Error", "Alert notification system is not initialized."
            )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error testing alert notification: %s", exc)
        await app.main_window.error_dialog("Test Error", f"Error testing alert notification: {exc}")


def on_test_notification_pressed(app: AccessiWeatherApp, widget: toga.Button) -> None:
    """Send a test notification using desktop-notifier."""
    try:
        if app._notifier:
            app._notifier.send_notification(
                title="Test Notification",
                message="This is a test notification from AccessiWeather (Debug Mode)",
                sound_event="notify",
            )
            logger.info("Test notification sent successfully.")
            app._update_status("Test notification sent.")
        else:
            logger.warning("Notifier not initialized; cannot send test notification")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to send test notification: %s", exc)
        app._update_status(f"Failed to send test notification: {exc}")
