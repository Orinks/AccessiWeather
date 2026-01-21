"""Tests for the notification event manager."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from accessiweather.models import AppSettings, CurrentConditions, WeatherData
from accessiweather.notifications.notification_event_manager import (
    NotificationEvent,
    NotificationEventManager,
    NotificationState,
)


class TestNotificationState:
    """Tests for NotificationState dataclass."""

    def test_default_state(self):
        """Test default state values."""
        state = NotificationState()
        assert state.last_discussion_issuance_time is None
        assert state.last_severe_risk is None
        assert state.last_check_time is None

    def test_to_dict(self):
        """Test state serialization."""
        issuance_time = datetime(2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc)
        state = NotificationState(
            last_discussion_issuance_time=issuance_time,
            last_severe_risk=50,
        )
        data = state.to_dict()
        assert data["last_discussion_issuance_time"] == issuance_time.isoformat()
        assert data["last_severe_risk"] == 50

    def test_from_dict(self):
        """Test state deserialization."""
        issuance_time_str = "2026-01-20T14:35:00+00:00"
        data = {
            "last_discussion_issuance_time": issuance_time_str,
            "last_severe_risk": 75,
            "last_check_time": None,
        }
        state = NotificationState.from_dict(data)
        assert state.last_discussion_issuance_time == datetime.fromisoformat(issuance_time_str)
        assert state.last_severe_risk == 75


class TestNotificationEventManager:
    """Tests for NotificationEventManager."""

    @pytest.fixture
    def manager(self):
        """Create a notification event manager without persistence."""
        return NotificationEventManager(state_file=None)

    @pytest.fixture
    def manager_with_file(self, tmp_path):
        """Create a notification event manager with persistence."""
        state_file = tmp_path / "notification_state.json"
        return NotificationEventManager(state_file=state_file)

    @pytest.fixture
    def settings_with_discussion(self):
        """Create settings with discussion notifications enabled."""
        settings = AppSettings()
        settings.notify_discussion_update = True
        settings.notify_severe_risk_change = False
        return settings

    @pytest.fixture
    def settings_with_severe_risk(self):
        """Create settings with severe risk notifications enabled."""
        settings = AppSettings()
        settings.notify_discussion_update = False
        settings.notify_severe_risk_change = True
        return settings

    @pytest.fixture
    def settings_both_enabled(self):
        """Create settings with both notifications enabled."""
        settings = AppSettings()
        settings.notify_discussion_update = True
        settings.notify_severe_risk_change = True
        return settings

    @pytest.fixture
    def settings_none_enabled(self):
        """Create settings with no event notifications enabled."""
        return AppSettings()  # Both are False by default

    def test_initialization(self, manager):
        """Test manager initialization."""
        assert manager.state.last_discussion_issuance_time is None
        assert manager.state.last_severe_risk is None

    def test_first_discussion_no_notification(self, manager, settings_with_discussion):
        """Test that first discussion doesn't trigger notification."""
        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = "First discussion text"
        weather_data.discussion_issuance_time = datetime(
            2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc
        )
        weather_data.current = None

        events = manager.check_for_events(weather_data, settings_with_discussion, "Test Location")
        assert len(events) == 0
        assert manager.state.last_discussion_issuance_time is not None

    def test_discussion_update_triggers_notification(self, manager, settings_with_discussion):
        """Test that discussion update triggers notification based on issuanceTime."""
        weather_data = MagicMock(spec=WeatherData)
        weather_data.current = None
        weather_data.discussion = "Discussion text"

        # First discussion with issuance time
        first_time = datetime(2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc)
        weather_data.discussion_issuance_time = first_time
        events1 = manager.check_for_events(weather_data, settings_with_discussion, "Test Location")
        assert len(events1) == 0

        # Same issuance time - no notification
        events2 = manager.check_for_events(weather_data, settings_with_discussion, "Test Location")
        assert len(events2) == 0

        # Newer issuance time - should notify
        newer_time = first_time + timedelta(hours=3)
        weather_data.discussion_issuance_time = newer_time
        events3 = manager.check_for_events(weather_data, settings_with_discussion, "Test Location")
        assert len(events3) == 1
        assert events3[0].event_type == "discussion_update"
        assert "Updated" in events3[0].title

    def test_discussion_notification_disabled(self, manager, settings_none_enabled):
        """Test that notifications are not sent when disabled."""
        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = "First discussion"
        weather_data.discussion_issuance_time = datetime(
            2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc
        )
        weather_data.current = None

        # First check
        manager.check_for_events(weather_data, settings_none_enabled, "Test Location")

        # Update discussion with newer issuance time
        weather_data.discussion_issuance_time = datetime(
            2026, 1, 20, 17, 35, 0, tzinfo=timezone.utc
        )
        events = manager.check_for_events(weather_data, settings_none_enabled, "Test Location")

        # Should not notify because setting is disabled
        assert len(events) == 0

    def test_no_issuance_time_no_notification(self, manager, settings_with_discussion):
        """Test that missing issuance time doesn't trigger notification."""
        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = "Some discussion text"
        weather_data.discussion_issuance_time = None  # Non-US location or API issue
        weather_data.current = None

        events = manager.check_for_events(weather_data, settings_with_discussion, "Test Location")
        assert len(events) == 0
        assert manager.state.last_discussion_issuance_time is None

    def test_first_severe_risk_no_notification(self, manager, settings_with_severe_risk):
        """Test that first severe risk doesn't trigger notification."""
        current = MagicMock(spec=CurrentConditions)
        current.severe_weather_risk = 50

        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = None
        weather_data.discussion_issuance_time = None
        weather_data.current = current

        events = manager.check_for_events(weather_data, settings_with_severe_risk, "Test Location")
        assert len(events) == 0
        assert manager.state.last_severe_risk == 50

    def test_severe_risk_category_change_triggers_notification(
        self, manager, settings_with_severe_risk
    ):
        """Test that severe risk category change triggers notification."""
        current = MagicMock(spec=CurrentConditions)
        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = None
        weather_data.discussion_issuance_time = None
        weather_data.current = current

        # First risk (low)
        current.severe_weather_risk = 20
        events1 = manager.check_for_events(weather_data, settings_with_severe_risk, "Test Location")
        assert len(events1) == 0

        # Same category (still low) - no notification
        current.severe_weather_risk = 25
        events2 = manager.check_for_events(weather_data, settings_with_severe_risk, "Test Location")
        assert len(events2) == 0

        # Category change to moderate - should notify
        current.severe_weather_risk = 50
        events3 = manager.check_for_events(weather_data, settings_with_severe_risk, "Test Location")
        assert len(events3) == 1
        assert events3[0].event_type == "severe_risk"
        assert "Increased" in events3[0].title
        assert "moderate" in events3[0].title.lower()

    def test_severe_risk_decrease_notification(self, manager, settings_with_severe_risk):
        """Test that severe risk decrease triggers notification."""
        current = MagicMock(spec=CurrentConditions)
        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = None
        weather_data.discussion_issuance_time = None
        weather_data.current = current

        # Start at high
        current.severe_weather_risk = 80
        manager.check_for_events(weather_data, settings_with_severe_risk, "Test Location")

        # Decrease to low
        current.severe_weather_risk = 20
        events = manager.check_for_events(weather_data, settings_with_severe_risk, "Test Location")
        assert len(events) == 1
        assert "Decreased" in events[0].title

    def test_state_persistence(self, tmp_path):
        """Test that state is persisted and loaded correctly."""
        state_file = tmp_path / "state.json"

        # Create manager and set some state
        manager1 = NotificationEventManager(state_file=state_file)
        issuance_time = datetime(2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc)
        manager1.state.last_discussion_issuance_time = issuance_time
        manager1.state.last_severe_risk = 42
        manager1._save_state()

        # Create new manager and verify state is loaded
        manager2 = NotificationEventManager(state_file=state_file)
        assert manager2.state.last_discussion_issuance_time == issuance_time
        assert manager2.state.last_severe_risk == 42

    def test_reset_state(self, manager):
        """Test state reset."""
        manager.state.last_discussion_issuance_time = datetime(
            2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc
        )
        manager.state.last_severe_risk = 75

        manager.reset_state()

        assert manager.state.last_discussion_issuance_time is None
        assert manager.state.last_severe_risk is None


class TestNotificationEvent:
    """Tests for NotificationEvent dataclass."""

    def test_event_creation(self):
        """Test creating a notification event."""
        event = NotificationEvent(
            event_type="discussion_update",
            title="Test Title",
            message="Test message",
            sound_event="notify",
        )
        assert event.event_type == "discussion_update"
        assert event.title == "Test Title"
        assert event.message == "Test message"
        assert event.sound_event == "notify"
