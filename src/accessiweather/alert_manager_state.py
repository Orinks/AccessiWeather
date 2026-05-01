"""State and settings models for alert management."""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime

from .constants import (
    ALERT_HISTORY_MAX_LENGTH,
    DEFAULT_ESCALATION_COOLDOWN_MINUTES,
    DEFAULT_FRESHNESS_WINDOW_MINUTES,
    DEFAULT_GLOBAL_COOLDOWN_MINUTES,
    DEFAULT_MAX_NOTIFICATIONS_PER_HOUR,
    DEFAULT_MIN_SEVERITY_PRIORITY,
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_PER_ALERT_COOLDOWN_MINUTES,
    DEFAULT_SOUND_ENABLED,
    SEVERITY_PRIORITY_MAP,
)


class AlertState:
    """
    Represents the state of a tracked alert with history tracking.

    Maintains a bounded history of content changes (hash, priority, timestamp)
    to enable accurate change detection and escalation tracking.
    """

    def __init__(
        self,
        alert_id: str,
        content_hash: str,
        first_seen: datetime,
        last_notified: datetime | None = None,
        notification_count: int = 0,
        severity_priority: int = 1,
        alert_sent_time: datetime | None = None,
    ):
        """Initialize alert state."""
        self.alert_id = alert_id
        self.first_seen = first_seen
        self.last_notified = last_notified
        self.notification_count = notification_count
        self.alert_sent_time = alert_sent_time

        self.hash_history: deque[tuple[str, int, float]] = deque(maxlen=ALERT_HISTORY_MAX_LENGTH)
        self.add_hash(content_hash, severity_priority)

    @property
    def content_hash(self) -> str:
        """Get current content hash."""
        if not self.hash_history:
            return ""
        return self.hash_history[-1][0]

    def add_hash(self, content_hash: str, severity_priority: int, timestamp: float | None = None):
        """Add a new content hash to history."""
        if timestamp is None:
            timestamp = time.time()
        self.hash_history.append((content_hash, severity_priority, timestamp))

    def has_changed(self, new_hash: str) -> bool:
        """Check if content has changed from most recent state."""
        if not self.hash_history:
            return True
        return self.hash_history[-1][0] != new_hash

    def is_escalated(self, new_priority: int) -> bool:
        """Check if alert has escalated against highest historical severity."""
        if not self.hash_history:
            return False
        max_historical_priority = max(entry[1] for entry in self.hash_history)
        return new_priority > max_historical_priority

    def get_previous_priority(self) -> int:
        """Get the previous severity priority."""
        if len(self.hash_history) < 2:
            return 1
        return self.hash_history[-2][1]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "alert_id": self.alert_id,
            "first_seen": self.first_seen.isoformat(),
            "last_notified": self.last_notified.isoformat() if self.last_notified else None,
            "notification_count": self.notification_count,
            "alert_sent_time": self.alert_sent_time.isoformat() if self.alert_sent_time else None,
            "hash_history": [[h, p, t] for h, p, t in self.hash_history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> AlertState:
        """Create from dictionary loaded from JSON."""
        alert_id = data["alert_id"]
        first_seen = datetime.fromisoformat(data["first_seen"])
        last_notified = (
            datetime.fromisoformat(data["last_notified"]) if data.get("last_notified") else None
        )
        notification_count = data.get("notification_count", 0)
        alert_sent_time = (
            datetime.fromisoformat(data["alert_sent_time"]) if data.get("alert_sent_time") else None
        )

        if "hash_history" in data:
            state = cls(
                alert_id=alert_id,
                content_hash="",
                first_seen=first_seen,
                last_notified=last_notified,
                notification_count=notification_count,
                severity_priority=1,
                alert_sent_time=alert_sent_time,
            )
            state.hash_history.clear()
            for entry in data["hash_history"]:
                h, p, t = entry
                state.hash_history.append((h, p, t))
            return state

        return cls(
            alert_id=alert_id,
            content_hash=data.get("content_hash", ""),
            first_seen=first_seen,
            last_notified=last_notified,
            notification_count=notification_count,
            severity_priority=1,
            alert_sent_time=alert_sent_time,
        )


class AlertSettings:
    """Alert notification settings and preferences."""

    def __init__(self):
        """Initialize the instance."""
        self.min_severity_priority = DEFAULT_MIN_SEVERITY_PRIORITY
        self.global_cooldown = DEFAULT_GLOBAL_COOLDOWN_MINUTES
        self.per_alert_cooldown = DEFAULT_PER_ALERT_COOLDOWN_MINUTES
        self.escalation_cooldown = DEFAULT_ESCALATION_COOLDOWN_MINUTES
        self.freshness_window_minutes = DEFAULT_FRESHNESS_WINDOW_MINUTES
        self.ignored_categories: set[str] = set()
        self.notifications_enabled = DEFAULT_NOTIFICATIONS_ENABLED
        self.sound_enabled = DEFAULT_SOUND_ENABLED
        self.max_notifications_per_hour = DEFAULT_MAX_NOTIFICATIONS_PER_HOUR

    def should_notify_severity(self, severity: str) -> bool:
        """Check if we should notify for this severity level."""
        if not self.notifications_enabled:
            return False
        priority = SEVERITY_PRIORITY_MAP.get(severity.lower(), SEVERITY_PRIORITY_MAP["unknown"])
        return priority >= self.min_severity_priority

    def should_notify_category(self, event: str) -> bool:
        """Check if we should notify for this event category."""
        if not event:
            return True
        return event.lower() not in self.ignored_categories
