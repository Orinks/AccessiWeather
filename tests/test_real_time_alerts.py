"""Tests for real-time alerts functionality."""

from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.settings.constants import (
    ALERT_RADIUS_KEY,
    PRECISE_LOCATION_ALERTS_KEY,
    UPDATE_INTERVAL_KEY,
)
from accessiweather.gui.weather_app import WeatherApp
from accessiweather.notifications import WeatherNotifier

# --- Test Data ---

SAMPLE_CONFIG = {
    "settings": {
        UPDATE_INTERVAL_KEY: 10,  # 10 minutes for regular updates
        ALERT_RADIUS_KEY: 25,
        PRECISE_LOCATION_ALERTS_KEY: True,
    }
}

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

SAMPLE_UPDATED_ALERT = {
    "id": "test-alert-1",
    "event": "Test Event",
    "headline": "Updated Test Alert",  # Changed headline
    "description": "Updated Test Description",  # Changed description
    "severity": "Severe",  # Changed severity
    "urgency": "Expected",
    "sent": "2024-04-16T08:00:00Z",
    "effective": "2024-04-16T08:00:00Z",
    "expires": "2024-04-16T14:00:00Z",
    "status": "Actual",
    "messageType": "Alert",
    "category": "Met",
    "response": "Execute",
}

SAMPLE_UPDATED_ALERTS_DATA = {"features": [{"properties": SAMPLE_UPDATED_ALERT}]}

# --- Fixtures ---


@pytest.fixture
def mock_weather_app():
    """Create a mock WeatherApp instance with necessary attributes."""
    # Create mock services
    mock_weather_service = MagicMock()
    mock_location_service = MagicMock()
    mock_notification_service = MagicMock()

    # Create mock timer
    mock_timer = MagicMock(spec=wx.Timer)

    # Create the app with mocked services
    with patch.object(WeatherApp, "__init__", return_value=None):
        app = WeatherApp()

        # Set up required attributes
        app.weather_service = mock_weather_service
        app.location_service = mock_location_service
        app.notification_service = mock_notification_service
        app.config = SAMPLE_CONFIG.copy()
        app.timer = mock_timer
        app.last_update = 0.0
        app.updating = False
        app._alerts_complete = True  # Add the missing attribute

        # Mock methods - using setattr to avoid type checking issues
        setattr(app, "SetStatusText", MagicMock())
        setattr(app, "UpdateWeatherData", MagicMock())

        yield app


@pytest.fixture
def mock_notifier():
    """Create a mock WeatherNotifier instance."""
    notifier = MagicMock()
    notifier.show_toast = MagicMock()
    return notifier


# --- Tests ---


def test_process_alerts_detects_new_alerts(mock_notifier):
    """Test that process_alerts detects new alerts."""
    # Set up the notifier with persistence disabled to avoid loading existing alerts
    notifier = WeatherNotifier(enable_persistence=False)
    notifier.toaster = mock_notifier

    # Process alerts for the first time
    with patch("time.time", return_value=1000.0):
        processed_alerts, new_count, updated_count = notifier.process_alerts(SAMPLE_ALERTS_DATA)

    # Verify results
    assert len(processed_alerts) == 1
    assert new_count == 1
    assert updated_count == 0
    # Check that the alert is tracked using deduplication key format
    assert len(notifier.active_alerts) == 1
    # The key should start with "dedup:" and contain the event name
    dedup_keys = [
        key
        for key in notifier.active_alerts.keys()
        if key.startswith("dedup:") and "Test Event" in key
    ]
    assert len(dedup_keys) == 1


def test_process_alerts_detects_updated_alerts():
    """Test that process_alerts detects updated alerts."""
    # Create a mock WeatherNotifier
    notifier = MagicMock(spec=WeatherNotifier)

    # Set up the mock to return the expected values
    notifier.process_alerts.return_value = (
        [SAMPLE_UPDATED_ALERT],  # processed_alerts
        0,  # new_count
        1,  # updated_count
    )

    # Call the method
    processed_alerts, new_count, updated_count = notifier.process_alerts(SAMPLE_UPDATED_ALERTS_DATA)

    # Verify results
    assert len(processed_alerts) == 1
    assert new_count == 0
    assert updated_count == 1

    # Verify that the method was called with the correct parameters
    notifier.process_alerts.assert_called_once_with(SAMPLE_UPDATED_ALERTS_DATA)


def test_show_notification_for_new_alert(mock_notifier):
    """Test showing notification for a new alert."""
    # Set up the notifier
    notifier = WeatherNotifier()
    notifier.toaster = mock_notifier

    # Show notification for a new alert
    notifier.show_notification(SAMPLE_ALERT, is_update=False)

    # Verify that the toaster was called with the correct parameters
    mock_notifier.show_toast.assert_called_once_with(
        title=f"Weather {SAMPLE_ALERT['event']}",
        msg=SAMPLE_ALERT["headline"],
        timeout=10,
        app_name="AccessiWeather",
    )


def test_show_notification_for_updated_alert(mock_notifier):
    """Test showing notification for an updated alert."""
    # Set up the notifier
    notifier = WeatherNotifier()
    notifier.toaster = mock_notifier

    # Show notification for an updated alert
    notifier.show_notification(SAMPLE_UPDATED_ALERT, is_update=True)

    # Verify that the toaster was called with the correct parameters
    mock_notifier.show_toast.assert_called_once_with(
        title=f"Updated: Weather {SAMPLE_UPDATED_ALERT['event']}",
        msg=SAMPLE_UPDATED_ALERT["headline"],
        timeout=10,
        app_name="AccessiWeather",
    )


def test_notify_alerts_with_new_and_updated_counts(mock_notifier):
    """Test notify_alerts with new and updated counts."""
    # Set up the notifier
    notifier = WeatherNotifier()
    notifier.toaster = mock_notifier

    # Call notify_alerts with new and updated counts
    notifier.notify_alerts(2, new_count=1, updated_count=1)

    # Verify that the toaster was called with the correct parameters
    mock_notifier.show_toast.assert_called_once_with(
        title="Weather Alerts",
        msg="1 new alert, 1 updated alert in your area",
        timeout=10,
        app_name="AccessiWeather",
    )
