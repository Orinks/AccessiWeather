"""
Tests for AlertNotificationSystem.

Tests the notification system's batch processing and sound handling,
including the fix to prevent overlapping sounds when multiple alerts
are processed simultaneously.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.alert_notification_system import AlertNotificationSystem
from accessiweather.alert_manager import AlertManager
from accessiweather.models import WeatherAlert, WeatherAlerts


class TestAlertNotificationBatchSound:
    """Tests for batch sound handling to prevent overlapping sounds."""

    @pytest.fixture
    def mock_notifier(self):
        """Create a mock notifier that tracks calls."""
        notifier = MagicMock()
        notifier.send_notification = MagicMock(return_value=True)
        notifier.sound_enabled = True
        return notifier

    @pytest.fixture
    def alert_manager(self, tmp_path):
        """Create an AlertManager instance."""
        return AlertManager(str(tmp_path / "alerts"))

    @pytest.fixture
    def notification_system(self, alert_manager, mock_notifier):
        """Create an AlertNotificationSystem instance."""
        return AlertNotificationSystem(
            alert_manager=alert_manager,
            notifier=mock_notifier,
        )

    @pytest.fixture
    def multiple_alerts(self):
        """Create multiple alerts of varying severity."""
        now = datetime.now(UTC)
        return WeatherAlerts(
            alerts=[
                WeatherAlert(
                    id="alert-minor",
                    title="Minor Alert",
                    description="Minor weather event.",
                    severity="Minor",
                    urgency="Future",
                    certainty="Possible",
                    event="Special Weather Statement",
                    expires=now + timedelta(hours=2),
                ),
                WeatherAlert(
                    id="alert-severe-1",
                    title="Severe Thunderstorm Warning",
                    description="Severe thunderstorms expected.",
                    severity="Severe",
                    urgency="Immediate",
                    certainty="Observed",
                    event="Severe Thunderstorm Warning",
                    expires=now + timedelta(hours=1),
                ),
                WeatherAlert(
                    id="alert-severe-2",
                    title="Flash Flood Warning",
                    description="Flash flooding expected.",
                    severity="Severe",
                    urgency="Immediate",
                    certainty="Observed",
                    event="Flash Flood Warning",
                    expires=now + timedelta(hours=3),
                ),
                WeatherAlert(
                    id="alert-extreme",
                    title="Tornado Warning",
                    description="A tornado has been spotted.",
                    severity="Extreme",
                    urgency="Immediate",
                    certainty="Observed",
                    event="Tornado Warning",
                    expires=now + timedelta(hours=1),
                ),
            ]
        )

    @pytest.mark.asyncio
    async def test_batch_alerts_only_one_sound(
        self, notification_system, mock_notifier, multiple_alerts
    ):
        """Test that multiple alerts in a batch only play one sound.
        
        When multiple alerts are processed at once, only the most severe
        alert should trigger a sound to prevent overlapping audio.
        """
        # Process all alerts
        notifications_sent = await notification_system.process_and_notify(multiple_alerts)

        # All alerts should generate notifications
        assert notifications_sent == 4

        # Check the send_notification calls
        calls = mock_notifier.send_notification.call_args_list
        assert len(calls) == 4

        # Count how many calls had play_sound=True
        sounds_played = sum(1 for call in calls if call.kwargs.get("play_sound", True))

        # Only one sound should be played
        assert sounds_played == 1, (
            f"Expected 1 sound to play, but {sounds_played} sounds were triggered. "
            "Multiple alerts should only play one sound to avoid overlap."
        )

    @pytest.mark.asyncio
    async def test_most_severe_alert_plays_sound(
        self, notification_system, mock_notifier, multiple_alerts
    ):
        """Test that the most severe alert is the one that plays sound."""
        await notification_system.process_and_notify(multiple_alerts)

        calls = mock_notifier.send_notification.call_args_list

        # Find the call that played sound
        sound_call = None
        for call in calls:
            if call.kwargs.get("play_sound", True):
                sound_call = call
                break

        assert sound_call is not None, "No notification played a sound"

        # The title should indicate an EXTREME alert (Tornado Warning)
        # Title is passed as a keyword argument
        title = sound_call.kwargs.get("title", "")
        assert "EXTREME" in title or "Tornado" in title, (
            f"Expected the most severe alert (Extreme/Tornado) to play sound, "
            f"but sound was played for: {title}"
        )

    @pytest.mark.asyncio
    async def test_single_alert_plays_sound(self, notification_system, mock_notifier):
        """Test that a single alert still plays its sound."""
        single_alert = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    id="single-alert",
                    title="Test Warning",
                    description="Test description.",
                    severity="Moderate",
                    urgency="Expected",
                    certainty="Likely",
                    event="Test Warning",
                    expires=datetime.now(UTC) + timedelta(hours=1),
                )
            ]
        )

        await notification_system.process_and_notify(single_alert)

        calls = mock_notifier.send_notification.call_args_list
        assert len(calls) == 1

        # The single alert should play sound
        assert calls[0].kwargs.get("play_sound", True) is True

    @pytest.mark.asyncio
    async def test_no_alerts_no_sound(self, notification_system, mock_notifier):
        """Test that no alerts means no notifications or sounds."""
        empty_alerts = WeatherAlerts(alerts=[])

        notifications_sent = await notification_system.process_and_notify(empty_alerts)

        assert notifications_sent == 0
        mock_notifier.send_notification.assert_not_called()


class TestAlertNotificationSoundControl:
    """Tests for the play_sound parameter in notifications."""

    @pytest.fixture
    def mock_notifier(self):
        """Create a mock notifier."""
        notifier = MagicMock()
        notifier.send_notification = MagicMock(return_value=True)
        notifier.sound_enabled = True
        return notifier

    @pytest.fixture
    def alert_manager(self, tmp_path):
        """Create an AlertManager instance."""
        return AlertManager(str(tmp_path / "alerts"))

    @pytest.fixture
    def notification_system(self, alert_manager, mock_notifier):
        """Create an AlertNotificationSystem instance."""
        return AlertNotificationSystem(
            alert_manager=alert_manager,
            notifier=mock_notifier,
        )

    @pytest.mark.asyncio
    async def test_send_notification_with_sound(self, notification_system, mock_notifier):
        """Test sending a notification with sound enabled."""
        alert = WeatherAlert(
            id="test-1",
            title="Test Alert",
            description="Test description.",
            severity="Moderate",
            event="Test Warning",
        )

        await notification_system._send_alert_notification(alert, "new_alert", play_sound=True)

        mock_notifier.send_notification.assert_called_once()
        call_kwargs = mock_notifier.send_notification.call_args.kwargs
        assert call_kwargs.get("play_sound") is True

    @pytest.mark.asyncio
    async def test_send_notification_without_sound(self, notification_system, mock_notifier):
        """Test sending a notification with sound disabled."""
        alert = WeatherAlert(
            id="test-2",
            title="Test Alert",
            description="Test description.",
            severity="Moderate",
            event="Test Warning",
        )

        await notification_system._send_alert_notification(alert, "new_alert", play_sound=False)

        mock_notifier.send_notification.assert_called_once()
        call_kwargs = mock_notifier.send_notification.call_args.kwargs
        assert call_kwargs.get("play_sound") is False
