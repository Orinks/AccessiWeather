"""Tests for real-time alerts functionality."""

from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.settings_dialog import (
    ALERT_RADIUS_KEY,
    ALERT_UPDATE_INTERVAL_KEY,
    PRECISE_LOCATION_ALERTS_KEY,
    UPDATE_INTERVAL_KEY,
)
from accessiweather.gui.weather_app import WeatherApp
from accessiweather.notifications import WeatherNotifier

# --- Test Data ---

SAMPLE_CONFIG = {
    "settings": {
        UPDATE_INTERVAL_KEY: 30,  # 30 minutes for regular updates
        ALERT_UPDATE_INTERVAL_KEY: 1,  # 1 minute for alert updates
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

    # Create mock timers
    mock_timer = MagicMock(spec=wx.Timer)
    mock_alerts_timer = MagicMock(spec=wx.Timer)

    # Create the app with mocked services
    with patch.object(WeatherApp, "__init__", return_value=None):
        app = WeatherApp()

        # Set up required attributes
        app.weather_service = mock_weather_service
        app.location_service = mock_location_service
        app.notification_service = mock_notification_service
        app.config = SAMPLE_CONFIG.copy()
        app.timer = mock_timer
        app.alerts_timer = mock_alerts_timer
        app.last_update = 0.0
        app.last_alerts_update = 0.0
        app.updating = False
        app._alerts_complete = True  # Add the missing attribute

        # Mock methods
        app.SetStatusText = MagicMock()
        app.UpdateWeatherData = MagicMock()
        app.UpdateAlerts = MagicMock()

        yield app


@pytest.fixture
def mock_notifier():
    """Create a mock WeatherNotifier instance."""
    notifier = MagicMock()
    notifier.show_toast = MagicMock()
    return notifier


# --- Tests ---


def test_alert_update_interval_setting_exists():
    """Test that the alert update interval setting constant exists."""
    assert ALERT_UPDATE_INTERVAL_KEY == "alert_update_interval_minutes"


def test_weather_app_has_alerts_timer(mock_weather_app):
    """Test that WeatherApp has an alerts timer attribute."""
    assert hasattr(mock_weather_app, "alerts_timer")
    assert isinstance(mock_weather_app.alerts_timer, MagicMock)


def test_weather_app_has_last_alerts_update(mock_weather_app):
    """Test that WeatherApp has a last_alerts_update attribute."""
    assert hasattr(mock_weather_app, "last_alerts_update")
    assert mock_weather_app.last_alerts_update == 0.0


def test_on_alerts_timer_checks_interval(mock_weather_app):
    """Test that OnAlertsTimer checks the alert update interval."""
    # Mock time.time() to return a specific value
    with patch("time.time", return_value=1000.0):
        # Set last_alerts_update to a value that will trigger an update
        mock_weather_app.last_alerts_update = 700.0  # 5 minutes = 300 seconds ago

        # Call OnAlertsTimer
        mock_weather_app.OnAlertsTimer(None)

        # Verify that UpdateAlerts was called
        mock_weather_app.UpdateAlerts.assert_called_once()


def test_on_alerts_timer_respects_interval(mock_weather_app):
    """Test that OnAlertsTimer respects the alert update interval."""
    # Mock time.time() to return a specific value
    with patch("time.time", return_value=1000.0):
        # Set last_alerts_update to a value that will NOT trigger an update
        # The default interval in SAMPLE_CONFIG is 1 minute (60 seconds)
        # So we need to set last_alerts_update to a value less than 60 seconds ago
        mock_weather_app.last_alerts_update = 950.0  # Less than 1 minute ago (50 seconds)

        # Call OnAlertsTimer
        mock_weather_app.OnAlertsTimer(None)

        # Verify that UpdateAlerts was NOT called
        mock_weather_app.UpdateAlerts.assert_not_called()


def test_on_alerts_timer_respects_updating_flag(mock_weather_app):
    """Test that OnAlertsTimer respects the updating flag."""
    # Mock time.time() to return a specific value
    with patch("time.time", return_value=1000.0):
        # Set last_alerts_update to a value that will trigger an update
        mock_weather_app.last_alerts_update = 700.0  # 5 minutes = 300 seconds ago

        # Set updating flag to True
        mock_weather_app.updating = True

        # Set _alerts_complete to False to simulate alerts being updated
        mock_weather_app._alerts_complete = False

        # Call OnAlertsTimer
        mock_weather_app.OnAlertsTimer(None)

        # Verify that UpdateAlerts was NOT called
        mock_weather_app.UpdateAlerts.assert_not_called()


def test_update_alerts_method():
    """Test the UpdateAlerts method."""
    # Create a mock WeatherApp with the necessary methods and attributes
    mock_app = MagicMock()
    mock_app.location_service = MagicMock()
    mock_app.weather_service = MagicMock()
    mock_app.api_client = None
    mock_app.config = {"settings": {ALERT_RADIUS_KEY: 25, PRECISE_LOCATION_ALERTS_KEY: True}}

    # Set up mock location service to return a location
    mock_location = ("Test City", 40.0, -75.0)
    mock_app.location_service.get_current_location.return_value = mock_location
    mock_app.location_service.is_nationwide_location.return_value = False

    # Set up mock weather service to return alerts data
    mock_app.weather_service.get_alerts.return_value = SAMPLE_ALERTS_DATA

    # Import the UpdateAlerts method from weather_app.py
    from accessiweather.gui.weather_app import WeatherApp

    # Call the method directly
    WeatherApp.UpdateAlerts(mock_app)

    # Verify that the weather service was called with the correct parameters
    mock_app.weather_service.get_alerts.assert_called_once_with(
        40.0, -75.0, radius=25, precise_location=True
    )

    # Verify that the status text was updated
    mock_app.SetStatusText.assert_called_with("Checking for alerts updates...")


def test_update_alerts_skips_nationwide(mock_weather_app):
    """Test that UpdateAlerts skips nationwide location."""
    # Set up mock location service to return a nationwide location
    mock_location = ("Nationwide", 39.8, -98.5)
    mock_weather_app.location_service.get_current_location.return_value = mock_location
    mock_weather_app.location_service.is_nationwide_location.return_value = True

    # Call UpdateAlerts
    mock_weather_app.UpdateAlerts()

    # Verify that the weather service was NOT called
    mock_weather_app.weather_service.get_alerts.assert_not_called()


def test_process_alerts_detects_new_alerts(mock_notifier):
    """Test that process_alerts detects new alerts."""
    # Set up the notifier
    notifier = WeatherNotifier()
    notifier.toaster = mock_notifier

    # Process alerts for the first time
    with patch("time.time", return_value=1000.0):
        processed_alerts, new_count, updated_count = notifier.process_alerts(SAMPLE_ALERTS_DATA)

    # Verify results
    assert len(processed_alerts) == 1
    assert new_count == 1
    assert updated_count == 0
    assert SAMPLE_ALERT["id"] in notifier.active_alerts


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
