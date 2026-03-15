"""Notification event helpers for :mod:`accessiweather.ui.main_window`."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


def refresh_notification_events_async(window: MainWindow) -> None:
    """Run a lightweight event check without refreshing the full weather UI."""
    if window.app.is_updating:
        logger.debug("Skipping event check while full weather refresh is in progress")
        return
    window.app.run_async(fetch_notification_event_data(window))


async def fetch_notification_event_data(window: MainWindow) -> None:
    """Fetch only the lightweight data needed for notifications."""
    try:
        location = window.app.config_manager.get_current_location()
        if not location or location.name == "Nationwide":
            return

        weather_data = await window.app.weather_client.get_notification_event_data(location)
        wx.CallAfter(window._on_notification_event_data_received, weather_data)
    except Exception as e:
        logger.debug(f"Failed to fetch lightweight notification data: {e}")


def get_notification_event_manager(window: MainWindow):
    """Get or create the notification event manager for AFD/severe risk notifications."""
    if (
        not hasattr(window, "_notification_event_manager")
        or window._notification_event_manager is None
    ):
        from ..notifications.notification_event_manager import NotificationEventManager

        state_file = window.app.paths.config / "notification_event_state.json"
        window._notification_event_manager = NotificationEventManager(state_file=state_file)
    return window._notification_event_manager


def get_fallback_notifier(window: MainWindow):
    """Get or create a cached fallback notifier for event notifications."""
    if not hasattr(window, "_fallback_notifier") or window._fallback_notifier is None:
        from ..notifications.toast_notifier import SafeDesktopNotifier

        window._fallback_notifier = SafeDesktopNotifier()
    return window._fallback_notifier


def on_notification_event_data_received(window: MainWindow, weather_data) -> None:
    """Handle lightweight event data without refreshing the visible weather UI."""
    try:
        if (
            weather_data.alerts
            and weather_data.alerts.has_alerts()
            and window.app.alert_notification_system
        ):
            window.app.run_async(
                window.app.alert_notification_system.process_and_notify(weather_data.alerts)
            )

        if (
            window.app.alert_notification_system
            and weather_data.alert_lifecycle_diff is not None
            and weather_data.alert_lifecycle_diff.has_changes
        ):
            window.app.run_async(
                window.app.alert_notification_system.notify_lifecycle_changes(
                    weather_data.alert_lifecycle_diff
                )
            )

        window._process_notification_events(weather_data)
    except Exception as e:
        logger.debug(f"Failed to process lightweight notification event data: {e}")


def process_notification_events(window: MainWindow, weather_data) -> None:
    """Process weather data for discussion and severe-risk notification events."""
    try:
        settings = window.app.config_manager.get_settings()

        if not settings.notify_discussion_update and not settings.notify_severe_risk_change:
            logger.debug(
                "[events] _process_notification_events: both discuss_update=%s and "
                "severe_risk=%s disabled — skipping",
                settings.notify_discussion_update,
                settings.notify_severe_risk_change,
            )
            return

        location = window.app.config_manager.get_current_location()
        if not location:
            logger.warning("[events] _process_notification_events: no current location")
            return

        notifier = getattr(window.app, "notifier", None)
        notifier_source = "app.notifier"
        if not notifier:
            notifier = window._get_fallback_notifier()
            notifier_source = "fallback_notifier"
        logger.debug(
            "[events] _process_notification_events: notifier=%s (%s), sound_enabled=%s",
            type(notifier).__name__,
            notifier_source,
            settings.sound_enabled,
        )

        event_manager = window._get_notification_event_manager()
        events = event_manager.check_for_events(weather_data, settings, location.name)

        logger.debug(
            "[events] check_for_events returned %d event(s) for location %r",
            len(events),
            location.name,
        )

        for event in events:
            try:
                logger.debug(
                    "[events] Sending %s notification: title=%r, sound_event=%r, play_sound=%s",
                    event.event_type,
                    event.title,
                    event.sound_event,
                    settings.sound_enabled,
                )
                success = notifier.send_notification(
                    title=event.title,
                    message=event.message,
                    timeout=10,
                    sound_event=event.sound_event,
                    play_sound=settings.sound_enabled,
                )

                if success:
                    logger.info("[events] Sent %s notification: %s", event.event_type, event.title)
                else:
                    logger.warning(
                        "[events] send_notification returned False for %s: %r",
                        event.event_type,
                        event.title,
                    )

            except Exception as e:
                logger.warning("[events] Failed to send event notification: %s", e)

    except Exception as e:
        logger.warning("[events] Error processing notification events: %s", e)
