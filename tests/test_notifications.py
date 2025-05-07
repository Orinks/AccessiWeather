"""Tests for weather notifications."""

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from dateutil.parser import isoparse  # type: ignore # requires python-dateutil

from accessiweather.notifications import SafeToastNotifier, WeatherNotifier

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
    """Create a WeatherNotifier instance."""
    return WeatherNotifier()


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
    mock_now = datetime(2024, 4, 16, 10, 0, tzinfo=timezone.utc)

    def mock_isoparse(timestamp_str):
        """Mock isoparse to return timezone-aware datetimes."""
        # Parse the timestamp manually for test data
        if timestamp_str == "2024-04-16T14:00:00Z":
            return datetime(2024, 4, 16, 14, 0, tzinfo=timezone.utc)
        elif timestamp_str == "2024-04-16T09:00:00Z":
            return datetime(2024, 4, 16, 9, 0, tzinfo=timezone.utc)
        elif timestamp_str == "2024-04-16T11:00:00Z":
            return datetime(2024, 4, 16, 11, 0, tzinfo=timezone.utc)
        else:
            # For unknown timestamps, use the real isoparse
            return isoparse(timestamp_str)

    with (
        patch("accessiweather.notifications.datetime") as mock_dt,
        patch("accessiweather.notifications.isoparse") as mock_parse,
    ):
        mock_dt.now.return_value = mock_now
        mock_dt.timezone = timezone  # Keep the real timezone
        mock_parse.side_effect = mock_isoparse
        yield mock_dt


# --- WeatherNotifier Tests ---


def test_init():
    """Test WeatherNotifier initialization."""
    notifier = WeatherNotifier()
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
    assert SAMPLE_ALERT["id"] in notifier.active_alerts
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
    assert SAMPLE_ALERT["id"] in notifier.active_alerts
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
    # Add one expired and one active alert
    expired_alert = dict(SAMPLE_ALERT)
    expired_alert["id"] = "expired"
    expired_alert["expires"] = "2024-04-16T09:00:00Z"  # Before mock now (10:00)

    active_alert = dict(SAMPLE_ALERT)
    active_alert["id"] = "active"
    active_alert["expires"] = "2024-04-16T11:00:00Z"  # After mock now (10:00)

    notifier.active_alerts = {"expired": expired_alert, "active": active_alert}

    notifier.clear_expired_alerts()

    assert "expired" not in notifier.active_alerts
    assert "active" in notifier.active_alerts


def test_clear_expired_alerts_invalid_timestamp(notifier, mock_datetime):
    """Test clearing alerts with invalid timestamp."""
    alert = dict(SAMPLE_ALERT)
    alert["expires"] = "invalid-timestamp"
    notifier.active_alerts = {"test": alert}

    notifier.clear_expired_alerts()

    # Alert should remain since we couldn't parse its timestamp
    assert "test" in notifier.active_alerts


def test_clear_expired_alerts_missing_expires(notifier, mock_datetime):
    """Test clearing alerts with missing expires field."""
    alert = dict(SAMPLE_ALERT)
    del alert["expires"]
    notifier.active_alerts = {"test": alert}

    notifier.clear_expired_alerts()

    # Alert should remain since it has no expires field
    assert "test" in notifier.active_alerts


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
        patch("accessiweather.notifications.notification") as mock_notify,
        patch("accessiweather.notifications.sys") as mock_sys,
    ):
        # Create a modules dict without pytest
        mock_modules = dict(sys.modules)
        mock_modules.pop("pytest", None)
        mock_sys.modules = mock_modules

        toaster = SafeToastNotifier()
        result = toaster.show_toast(title="Test Title", msg="Test Message", duration=5)

        assert result is True
        mock_notify.notify.assert_called_once_with(
            title="Test Title", message="Test Message", app_name="AccessiWeather", timeout=5
        )


def test_safe_toast_exception():
    """Test toast notification with exception."""
    with (
        patch("accessiweather.notifications.notification") as mock_notify,
        patch("accessiweather.notifications.sys") as mock_sys,
    ):
        # Create a modules dict without pytest
        mock_modules = dict(sys.modules)
        mock_modules.pop("pytest", None)
        mock_sys.modules = mock_modules

        mock_notify.notify.side_effect = Exception("Test error")
        toaster = SafeToastNotifier()
        result = toaster.show_toast(title="Test Title", msg="Test Message")

        assert result is False


def test_safe_toast_pytest():
    """Test toast notification in pytest environment."""
    # pytest is already in sys.modules when running these tests
    toaster = SafeToastNotifier()
    with patch("accessiweather.notifications.notification") as mock_notify:
        result = toaster.show_toast(title="Test Title", msg="Test Message")

        assert result is True
        mock_notify.notify.assert_not_called()
