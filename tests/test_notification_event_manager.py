"""Tests for the notification event manager."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from accessiweather.models import AppSettings, CurrentConditions, WeatherData
from accessiweather.notifications.minutely_precipitation import (
    INTENSITY_THRESHOLD_HEAVY,
    INTENSITY_THRESHOLD_LIGHT,
    INTENSITY_THRESHOLD_MODERATE,
    build_minutely_transition_signature,
    detect_minutely_precipitation_transition,
    is_wet,
    parse_pirate_weather_minutely_block,
)
from accessiweather.notifications.notification_event_manager import (
    NotificationEvent,
    NotificationEventManager,
    NotificationState,
    get_risk_category,
)
from accessiweather.runtime_state import RuntimeStateManager


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

    def test_minutely_signature_round_trip(self):
        """Test minutely state serialization."""
        state = NotificationState(last_minutely_transition_signature="starting:12:rain")

        data = state.to_dict()
        restored = NotificationState.from_dict(data)

        assert restored.last_minutely_transition_signature == "starting:12:rain"


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
    def runtime_manager(self, tmp_path):
        """Create a manager backed by the unified runtime state store."""
        return NotificationEventManager(
            runtime_state_manager=RuntimeStateManager(tmp_path / "config")
        )

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
    def settings_with_minutely(self):
        """Create settings with minutely precipitation notifications enabled."""
        settings = AppSettings()
        settings.notify_discussion_update = False
        settings.notify_severe_risk_change = False
        settings.notify_minutely_precipitation_start = True
        settings.notify_minutely_precipitation_stop = True
        return settings

    @pytest.fixture
    def settings_none_enabled(self):
        """Create settings with no event notifications enabled."""
        settings = AppSettings()
        settings.notify_discussion_update = False
        settings.notify_severe_risk_change = False
        return settings

    def test_initialization(self, manager):
        """Test manager initialization."""
        assert manager.state.last_discussion_issuance_time is None
        assert manager.state.last_severe_risk is None

    def test_runtime_state_path_is_canonical_under_config_root(self, runtime_manager, tmp_path):
        assert runtime_manager.runtime_state_manager is not None
        assert (
            runtime_manager.runtime_state_manager.state_file
            == tmp_path / "config" / "state" / "runtime_state.json"
        )

    def test_first_discussion_no_notification(self, manager, settings_with_discussion):
        """Test that first discussion doesn't trigger notification."""
        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = "First discussion text"
        weather_data.discussion_issuance_time = datetime(
            2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc
        )
        weather_data.current = None
        weather_data.minutely_precipitation = None

        events = manager.check_for_events(weather_data, settings_with_discussion, "Test Location")
        assert len(events) == 0
        assert manager.state.last_discussion_issuance_time is not None

    def test_discussion_update_triggers_notification(self, manager, settings_with_discussion):
        """Test that discussion update triggers notification based on issuanceTime."""
        weather_data = MagicMock(spec=WeatherData)
        weather_data.current = None
        weather_data.discussion = "Discussion text"
        weather_data.minutely_precipitation = None

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
        weather_data.discussion = (
            "Area Forecast Discussion\n"
            "National Weather Service Test Office\n"
            "1235 PM EST MON JAN 20 2026\n\n"
            ".WHAT HAS CHANGED...\n"
            "Rain arrives earlier."
        )
        weather_data.discussion_issuance_time = newer_time
        events3 = manager.check_for_events(weather_data, settings_with_discussion, "Test Location")
        assert len(events3) == 1
        assert events3[0].event_type == "discussion_update"
        assert "Updated" in events3[0].title
        assert "12:35 PM EST" in events3[0].message
        assert "Change summary:" not in events3[0].message
        assert "Rain arrives earlier." in events3[0].message

    def test_discussion_update_uses_standard_afd_header_time(
        self, manager, settings_with_discussion
    ):
        """Use the standard AFD local header time when present in the discussion text."""
        weather_data = MagicMock(spec=WeatherData)
        weather_data.current = None
        weather_data.discussion = "Old discussion"
        weather_data.minutely_precipitation = None

        first_time = datetime(2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc)
        weather_data.discussion_issuance_time = first_time
        manager.check_for_events(weather_data, settings_with_discussion, "Test Location")

        weather_data.discussion = (
            "\n000\nFXUS61 KOKX 201435\nAFDOKX\n\n"
            "Area Forecast Discussion\n"
            "National Weather Service New York NY\n"
            "935 AM EST Tue Jan 20 2026\n\n"
            ".WHAT HAS CHANGED...\n"
            "No significant changes made to forecast."
        )
        weather_data.discussion_issuance_time = first_time + timedelta(hours=1)
        events = manager.check_for_events(weather_data, settings_with_discussion, "Test Location")

        assert len(events) == 1
        assert "9:35 AM EST" in events[0].message
        assert "No significant changes made to forecast." in events[0].message

    def test_discussion_update_falls_back_to_metadata_time(self, manager, settings_with_discussion):
        """Use the metadata timestamp when the AFD text has no parseable issued line."""
        weather_data = MagicMock(spec=WeatherData)
        weather_data.current = None
        weather_data.discussion = "Discussion text without an issued header"
        weather_data.minutely_precipitation = None

        first_time = datetime(2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc)
        weather_data.discussion_issuance_time = first_time
        manager.check_for_events(weather_data, settings_with_discussion, "Test Location")

        weather_data.discussion_issuance_time = first_time + timedelta(hours=3)
        events = manager.check_for_events(weather_data, settings_with_discussion, "Test Location")

        assert len(events) == 1
        assert "5:35 PM UTC" in events[0].message

    def test_discussion_notification_disabled(self, manager, settings_none_enabled):
        """Test that notifications are not sent when disabled."""
        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = "First discussion"
        weather_data.discussion_issuance_time = datetime(
            2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc
        )
        weather_data.current = None
        weather_data.minutely_precipitation = None

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
        weather_data.minutely_precipitation = None

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
        weather_data.minutely_precipitation = None

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
        weather_data.minutely_precipitation = None

        # First risk (low: 20-39)
        current.severe_weather_risk = 25
        events1 = manager.check_for_events(weather_data, settings_with_severe_risk, "Test Location")
        assert len(events1) == 0

        # Same category (still low) - no notification
        current.severe_weather_risk = 35
        events2 = manager.check_for_events(weather_data, settings_with_severe_risk, "Test Location")
        assert len(events2) == 0

        # Category change to moderate (40-59) - should notify
        current.severe_weather_risk = 45
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
        weather_data.minutely_precipitation = None

        # Start at extreme (80+)
        current.severe_weather_risk = 85
        manager.check_for_events(weather_data, settings_with_severe_risk, "Test Location")

        # Decrease to low (20-39)
        current.severe_weather_risk = 25
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

    def test_loaded_discussion_state_preserves_first_run_no_spam(self, tmp_path):
        """Persisted discussion state should suppress same-issuance notifications after restart."""
        state_file = tmp_path / "notification_event_state.json"
        issuance_time = datetime(2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc)
        manager1 = NotificationEventManager(state_file=state_file)
        manager1.state.last_discussion_issuance_time = issuance_time
        manager1.state.last_discussion_text = "Old discussion text"
        manager1._save_state()

        manager2 = NotificationEventManager(state_file=state_file)
        settings = AppSettings(notify_discussion_update=True, notify_severe_risk_change=False)
        weather_data = MagicMock(spec=WeatherData)
        weather_data.current = None
        weather_data.discussion = "Same issuance discussion text"
        weather_data.discussion_issuance_time = issuance_time
        weather_data.minutely_precipitation = None

        same_events = manager2.check_for_events(weather_data, settings, "Test Location")

        assert same_events == []

    def test_unified_runtime_state_preserves_first_run_no_spam(self, tmp_path):
        """Persisted unified discussion state should suppress same-issuance notifications."""
        runtime_state = RuntimeStateManager(tmp_path / "config")
        issuance_time = datetime(2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc)
        runtime_state.save_section(
            "notification_events",
            {
                "discussion": {
                    "last_issuance_time": issuance_time.isoformat(),
                    "last_text": "Old discussion text",
                    "last_check_time": None,
                },
                "severe_risk": {
                    "last_value": None,
                    "last_check_time": None,
                },
            },
        )

        manager = NotificationEventManager(runtime_state_manager=runtime_state)
        settings = AppSettings(notify_discussion_update=True, notify_severe_risk_change=False)
        weather_data = MagicMock(spec=WeatherData)
        weather_data.current = None
        weather_data.discussion = "Same issuance discussion text"
        weather_data.discussion_issuance_time = issuance_time
        weather_data.minutely_precipitation = None

        same_events = manager.check_for_events(weather_data, settings, "Test Location")

        assert same_events == []

    def test_legacy_severe_risk_numeric_value_migrates_without_category_change_notification(
        self, tmp_path
    ):
        state_file = tmp_path / "notification_event_state.json"
        state_file.write_text(
            '{"last_discussion_issuance_time": null, "last_discussion_text": null, '
            '"last_severe_risk": 25, "last_check_time": null}',
            encoding="utf-8",
        )
        runtime_state = RuntimeStateManager(tmp_path / "config")
        manager = NotificationEventManager(
            state_file=state_file,
            runtime_state_manager=runtime_state,
        )
        settings = AppSettings(notify_discussion_update=False, notify_severe_risk_change=True)
        current = MagicMock(spec=CurrentConditions)
        current.severe_weather_risk = 35
        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = None
        weather_data.discussion_issuance_time = None
        weather_data.current = current
        weather_data.minutely_precipitation = None

        events = manager.check_for_events(weather_data, settings, "Test Location")
        reloaded = NotificationEventManager(runtime_state_manager=runtime_state)

        assert events == []
        assert reloaded.state.last_severe_risk == 35

    def test_loaded_severe_risk_state_tracks_numeric_value_within_category(self, tmp_path):
        """Persisted severe-risk state should keep the latest value before a threshold crossing."""
        state_file = tmp_path / "notification_event_state.json"
        manager1 = NotificationEventManager(state_file=state_file)
        manager1.state.last_severe_risk = 25
        manager1._save_state()

        manager2 = NotificationEventManager(state_file=state_file)
        settings = AppSettings(notify_discussion_update=False, notify_severe_risk_change=True)
        current = MagicMock(spec=CurrentConditions)
        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = None
        weather_data.discussion_issuance_time = None
        weather_data.current = current
        weather_data.minutely_precipitation = None

        current.severe_weather_risk = 35
        same_category_events = manager2.check_for_events(weather_data, settings, "Test Location")

        assert same_category_events == []
        assert manager2.state.last_severe_risk == 35

        current.severe_weather_risk = 45
        threshold_events = manager2.check_for_events(weather_data, settings, "Test Location")

        assert len(threshold_events) == 1
        assert threshold_events[0].event_type == "severe_risk"

    def test_parse_pirate_weather_minutely_block(self):
        """Pirate Weather minutely payloads should parse into the shared forecast model."""
        forecast = parse_pirate_weather_minutely_block(
            {
                "minutely": {
                    "summary": "Rain starting in 12 minutes.",
                    "icon": "rain",
                    "data": [
                        {"time": 1768917600, "precipIntensity": 0, "precipProbability": 0},
                        {
                            "time": 1768917660,
                            "precipIntensity": 0.02,
                            "precipProbability": 0.8,
                            "precipType": "rain",
                        },
                    ],
                }
            }
        )

        assert forecast is not None
        assert forecast.summary == "Rain starting in 12 minutes."
        assert len(forecast.points) == 2
        assert forecast.points[1].precipitation_type == "rain"

    def test_detect_minutely_precipitation_start_transition(self):
        """Dry-to-wet transitions should use the first wet minute and precip type."""
        forecast = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0},
                    {"time": 1768917660, "precipIntensity": 0},
                    {"time": 1768917720, "precipIntensity": 0.02, "precipType": "rain"},
                ]
            }
        )

        transition = detect_minutely_precipitation_transition(forecast)

        assert transition is not None
        assert transition.transition_type == "starting"
        assert transition.minutes_until == 2
        assert transition.precipitation_type == "rain"
        assert build_minutely_transition_signature(forecast) == "starting:2:rain"

    def test_detect_minutely_precipitation_stop_transition(self):
        """Wet-to-dry transitions should announce when precipitation stops."""
        forecast = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0.03, "precipType": "snow"},
                    {"time": 1768917660, "precipIntensity": 0.01, "precipType": "snow"},
                    {"time": 1768917720, "precipIntensity": 0},
                ]
            }
        )

        transition = detect_minutely_precipitation_transition(forecast)

        assert transition is not None
        assert transition.transition_type == "stopping"
        assert transition.minutes_until == 2
        assert transition.precipitation_type == "snow"

    def test_minutely_precipitation_transition_triggers_notification(
        self, manager, settings_with_minutely
    ):
        """A changed minutely transition should generate a user-facing notification."""
        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = None
        weather_data.discussion_issuance_time = None
        weather_data.current = None
        weather_data.minutely_precipitation = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0},
                    {"time": 1768917660, "precipIntensity": 0.02, "precipType": "rain"},
                ]
            }
        )

        first_events = manager.check_for_events(weather_data, settings_with_minutely, "Test City")
        second_events = manager.check_for_events(weather_data, settings_with_minutely, "Test City")
        assert first_events == []
        assert second_events == []

        weather_data.minutely_precipitation = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0},
                    {"time": 1768917660, "precipIntensity": 0},
                    {"time": 1768917720, "precipIntensity": 0.02, "precipType": "rain"},
                ]
            }
        )

        events = manager.check_for_events(weather_data, settings_with_minutely, "Test City")

        assert len(events) == 1
        assert events[0].event_type == "minutely_precipitation_start"
        assert events[0].title == "Rain starting in 2 minutes"
        assert events[0].message == "Rain starting in 2 minutes for Test City."
        assert manager.state.last_minutely_transition_signature == "starting:2:rain"

    def test_minutely_precipitation_stop_can_be_disabled(self, manager):
        """Disabled stop notifications should still update state without notifying."""
        settings = AppSettings(
            notify_discussion_update=False,
            notify_severe_risk_change=False,
            notify_minutely_precipitation_start=True,
            notify_minutely_precipitation_stop=False,
        )
        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = None
        weather_data.discussion_issuance_time = None
        weather_data.current = None
        weather_data.minutely_precipitation = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0.04, "precipType": "rain"},
                    {"time": 1768917660, "precipIntensity": 0},
                ]
            }
        )

        first_events = manager.check_for_events(weather_data, settings, "Test City")
        assert first_events == []

        weather_data.minutely_precipitation = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0.04, "precipType": "rain"},
                    {"time": 1768917660, "precipIntensity": 0.03, "precipType": "rain"},
                    {"time": 1768917720, "precipIntensity": 0},
                ]
            }
        )

        events = manager.check_for_events(weather_data, settings, "Test City")

        assert events == []
        assert manager.state.last_minutely_transition_signature == "stopping:2:rain"

    # ------------------------------------------------------------------
    # is_wet threshold tests
    # ------------------------------------------------------------------

    def test_is_wet_default_threshold_zero(self):
        """Default threshold (0.0) treats any positive intensity as wet."""
        from datetime import UTC, datetime

        from accessiweather.models import MinutelyPrecipitationPoint

        dry = MinutelyPrecipitationPoint(time=datetime.now(UTC), precipitation_intensity=0.0)
        trace = MinutelyPrecipitationPoint(time=datetime.now(UTC), precipitation_intensity=0.005)
        assert not is_wet(dry)
        assert is_wet(trace)

    def test_is_wet_light_threshold_filters_trace(self):
        """INTENSITY_THRESHOLD_LIGHT should suppress trace/noise readings."""
        from datetime import UTC, datetime

        from accessiweather.models import MinutelyPrecipitationPoint

        trace = MinutelyPrecipitationPoint(time=datetime.now(UTC), precipitation_intensity=0.005)
        light = MinutelyPrecipitationPoint(time=datetime.now(UTC), precipitation_intensity=0.02)
        assert not is_wet(trace, threshold=INTENSITY_THRESHOLD_LIGHT)
        assert is_wet(light, threshold=INTENSITY_THRESHOLD_LIGHT)

    def test_is_wet_moderate_threshold(self):
        """INTENSITY_THRESHOLD_MODERATE should filter light rain."""
        from datetime import UTC, datetime

        from accessiweather.models import MinutelyPrecipitationPoint

        light_rain = MinutelyPrecipitationPoint(
            time=datetime.now(UTC), precipitation_intensity=0.05
        )
        moderate_rain = MinutelyPrecipitationPoint(
            time=datetime.now(UTC), precipitation_intensity=0.2
        )
        assert not is_wet(light_rain, threshold=INTENSITY_THRESHOLD_MODERATE)
        assert is_wet(moderate_rain, threshold=INTENSITY_THRESHOLD_MODERATE)

    def test_is_wet_heavy_threshold(self):
        """INTENSITY_THRESHOLD_HEAVY should only flag heavy rain."""
        from datetime import UTC, datetime

        from accessiweather.models import MinutelyPrecipitationPoint

        moderate = MinutelyPrecipitationPoint(time=datetime.now(UTC), precipitation_intensity=0.5)
        heavy = MinutelyPrecipitationPoint(time=datetime.now(UTC), precipitation_intensity=1.5)
        assert not is_wet(moderate, threshold=INTENSITY_THRESHOLD_HEAVY)
        assert is_wet(heavy, threshold=INTENSITY_THRESHOLD_HEAVY)

    def test_detect_transition_with_moderate_threshold_ignores_light_rain(self):
        """With moderate threshold, light rain should not trigger a wet transition."""
        forecast = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0},
                    {"time": 1768917660, "precipIntensity": 0.05, "precipType": "rain"},
                    {"time": 1768917720, "precipIntensity": 0.05, "precipType": "rain"},
                ]
            }
        )
        # Light rain (0.05) is below moderate threshold (0.1) — no transition
        transition = detect_minutely_precipitation_transition(
            forecast, threshold=INTENSITY_THRESHOLD_MODERATE
        )
        assert transition is None

    def test_detect_transition_with_moderate_threshold_fires_for_moderate_rain(self):
        """With moderate threshold, moderate+ rain should trigger a wet transition."""
        forecast = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0},
                    {"time": 1768917660, "precipIntensity": 0.2, "precipType": "rain"},
                ]
            }
        )
        transition = detect_minutely_precipitation_transition(
            forecast, threshold=INTENSITY_THRESHOLD_MODERATE
        )
        assert transition is not None
        assert transition.transition_type == "starting"

    def test_notification_manager_respects_sensitivity_setting(self, manager):
        """Precipitation sensitivity setting should filter out sub-threshold rain."""
        settings = AppSettings(
            notify_discussion_update=False,
            notify_severe_risk_change=False,
            notify_minutely_precipitation_start=True,
            notify_minutely_precipitation_stop=True,
            precipitation_sensitivity="moderate",
        )
        weather_data = MagicMock(spec=WeatherData)
        weather_data.discussion = None
        weather_data.discussion_issuance_time = None
        weather_data.current = None

        # Light rain only (0.05 mm/h) — below moderate threshold (0.1 mm/h)
        weather_data.minutely_precipitation = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0},
                    {"time": 1768917660, "precipIntensity": 0.05, "precipType": "rain"},
                    {"time": 1768917720, "precipIntensity": 0.05, "precipType": "rain"},
                ]
            }
        )

        # First call stores state
        manager.check_for_events(weather_data, settings, "Test City")

        # Update to light rain start — should not trigger with moderate sensitivity
        weather_data.minutely_precipitation = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0},
                    {"time": 1768917660, "precipIntensity": 0},
                    {"time": 1768917720, "precipIntensity": 0.05, "precipType": "rain"},
                ]
            }
        )
        events = manager.check_for_events(weather_data, settings, "Test City")
        # Signature changed but no transition detected above threshold
        assert all(e.event_type != "minutely_precipitation_start" for e in events)

    def test_reset_state(self, manager):
        """Test state reset."""
        manager.state.last_discussion_issuance_time = datetime(
            2026, 1, 20, 14, 35, 0, tzinfo=timezone.utc
        )
        manager.state.last_severe_risk = 75

        manager.reset_state()

        assert manager.state.last_discussion_issuance_time is None
        assert manager.state.last_severe_risk is None
        assert manager.state.last_minutely_transition_signature is None


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


class TestGetRiskCategory:
    """Tests for get_risk_category function."""

    def test_minimal_risk(self):
        """Test minimal risk category (0-19)."""
        assert get_risk_category(0) == "minimal"
        assert get_risk_category(10) == "minimal"
        assert get_risk_category(19) == "minimal"

    def test_low_risk(self):
        """Test low risk category (20-39)."""
        assert get_risk_category(20) == "low"
        assert get_risk_category(30) == "low"
        assert get_risk_category(39) == "low"

    def test_moderate_risk(self):
        """Test moderate risk category (40-59)."""
        assert get_risk_category(40) == "moderate"
        assert get_risk_category(50) == "moderate"
        assert get_risk_category(59) == "moderate"

    def test_high_risk(self):
        """Test high risk category (60-79)."""
        assert get_risk_category(60) == "high"
        assert get_risk_category(70) == "high"
        assert get_risk_category(79) == "high"

    def test_extreme_risk(self):
        """Test extreme risk category (80+)."""
        assert get_risk_category(80) == "extreme"
        assert get_risk_category(90) == "extreme"
        assert get_risk_category(100) == "extreme"
