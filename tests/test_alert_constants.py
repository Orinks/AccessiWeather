"""Tests for alert system constants."""

from __future__ import annotations

import pytest

from accessiweather.constants import (
    ALERT_HISTORY_MAX_LENGTH,
    ALERT_STATE_RETENTION_DAYS,
    DEFAULT_ESCALATION_COOLDOWN_MINUTES,
    DEFAULT_GLOBAL_COOLDOWN_MINUTES,
    DEFAULT_MAX_NOTIFICATIONS_PER_HOUR,
    DEFAULT_MIN_SEVERITY_PRIORITY,
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_PER_ALERT_COOLDOWN_MINUTES,
    DEFAULT_SOUND_ENABLED,
    MAX_DISPLAYED_AREAS,
    MAX_NOTIFICATION_DESCRIPTION_LENGTH,
    NOTIFICATION_TIMEOUT_SECONDS,
    SECONDS_PER_HOUR,
    SEVERITY_PRIORITY_EXTREME,
    SEVERITY_PRIORITY_MAP,
    SEVERITY_PRIORITY_MINOR,
    SEVERITY_PRIORITY_MODERATE,
    SEVERITY_PRIORITY_SEVERE,
    SEVERITY_PRIORITY_UNKNOWN,
)


@pytest.mark.unit
class TestSeverityPriorities:
    """Test severity priority constants."""

    def test_severity_priorities_are_ordered(self):
        """Severity priorities should increase with severity level."""
        assert SEVERITY_PRIORITY_UNKNOWN == 1
        assert SEVERITY_PRIORITY_MINOR == 2
        assert SEVERITY_PRIORITY_MODERATE == 3
        assert SEVERITY_PRIORITY_SEVERE == 4
        assert SEVERITY_PRIORITY_EXTREME == 5

    def test_severity_map_completeness(self):
        """Severity map should contain all severity levels."""
        expected_keys = {"unknown", "minor", "moderate", "severe", "extreme"}
        assert set(SEVERITY_PRIORITY_MAP.keys()) == expected_keys

    def test_severity_map_values_match_constants(self):
        """Severity map values should match individual constants."""
        assert SEVERITY_PRIORITY_MAP["unknown"] == SEVERITY_PRIORITY_UNKNOWN
        assert SEVERITY_PRIORITY_MAP["minor"] == SEVERITY_PRIORITY_MINOR
        assert SEVERITY_PRIORITY_MAP["moderate"] == SEVERITY_PRIORITY_MODERATE
        assert SEVERITY_PRIORITY_MAP["severe"] == SEVERITY_PRIORITY_SEVERE
        assert SEVERITY_PRIORITY_MAP["extreme"] == SEVERITY_PRIORITY_EXTREME

    def test_severity_map_is_dict_str_int(self):
        """Severity map should be properly typed."""
        assert isinstance(SEVERITY_PRIORITY_MAP, dict)
        for key, value in SEVERITY_PRIORITY_MAP.items():
            assert isinstance(key, str)
            assert isinstance(value, int)


@pytest.mark.unit
class TestCooldownConstants:
    """Test cooldown period constants."""

    def test_cooldown_values_are_positive(self):
        """All cooldown values should be positive integers."""
        assert DEFAULT_GLOBAL_COOLDOWN_MINUTES > 0
        assert DEFAULT_PER_ALERT_COOLDOWN_MINUTES > 0
        assert DEFAULT_ESCALATION_COOLDOWN_MINUTES > 0

    def test_cooldown_relationships(self):
        """Cooldown periods should have logical relationships."""
        # Global should be shortest (most frequent)
        assert DEFAULT_GLOBAL_COOLDOWN_MINUTES < DEFAULT_PER_ALERT_COOLDOWN_MINUTES
        # Escalation should be shorter than per-alert
        assert DEFAULT_ESCALATION_COOLDOWN_MINUTES < DEFAULT_PER_ALERT_COOLDOWN_MINUTES
        # Escalation can be longer than global
        assert DEFAULT_ESCALATION_COOLDOWN_MINUTES >= DEFAULT_GLOBAL_COOLDOWN_MINUTES


@pytest.mark.unit
class TestRateLimitingConstants:
    """Test rate limiting constants."""

    def test_max_notifications_per_hour_is_reasonable(self):
        """Max notifications per hour should be a reasonable limit."""
        assert DEFAULT_MAX_NOTIFICATIONS_PER_HOUR > 0
        assert DEFAULT_MAX_NOTIFICATIONS_PER_HOUR <= 60  # No more than 1 per minute

    def test_seconds_per_hour_is_correct(self):
        """Seconds per hour should be accurate."""
        assert SECONDS_PER_HOUR == 3600


@pytest.mark.unit
class TestNotificationFormattingConstants:
    """Test notification formatting constants."""

    def test_description_length_is_reasonable(self):
        """Max description length should be reasonable for notifications."""
        assert MAX_NOTIFICATION_DESCRIPTION_LENGTH > 50  # Not too short
        assert MAX_NOTIFICATION_DESCRIPTION_LENGTH <= 500  # Not too long

    def test_displayed_areas_limit_is_reasonable(self):
        """Max displayed areas should prevent notification overflow."""
        assert MAX_DISPLAYED_AREAS >= 1
        assert MAX_DISPLAYED_AREAS <= 5

    def test_notification_timeout_is_reasonable(self):
        """Notification timeout should give users time to read."""
        assert NOTIFICATION_TIMEOUT_SECONDS >= 5  # At least 5 seconds
        assert NOTIFICATION_TIMEOUT_SECONDS <= 60  # No more than 1 minute


@pytest.mark.unit
class TestStateManagementConstants:
    """Test alert state management constants."""

    def test_retention_days_is_reasonable(self):
        """Alert state retention should be long enough but not excessive."""
        assert ALERT_STATE_RETENTION_DAYS >= 1  # At least 1 day
        assert ALERT_STATE_RETENTION_DAYS <= 30  # No more than 1 month

    def test_history_max_length_is_reasonable(self):
        """History length should be sufficient for change detection."""
        assert ALERT_HISTORY_MAX_LENGTH >= 3  # At least 3 entries
        assert ALERT_HISTORY_MAX_LENGTH <= 20  # Not excessive


@pytest.mark.unit
class TestDefaultAlertSettings:
    """Test default alert setting constants."""

    def test_default_min_severity_is_valid(self):
        """Default minimum severity should be a valid priority."""
        assert DEFAULT_MIN_SEVERITY_PRIORITY in SEVERITY_PRIORITY_MAP.values()

    def test_default_min_severity_is_reasonable(self):
        """Default should notify for minor and above."""
        assert DEFAULT_MIN_SEVERITY_PRIORITY == SEVERITY_PRIORITY_MINOR

    def test_default_notifications_enabled(self):
        """Notifications should be enabled by default."""
        assert DEFAULT_NOTIFICATIONS_ENABLED is True

    def test_default_sound_enabled(self):
        """Sound should be enabled by default."""
        assert DEFAULT_SOUND_ENABLED is True


@pytest.mark.unit
class TestConstantsIntegration:
    """Test that constants work together correctly."""

    def test_severity_priorities_support_threshold_filtering(self):
        """Verify severity priorities can be used for threshold filtering."""
        # Simulate filtering alerts by minimum severity
        min_severity = SEVERITY_PRIORITY_MODERATE

        # These should pass the filter
        assert SEVERITY_PRIORITY_MAP["moderate"] >= min_severity
        assert SEVERITY_PRIORITY_MAP["severe"] >= min_severity
        assert SEVERITY_PRIORITY_MAP["extreme"] >= min_severity

        # These should not pass
        assert SEVERITY_PRIORITY_MAP["minor"] < min_severity
        assert SEVERITY_PRIORITY_MAP["unknown"] < min_severity

    def test_cooldown_constants_support_timedelta_creation(self):
        """Verify cooldown constants can create timedelta objects."""
        from datetime import timedelta

        # Should be able to create timedeltas without errors
        global_cooldown = timedelta(minutes=DEFAULT_GLOBAL_COOLDOWN_MINUTES)
        per_alert_cooldown = timedelta(minutes=DEFAULT_PER_ALERT_COOLDOWN_MINUTES)
        escalation_cooldown = timedelta(minutes=DEFAULT_ESCALATION_COOLDOWN_MINUTES)

        assert isinstance(global_cooldown, timedelta)
        assert isinstance(per_alert_cooldown, timedelta)
        assert isinstance(escalation_cooldown, timedelta)
