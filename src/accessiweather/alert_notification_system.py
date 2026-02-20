"""
Enhanced alert notification system for AccessiWeather.

This module provides a comprehensive notification system that integrates
with the AlertManager to provide user-controlled, accessible notifications
with proper cooldown and filtering capabilities.
"""

import asyncio
import logging

from .alert_manager import AlertManager, AlertSettings
from .constants import (
    MAX_DISPLAYED_AREAS,
    MAX_NOTIFICATION_DESCRIPTION_LENGTH,
    SEVERITY_PRIORITY_EXTREME,
    SEVERITY_PRIORITY_MAP,
    SEVERITY_PRIORITY_MINOR,
    SEVERITY_PRIORITY_MODERATE,
    SEVERITY_PRIORITY_SEVERE,
    SEVERITY_PRIORITY_UNKNOWN,
)
from .display.presentation.formatters import format_display_datetime
from .models import AppSettings, WeatherAlert, WeatherAlerts
from .notifications.toast_notifier import SafeDesktopNotifier

logger = logging.getLogger(__name__)


def format_accessible_message(
    alert: WeatherAlert,
    reason: str,
    include_areas: bool = True,
    include_expiration: bool = True,
    settings: AppSettings | None = None,
) -> tuple[str, str]:
    """
    Format alert information for screen reader accessibility.

    Creates structured, concise messages that work well with assistive technology.
    Information is ordered by importance: severity/urgency, event type, headline,
    then supporting details.

    Args:
    ----
        alert: The weather alert to format
        reason: The reason for notification (new_alert, escalation, content_changed, reminder)
        include_areas: Whether to include affected areas in message
        include_expiration: Whether to include expiration time in message
        settings: Application settings for formatting preferences

    Returns:
    -------
        Tuple of (title, message) formatted for accessibility

    """
    # Format title with severity context
    severity = (alert.severity or "Unknown").upper()
    event = alert.event or "Weather Alert"

    if reason == "escalation":
        title = f"ESCALATED {severity}: {event}"
    elif reason == "content_changed":
        title = f"UPDATED {severity}: {event}"
    elif reason == "reminder":
        title = f"ACTIVE {severity}: {event}"
    else:  # new_alert
        title = f"{severity} ALERT: {event}"

    # Start message with urgency if available and critical
    message_parts = []

    urgency = (alert.urgency or "").lower()
    if urgency in ("immediate", "expected"):
        message_parts.append(f"{urgency.title()} action may be required.")

    # Add headline (primary content)
    headline = alert.headline or alert.title
    if headline:
        message_parts.append(headline)
    else:
        logger.warning(f"Alert {alert.get_unique_id()} missing headline")
        message_parts.append(f"A {severity.lower()} weather alert has been issued.")

    # Add truncated description if available
    if alert.description:
        desc = alert.description[:MAX_NOTIFICATION_DESCRIPTION_LENGTH]
        if len(alert.description) > MAX_NOTIFICATION_DESCRIPTION_LENGTH:
            desc += "..."
        message_parts.append(desc)

    # Add affected areas if requested and available
    if include_areas and alert.areas:
        location_parts = alert.areas[:MAX_DISPLAYED_AREAS]
        location_text = ", ".join(location_parts)
        if len(alert.areas) > MAX_DISPLAYED_AREAS:
            location_text += f" and {len(alert.areas) - MAX_DISPLAYED_AREAS} more"
        message_parts.append(f"Areas: {location_text}")

    # Add expiration if requested and available
    if include_expiration and alert.expires:
        # Extract time preferences
        if settings:
            time_display_mode = getattr(settings, "time_display_mode", "local")
            time_format_12hour = getattr(settings, "time_format_12hour", True)
            show_timezone_suffix = getattr(settings, "show_timezone_suffix", False)
        else:
            time_display_mode = "local"
            time_format_12hour = True
            show_timezone_suffix = False

        expires_str = format_display_datetime(
            alert.expires,
            time_display_mode=time_display_mode,
            use_12hour=time_format_12hour,
            show_timezone=show_timezone_suffix,
            date_format="%b %d",
        )
        message_parts.append(f"Expires: {expires_str}")

    # Join all parts with double newlines for screen reader pause
    message = "\n\n".join(message_parts)

    return title, message


class AlertNotificationSystem:
    """Enhanced notification system with user controls and accessibility features."""

    def __init__(
        self,
        alert_manager: AlertManager,
        notifier: SafeDesktopNotifier | None = None,
        settings: AppSettings | None = None,
    ):
        """Initialize the instance."""
        self.alert_manager = alert_manager
        self.notifier = notifier or SafeDesktopNotifier()
        self.settings = settings

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
            logger.debug(f"[notify] process_and_notify: {alert_count} alert(s) received")

            # Use AlertManager to determine which alerts need notifications
            notifications_to_send = self.alert_manager.process_alerts(alerts)

            if not notifications_to_send:
                logger.debug(
                    f"[notify] AlertManager returned 0 notifications to send "
                    f"(all {alert_count} alert(s) already seen / in cooldown)"
                )
                return 0

            logger.info(f"[notify] AlertManager queued {len(notifications_to_send)} notification(s) to send")

            # Sort notifications by severity (highest first) to play sound for most severe
            # Higher priority number = more severe
            sorted_notifications = sorted(
                notifications_to_send,
                key=lambda x: SEVERITY_PRIORITY_MAP.get(
                    (x[0].severity or "unknown").lower(), SEVERITY_PRIORITY_UNKNOWN
                ),
                reverse=True,
            )

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
            success = self.notifier.send_notification(
                title=title,
                message=message,
                timeout=15,  # Longer timeout for weather alerts
                sound_candidates=sound_candidates,
                play_sound=play_sound,
            )

            if success:
                logger.info(f"[notify] Alert notification sent: {title[:60]!r}")
            else:
                logger.warning(f"[notify] notifier.send_notification returned False: {title[:60]!r}")

            return success

        except Exception as e:
            logger.error(f"[notify] Error in _send_alert_notification: {type(e).__name__}: {e}")
            return False

    def update_settings(
        self,
        settings: AlertSettings,
    ):
        """Update alert notification settings."""
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


class AlertNotificationPreferences:
    """User preferences for alert notifications."""

    def __init__(self):
        """Initialize the instance."""
        # Severity preferences
        self.notify_extreme = True
        self.notify_severe = True
        self.notify_moderate = True
        self.notify_minor = False
        self.notify_unknown = False

        # Category preferences (event types to ignore)
        self.ignored_categories = set()

        # Timing preferences
        self.global_cooldown_minutes = 5
        self.per_alert_cooldown_minutes = 60
        self.escalation_cooldown_minutes = 15
        self.max_notifications_per_hour = 10

        # General preferences
        self.notifications_enabled = True
        self.sound_enabled = True
        self.show_expiration_time = True
        self.show_affected_areas = True
        self.notification_timeout_seconds = 15

    def to_alert_settings(self) -> AlertSettings:
        """Convert to AlertSettings object for AlertManager."""
        settings = AlertSettings()

        # Map severity preferences to minimum priority
        if self.notify_unknown:
            settings.min_severity_priority = 1
        elif self.notify_minor:
            settings.min_severity_priority = 2
        elif self.notify_moderate:
            settings.min_severity_priority = 3
        elif self.notify_severe:
            settings.min_severity_priority = 4
        elif self.notify_extreme:
            settings.min_severity_priority = 5
        else:
            settings.min_severity_priority = 6  # Effectively disable notifications

        # Copy other settings
        settings.ignored_categories = self.ignored_categories.copy()
        settings.global_cooldown = self.global_cooldown_minutes
        settings.per_alert_cooldown = self.per_alert_cooldown_minutes
        settings.escalation_cooldown = self.escalation_cooldown_minutes
        settings.max_notifications_per_hour = self.max_notifications_per_hour
        settings.notifications_enabled = self.notifications_enabled
        settings.sound_enabled = self.sound_enabled

        return settings

    def from_alert_settings(self, settings: AlertSettings):
        """Update preferences from AlertSettings object."""
        # Map minimum priority back to individual severity flags
        self.notify_extreme = settings.min_severity_priority <= SEVERITY_PRIORITY_EXTREME
        self.notify_severe = settings.min_severity_priority <= SEVERITY_PRIORITY_SEVERE
        self.notify_moderate = settings.min_severity_priority <= SEVERITY_PRIORITY_MODERATE
        self.notify_minor = settings.min_severity_priority <= SEVERITY_PRIORITY_MINOR
        self.notify_unknown = settings.min_severity_priority <= SEVERITY_PRIORITY_UNKNOWN

        # Copy other settings
        self.ignored_categories = settings.ignored_categories.copy()
        self.global_cooldown_minutes = settings.global_cooldown
        self.per_alert_cooldown_minutes = settings.per_alert_cooldown
        self.escalation_cooldown_minutes = settings.escalation_cooldown
        self.max_notifications_per_hour = settings.max_notifications_per_hour
        self.notifications_enabled = settings.notifications_enabled
        self.sound_enabled = settings.sound_enabled

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "notify_extreme": self.notify_extreme,
            "notify_severe": self.notify_severe,
            "notify_moderate": self.notify_moderate,
            "notify_minor": self.notify_minor,
            "notify_unknown": self.notify_unknown,
            "ignored_categories": list(self.ignored_categories),
            "global_cooldown_minutes": self.global_cooldown_minutes,
            "per_alert_cooldown_minutes": self.per_alert_cooldown_minutes,
            "escalation_cooldown_minutes": self.escalation_cooldown_minutes,
            "max_notifications_per_hour": self.max_notifications_per_hour,
            "notifications_enabled": self.notifications_enabled,
            "sound_enabled": self.sound_enabled,
            "show_expiration_time": self.show_expiration_time,
            "show_affected_areas": self.show_affected_areas,
            "notification_timeout_seconds": self.notification_timeout_seconds,
        }

    def from_dict(self, data: dict):
        """Load from dictionary."""
        self.notify_extreme = data.get("notify_extreme", True)
        self.notify_severe = data.get("notify_severe", True)
        self.notify_moderate = data.get("notify_moderate", True)
        self.notify_minor = data.get("notify_minor", False)
        self.notify_unknown = data.get("notify_unknown", False)
        self.ignored_categories = set(data.get("ignored_categories", []))
        self.global_cooldown_minutes = data.get("global_cooldown_minutes", 5)
        self.per_alert_cooldown_minutes = data.get("per_alert_cooldown_minutes", 60)
        self.escalation_cooldown_minutes = data.get("escalation_cooldown_minutes", 15)
        self.max_notifications_per_hour = data.get("max_notifications_per_hour", 10)
        self.notifications_enabled = data.get("notifications_enabled", True)
        self.sound_enabled = data.get("sound_enabled", True)
        self.show_expiration_time = data.get("show_expiration_time", True)
        self.show_affected_areas = data.get("show_affected_areas", True)
        self.notification_timeout_seconds = data.get("notification_timeout_seconds", 15)
