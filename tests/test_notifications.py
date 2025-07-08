"""Tests for weather notifications."""

import sys
from datetime import UTC, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from dateutil.parser import isoparse  # type: ignore # requires python-dateutil

from accessiweather.notifications import SafeToastNotifier, WeatherNotifier
from accessiweather.notifications.toast_notifier import SafeDesktopNotifier

import os
import json
import logging
import shutil
import tempfile
from pathlib import Path
import pytest
from unittest import mock

import src.accessiweather.notifications.sound_player as sound_player

# --- Test Data ---

SAMPLE_ALERT = {
    "id": "test-alert-1",
    "event": "Test Event",
    "headline": "Test Alert",
    "description": "Test Description",
    "severity": "Moderate",
    "urgency": "Expected",
    "sent": "2024-04-16T08:00:00Z",
    "effective": "2024-04-16T08:00:00Z",
    "expires": "2024-04-16T14:00:00Z",
    "status": "Actual",
    "messageType": "Alert",
    "category": "Met",
    "response": "Execute",
}

SAMPLE_ALERTS_DATA = {"features": [{"properties": SAMPLE_ALERT}]}

SAMPLE_ALERTS_DATA_MULTIPLE = {
    "features": [
        {"properties": SAMPLE_ALERT},
        {
            "properties": {
                "id": "test-alert-2",
                "event": "Another Event",
                "headline": "Another Alert",
                "description": "Another Description",
                "severity": "Severe",
                "urgency": "Immediate",
                "sent": "2024-04-16T08:00:00Z",
                "effective": "2024-04-16T08:00:00Z",
                "expires": "2024-04-16T14:00:00Z",
                "status": "Actual",
                "messageType": "Alert",
                "category": "Met",
                "response": "Execute",
            }
        },
    ]
}

# --- Fixtures ---


@pytest.fixture
def notifier():
    """Create a WeatherNotifier instance with persistence disabled for testing."""
    return WeatherNotifier(enable_persistence=False)


@pytest.fixture
def mock_toaster():
    """Mock SafeToastNotifier."""
    with patch("accessiweather.notifications.SafeToastNotifier") as mock:
        mock_instance = MagicMock()
        mock_instance.show_toast.return_value = True
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_datetime():
    """Mock datetime.now and isoparse."""
    mock_now = datetime(2024, 4, 16, 10, 0, tzinfo=UTC)

    def mock_isoparse(timestamp_str):
        """Mock isoparse to return timezone-aware datetimes."""
        # Parse the timestamp manually for test data
        if timestamp_str == "2024-04-16T14:00:00Z":
            return datetime(2024, 4, 16, 14, 0, tzinfo=UTC)
        if timestamp_str == "2024-04-16T09:00:00Z":
            return datetime(2024, 4, 16, 9, 0, tzinfo=UTC)
        if timestamp_str == "2024-04-16T11:00:00Z":
            return datetime(2024, 4, 16, 11, 0, tzinfo=UTC)
        # For unknown timestamps, use the real isoparse
        return isoparse(timestamp_str)

    with (
        patch("accessiweather.notifications.weather_notifier.datetime") as mock_dt,
        patch("accessiweather.notifications.weather_notifier.isoparse") as mock_parse,
    ):
        mock_dt.now.return_value = mock_now
        mock_dt.timezone = timezone  # Keep the real timezone
        mock_parse.side_effect = mock_isoparse
        yield mock_dt


# --- Notification Sound Playback & Sound Pack Tests (TDD Scaffold) ---

@pytest.fixture
def mock_sound_player():
    """Mock the sound playback function/class."""
    with patch("accessiweather.notifications.sound_player.SoundPlayer") as mock_player_class:
        mock_player = MagicMock()
        mock_player_class.return_value = mock_player
        yield mock_player

@pytest.fixture
def mock_toga_dummy_backend():
    """Mock Toga dummy backend for sound playback integration tests."""
    with patch("toga_dummy_backend.sound") as mock_toga_sound:
        yield mock_toga_sound


# --- WeatherNotifier Tests ---


def test_init():
    """Test WeatherNotifier initialization."""
    notifier = WeatherNotifier(enable_persistence=False)
    assert isinstance(notifier.toaster, SafeToastNotifier)
    assert notifier.active_alerts == {}


def test_notify_alerts_none(notifier, mock_toaster):
    """Test notify_alerts with no alerts."""
    notifier.toaster = mock_toaster
    notifier.notify_alerts(0)
    mock_toaster.show_toast.assert_not_called()


def test_notify_alerts_single(notifier, mock_toaster):
    """Test notify_alerts with one alert."""
    notifier.toaster = mock_toaster
    notifier.notify_alerts(1)
    mock_toaster.show_toast.assert_called_once_with(
        title="Weather Alerts",
        msg="1 active weather alert in your area",
        timeout=10,
        app_name="AccessiWeather",
    )


def test_notify_alerts_multiple(notifier, mock_toaster):
    """Test notify_alerts with multiple alerts."""
    notifier.toaster = mock_toaster
    notifier.notify_alerts(3)
    mock_toaster.show_toast.assert_called_once_with(
        title="Weather Alerts",
        msg="3 active weather alerts in your area",
        timeout=10,
        app_name="AccessiWeather",
    )


def test_process_alerts_new(notifier, mock_toaster, mock_datetime):
    """Test processing new alerts."""
    notifier.toaster = mock_toaster

    result = notifier.process_alerts(SAMPLE_ALERTS_DATA)
    processed_alerts, new_count, updated_count = result

    assert len(processed_alerts) == 1
    assert processed_alerts[0]["id"] == SAMPLE_ALERT["id"]
    assert new_count == 1
    assert updated_count == 0
    # Check that the alert is tracked (now using deduplication keys)
    assert len(notifier.active_alerts) == 1
    mock_toaster.show_toast.assert_called_once_with(
        title=f"Weather {SAMPLE_ALERT['event']}",
        msg=SAMPLE_ALERT["headline"],
        timeout=10,
        app_name="AccessiWeather",
    )


def test_process_alerts_existing(notifier, mock_toaster, mock_datetime):
    """Test processing existing alerts."""
    notifier.toaster = mock_toaster

    # First call to populate active_alerts
    notifier.process_alerts(SAMPLE_ALERTS_DATA)
    mock_toaster.show_toast.reset_mock()

    # Second call with same data
    result = notifier.process_alerts(SAMPLE_ALERTS_DATA)
    processed_alerts, new_count, updated_count = result

    assert len(processed_alerts) == 1
    assert processed_alerts[0]["id"] == SAMPLE_ALERT["id"]
    assert new_count == 0
    assert updated_count == 0
    # Check that the alert is still tracked (now using deduplication keys)
    assert len(notifier.active_alerts) == 1
    mock_toaster.show_toast.assert_not_called()  # No notification for existing alert


def test_process_alerts_mixed(notifier, mock_toaster, mock_datetime):
    """Test processing mixed new and existing alerts."""
    notifier.toaster = mock_toaster

    # First call with one alert
    notifier.process_alerts(SAMPLE_ALERTS_DATA)
    mock_toaster.show_toast.reset_mock()

    # Second call with two alerts (one new, one existing)
    result = notifier.process_alerts(SAMPLE_ALERTS_DATA_MULTIPLE)
    processed_alerts, new_count, updated_count = result

    assert len(processed_alerts) == 2
    assert new_count == 1
    assert updated_count == 0
    assert len(notifier.active_alerts) == 2
    mock_toaster.show_toast.assert_called_once()  # Only for the new alert


def test_process_alerts_empty(notifier, mock_toaster):
    """Test processing empty alerts data."""
    notifier.toaster = mock_toaster

    result = notifier.process_alerts({"features": []})
    processed_alerts, new_count, updated_count = result

    assert len(processed_alerts) == 0
    assert new_count == 0
    assert updated_count == 0
    assert not notifier.active_alerts
    mock_toaster.show_toast.assert_not_called()


def test_show_notification(notifier, mock_toaster):
    """Test showing a notification."""
    notifier.toaster = mock_toaster

    notifier.show_notification(SAMPLE_ALERT)

    mock_toaster.show_toast.assert_called_once_with(
        title=f"Weather {SAMPLE_ALERT['event']}",
        msg=SAMPLE_ALERT["headline"],
        timeout=10,
        app_name="AccessiWeather",
    )


def test_show_notification_no_headline(notifier, mock_toaster):
    """Test showing a notification without a headline."""
    notifier.toaster = mock_toaster
    alert = dict(SAMPLE_ALERT)
    del alert["headline"]

    notifier.show_notification(alert)

    mock_toaster.show_toast.assert_called_once_with(
        title=f"Weather {alert['event']}",
        msg="Weather alert in your area",
        timeout=10,
        app_name="AccessiWeather",
    )


def test_clear_expired_alerts(notifier, mock_datetime):
    """Test clearing expired alerts."""
    # Add one expired and one active alert using deduplication keys
    expired_alert = dict(SAMPLE_ALERT)
    expired_alert["id"] = "expired"
    expired_alert["expires"] = "2024-04-16T09:00:00Z"  # Before mock now (10:00)
    expired_alert["areaDesc"] = ""

    active_alert = dict(SAMPLE_ALERT)
    active_alert["id"] = "active"
    active_alert["expires"] = "2024-04-16T11:00:00Z"  # After mock now (10:00)
    active_alert["areaDesc"] = ""

    # Use deduplication keys as the new system does
    expired_key = "dedup:Test Event|2024-04-16T08:00:00Z|2024-04-16T09:00:00Z"
    active_key = "dedup:Test Event|2024-04-16T08:00:00Z|2024-04-16T11:00:00Z"

    notifier.active_alerts = {expired_key: expired_alert, active_key: active_alert}

    notifier.clear_expired_alerts()

    assert expired_key not in notifier.active_alerts
    assert active_key in notifier.active_alerts


def test_clear_expired_alerts_invalid_timestamp(notifier, mock_datetime):
    """Test clearing alerts with invalid timestamp."""
    alert = dict(SAMPLE_ALERT)
    alert["expires"] = "invalid-timestamp"
    alert["areaDesc"] = ""
    test_key = "dedup:test_key"
    notifier.active_alerts = {test_key: alert}

    notifier.clear_expired_alerts()

    # Alert should remain since we couldn't parse its timestamp
    assert test_key in notifier.active_alerts


def test_clear_expired_alerts_missing_expires(notifier, mock_datetime):
    """Test clearing alerts with missing expires field."""
    alert = dict(SAMPLE_ALERT)
    del alert["expires"]
    alert["areaDesc"] = ""
    test_key = "dedup:test_key"
    notifier.active_alerts = {test_key: alert}

    notifier.clear_expired_alerts()

    # Alert should remain since it has no expires field
    assert test_key in notifier.active_alerts


def test_get_sorted_alerts(notifier):
    """Test getting sorted alerts."""
    # Add alerts with different severities
    extreme = dict(SAMPLE_ALERT, id="extreme", severity="Extreme")
    severe = dict(SAMPLE_ALERT, id="severe", severity="Severe")
    moderate = dict(SAMPLE_ALERT, id="moderate", severity="Moderate")
    minor = dict(SAMPLE_ALERT, id="minor", severity="Minor")
    unknown = dict(SAMPLE_ALERT, id="unknown", severity="Unknown")

    notifier.active_alerts = {
        "minor": minor,
        "extreme": extreme,
        "unknown": unknown,
        "moderate": moderate,
        "severe": severe,
    }

    sorted_alerts = notifier.get_sorted_alerts()

    assert len(sorted_alerts) == 5
    assert sorted_alerts[0]["id"] == "extreme"
    assert sorted_alerts[1]["id"] == "severe"
    assert sorted_alerts[2]["id"] == "moderate"
    assert sorted_alerts[3]["id"] == "minor"
    assert sorted_alerts[4]["id"] == "unknown"


# --- SafeToastNotifier Tests ---


def test_safe_toast_success():
    """Test successful toast notification."""
    with (
        patch(
            "accessiweather.notifications.toast_notifier.SafeDesktopNotifier"
        ) as mock_notifier_class,
        patch("accessiweather.notifications.toast_notifier.sys") as mock_sys,
    ):
        # Create a modules dict without pytest
        mock_modules = dict(sys.modules)
        mock_modules.pop("pytest", None)
        mock_sys.modules = mock_modules

        # Mock the SafeDesktopNotifier instance
        mock_notifier_instance = MagicMock()
        mock_notifier_instance.send_notification.return_value = True
        mock_notifier_class.return_value = mock_notifier_instance

        toaster = SafeToastNotifier()
        result = toaster.show_toast(title="Test Title", msg="Test Message", duration=5)

        assert result is True
        mock_notifier_instance.send_notification.assert_called_once_with(
            "Test Title", "Test Message", 5
        )


def test_safe_toast_exception():
    """Test toast notification with exception."""
    with (
        patch(
            "accessiweather.notifications.toast_notifier.SafeDesktopNotifier"
        ) as mock_notifier_class,
        patch("accessiweather.notifications.toast_notifier.sys") as mock_sys,
    ):
        # Create a modules dict without pytest
        mock_modules = dict(sys.modules)
        mock_modules.pop("pytest", None)
        mock_sys.modules = mock_modules

        # Mock the SafeDesktopNotifier instance to raise exception
        mock_notifier_instance = MagicMock()
        mock_notifier_instance.send_notification.return_value = False
        mock_notifier_class.return_value = mock_notifier_instance

        toaster = SafeToastNotifier()
        result = toaster.show_toast(title="Test Title", msg="Test Message")

        assert result is False


def test_safe_toast_pytest():
    """Test toast notification in pytest environment."""
    # pytest is already in sys.modules when running these tests
    toaster = SafeToastNotifier()
    with patch(
        "accessiweather.notifications.toast_notifier.SafeDesktopNotifier"
    ) as mock_notifier_class:
        mock_notifier_instance = MagicMock()
        mock_notifier_class.return_value = mock_notifier_instance

        result = toaster.show_toast(title="Test Title", msg="Test Message")

        assert result is True
        # In pytest environment, it should just log and return True without calling the notifier
        mock_notifier_instance.send_notification.assert_not_called()


# --- SafeDesktopNotifier Tests ---


def test_safe_desktop_notifier_success():
    """Test successful desktop notification."""
    with patch(
        "accessiweather.notifications.toast_notifier.DesktopNotifier"
    ) as mock_desktop_notifier_class:
        mock_desktop_notifier_instance = MagicMock()
        mock_desktop_notifier_class.return_value = mock_desktop_notifier_instance

        # Mock the async send method
        async def mock_send(*args, **kwargs):
            return None

        mock_desktop_notifier_instance.send = mock_send

        notifier = SafeDesktopNotifier()
        result = notifier.send_notification("Test Title", "Test Message", 10)

        assert result is True


def test_safe_desktop_notifier_exception():
    """Test desktop notification with exception."""
    with patch(
        "accessiweather.notifications.toast_notifier.DesktopNotifier"
    ) as mock_desktop_notifier_class:
        mock_desktop_notifier_instance = MagicMock()
        mock_desktop_notifier_class.return_value = mock_desktop_notifier_instance

        # Mock the async send method to raise exception
        async def mock_send(*args, **kwargs):
            raise Exception("Test error")

        mock_desktop_notifier_instance.send = mock_send

        notifier = SafeDesktopNotifier()
        result = notifier.send_notification("Test Title", "Test Message", 10)

        assert result is False


# --- Notification Sound Playback & Sound Pack Tests (TDD Scaffold) ---

@pytest.fixture
def mock_sound_player():
    """Mock the sound playback function/class."""
    with patch("accessiweather.notifications.sound_player.SoundPlayer") as mock_player_class:
        mock_player = MagicMock()
        mock_player_class.return_value = mock_player
        yield mock_player

@pytest.fixture
def mock_toga_dummy_backend():
    """Mock Toga dummy backend for sound playback integration tests."""
    with patch("toga_dummy_backend.sound") as mock_toga_sound:
        yield mock_toga_sound


def test_notification_plays_sound_on_send(mock_sound_player, mock_toaster):
    """Test that a sound is played when a notification is sent."""
    # TODO: Implement test logic after sound feature is added
    pass


def test_selects_correct_sound_file_based_on_user_preference(mock_sound_player):
    """Test that the correct sound file is selected based on user preference."""
    # TODO: Implement test logic after sound feature is added
    pass


def test_fallback_to_default_sound_if_selected_missing(mock_sound_player):
    """Test fallback to default sound if the selected sound file is missing."""
    # TODO: Implement test logic after sound feature is added
    pass


def test_error_handling_for_sound_playback_failure(mock_sound_player):
    """Test error handling when sound playback fails (e.g., file not found, playback error)."""
    # TODO: Implement test logic after sound feature is added
    pass


def test_no_sound_played_if_user_disables_sounds(mock_sound_player):
    """Test that no sound is played if the user disables notification sounds in preferences."""
    # TODO: Implement test logic after sound feature is added
    pass


def test_list_and_load_available_sound_packs():
    """Test listing and loading available sound packs."""
    # TODO: Implement test logic after sound feature is added
    pass


def test_toga_dummy_backend_sound_integration(mock_toga_dummy_backend, mock_sound_player):
    """Test integration of sound playback with Toga dummy backend (for CI and headless testing)."""
    # TODO: Implement test logic after sound feature is added
    pass


# --- Sound Pack System Tests (TDD Scaffold) ---

def test_load_sound_pack_metadata():
    """Test loading sound pack metadata from pack.json."""
    # TODO: Implement test logic after sound pack loader is added
    pass


def test_list_available_sound_packs():
    """Test listing available sound packs in the soundpacks/ directory."""
    # TODO: Implement test logic after sound pack loader is added
    pass


def test_select_sound_for_alert_type_and_severity():
    """Test selecting a sound for a given alert type and severity."""
    # TODO: Implement test logic after sound pack loader is added
    pass


def test_fallback_to_alert_type_if_severity_missing():
    """Test fallback to alert type sound if severity-specific sound is missing."""
    # TODO: Implement test logic after sound pack loader is added
    pass


def test_fallback_to_default_if_alert_type_missing():
    """Test fallback to default sound if alert type sound is missing."""
    # TODO: Implement test logic after sound pack loader is added
    pass


def test_user_can_select_and_preview_sounds():
    """Test that user can select and preview sounds for each alert type/severity."""
    # TODO: Implement test logic after sound pack loader is added
    pass


def test_add_new_sound_pack():
    """Test adding a new sound pack by placing a zip/folder in soundpacks/."""
    # TODO: Implement test logic after sound pack loader is added
    pass


def test_remove_sound_pack():
    """Test removing a sound pack from the soundpacks/ directory."""
    # TODO: Implement test logic after sound pack loader is added
    pass


def test_error_handling_for_malformed_or_missing_pack_json():
    """Test error handling for malformed or missing pack.json in a sound pack."""
    # TODO: Implement test logic after sound pack loader is added
    pass


@pytest.fixture
def temp_soundpacks(tmp_path):
    # Create a temp soundpacks dir with a default pack and a custom pack
    soundpacks = tmp_path / "soundpacks"
    soundpacks.mkdir()
    # Default pack
    default_pack = soundpacks / "default"
    default_pack.mkdir()
    (default_pack / "alert.wav").write_bytes(b"fakewav")
    (default_pack / "notify.wav").write_bytes(b"fakewav")
    (default_pack / "pack.json").write_text(json.dumps({
        "name": "Default",
        "author": "Test",
        "description": "Default pack",
        "sounds": {"alert": "alert.wav", "notify": "notify.wav"}
    }))
    # Custom pack (missing alert.wav)
    custom_pack = soundpacks / "custom"
    custom_pack.mkdir()
    (custom_pack / "notify.wav").write_bytes(b"fakewav")
    (custom_pack / "pack.json").write_text(json.dumps({
        "name": "Custom",
        "author": "Test",
        "description": "Custom pack",
        "sounds": {"alert": "alert.wav", "notify": "notify.wav"}
    }))
    # Patch SOUNDPACKS_DIR for the duration of the test
    orig_dir = sound_player.SOUNDPACKS_DIR
    sound_player.SOUNDPACKS_DIR = soundpacks
    yield soundpacks
    sound_player.SOUNDPACKS_DIR = orig_dir


def test_get_sound_file_found(temp_soundpacks):
    f = sound_player.get_sound_file("alert", "default")
    assert f is not None
    assert f.name == "alert.wav"
    assert f.parent.name == "default"

def test_get_sound_file_fallback_to_default(temp_soundpacks):
    # custom pack missing alert.wav, should fallback to default
    f = sound_player.get_sound_file("alert", "custom")
    assert f is not None
    assert f.name == "alert.wav"
    assert f.parent.name == "default"

def test_get_sound_file_missing_everywhere(temp_soundpacks):
    # Remove alert.wav from default
    (temp_soundpacks / "default" / "alert.wav").unlink()
    f = sound_player.get_sound_file("alert", "custom")
    assert f is None

def test_get_sound_file_missing_pack_json(temp_soundpacks, caplog):
    # Remove pack.json from custom
    (temp_soundpacks / "custom" / "pack.json").unlink()
    with caplog.at_level(logging.WARNING):
        f = sound_player.get_sound_file("alert", "custom")
        assert f is not None  # Should fallback to default
        assert f.parent.name == "default"
        assert "pack.json not found" in caplog.text

def test_get_sound_file_missing_default_pack_json(temp_soundpacks, caplog):
    # Remove pack.json from both
    (temp_soundpacks / "custom" / "pack.json").unlink(missing_ok=True)
    (temp_soundpacks / "default" / "pack.json").unlink(missing_ok=True)
    with caplog.at_level(logging.ERROR):
        f = sound_player.get_sound_file("alert", "custom")
        assert f is None
        assert "Default sound pack is missing" in caplog.text

@mock.patch("src.accessiweather.notifications.sound_player.playsound")
def test_play_notification_sound_success(mock_playsound, temp_soundpacks):
    sound_player.play_notification_sound("alert", "default")
    mock_playsound.assert_called_once()
    # Should call with the alert.wav path
    arg = mock_playsound.call_args[0][0]
    assert arg.endswith("alert.wav")

@mock.patch("src.accessiweather.notifications.sound_player.playsound", None)
def test_play_notification_sound_no_playsound(temp_soundpacks, caplog):
    with caplog.at_level(logging.WARNING):
        sound_player.play_notification_sound("alert", "default")
        assert "Sound playback not available" in caplog.text

@mock.patch("src.accessiweather.notifications.sound_player.play_notification_sound")
def test_play_sample_sound_delegates(mock_play, temp_soundpacks):
    sound_player.play_sample_sound("default")
    mock_play.assert_called_once_with(sound_player.DEFAULT_EVENT, "default")
