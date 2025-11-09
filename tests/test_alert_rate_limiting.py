"""
Tests for alert rate limiting with token bucket algorithm.

Validates that the rate limiter correctly implements token bucket behavior
including burst capacity, refill rate, and proper blocking.
"""

from unittest.mock import patch

import pytest

from accessiweather.alert_manager import AlertManager, AlertSettings
from accessiweather.constants import SECONDS_PER_HOUR
from accessiweather.models import WeatherAlert, WeatherAlerts


@pytest.mark.unit
class TestTokenBucketRateLimiter:
    """Tests for token bucket rate limiting algorithm."""

    def test_rate_limiter_initialization(self, tmp_path):
        """Test that rate limiter initializes with correct values."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 10

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Should start with full capacity
        assert manager._rate_limit_capacity == 10.0
        assert manager._rate_limit_tokens == 10.0
        assert manager._rate_limit_refill_rate == 10.0 / SECONDS_PER_HOUR
        assert manager._rate_limit_last_refill > 0

    def test_rate_limiter_allows_up_to_capacity(self, tmp_path):
        """Test that rate limiter allows notifications up to capacity."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 5
        settings.notifications_enabled = True
        settings.min_severity_priority = 1  # Allow all

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Should allow 5 notifications (full capacity)
        for i in range(5):
            result = manager._check_rate_limit()
            assert result is True, f"Notification {i + 1} should be allowed"

        # 6th should be blocked
        result = manager._check_rate_limit()
        assert result is False, "Should be blocked after consuming all tokens"

    def test_rate_limiter_refills_over_time(self, tmp_path):
        """Test that tokens refill at correct rate over time."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 10  # 10 tokens/hour = 1 token per 360 seconds

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Consume all tokens
        for _ in range(10):
            manager._check_rate_limit()

        assert manager._rate_limit_tokens < 1.0

        # Mock time.time() to simulate 360 seconds passing (should refill 1 token)
        original_time = manager._rate_limit_last_refill

        with patch("time.time", return_value=original_time + 360):
            manager._refill_rate_limit_tokens()

        # Should have refilled 1 token
        assert 0.95 <= manager._rate_limit_tokens <= 1.05  # Allow small floating point error

    def test_rate_limiter_respects_capacity_ceiling(self, tmp_path):
        """Test that tokens never exceed capacity."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 10

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Start with full capacity
        assert manager._rate_limit_tokens == 10.0

        # Simulate time passing (should not exceed capacity)
        original_time = manager._rate_limit_last_refill

        with patch("time.time", return_value=original_time + 7200):  # 2 hours
            manager._refill_rate_limit_tokens()

        # Should be capped at capacity
        assert manager._rate_limit_tokens == manager._rate_limit_capacity

    def test_rate_limiter_updates_with_settings_change(self, tmp_path):
        """Test that rate limiter reconfigures when settings change."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 10

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Consume half the tokens
        for _ in range(5):
            manager._check_rate_limit()

        assert manager._rate_limit_tokens == pytest.approx(5.0)

        # Update settings to double capacity
        new_settings = AlertSettings()
        new_settings.max_notifications_per_hour = 20

        manager.update_settings(new_settings)

        # Token ratio should be preserved (was 50%, should now be 50% of 20 = 10)
        assert manager._rate_limit_capacity == 20.0
        assert manager._rate_limit_tokens == pytest.approx(10.0)
        assert manager._rate_limit_refill_rate == pytest.approx(20.0 / SECONDS_PER_HOUR)

    def test_rate_limiter_fractional_tokens(self, tmp_path):
        """Test that rate limiter handles fractional token refills correctly."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 10

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Consume all tokens
        for _ in range(10):
            manager._check_rate_limit()

        # Simulate small time increment (should add fractional tokens)
        original_time = manager._rate_limit_last_refill

        # 36 seconds = 0.1 tokens (at 10 tokens/hour)
        with patch("time.time", return_value=original_time + 36):
            result = manager._check_rate_limit()

        # Should have ~0.1 tokens (not enough for notification)
        # Note: _check_rate_limit() refills internally, so we check result
        assert result is False, "Should not have enough tokens yet"

        # Simulate another 324 seconds (total 360 = 1 full token)
        with patch("time.time", return_value=original_time + 360):
            result = manager._check_rate_limit()

        # Should now allow notification with ~1 token
        assert result is True, "Should have enough tokens after full refill"


@pytest.mark.unit
class TestRateLimitingIntegration:
    """Integration tests for rate limiting with alert processing."""

    def test_rate_limit_blocks_excess_alerts(self, tmp_path):
        """Test that rate limiter blocks alerts when limit exceeded."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 3
        settings.notifications_enabled = True
        settings.min_severity_priority = 1
        settings.global_cooldown = 0  # Disable cooldown for this test

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Create 5 alerts
        alerts_list = [
            WeatherAlert(
                title=f"Alert {i}",
                description=f"Description {i}",
                id=f"test-alert-{i}",
                event="Test Event",
                severity="Severe",
            )
            for i in range(5)
        ]

        alerts = WeatherAlerts(alerts=alerts_list)

        # Process alerts - should only notify for first 3 due to rate limit
        notifications = manager.process_alerts(alerts)

        assert len(notifications) == 3, "Should only send 3 notifications (rate limit)"

    def test_rate_limit_allows_after_refill(self, tmp_path):
        """Test that alerts are allowed after tokens refill."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 2
        settings.notifications_enabled = True
        settings.min_severity_priority = 1
        settings.global_cooldown = 0

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Create 2 initial alerts
        alerts1 = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    title="Alert 1",
                    description="Description 1",
                    id="alert-1",
                    event="Test",
                    severity="Severe",
                ),
                WeatherAlert(
                    title="Alert 2",
                    description="Description 2",
                    id="alert-2",
                    event="Test",
                    severity="Severe",
                ),
            ]
        )

        # First batch - should send 2
        notifications1 = manager.process_alerts(alerts1)
        assert len(notifications1) == 2

        # Third alert immediately - should be blocked
        alerts2 = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    title="Alert 3",
                    description="Description 3",
                    id="alert-3",
                    event="Test",
                    severity="Severe",
                )
            ]
        )

        notifications2 = manager.process_alerts(alerts2)
        assert len(notifications2) == 0, "Should be blocked by rate limit"

        # Simulate time passing (1 token refill = 1800 seconds at 2/hour)
        original_time = manager._rate_limit_last_refill

        with patch("time.time", return_value=original_time + 1800):
            notifications3 = manager.process_alerts(alerts2)

        # Should now allow 1 notification
        assert len(notifications3) == 1, "Should allow after token refill"

    def test_rate_limiter_statistics(self, tmp_path):
        """Test that statistics include rate limiter state."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 10

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Consume some tokens
        for _ in range(3):
            manager._check_rate_limit()

        stats = manager.get_alert_statistics()

        # Should include rate limiter info
        assert "rate_limiter" in stats
        assert "available_tokens" in stats["rate_limiter"]
        assert "capacity" in stats["rate_limiter"]
        assert "refill_rate_per_second" in stats["rate_limiter"]

        # Check values
        assert stats["rate_limiter"]["capacity"] == 10.0
        assert stats["rate_limiter"]["available_tokens"] == pytest.approx(7.0)
        # Allow for rounding in the statistics display
        assert stats["rate_limiter"]["refill_rate_per_second"] == pytest.approx(
            10.0 / SECONDS_PER_HOUR, abs=0.0001
        )

    def test_rate_limit_zero_tokens_edge_case(self, tmp_path):
        """Test behavior when tokens reach exactly zero."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 1

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Consume the single token
        assert manager._check_rate_limit() is True

        # Should have exactly 0 tokens
        assert manager._rate_limit_tokens == pytest.approx(0.0)

        # Should block next notification
        assert manager._check_rate_limit() is False


@pytest.mark.unit
class TestRateLimitingEdgeCases:
    """Tests for edge cases in rate limiting."""

    def test_high_frequency_refills(self, tmp_path):
        """Test that frequent refill calls don't cause issues."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 10

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Consume all tokens
        for _ in range(10):
            manager._check_rate_limit()

        # Record initial refill time
        base_time = manager._rate_limit_last_refill

        # Call refill many times with small time increments
        # Each call updates _rate_limit_last_refill, so we need to track cumulative time
        for i in range(1, 101):  # 1 to 100 inclusive
            with patch("time.time", return_value=base_time + i):
                manager._refill_rate_limit_tokens()

        # After 100 iterations, the last refill was at base_time + 100
        # So total elapsed time from initial consumption is 100 seconds
        # Expected tokens: (10/3600) * 100 = 0.2777... tokens
        # But due to incremental refills, we get slightly less due to the way
        # _rate_limit_last_refill is updated each time
        expected_tokens = (10.0 / SECONDS_PER_HOUR) * 100
        assert manager._rate_limit_tokens == pytest.approx(expected_tokens, abs=0.01)

    def test_very_low_rate_limit(self, tmp_path):
        """Test rate limiter with very low notification limit."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 1  # Only 1 per hour

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Should allow 1 notification
        assert manager._check_rate_limit() is True

        # Should block all others
        for _ in range(10):
            assert manager._check_rate_limit() is False

    def test_very_high_rate_limit(self, tmp_path):
        """Test rate limiter with very high notification limit."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 1000  # Very high

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Should allow many notifications without issue
        for _ in range(1000):
            assert manager._check_rate_limit() is True

        # 1001st should fail
        assert manager._check_rate_limit() is False

    def test_settings_update_with_zero_capacity(self, tmp_path):
        """Test that settings update handles edge case of zero capacity."""
        settings = AlertSettings()
        settings.max_notifications_per_hour = 10

        manager = AlertManager(config_dir=tmp_path, settings=settings)

        # Edge case: update to 0 capacity (effectively disable)
        new_settings = AlertSettings()
        new_settings.max_notifications_per_hour = 0

        manager.update_settings(new_settings)

        # Should handle gracefully (tokens become 0)
        assert manager._rate_limit_capacity == 0.0
        assert manager._rate_limit_tokens == 0.0
        assert manager._check_rate_limit() is False
