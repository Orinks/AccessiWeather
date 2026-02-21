"""
Alert management system for AccessiWeather.

This module provides comprehensive alert state tracking, change detection,
and notification management following the design principles for unique
alert identification and user controls.
"""

import json
import logging
import os
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
    SECONDS_PER_HOUR,
    SEVERITY_PRIORITY_MAP,
)
from .models import WeatherAlert, WeatherAlerts

logger = logging.getLogger(__name__)


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
        """
        Initialize alert state.

        Args:
        ----
            alert_id: Unique identifier for the alert
            content_hash: Hash of alert content for change detection
            first_seen: Timestamp when alert was first seen
            last_notified: Timestamp of last notification sent
            notification_count: Number of times notifications were sent
            severity_priority: Numeric severity priority (1-5)
            alert_sent_time: Timestamp when alert was issued by the provider (sent/effective)

        """
        self.alert_id = alert_id
        self.first_seen = first_seen
        self.last_notified = last_notified
        self.notification_count = notification_count
        self.alert_sent_time = alert_sent_time

        # Bounded history: (content_hash, severity_priority, timestamp)
        self.hash_history: deque[tuple[str, int, float]] = deque(maxlen=ALERT_HISTORY_MAX_LENGTH)
        # Add initial state to history
        self.add_hash(content_hash, severity_priority)

    @property
    def content_hash(self) -> str:
        """Get current content hash (most recent in history)."""
        if not self.hash_history:
            return ""
        return self.hash_history[-1][0]

    def add_hash(self, content_hash: str, severity_priority: int, timestamp: float | None = None):
        """
        Add a new content hash to history.

        Args:
        ----
            content_hash: Hash of alert content
            severity_priority: Numeric severity priority (1-5)
            timestamp: Unix timestamp (defaults to current time)

        """
        if timestamp is None:
            timestamp = time.time()
        self.hash_history.append((content_hash, severity_priority, timestamp))

    def has_changed(self, new_hash: str) -> bool:
        """
        Check if content has changed from most recent state.

        Args:
        ----
            new_hash: New content hash to compare

        Returns:
        -------
            True if content has changed

        """
        if not self.hash_history:
            return True
        return self.hash_history[-1][0] != new_hash

    def is_escalated(self, new_priority: int) -> bool:
        """
        Check if alert has escalated in severity.

        Compares new priority against the highest priority seen in history.

        Args:
        ----
            new_priority: New severity priority to check

        Returns:
        -------
            True if new priority is higher than any in history

        """
        if not self.hash_history:
            return False

        # Get highest priority from history
        max_historical_priority = max(entry[1] for entry in self.hash_history)
        return new_priority > max_historical_priority

    def get_previous_priority(self) -> int:
        """
        Get the previous severity priority.

        Returns
        -------
            Previous priority, or 1 (unknown) if no history

        """
        if len(self.hash_history) < 2:
            return 1  # Default to unknown priority
        return self.hash_history[-2][1]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "alert_id": self.alert_id,
            "first_seen": self.first_seen.isoformat(),
            "last_notified": self.last_notified.isoformat() if self.last_notified else None,
            "notification_count": self.notification_count,
            "alert_sent_time": self.alert_sent_time.isoformat() if self.alert_sent_time else None,
            # Store history as list of [hash, priority, timestamp]
            "hash_history": [[h, p, t] for h, p, t in self.hash_history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AlertState":
        """
        Create from dictionary loaded from JSON.

        Handles both old format (single content_hash) and new format (hash_history).
        """
        alert_id = data["alert_id"]
        first_seen = datetime.fromisoformat(data["first_seen"])
        last_notified = (
            datetime.fromisoformat(data["last_notified"]) if data.get("last_notified") else None
        )
        notification_count = data.get("notification_count", 0)
        alert_sent_time = (
            datetime.fromisoformat(data["alert_sent_time"]) if data.get("alert_sent_time") else None
        )

        # Handle migration from old format
        if "hash_history" in data:
            # New format with history
            state = cls(
                alert_id=alert_id,
                content_hash="",  # Will be replaced by history
                first_seen=first_seen,
                last_notified=last_notified,
                notification_count=notification_count,
                severity_priority=1,
                alert_sent_time=alert_sent_time,
            )
            # Clear the initial entry and load history
            state.hash_history.clear()
            for entry in data["hash_history"]:
                h, p, t = entry
                state.hash_history.append((h, p, t))
        else:
            # Old format with single content_hash - migrate
            content_hash = data.get("content_hash", "")
            state = cls(
                alert_id=alert_id,
                content_hash=content_hash,
                first_seen=first_seen,
                last_notified=last_notified,
                notification_count=notification_count,
                severity_priority=1,  # Unknown priority for migrated data
                alert_sent_time=alert_sent_time,
            )

        return state


class AlertSettings:
    """Alert notification settings and preferences."""

    def __init__(self):
        """Initialize the instance."""
        # Severity threshold (minimum severity to notify)
        self.min_severity_priority = DEFAULT_MIN_SEVERITY_PRIORITY

        # Cooldown periods (in minutes)
        self.global_cooldown = DEFAULT_GLOBAL_COOLDOWN_MINUTES
        self.per_alert_cooldown = DEFAULT_PER_ALERT_COOLDOWN_MINUTES
        self.escalation_cooldown = DEFAULT_ESCALATION_COOLDOWN_MINUTES
        self.freshness_window_minutes = DEFAULT_FRESHNESS_WINDOW_MINUTES

        # Category filters (event types to ignore)
        self.ignored_categories: set[str] = set()

        # General settings
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

        # Token bucket for rate limiting
        self._rate_limit_tokens: float = float(self.settings.max_notifications_per_hour)
        self._rate_limit_capacity: float = float(self.settings.max_notifications_per_hour)
        self._rate_limit_refill_rate: float = (
            self.settings.max_notifications_per_hour / SECONDS_PER_HOUR
        )  # tokens per second
        self._rate_limit_last_refill: float = time.time()

        # Defer state loading until first use for faster startup
        self._state_loaded = False

        logger.info(f"AlertManager initialized with state file: {self.state_file}")

    def _ensure_state_loaded(self):
        """Ensure state is loaded before first use (lazy loading)."""
        if self._state_loaded:
            return
        self._state_loaded = True
        self._load_state()

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

            # Set secure permissions on POSIX systems
            try:
                if os.name != "nt":
                    os.chmod(self.state_file, 0o600)
            except Exception:
                logger.debug("Could not set strict permissions on alert state file", exc_info=True)

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

    def _refill_rate_limit_tokens(self):
        """
        Refill rate limit tokens based on elapsed time.

        Implements token bucket algorithm: tokens refill at a constant rate,
        allowing burst capacity up to the bucket size.
        """
        current_time = time.time()
        elapsed = current_time - self._rate_limit_last_refill

        # Calculate tokens to add based on elapsed time and refill rate
        tokens_to_add = elapsed * self._rate_limit_refill_rate

        # Add tokens but don't exceed capacity
        self._rate_limit_tokens = min(
            self._rate_limit_capacity, self._rate_limit_tokens + tokens_to_add
        )

        self._rate_limit_last_refill = current_time

        logger.debug(
            f"Rate limiter refilled: {tokens_to_add:.2f} tokens added, "
            f"current: {self._rate_limit_tokens:.2f}/{self._rate_limit_capacity}"
        )

    def _check_rate_limit(self) -> bool:
        """
        Check if rate limit allows sending a notification.

        Returns
        -------
            True if a token is available (notification can be sent)

        """
        self._refill_rate_limit_tokens()

        if self._rate_limit_tokens >= 1.0:
            self._rate_limit_tokens -= 1.0
            logger.debug(
                f"Rate limit check: PASS (tokens remaining: {self._rate_limit_tokens:.2f})"
            )
            return True

        logger.debug(
            f"Rate limit check: BLOCKED (tokens: {self._rate_limit_tokens:.2f}, need: 1.0)"
        )
        return False

    def _can_send_global_notification(self) -> bool:
        """Check if we can send a notification based on global cooldown."""
        if not self.last_global_notification:
            return True

        cooldown_period = timedelta(minutes=self.settings.global_cooldown)
        elapsed = datetime.now(UTC) - self.last_global_notification
        can_send = elapsed > cooldown_period
        if not can_send:
            remaining = cooldown_period - elapsed
            logger.debug(
                "[alertmgr] global cooldown active: elapsed=%.1fm, cooldown=%.0fm, remaining=%.1fm",
                elapsed.total_seconds() / 60,
                self.settings.global_cooldown,
                remaining.total_seconds() / 60,
            )
        return can_send

    def _is_alert_fresh(self, alert_sent_time: datetime | None) -> bool:
        """
        Check if alert was issued within the freshness window.

        Args:
        ----
            alert_sent_time: When the alert was issued by the provider (sent/effective timestamp)

        Returns:
        -------
            True if alert is within freshness window, False otherwise

        """
        if not alert_sent_time:
            return False

        # Ensure timezone-aware comparison
        # If naive datetime, assume it's already in UTC (as it should be from our parsers)
        if alert_sent_time.tzinfo is None:
            alert_sent_time = alert_sent_time.replace(tzinfo=UTC)

        # Get current time in UTC
        now = datetime.now(UTC)

        # Calculate age
        freshness_period = timedelta(minutes=self.settings.freshness_window_minutes)
        try:
            age = now - alert_sent_time
        except TypeError:
            # Handle any remaining timezone issues
            logger.warning(f"Timezone mismatch in freshness check: {now} vs {alert_sent_time}")
            return False

        is_fresh = age <= freshness_period and age >= timedelta(0)
        if is_fresh:
            logger.info(
                f"Alert is FRESH (age: {age.total_seconds() / 60:.1f} min, "
                f"window: {self.settings.freshness_window_minutes} min)"
            )
        return is_fresh

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
        elapsed = datetime.now(UTC) - alert_state.last_notified
        can_send = elapsed > cooldown_period
        if not can_send:
            remaining = cooldown_period - elapsed
            logger.debug(
                "[alertmgr] per-alert cooldown active for %r: "
                "elapsed=%.1fm, cooldown=%.0fm, remaining=%.1fm",
                alert_state.alert_id,
                elapsed.total_seconds() / 60,
                cooldown_minutes,
                remaining.total_seconds() / 60,
            )
        return can_send

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

        # Check token bucket rate limit
        if not self._check_rate_limit():
            return False, "rate_limit_exceeded"

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
        # Ensure state is loaded (lazy loading for faster startup)
        self._ensure_state_loaded()

        if not alerts or not alerts.has_alerts():
            return []

        notifications_to_send = []
        active_alerts = alerts.get_active_alerts()
        current_time = datetime.now(UTC)

        for alert in active_alerts:
            alert_id = alert.get_unique_id()
            content_hash = alert.get_content_hash()
            severity_priority = alert.get_severity_priority()

            # Extract alert sent/effective timestamp for freshness check
            alert_sent_time = alert.sent or alert.effective

            # Check if we should notify for this alert
            should_notify, reason = self._should_notify_alert(alert)
            if not should_notify:
                logger.info(
                    "[alertmgr] Skipping alert %r: %s (severity=%s)",
                    alert_id,
                    reason,
                    alert.severity,
                )
                continue

            # Get existing state or create new one
            existing_state = self.alert_states.get(alert_id)

            if existing_state is None:
                # New alert - always notify
                new_state = AlertState(
                    alert_id=alert_id,
                    content_hash=content_hash,
                    first_seen=current_time,
                    severity_priority=severity_priority,
                    alert_sent_time=alert_sent_time,
                )
                self.alert_states[alert_id] = new_state
                notifications_to_send.append((alert, "new_alert"))
                logger.info(f"New alert detected: {alert_id}")

            elif existing_state.has_changed(content_hash):
                # Alert content changed - check if we should notify
                is_escalation = existing_state.is_escalated(severity_priority)

                if self._can_send_alert_notification(existing_state, is_escalation):
                    # Add new state to history
                    existing_state.add_hash(content_hash, severity_priority)
                    # Update sent time if changed
                    if alert_sent_time and alert_sent_time != existing_state.alert_sent_time:
                        existing_state.alert_sent_time = alert_sent_time
                    notification_reason = "escalation" if is_escalation else "content_changed"
                    notifications_to_send.append((alert, notification_reason))
                    logger.info(f"Alert content changed: {alert_id} ({notification_reason})")
                else:
                    # Update hash even if we don't notify (track the change)
                    existing_state.add_hash(content_hash, severity_priority)
                    logger.info(
                        "[alertmgr] Alert content changed but per-alert cooldown active: %r",
                        alert_id,
                    )

            else:
                # Same alert, no changes - check freshness bypass
                # Only apply freshness bypass if content is identical AND alert never notified
                is_fresh = self._is_alert_fresh(alert_sent_time)

                if is_fresh and existing_state.last_notified is None:
                    # Fresh alert that was never notified - bypass per-alert cooldown
                    notifications_to_send.append((alert, "fresh_alert"))
                    logger.info(f"Fresh alert detected (never notified): {alert_id}")
                elif self._can_send_alert_notification(existing_state, False):
                    # Standard reminder after cooldown period
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

    def mark_alert_resolved(self, alert_id: str):
        """Mark an alert as resolved/expired."""
        self._ensure_state_loaded()
        if alert_id in self.alert_states:
            # We could add a resolved timestamp here if needed
            logger.info(f"Alert marked as resolved: {alert_id}")
            # For now, we keep the state for cooldown purposes
            # Could be enhanced to track resolution time

    def get_alert_statistics(self) -> dict:
        """Get statistics about alert processing."""
        self._ensure_state_loaded()
        now = datetime.now(UTC)

        # Refill tokens to get current state
        self._refill_rate_limit_tokens()

        # Count recent notifications
        recent_notifications = sum(
            1
            for state in self.alert_states.values()
            if state.last_notified
            and (now - state.last_notified).total_seconds() < SECONDS_PER_HOUR
        )

        return {
            "total_tracked_alerts": len(self.alert_states),
            "notifications_this_hour": self.notifications_this_hour,
            "recent_notifications": recent_notifications,
            "last_global_notification": self.last_global_notification.isoformat()
            if self.last_global_notification
            else None,
            "rate_limiter": {
                "available_tokens": round(self._rate_limit_tokens, 2),
                "capacity": self._rate_limit_capacity,
                "refill_rate_per_second": round(self._rate_limit_refill_rate, 4),
            },
            "settings": {
                "notifications_enabled": self.settings.notifications_enabled,
                "min_severity_priority": self.settings.min_severity_priority,
                "global_cooldown_minutes": self.settings.global_cooldown,
                "per_alert_cooldown_minutes": self.settings.per_alert_cooldown,
            },
        }

    def update_settings(self, new_settings: AlertSettings):
        """Update alert settings and reconfigure rate limiter."""
        old_max = self.settings.max_notifications_per_hour
        self.settings = new_settings

        # Reconfigure rate limiter if max notifications changed
        if old_max != new_settings.max_notifications_per_hour:
            # Preserve token ratio when capacity changes
            token_ratio = (
                self._rate_limit_tokens / self._rate_limit_capacity
                if self._rate_limit_capacity > 0
                else 1.0
            )

            self._rate_limit_capacity = float(new_settings.max_notifications_per_hour)
            self._rate_limit_tokens = token_ratio * self._rate_limit_capacity
            self._rate_limit_refill_rate = (
                new_settings.max_notifications_per_hour / SECONDS_PER_HOUR
            )

            logger.info(
                f"Rate limiter reconfigured: capacity={self._rate_limit_capacity}, "
                f"refill_rate={self._rate_limit_refill_rate:.4f} tokens/sec"
            )

        logger.info("Alert settings updated")

    def clear_state(self):
        """Clear all alert state (for testing or reset)."""
        self._state_loaded = True
        self.alert_states.clear()
        self.last_global_notification = None
        self.notifications_this_hour = 0
        self._save_state()
        logger.info("Alert state cleared")
