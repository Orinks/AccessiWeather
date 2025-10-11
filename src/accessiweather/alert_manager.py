"""
Alert management system for AccessiWeather.

This module provides comprehensive alert state tracking, change detection,
and notification management following the design principles for unique
alert identification and user controls.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import WeatherAlert, WeatherAlerts

logger = logging.getLogger(__name__)


class AlertState:
    """Represents the state of a tracked alert."""

    def __init__(
        self,
        alert_id: str,
        content_hash: str,
        first_seen: datetime,
        last_notified: datetime | None = None,
        notification_count: int = 0,
    ):
        """Initialize the instance."""
        self.alert_id = alert_id
        self.content_hash = content_hash
        self.first_seen = first_seen
        self.last_notified = last_notified
        self.notification_count = notification_count

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "alert_id": self.alert_id,
            "content_hash": self.content_hash,
            "first_seen": self.first_seen.isoformat(),
            "last_notified": self.last_notified.isoformat() if self.last_notified else None,
            "notification_count": self.notification_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AlertState":
        """Create from dictionary loaded from JSON."""
        return cls(
            alert_id=data["alert_id"],
            content_hash=data["content_hash"],
            first_seen=datetime.fromisoformat(data["first_seen"]),
            last_notified=datetime.fromisoformat(data["last_notified"])
            if data.get("last_notified")
            else None,
            notification_count=data.get("notification_count", 0),
        )


class AlertSettings:
    """Alert notification settings and preferences."""

    def __init__(self):
        """Initialize the instance."""
        # Severity threshold (minimum severity to notify)
        self.min_severity_priority = 2  # Default: minor and above

        # Cooldown periods (in minutes)
        self.global_cooldown = 5  # Don't spam notifications
        self.per_alert_cooldown = 60  # Don't re-notify same alert within 1 hour
        self.escalation_cooldown = 15  # Allow re-notification if severity increases

        # Category filters (event types to ignore)
        self.ignored_categories: set[str] = set()

        # General settings
        self.notifications_enabled = True
        self.sound_enabled = True
        self.max_notifications_per_hour = 10

    def should_notify_severity(self, severity: str) -> bool:
        """Check if we should notify for this severity level."""
        if not self.notifications_enabled:
            return False

        severity_map = {"extreme": 5, "severe": 4, "moderate": 3, "minor": 2, "unknown": 1}
        priority = severity_map.get(severity.lower(), 1)
        return priority >= self.min_severity_priority

    def should_notify_category(self, event: str) -> bool:
        """Check if we should notify for this event category."""
        if not event:
            return True
        return event.lower() not in self.ignored_categories


class AlertManager:
    """Manages alert state tracking, change detection, and notifications."""

    def __init__(self, config_dir: str, settings: AlertSettings | None = None):
        """Initialize the instance."""
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.config_dir / "alert_state.json"
        self.settings = settings or AlertSettings()

        # In-memory state tracking
        self.alert_states: dict[str, AlertState] = {}
        self.last_global_notification: datetime | None = None
        self.notifications_this_hour = 0
        self.hour_reset_time = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)

        # Load existing state
        self._load_state()

        logger.info(f"AlertManager initialized with state file: {self.state_file}")

    def _load_state(self):
        """Load alert state from persistent storage."""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    data = json.load(f)

                # Load alert states
                for state_data in data.get("alert_states", []):
                    state = AlertState.from_dict(state_data)
                    self.alert_states[state.alert_id] = state

                # Load global state
                if data.get("last_global_notification"):
                    self.last_global_notification = datetime.fromisoformat(
                        data["last_global_notification"]
                    )

                logger.info(f"Loaded {len(self.alert_states)} alert states from storage")
            else:
                logger.info("No existing alert state file found, starting fresh")

        except Exception as e:
            logger.error(f"Failed to load alert state: {e}")
            self.alert_states = {}

    def _save_state(self):
        """Save alert state to persistent storage."""
        try:
            # Clean up expired states before saving
            self._cleanup_expired_states()

            data = {
                "alert_states": [state.to_dict() for state in self.alert_states.values()],
                "last_global_notification": (
                    self.last_global_notification.isoformat()
                    if self.last_global_notification
                    else None
                ),
                "saved_at": datetime.now(UTC).isoformat(),
            }

            # Write atomically
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2)

            temp_file.replace(self.state_file)
            logger.debug(f"Saved {len(self.alert_states)} alert states to storage")

        except Exception as e:
            logger.error(f"Failed to save alert state: {e}")

    def _cleanup_expired_states(self):
        """Remove old alert states to prevent unbounded growth."""
        cutoff_time = datetime.now(UTC) - timedelta(days=7)  # Keep states for 7 days

        expired_ids = [
            alert_id
            for alert_id, state in self.alert_states.items()
            if state.first_seen < cutoff_time
        ]

        for alert_id in expired_ids:
            del self.alert_states[alert_id]

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired alert states")

    def _reset_hourly_counter(self):
        """Reset hourly notification counter if needed."""
        now = datetime.now(UTC)
        current_hour = now.replace(minute=0, second=0, microsecond=0)

        if current_hour > self.hour_reset_time:
            self.notifications_this_hour = 0
            self.hour_reset_time = current_hour

    def _can_send_global_notification(self) -> bool:
        """Check if we can send a notification based on global cooldown."""
        if not self.last_global_notification:
            return True

        cooldown_period = timedelta(minutes=self.settings.global_cooldown)
        return datetime.now(UTC) - self.last_global_notification > cooldown_period

    def _can_send_alert_notification(
        self, alert_state: AlertState, is_escalation: bool = False
    ) -> bool:
        """Check if we can send a notification for a specific alert."""
        if not alert_state.last_notified:
            return True

        # Use shorter cooldown for escalations
        cooldown_minutes = (
            self.settings.escalation_cooldown if is_escalation else self.settings.per_alert_cooldown
        )
        cooldown_period = timedelta(minutes=cooldown_minutes)

        return datetime.now(UTC) - alert_state.last_notified > cooldown_period

    def _should_notify_alert(self, alert: WeatherAlert) -> tuple[bool, str]:
        """Determine if we should notify for this alert and why."""
        # Check if notifications are enabled
        if not self.settings.notifications_enabled:
            return False, "notifications_disabled"

        # Check severity threshold
        if not self.settings.should_notify_severity(alert.severity):
            return False, f"severity_below_threshold_{alert.severity}"

        # Check category filters
        if alert.event and not self.settings.should_notify_category(alert.event):
            return False, f"category_ignored_{alert.event}"

        # Check if alert is expired
        if alert.is_expired():
            return False, "alert_expired"

        # Check hourly rate limit
        self._reset_hourly_counter()
        if self.notifications_this_hour >= self.settings.max_notifications_per_hour:
            return False, "hourly_rate_limit_exceeded"

        # Check global cooldown
        if not self._can_send_global_notification():
            return False, "global_cooldown_active"

        return True, "allowed"

    def process_alerts(self, alerts: WeatherAlerts) -> list[tuple[WeatherAlert, str]]:
        """
        Process incoming alerts and return list of alerts to notify.

        Returns
        -------
            List of tuples (alert, notification_reason) for alerts that should trigger notifications.

        """
        if not alerts or not alerts.has_alerts():
            return []

        notifications_to_send = []
        active_alerts = alerts.get_active_alerts()
        current_time = datetime.now(UTC)

        for alert in active_alerts:
            alert_id = alert.get_unique_id()
            content_hash = alert.get_content_hash()

            # Check if we should notify for this alert
            should_notify, reason = self._should_notify_alert(alert)
            if not should_notify:
                logger.debug(f"Skipping notification for alert {alert_id}: {reason}")
                continue

            # Get existing state or create new one
            existing_state = self.alert_states.get(alert_id)

            if existing_state is None:
                # New alert - always notify
                new_state = AlertState(
                    alert_id=alert_id, content_hash=content_hash, first_seen=current_time
                )
                self.alert_states[alert_id] = new_state
                notifications_to_send.append((alert, "new_alert"))
                logger.info(f"New alert detected: {alert_id}")

            elif existing_state.content_hash != content_hash:
                # Alert content changed - check if we should notify
                is_escalation = (
                    alert.get_severity_priority()
                    > self._get_previous_severity_priority(existing_state)
                )

                if self._can_send_alert_notification(existing_state, is_escalation):
                    existing_state.content_hash = content_hash
                    notification_reason = "escalation" if is_escalation else "content_changed"
                    notifications_to_send.append((alert, notification_reason))
                    logger.info(f"Alert content changed: {alert_id} ({notification_reason})")
                else:
                    logger.debug(f"Alert changed but in cooldown: {alert_id}")

            else:
                # Same alert, no changes - check if we should re-notify
                if self._can_send_alert_notification(existing_state, False):
                    notifications_to_send.append((alert, "reminder"))
                    logger.debug(f"Alert reminder: {alert_id}")

        # Update notification timestamps for alerts we're about to notify
        for alert, _reason in notifications_to_send:
            alert_id = alert.get_unique_id()
            if alert_id in self.alert_states:
                state = self.alert_states[alert_id]
                state.last_notified = current_time
                state.notification_count += 1

        # Update global notification time if we're sending any notifications
        if notifications_to_send:
            self.last_global_notification = current_time
            self.notifications_this_hour += len(notifications_to_send)

        # Save state changes
        if notifications_to_send or any(
            alert.get_unique_id() not in self.alert_states for alert in active_alerts
        ):
            self._save_state()

        logger.info(
            f"Processed {len(active_alerts)} alerts, {len(notifications_to_send)} notifications to send"
        )
        return notifications_to_send

    def _get_previous_severity_priority(self, state: AlertState) -> int:
        """
        Get the severity priority from the previous version of an alert.

        This is a simplified implementation - in a more sophisticated system,
        we might store the previous alert data.
        """
        # For now, assume previous severity was lower if content changed
        # This could be enhanced by storing more alert history
        return 1

    def mark_alert_resolved(self, alert_id: str):
        """Mark an alert as resolved/expired."""
        if alert_id in self.alert_states:
            # We could add a resolved timestamp here if needed
            logger.info(f"Alert marked as resolved: {alert_id}")
            # For now, we keep the state for cooldown purposes
            # Could be enhanced to track resolution time

    def get_alert_statistics(self) -> dict:
        """Get statistics about alert processing."""
        now = datetime.now(UTC)

        # Count recent notifications
        recent_notifications = sum(
            1
            for state in self.alert_states.values()
            if state.last_notified and (now - state.last_notified).total_seconds() < 3600
        )

        return {
            "total_tracked_alerts": len(self.alert_states),
            "notifications_this_hour": self.notifications_this_hour,
            "recent_notifications": recent_notifications,
            "last_global_notification": self.last_global_notification.isoformat()
            if self.last_global_notification
            else None,
            "settings": {
                "notifications_enabled": self.settings.notifications_enabled,
                "min_severity_priority": self.settings.min_severity_priority,
                "global_cooldown_minutes": self.settings.global_cooldown,
                "per_alert_cooldown_minutes": self.settings.per_alert_cooldown,
            },
        }

    def update_settings(self, new_settings: AlertSettings):
        """Update alert settings."""
        self.settings = new_settings
        logger.info("Alert settings updated")

    def clear_state(self):
        """Clear all alert state (for testing or reset)."""
        self.alert_states.clear()
        self.last_global_notification = None
        self.notifications_this_hour = 0
        self._save_state()
        logger.info("Alert state cleared")
