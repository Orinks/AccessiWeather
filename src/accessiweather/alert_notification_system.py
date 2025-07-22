"""Enhanced alert notification system for AccessiWeather.

This module provides a comprehensive notification system that integrates
with the AlertManager to provide user-controlled, accessible notifications
with proper cooldown and filtering capabilities.
"""

import asyncio
import logging

from .alert_manager import AlertManager, AlertSettings
from .models import WeatherAlert, WeatherAlerts
from .notifications.toast_notifier import SafeDesktopNotifier

logger = logging.getLogger(__name__)


class AlertNotificationSystem:
    """Enhanced notification system with user controls and accessibility features."""

    def __init__(self, alert_manager: AlertManager, notifier: SafeDesktopNotifier | None = None):
        self.alert_manager = alert_manager
        self.notifier = notifier or SafeDesktopNotifier()

        # Notification templates for different reasons
        self.notification_templates = {
            "new_alert": {
                "title_format": "New Weather Alert: {event}",
                "message_format": "{headline}",
                "sound_type": "alert",
            },
            "escalation": {
                "title_format": "ESCALATED: {event}",
                "message_format": "Severity increased - {headline}",
                "sound_type": "urgent",
            },
            "content_changed": {
                "title_format": "Updated: {event}",
                "message_format": "Alert updated - {headline}",
                "sound_type": "notification",
            },
            "reminder": {
                "title_format": "Reminder: {event}",
                "message_format": "{headline}",
                "sound_type": "notification",
            },
        }

        logger.info("AlertNotificationSystem initialized")

    async def process_and_notify(self, alerts: WeatherAlerts) -> int:
        """Process alerts and send notifications for qualifying alerts.

        Returns:
            Number of notifications sent.

        """
        try:
            # Use AlertManager to determine which alerts need notifications
            notifications_to_send = self.alert_manager.process_alerts(alerts)

            if not notifications_to_send:
                logger.debug("No notifications to send")
                return 0

            # Send notifications
            notifications_sent = 0
            for alert, reason in notifications_to_send:
                try:
                    success = await self._send_alert_notification(alert, reason)
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

    async def _send_alert_notification(self, alert: WeatherAlert, reason: str) -> bool:
        """Send a notification for a specific alert.

        Args:
            alert: The weather alert to notify about
            reason: The reason for notification (new_alert, escalation, etc.)

        Returns:
            True if notification was sent successfully

        """
        try:
            # Get notification template
            template = self.notification_templates.get(
                reason, self.notification_templates["new_alert"]
            )

            # Format title and message
            title = template["title_format"].format(
                event=alert.event or "Weather Alert", severity=alert.severity or "Unknown"
            )

            message = template["message_format"].format(
                headline=alert.headline or alert.title or "A weather alert has been issued.",
                description=alert.description[:100] + "..."
                if len(alert.description or "") > 100
                else alert.description or "",
                severity=alert.severity or "Unknown",
                urgency=alert.urgency or "Unknown",
            )

            # Add location context if available
            if alert.areas:
                location_text = ", ".join(alert.areas[:2])  # Limit to first 2 areas
                if len(alert.areas) > 2:
                    location_text += f" and {len(alert.areas) - 2} more areas"
                message += f"\n\nAffected areas: {location_text}"

            # Add expiration info if available
            if alert.expires:
                expires_str = alert.expires.strftime("%I:%M %p on %m/%d")
                message += f"\n\nExpires: {expires_str}"

            # Send the notification
            success = self.notifier.send_notification(
                title=title,
                message=message,
                timeout=15,  # Longer timeout for weather alerts
            )

            if success:
                logger.info(f"Alert notification sent: {title[:50]}...")
            else:
                logger.warning(f"Failed to send alert notification: {title[:50]}...")

            return success

        except Exception as e:
            logger.error(f"Error formatting/sending alert notification: {e}")
            return False

    def update_settings(self, settings: AlertSettings):
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
        """Send a test notification to verify the system is working.

        Args:
            severity: Severity level for the test alert

        Returns:
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
        self.notify_extreme = settings.min_severity_priority <= 5
        self.notify_severe = settings.min_severity_priority <= 4
        self.notify_moderate = settings.min_severity_priority <= 3
        self.notify_minor = settings.min_severity_priority <= 2
        self.notify_unknown = settings.min_severity_priority <= 1

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
