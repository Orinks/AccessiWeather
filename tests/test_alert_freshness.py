"""Tests for alert freshness detection and timestamp-based notification bypass."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from accessiweather.alert_manager import AlertManager, AlertSettings, AlertState
from accessiweather.models import WeatherAlert, WeatherAlerts


@pytest.mark.unit
class TestAlertFreshnessDetection:
    """Test alert freshness window detection logic."""

    def test_is_alert_fresh_within_window(self):
        """Alert issued within freshness window should be detected as fresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 15
            manager = AlertManager(tmpdir, settings)

            # Alert sent 10 minutes ago (within 15 minute window)
            alert_sent_time = datetime.now(UTC) - timedelta(minutes=10)

            assert manager._is_alert_fresh(alert_sent_time) is True

    def test_is_alert_fresh_outside_window(self):
        """Alert issued outside freshness window should not be fresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 15
            manager = AlertManager(tmpdir, settings)

            # Alert sent 20 minutes ago (outside 15 minute window)
            alert_sent_time = datetime.now(UTC) - timedelta(minutes=20)

            assert manager._is_alert_fresh(alert_sent_time) is False

    def test_is_alert_fresh_at_boundary(self):
        """Alert at exact boundary should be considered fresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 15
            manager = AlertManager(tmpdir, settings)

            # Fix the current time to avoid timing issues
            fixed_now = datetime.now(UTC)
            # Alert sent exactly 15 minutes ago
            alert_sent_time = fixed_now - timedelta(minutes=15)

            # Mock datetime.now to return our fixed time
            with patch("accessiweather.alert_manager.datetime") as mock_datetime:
                mock_datetime.now.return_value = fixed_now
                mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

                assert manager._is_alert_fresh(alert_sent_time) is True

    def test_is_alert_fresh_no_timestamp(self):
        """Alert without timestamp should not be considered fresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 15
            manager = AlertManager(tmpdir, settings)

            assert manager._is_alert_fresh(None) is False

    def test_is_alert_fresh_naive_datetime_converted_to_utc(self):
        """Alert with naive datetime should be treated as UTC and checked for freshness."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 15
            manager = AlertManager(tmpdir, settings)

            # Naive datetime (will be treated as UTC)
            # Create a time that would be fresh if interpreted as UTC
            alert_sent_time_utc = datetime.now(UTC) - timedelta(minutes=5)
            alert_sent_time_naive = alert_sent_time_utc.replace(tzinfo=None)

            # Should handle timezone and detect as fresh
            assert manager._is_alert_fresh(alert_sent_time_naive) is True

    def test_freshness_window_configurable(self):
        """Freshness window should respect configured duration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 30
            manager = AlertManager(tmpdir, settings)

            # Alert sent 25 minutes ago (within 30 minute window)
            alert_sent_time = datetime.now(UTC) - timedelta(minutes=25)

            assert manager._is_alert_fresh(alert_sent_time) is True

            # Alert sent 35 minutes ago (outside 30 minute window)
            alert_sent_time_old = datetime.now(UTC) - timedelta(minutes=35)

            assert manager._is_alert_fresh(alert_sent_time_old) is False


@pytest.mark.unit
class TestAlertStateSentTimeTracking:
    """Test AlertState tracking of alert sent/effective timestamps."""

    def test_alert_state_stores_sent_time(self):
        """AlertState should store alert sent time."""
        sent_time = datetime.now(UTC) - timedelta(minutes=5)
        state = AlertState(
            alert_id="test-alert",
            content_hash="abc123",
            first_seen=datetime.now(UTC),
            severity_priority=3,
            alert_sent_time=sent_time,
        )

        assert state.alert_sent_time == sent_time

    def test_alert_state_sent_time_optional(self):
        """AlertState should work without sent time (backward compatibility)."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="abc123",
            first_seen=datetime.now(UTC),
            severity_priority=3,
        )

        assert state.alert_sent_time is None

    def test_alert_state_serialization_includes_sent_time(self):
        """AlertState serialization should include sent time."""
        sent_time = datetime.now(UTC) - timedelta(minutes=5)
        state = AlertState(
            alert_id="test-alert",
            content_hash="abc123",
            first_seen=datetime.now(UTC),
            severity_priority=3,
            alert_sent_time=sent_time,
        )

        data = state.to_dict()
        assert "alert_sent_time" in data
        assert data["alert_sent_time"] == sent_time.isoformat()

    def test_alert_state_deserialization_loads_sent_time(self):
        """AlertState deserialization should restore sent time."""
        sent_time = datetime.now(UTC) - timedelta(minutes=5)
        data = {
            "alert_id": "test-alert",
            "first_seen": datetime.now(UTC).isoformat(),
            "last_notified": None,
            "notification_count": 0,
            "alert_sent_time": sent_time.isoformat(),
            "hash_history": [["abc123", 3, 1234567890.0]],
        }

        state = AlertState.from_dict(data)
        assert state.alert_sent_time is not None
        assert state.alert_sent_time == sent_time

    def test_alert_state_deserialization_handles_missing_sent_time(self):
        """AlertState deserialization should handle missing sent time (old format)."""
        data = {
            "alert_id": "test-alert",
            "first_seen": datetime.now(UTC).isoformat(),
            "last_notified": None,
            "notification_count": 0,
            "hash_history": [["abc123", 3, 1234567890.0]],
        }

        state = AlertState.from_dict(data)
        assert state.alert_sent_time is None


@pytest.mark.unit
class TestFreshnessBasedNotificationBypass:
    """Test that fresh alerts bypass per-alert cooldown when never notified."""

    def test_fresh_alert_bypasses_cooldown_never_notified(self):
        """Fresh alert that was never notified should trigger notification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 15
            settings.per_alert_cooldown = 60
            settings.notifications_enabled = True
            settings.min_severity_priority = 1
            manager = AlertManager(tmpdir, settings)

            # Create alert sent 10 minutes ago (fresh)
            sent_time = datetime.now(UTC) - timedelta(minutes=10)
            alert = WeatherAlert(
                id="test-alert-1",
                title="Test Alert",
                description="Test description",
                severity="Severe",
                sent=sent_time,
                effective=sent_time,
            )

            # First process: should notify (new alert)
            alerts = WeatherAlerts(alerts=[alert])
            notifications = manager.process_alerts(alerts)
            assert len(notifications) == 1
            assert notifications[0][1] == "new_alert"

            # Immediately process again (within 60 min cooldown)
            # But alert is fresh and last_notified is set, so should NOT bypass
            notifications2 = manager.process_alerts(alerts)
            assert len(notifications2) == 0

    def test_fresh_alert_seen_but_never_notified_same_content(self):
        """Fresh alert with same content that was never notified should trigger fresh_alert notification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 15
            settings.per_alert_cooldown = 60
            settings.notifications_enabled = True
            settings.min_severity_priority = 1
            manager = AlertManager(tmpdir, settings)

            # Manually create an alert state that was seen but never notified
            sent_time = datetime.now(UTC) - timedelta(minutes=5)

            # Create alert first to get its content hash
            alert = WeatherAlert(
                id="test-alert-1",
                title="Test Alert",
                description="Test description",
                severity="Severe",
                sent=sent_time,
                effective=sent_time,
            )
            content_hash = alert.get_content_hash()

            # Create state with SAME content hash
            state = AlertState(
                alert_id="test-alert-1",
                content_hash=content_hash,
                first_seen=datetime.now(UTC) - timedelta(minutes=30),
                last_notified=None,  # Never notified
                severity_priority=4,
                alert_sent_time=sent_time,
            )
            manager.alert_states["test-alert-1"] = state

            # Process: should notify because it's fresh and never notified
            alerts = WeatherAlerts(alerts=[alert])
            notifications = manager.process_alerts(alerts)
            assert len(notifications) == 1
            assert notifications[0][1] == "fresh_alert"

    def test_stale_alert_same_content_never_notified_still_notifies(self):
        """
        Stale alert with same content that was never notified should still notify as reminder.

        This is correct behavior: if an alert was tracked but never notified (perhaps due to
        settings or filters at the time), and it's still active, the user should be notified
        eventually. The freshness bypass is an optimization for truly fresh alerts, but
        doesn't prevent eventual notification.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 15
            settings.per_alert_cooldown = 60
            settings.notifications_enabled = True
            settings.min_severity_priority = 1
            manager = AlertManager(tmpdir, settings)

            # Manually create an alert state with recent first_seen, never notified
            sent_time = datetime.now(UTC) - timedelta(minutes=60)  # Old alert

            # Create alert first to get content hash
            alert = WeatherAlert(
                id="test-alert-1",
                title="Test Alert",
                description="Test description",
                severity="Severe",
                sent=sent_time,
                effective=sent_time,
            )
            content_hash = alert.get_content_hash()

            state = AlertState(
                alert_id="test-alert-1",
                content_hash=content_hash,  # Same content
                first_seen=datetime.now(UTC) - timedelta(minutes=70),  # Seen long ago
                last_notified=None,
                severity_priority=4,
                alert_sent_time=sent_time,
            )
            manager.alert_states["test-alert-1"] = state

            # Process: SHOULD notify as "reminder" because never notified before
            # (The freshness bypass doesn't prevent standard notification logic)
            alerts = WeatherAlerts(alerts=[alert])
            notifications = manager.process_alerts(alerts)
            assert len(notifications) == 1
            assert notifications[0][1] == "reminder"

    def test_fresh_alert_already_notified_respects_cooldown(self):
        """Fresh alert that was already notified should respect per-alert cooldown."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 15
            settings.per_alert_cooldown = 60
            settings.notifications_enabled = True
            settings.min_severity_priority = 1
            manager = AlertManager(tmpdir, settings)

            # Create alert state that was recently notified
            sent_time = datetime.now(UTC) - timedelta(minutes=5)
            state = AlertState(
                alert_id="test-alert-1",
                content_hash="abc123",
                first_seen=datetime.now(UTC) - timedelta(minutes=30),
                last_notified=datetime.now(UTC) - timedelta(minutes=2),  # Recently notified
                severity_priority=4,
                alert_sent_time=sent_time,
            )
            manager.alert_states["test-alert-1"] = state

            # Create fresh alert
            alert = WeatherAlert(
                id="test-alert-1",
                title="Test Alert",
                description="Test description",
                severity="Severe",
                sent=sent_time,
                effective=sent_time,
            )

            # Process: should NOT notify because already notified recently
            alerts = WeatherAlerts(alerts=[alert])
            notifications = manager.process_alerts(alerts)
            assert len(notifications) == 0


@pytest.mark.unit
class TestWeatherAlertTimestampFields:
    """Test WeatherAlert model includes sent and effective timestamps."""

    def test_weather_alert_has_sent_field(self):
        """WeatherAlert should have sent timestamp field."""
        sent_time = datetime.now(UTC)
        alert = WeatherAlert(
            title="Test",
            description="Test description",
            sent=sent_time,
        )
        assert alert.sent == sent_time

    def test_weather_alert_has_effective_field(self):
        """WeatherAlert should have effective timestamp field."""
        effective_time = datetime.now(UTC)
        alert = WeatherAlert(
            title="Test",
            description="Test description",
            effective=effective_time,
        )
        assert alert.effective == effective_time

    def test_weather_alert_timestamps_optional(self):
        """WeatherAlert should work without sent/effective (backward compatibility)."""
        alert = WeatherAlert(
            title="Test",
            description="Test description",
        )
        assert alert.sent is None
        assert alert.effective is None


@pytest.mark.unit
class TestFreshnessIntegration:
    """Integration tests for complete freshness detection workflow."""

    def test_nws_style_alert_with_sent_timestamp(self):
        """Test NWS-style alert with sent timestamp triggers freshness logic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 15
            settings.per_alert_cooldown = 60
            settings.notifications_enabled = True
            settings.min_severity_priority = 1
            manager = AlertManager(tmpdir, settings)

            # Simulate NWS alert with sent timestamp
            sent_time = datetime.now(UTC) - timedelta(minutes=8)
            alert = WeatherAlert(
                id="nws-alert-123",
                title="Severe Thunderstorm Warning",
                description="Severe thunderstorm warning for the area",
                severity="Severe",
                urgency="Immediate",
                event="Severe Thunderstorm Warning",
                sent=sent_time,
                effective=sent_time,
                onset=sent_time,
                expires=datetime.now(UTC) + timedelta(hours=2),
                source="NWS",
            )

            # First pass: should notify
            alerts = WeatherAlerts(alerts=[alert])
            notifications = manager.process_alerts(alerts)
            assert len(notifications) == 1
            assert notifications[0][0].id == "nws-alert-123"

    def test_visual_crossing_style_alert_with_effective_timestamp(self):
        """Test Visual Crossing-style alert with effective timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 15
            settings.per_alert_cooldown = 60
            settings.notifications_enabled = True
            settings.min_severity_priority = 1
            manager = AlertManager(tmpdir, settings)

            # Simulate Visual Crossing alert with effective timestamp
            effective_time = datetime.now(UTC) - timedelta(minutes=12)
            alert = WeatherAlert(
                id="vc-alert-456",
                title="Winter Storm Warning",
                description="Winter storm warning for the region",
                severity="Severe",
                urgency="Expected",
                event="Winter Storm Warning",
                effective=effective_time,
                onset=effective_time,
                expires=datetime.now(UTC) + timedelta(hours=6),
                source="VisualCrossing",
            )

            # First pass: should notify
            alerts = WeatherAlerts(alerts=[alert])
            notifications = manager.process_alerts(alerts)
            assert len(notifications) == 1
            assert notifications[0][0].id == "vc-alert-456"

    def test_multiple_fresh_alerts_processed_correctly(self):
        """Test multiple fresh alerts are processed with freshness logic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AlertSettings()
            settings.freshness_window_minutes = 15
            settings.per_alert_cooldown = 60
            settings.notifications_enabled = True
            settings.min_severity_priority = 1
            manager = AlertManager(tmpdir, settings)

            # Create two fresh alerts
            sent_time1 = datetime.now(UTC) - timedelta(minutes=5)
            alert1 = WeatherAlert(
                id="alert-1",
                title="Alert 1",
                description="First alert",
                severity="Severe",
                sent=sent_time1,
            )

            sent_time2 = datetime.now(UTC) - timedelta(minutes=10)
            alert2 = WeatherAlert(
                id="alert-2",
                title="Alert 2",
                description="Second alert",
                severity="Moderate",
                sent=sent_time2,
            )

            # Process both alerts
            alerts = WeatherAlerts(alerts=[alert1, alert2])
            notifications = manager.process_alerts(alerts)

            # Both should notify (new alerts)
            assert len(notifications) == 2
            alert_ids = {n[0].id for n in notifications}
            assert "alert-1" in alert_ids
            assert "alert-2" in alert_ids
