"""User preference model for alert notifications."""

from __future__ import annotations

from .alert_manager import AlertSettings
from .constants import (
    SEVERITY_PRIORITY_EXTREME,
    SEVERITY_PRIORITY_MINOR,
    SEVERITY_PRIORITY_MODERATE,
    SEVERITY_PRIORITY_SEVERE,
    SEVERITY_PRIORITY_UNKNOWN,
)


class AlertNotificationPreferences:
    """User preferences for alert notifications."""

    def __init__(self):
        """Initialize the instance."""
        self.notify_extreme = True
        self.notify_severe = True
        self.notify_moderate = True
        self.notify_minor = False
        self.notify_unknown = False
        self.ignored_categories = set()
        self.global_cooldown_minutes = 5
        self.per_alert_cooldown_minutes = 60
        self.escalation_cooldown_minutes = 15
        self.max_notifications_per_hour = 10
        self.notifications_enabled = True
        self.sound_enabled = True
        self.show_expiration_time = True
        self.show_affected_areas = True
        self.notification_timeout_seconds = 15

    def to_alert_settings(self) -> AlertSettings:
        """Convert to AlertSettings object for AlertManager."""
        settings = AlertSettings()

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
            settings.min_severity_priority = 6

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
        self.notify_extreme = settings.min_severity_priority <= SEVERITY_PRIORITY_EXTREME
        self.notify_severe = settings.min_severity_priority <= SEVERITY_PRIORITY_SEVERE
        self.notify_moderate = settings.min_severity_priority <= SEVERITY_PRIORITY_MODERATE
        self.notify_minor = settings.min_severity_priority <= SEVERITY_PRIORITY_MINOR
        self.notify_unknown = settings.min_severity_priority <= SEVERITY_PRIORITY_UNKNOWN
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
