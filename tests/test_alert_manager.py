"""
Tests for the AlertManager.

Tests alert state tracking, change detection, and notification logic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from accessiweather.alert_manager import AlertManager, AlertSettings, AlertState
from accessiweather.models import WeatherAlert, WeatherAlerts


class TestAlertState:
    """Tests for AlertState class."""

    def test_create_alert_state(self):
        """Test creating an alert state."""
        state = AlertState(
            alert_id="test-123",
            content_hash="abc123",
            first_seen=datetime.now(UTC),
            severity_priority=3,
        )
        assert state.alert_id == "test-123"
        assert state.content_hash == "abc123"
        assert state.notification_count == 0

    def test_has_changed(self):
        """Test content change detection."""
        state = AlertState(
            alert_id="test",
            content_hash="hash1",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )
        assert state.has_changed("hash2") is True
        assert state.has_changed("hash1") is False

    def test_is_escalated(self):
        """Test escalation detection."""
        state = AlertState(
            alert_id="test",
            content_hash="hash",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )
        # Higher priority = escalated
        assert state.is_escalated(4) is True
        # Same or lower = not escalated
        assert state.is_escalated(2) is False
        assert state.is_escalated(1) is False

    def test_hash_history(self):
        """Test hash history tracking."""
        state = AlertState(
            alert_id="test",
            content_hash="hash1",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )
        state.add_hash("hash2", 3)
        state.add_hash("hash3", 4)

        assert state.content_hash == "hash3"  # Most recent
        assert len(state.hash_history) == 3

    def test_serialization(self):
        """Test to_dict and from_dict roundtrip."""
        original = AlertState(
            alert_id="test",
            content_hash="hash",
            first_seen=datetime.now(UTC),
            last_notified=datetime.now(UTC),
            notification_count=5,
            severity_priority=3,
        )
        data = original.to_dict()
        restored = AlertState.from_dict(data)

        assert restored.alert_id == original.alert_id
        assert restored.content_hash == original.content_hash
        assert restored.notification_count == original.notification_count


class TestAlertSettings:
    """Tests for AlertSettings class."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = AlertSettings()
        assert settings.notifications_enabled is True
        assert settings.min_severity_priority == 2  # Default is Minor (2)
        assert settings.global_cooldown == 5  # DEFAULT_GLOBAL_COOLDOWN_MINUTES

    def test_should_notify_severity(self):
        """Test severity filtering."""
        settings = AlertSettings()
        settings.min_severity_priority = 3  # Only Moderate and above

        # Severe (priority 4) should notify
        assert settings.should_notify_severity("Severe") is True
        # Minor (priority 2) should not
        assert settings.should_notify_severity("Minor") is False

    def test_should_notify_category(self):
        """Test category filtering."""
        settings = AlertSettings()
        settings.ignored_categories = {"heat advisory"}

        assert settings.should_notify_category("Tornado Warning") is True
        assert settings.should_notify_category("Heat Advisory") is False

    def test_disabled_notifications(self):
        """Test that disabled notifications blocks all."""
        settings = AlertSettings()
        settings.notifications_enabled = False

        assert settings.should_notify_severity("Extreme") is False


class TestAlertManager:
    """Tests for AlertManager class."""

    @pytest.fixture
    def config_dir(self, tmp_path):
        """Create temporary config directory."""
        return tmp_path / "alerts"

    @pytest.fixture
    def manager(self, config_dir):
        """Create AlertManager instance."""
        return AlertManager(str(config_dir))

    @pytest.fixture
    def sample_alert(self):
        """Create a sample alert."""
        return WeatherAlert(
            id="NWS-ALERT-001",
            title="Severe Thunderstorm Warning",
            description="Severe thunderstorms expected.",
            severity="Severe",
            urgency="Immediate",
            certainty="Observed",
            event="Severe Thunderstorm Warning",
            headline="Severe Thunderstorm Warning in effect",
            onset=datetime.now(UTC),
            expires=datetime.now(UTC) + timedelta(hours=2),
        )

    def test_process_new_alert(self, manager, sample_alert):
        """Test processing a new alert triggers notification."""
        alerts = WeatherAlerts(alerts=[sample_alert])
        notifications = manager.process_alerts(alerts)

        assert len(notifications) == 1
        alert, reason = notifications[0]
        assert reason == "new_alert"
        assert alert.id == sample_alert.id

    def test_duplicate_alert_no_notification(self, manager, sample_alert):
        """Test that duplicate alerts don't trigger notifications."""
        alerts = WeatherAlerts(alerts=[sample_alert])

        # First time - should notify
        manager.process_alerts(alerts)

        # Second time - should not notify (within cooldown)
        notifications = manager.process_alerts(alerts)
        # The second call should not produce a new_alert notification
        new_alerts = [n for n in notifications if n[1] == "new_alert"]
        assert len(new_alerts) == 0

    def test_expired_alert_filtered(self, manager):
        """Test that expired alerts are not processed."""
        expired_alert = WeatherAlert(
            id="expired",
            title="Expired Alert",
            description="This alert has expired.",
            severity="Moderate",
            urgency="Past",
            certainty="Observed",
            event="Test",
            expires=datetime.now(UTC) - timedelta(hours=1),  # Expired
        )
        alerts = WeatherAlerts(alerts=[expired_alert])
        notifications = manager.process_alerts(alerts)
        assert len(notifications) == 0

    def test_severity_filtering(self, manager):
        """Test that low severity alerts can be filtered."""
        manager.settings.min_severity_priority = 4  # Only Severe and above

        minor_alert = WeatherAlert(
            id="minor",
            title="Minor Alert",
            description="Minor weather event.",
            severity="Minor",
            urgency="Future",
            certainty="Possible",
            event="Minor Alert",
            expires=datetime.now(UTC) + timedelta(hours=1),
        )
        alerts = WeatherAlerts(alerts=[minor_alert])
        notifications = manager.process_alerts(alerts)
        assert len(notifications) == 0

    def test_state_persistence(self, config_dir, sample_alert):
        """Test that alert state is persisted across manager instances."""
        # First manager processes alert
        manager1 = AlertManager(str(config_dir))
        alerts = WeatherAlerts(alerts=[sample_alert])
        manager1.process_alerts(alerts)

        # Second manager loads state
        manager2 = AlertManager(str(config_dir))
        manager2._ensure_state_loaded()

        assert sample_alert.get_unique_id() in manager2.alert_states

    def test_get_statistics(self, manager, sample_alert):
        """Test getting alert statistics."""
        alerts = WeatherAlerts(alerts=[sample_alert])
        manager.process_alerts(alerts)

        stats = manager.get_alert_statistics()
        assert stats["total_tracked_alerts"] == 1
        assert "rate_limiter" in stats
        assert "settings" in stats

    def test_clear_state(self, manager, sample_alert):
        """Test clearing all state."""
        alerts = WeatherAlerts(alerts=[sample_alert])
        manager.process_alerts(alerts)

        manager.clear_state()
        assert len(manager.alert_states) == 0

    def test_rate_limiting(self, manager):
        """Test rate limiting prevents excessive notifications."""
        manager.settings.max_notifications_per_hour = 2
        manager._rate_limit_tokens = 2.0
        manager._rate_limit_capacity = 2.0

        alerts_list = []
        for i in range(5):
            alerts_list.append(
                WeatherAlert(
                    id=f"alert-{i}",
                    title=f"Alert {i}",
                    description=f"Description {i}",
                    severity="Severe",
                    urgency="Immediate",
                    certainty="Observed",
                    event=f"Event {i}",
                    expires=datetime.now(UTC) + timedelta(hours=1),
                )
            )

        alerts = WeatherAlerts(alerts=alerts_list)
        notifications = manager.process_alerts(alerts)

        # Should be rate limited to 2
        assert len(notifications) <= 2
