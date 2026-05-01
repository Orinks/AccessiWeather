"""
Enhanced alert notification system for AccessiWeather.

This module provides a comprehensive notification system that integrates
with the AlertManager to provide user-controlled, accessible notifications
with proper cooldown and filtering capabilities.
"""

import asyncio
import logging
from collections.abc import Callable

from .alert_lifecycle import AlertLifecycleDiff
from .alert_manager import AlertManager, AlertSettings
from .alert_notification_formatting import (
    app_settings_debug_summary as _app_settings_debug_summary,
    format_accessible_message as format_accessible_message,
)
from .alert_notification_preferences import (
    AlertNotificationPreferences as AlertNotificationPreferences,
)
from .constants import (
    SEVERITY_PRIORITY_MAP,
    SEVERITY_PRIORITY_UNKNOWN,
)
from .models import AppSettings, WeatherAlert, WeatherAlerts
from .notification_activation import NotificationActivationRequest, serialize_activation_request
from .notifications.toast_notifier import SafeDesktopNotifier

logger = logging.getLogger(__name__)


class AlertNotificationSystem:
    """Enhanced notification system with user controls and accessibility features."""

    def __init__(
        self,
        alert_manager: AlertManager,
        notifier: SafeDesktopNotifier | None = None,
        settings: AppSettings | None = None,
        on_alerts_popup: Callable[[list[WeatherAlert]], None] | None = None,
    ):
        """Initialize the instance."""
        self.alert_manager = alert_manager
        self.notifier = notifier or SafeDesktopNotifier()
        self.settings = settings
        self.on_alerts_popup = on_alerts_popup

        logger.info("AlertNotificationSystem initialized")

    async def process_and_notify(self, alerts: WeatherAlerts) -> int:
        """
        Process alerts and send notifications for qualifying alerts.

        When multiple alerts are processed in a batch, only one sound is played
        (for the most severe alert) to avoid overlapping sounds.

        Returns
        -------
            Number of notifications sent.

        """
        try:
            alert_count = len(alerts.alerts) if alerts else 0
            active_alerts = alerts.get_active_alerts() if alerts and alerts.has_alerts() else []
            logger.debug(
                "[notify] process_and_notify: alerts=%d app_settings=%s manager_settings=%s",
                alert_count,
                _app_settings_debug_summary(self.settings),
                self.alert_manager._settings_debug_summary(),
            )
            if active_alerts:
                logger.info(
                    "[notify] process_and_notify received %d active alert(s): %s",
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

            # Use AlertManager to determine which alerts need notifications
            notifications_to_send = self.alert_manager.process_alerts(alerts)

            if not notifications_to_send:
                logger.info(
                    "[notify] AlertManager queued 0 notifications for active alerts; "
                    "manager_settings=%s tracked_alerts=%d",
                    self.alert_manager._settings_debug_summary(),
                    len(self.alert_manager.alert_states),
                )
                logger.debug(
                    f"[notify] AlertManager returned 0 notifications to send "
                    f"(all {alert_count} alert(s) already seen / in cooldown)"
                )
                return 0

            logger.info(
                f"[notify] AlertManager queued {len(notifications_to_send)} notification(s) to send"
            )

            # Sort notifications by severity (highest first) to play sound for most severe
            # Higher priority number = more severe
            sorted_notifications = sorted(
                notifications_to_send,
                key=lambda x: SEVERITY_PRIORITY_MAP.get(
                    (x[0].severity or "unknown").lower(), SEVERITY_PRIORITY_UNKNOWN
                ),
                reverse=True,
            )

            self._trigger_immediate_alert_popup_if_enabled(sorted_notifications)

            # Send notifications - only play sound for the first (most severe) one
            notifications_sent = 0
            for i, (alert, reason) in enumerate(sorted_notifications):
                try:
                    # Only play sound for the first notification to avoid overlap
                    play_sound = i == 0
                    success = await self._send_alert_notification(
                        alert, reason, play_sound=play_sound
                    )
                    if success:
                        notifications_sent += 1
                except Exception as e:
                    logger.error(
                        f"Failed to send notification for alert {alert.get_unique_id()}: {e}"
                    )

            logger.info(
                f"Sent {notifications_sent} of {len(notifications_to_send)} alert notifications"
            )
            return notifications_sent

        except Exception as e:
            logger.error(f"Error processing alert notifications: {e}")
            return 0

    def _trigger_immediate_alert_popup_if_enabled(
        self,
        sorted_notifications: list[tuple[WeatherAlert, str]],
    ) -> None:
        """Open in-app alert popups for the current eligible batch when opted in."""
        if not getattr(self.settings, "immediate_alert_details_popups", False):
            return
        if not callable(self.on_alerts_popup):
            return

        popup_alerts = [alert for alert, _reason in sorted_notifications]
        if not popup_alerts:
            return

        try:
            self.on_alerts_popup(popup_alerts)
        except Exception as exc:
            logger.error("Failed to trigger immediate alert popup: %s", exc)

    async def _send_alert_notification(
        self, alert: WeatherAlert, reason: str, play_sound: bool = True
    ) -> bool:
        """
        Send a notification for a specific alert.

        Args:
        ----
            alert: The weather alert to notify about
            reason: The reason for notification (new_alert, escalation, etc.)
            play_sound: Whether to play a sound with this notification

        Returns:
        -------
            True if notification was sent successfully

        """
        try:
            # Format title and message using accessibility helper
            title, message = format_accessible_message(
                alert=alert,
                reason=reason,
                include_areas=True,
                include_expiration=True,
                settings=self.settings,
            )

            logger.debug(
                f"[notify] _send_alert_notification: reason={reason!r}, "
                f"play_sound={play_sound}, alert_id={alert.get_unique_id()!r}, "
                f"title={title!r}"
            )

            # Compute sound candidates based on alert content (only if playing sound)
            sound_candidates = None
            if play_sound:
                try:
                    from .notifications.alert_sound_mapper import get_candidate_sound_events

                    sound_candidates = get_candidate_sound_events(alert)
                    logger.debug(f"[notify] Sound candidates for alert: {sound_candidates}")
                except Exception as e:
                    logger.debug(f"[notify] Sound mapper unavailable: {e}")

            # Send the notification, providing candidate-based sound selection
            logger.debug(f"[notify] Calling notifier.send_notification for: {title!r}")
            logger.info(
                "[notify] Sending alert notification: alert_id=%r reason=%s play_sound=%s "
                "title=%r activation=%r",
                alert.get_unique_id(),
                reason,
                play_sound,
                title,
                "alert_details",
            )
            success = self.notifier.send_notification(
                title=title,
                message=message,
                timeout=15,  # Longer timeout for weather alerts
                sound_candidates=sound_candidates,
                play_sound=play_sound,
                activation_arguments=serialize_activation_request(
                    NotificationActivationRequest(
                        kind="alert_details",
                        alert_id=alert.get_unique_id(),
                    )
                ),
            )

            if success:
                logger.info(f"[notify] Alert notification sent: {title[:60]!r}")
            else:
                logger.warning(
                    f"[notify] notifier.send_notification returned False: {title[:60]!r}"
                )

            return success

        except Exception as e:
            logger.error(f"[notify] Error in _send_alert_notification: {type(e).__name__}: {e}")
            return False

    async def notify_lifecycle_changes(
        self,
        diff: AlertLifecycleDiff,
    ) -> int:
        """
        Fire desktop notifications for updated, escalated, extended, and cancelled alerts.

        New alerts are handled by :meth:`process_and_notify`.  This method
        covers the remaining lifecycle events so users hear about alerts that
        changed content, escalated in severity, had their expiry extended, or
        were withdrawn.

        Args:
        ----
            diff: The :class:`~accessiweather.alert_lifecycle.AlertLifecycleDiff`
                produced by the most recent fetch.

        Returns:
        -------
            Number of notifications sent.

        """
        if not diff.has_changes:
            return 0

        if not self.alert_manager.settings.notifications_enabled:
            logger.debug("[notify] lifecycle notifications skipped — notifications disabled")
            return 0

        sent = 0

        # --- Updated alerts (content changed, not escalated) ---
        for change in diff.updated_alerts:
            if change.alert is None:
                continue
            reason = "content_changed"
            try:
                success = await self._send_alert_notification(
                    change.alert, reason, play_sound=False
                )
                if success:
                    sent += 1
                    logger.info(
                        f"[notify] lifecycle update notification sent: "
                        f"{change.title!r} reason={reason}"
                    )
            except Exception as exc:
                logger.error(
                    f"[notify] lifecycle update notification failed for {change.alert_id!r}: {exc}"
                )

        # --- Escalated alerts (severity upgraded -- play sound) ---
        for change in diff.escalated_alerts:
            if change.alert is None:
                continue
            try:
                success = await self._send_alert_notification(
                    change.alert, "escalation", play_sound=True
                )
                if success:
                    sent += 1
                    logger.info(
                        f"[notify] lifecycle escalation notification sent: {change.title!r} "
                        f"({change.old_severity} -> {change.new_severity})"
                    )
            except Exception as exc:
                logger.error(
                    f"[notify] lifecycle escalation notification failed for "
                    f"{change.alert_id!r}: {exc}"
                )

        # --- Extended alerts (expiry pushed out -- informational, no sound) ---
        for change in diff.extended_alerts:
            if change.alert is None:
                continue
            try:
                success = await self._send_alert_notification(
                    change.alert, "extended", play_sound=False
                )
                if success:
                    sent += 1
                    logger.info(f"[notify] lifecycle extended notification sent: {change.title!r}")
            except Exception as exc:
                logger.error(
                    f"[notify] lifecycle extended notification failed for "
                    f"{change.alert_id!r}: {exc}"
                )

        # --- Cancelled alerts ---
        for change in diff.cancelled_alerts:
            try:
                title = f"CANCELLED: {change.title}" if change.title else "Alert Cancelled"
                message = (
                    f"The alert '{change.title}' has been cancelled or expired."
                    if change.title
                    else "A weather alert has been cancelled."
                )
                success = self.notifier.send_notification(
                    title=title,
                    message=message,
                    timeout=10,
                    play_sound=False,
                )
                if success:
                    sent += 1
                    logger.info(f"[notify] lifecycle cancel notification sent: {change.title!r}")
            except Exception as exc:
                logger.error(
                    f"[notify] lifecycle cancel notification failed for {change.alert_id!r}: {exc}"
                )

        return sent

    def update_settings(
        self,
        settings: AlertSettings,
    ):
        """Update alert notification settings."""
        logger.debug(
            "[notify] update_settings: app_settings=%s incoming_manager_settings=%s",
            _app_settings_debug_summary(self.settings),
            {
                "notifications_enabled": settings.notifications_enabled,
                "sound_enabled": settings.sound_enabled,
                "min_severity_priority": settings.min_severity_priority,
                "global_cooldown_minutes": settings.global_cooldown,
                "per_alert_cooldown_minutes": settings.per_alert_cooldown,
                "freshness_window_minutes": settings.freshness_window_minutes,
                "max_notifications_per_hour": settings.max_notifications_per_hour,
            },
        )
        self.alert_manager.update_settings(settings)
        logger.info("Alert notification settings updated")

    def get_settings(self) -> AlertSettings:
        """Get current alert notification settings."""
        return self.alert_manager.settings

    def get_statistics(self) -> dict:
        """Get notification statistics."""
        return self.alert_manager.get_alert_statistics()

    def clear_alert_state(self):
        """Clear all alert state (for testing or reset)."""
        self.alert_manager.clear_state()
        logger.info("Alert notification state cleared")

    async def test_notification(self, severity: str = "Moderate") -> bool:
        """
        Send a test notification to verify the system is working.

        Args:
        ----
            severity: Severity level for the test alert

        Returns:
        -------
            True if test notification was sent successfully

        """
        try:
            test_alert = WeatherAlert(
                title="Test Weather Alert",
                description="This is a test notification to verify the alert system is working properly.",
                severity=severity,
                urgency="Immediate",
                certainty="Observed",
                event="Test Alert",
                headline="Test notification - AccessiWeather alert system is functioning",
                instruction="No action required - this is a test.",
                areas=["Test Area"],
                id="test-alert-" + str(asyncio.get_event_loop().time()),
            )

            success = await self._send_alert_notification(test_alert, "new_alert")

            if success:
                logger.info("Test alert notification sent successfully")
            else:
                logger.warning("Test alert notification failed")

            return success

        except Exception as e:
            logger.error(f"Error sending test notification: {e}")
            return False
