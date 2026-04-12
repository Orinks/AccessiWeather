"""
Notification event helpers for the main window.

This keeps lightweight polling and event notification logic out of
``main_window.py`` without changing MainWindow's public method surface.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx

from ..notification_activation import NotificationActivationRequest, serialize_activation_request
from ..notifications.notification_event_manager import NotificationEventManager
from ..notifications.toast_notifier import SafeDesktopNotifier
from ..runtime_state import RuntimeStateManager

if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


def _log_reviewable_event_text(window: MainWindow, title: str, message: str) -> None:
    """Append reviewable user-facing event text to the Event Center when available."""
    log_method = getattr(window, "append_event_center_entry", None)
    if callable(log_method) and message:
        log_method(message, category=title)


def refresh_notification_events_async(window: MainWindow) -> None:
    """Run a lightweight event check without refreshing the full weather UI."""
    if window.app.is_updating:
        logger.debug("Skipping event check while full weather refresh is in progress")
        return

    coro = fetch_notification_event_data(window)
    window.app.run_async(coro)
    if window.app.__dict__.get("_async_loop") is None:
        coro.close()


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
        config_root = window.app.config_manager.config_dir
        window._notification_event_manager = NotificationEventManager(
            runtime_state_manager=RuntimeStateManager(config_root)
        )
    return window._notification_event_manager


def get_fallback_notifier(window: MainWindow):
    """Get or create a cached fallback notifier for event notifications."""
    if not hasattr(window, "_fallback_notifier") or window._fallback_notifier is None:
        window._fallback_notifier = SafeDesktopNotifier()
    return window._fallback_notifier


def on_notification_event_data_received(window: MainWindow, weather_data) -> None:
    """
    Handle lightweight event data without refreshing the visible weather UI.

    Note: We only process alert notifications here, NOT discussion updates.
    Discussion updates are handled in _on_weather_data_received after full weather
    refreshes. This prevents duplicate notifications when full refresh and event
    poll happen around the same time.
    """
    try:
        # Only process alerts in the lightweight path - discussion updates are handled
        # in _on_weather_data_received to prevent duplicate notifications
        if (
            weather_data.alerts
            and weather_data.alerts.has_alerts()
            and window.app.alert_notification_system
        ):
            active_alerts = weather_data.alerts.get_active_alerts()
            logger.info(
                "[notify-ui] lightweight poll scheduling alert processing for %d active alert(s): %s",
                len(active_alerts),
                [
                    {
                        "id": alert.get_unique_id(),
                        "event": alert.event,
                        "severity": alert.severity,
                    }
                    for alert in active_alerts
                ],
            )
            window.app.run_async(
                window.app.alert_notification_system.process_and_notify(weather_data.alerts)
            )

        if (
            window.app.alert_notification_system
            and weather_data.alert_lifecycle_diff is not None
            and weather_data.alert_lifecycle_diff.has_changes
        ):
            diff = weather_data.alert_lifecycle_diff
            logger.info(
                "[notify-ui] lightweight poll scheduling lifecycle notifications: "
                "updated=%d escalated=%d extended=%d cancelled=%d",
                len(diff.updated_alerts),
                len(diff.escalated_alerts),
                len(diff.extended_alerts),
                len(diff.cancelled_alerts),
            )
            window.app.run_async(
                window.app.alert_notification_system.notify_lifecycle_changes(
                    weather_data.alert_lifecycle_diff
                )
            )

        # Note: DO NOT call window._process_notification_events here.
        # Discussion updates and severe risk changes are processed in
        # _on_weather_data_received after full weather refreshes.
    except Exception as e:
        logger.debug(f"Failed to process lightweight notification event data: {e}")


def process_notification_events(window: MainWindow, weather_data) -> None:
    """
    Process weather data for notification events.

    Checks for:
    - Area Forecast Discussion (AFD) updates (NWS US only)
    - Severe weather risk level changes (Visual Crossing only)
    - Minutely precipitation start/stop transitions (Pirate Weather)

    Both are opt-in notifications (disabled by default).
    """
    try:
        settings = window.app.config_manager.get_settings()

        if (
            not settings.notify_discussion_update
            and not settings.notify_severe_risk_change
            and not settings.notify_minutely_precipitation_start
            and not settings.notify_minutely_precipitation_stop
        ):
            logger.debug(
                "[events] _process_notification_events: discussion=%s severe_risk=%s "
                "minutely_start=%s minutely_stop=%s disabled -- skipping",
                settings.notify_discussion_update,
                settings.notify_severe_risk_change,
                settings.notify_minutely_precipitation_start,
                settings.notify_minutely_precipitation_stop,
            )
            return

        location = window.app.config_manager.get_current_location()
        if not location:
            logger.warning("[events] _process_notification_events: no current location")
            return

        notifier = getattr(window.app, "notifier", None)
        notifier_source = "app.notifier"
        if not notifier:
            notifier = get_fallback_notifier(window)
            notifier_source = "fallback_notifier"
        logger.debug(
            "[events] _process_notification_events: notifier=%s (%s), sound_enabled=%s",
            type(notifier).__name__,
            notifier_source,
            settings.sound_enabled,
        )

        event_manager = get_notification_event_manager(window)
        events = event_manager.check_for_events(weather_data, settings, location.name)

        logger.debug(
            "[events] check_for_events returned %d event(s) for location %r",
            len(events),
            location.name,
        )

        for event in events:
            try:
                _log_reviewable_event_text(window, event.title, event.message)
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
                    activation_arguments=(
                        serialize_activation_request(
                            NotificationActivationRequest(kind="discussion")
                        )
                        if event.event_type == "discussion_update"
                        else serialize_activation_request(
                            NotificationActivationRequest(kind="generic_fallback")
                        )
                    ),
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
