"""Tests for the NotificationService class."""

import pytest
from unittest.mock import MagicMock

from accessiweather.services.notification_service import NotificationService
from accessiweather.notifications import WeatherNotifier

# Sample test data
SAMPLE_ALERTS = [
    {
        "id": "alert1",
        "event": "Test Event 1",
        "headline": "Test Alert 1",
        "description": "Description 1",
        "severity": "Moderate",
        "urgency": "Expected",
        "sent": "2024-01-01T00:00:00Z",
        "effective": "2024-01-01T00:00:00Z",
        "expires": "2024-01-02T00:00:00Z",
        "status": "Actual",
        "messageType": "Alert",
        "category": "Met",
        "response": "Execute"
    },
    {
        "id": "alert2",
        "event": "Test Event 2",
        "headline": "Test Alert 2",
        "description": "Description 2",
        "severity": "Severe",
        "urgency": "Immediate",
        "sent": "2024-01-01T00:00:00Z",
        "effective": "2024-01-01T00:00:00Z",
        "expires": "2024-01-02T00:00:00Z",
        "status": "Actual",
        "messageType": "Alert",
        "category": "Met",
        "response": "Execute"
    }
]

SAMPLE_ALERTS_DATA = {
    "features": [
        {
            "id": "feature1",
            "properties": alert
        } for alert in SAMPLE_ALERTS
    ]
}

# Fixture to create a mocked WeatherNotifier
@pytest.fixture
def mock_notifier():
    notifier = MagicMock(spec=WeatherNotifier)
    # Set default return values
    notifier.process_alerts.return_value = (SAMPLE_ALERTS, 2, 0)  # (processed_alerts, new_count, updated_count)
    notifier.get_sorted_alerts.return_value = sorted(
        SAMPLE_ALERTS,
        key=lambda x: WeatherNotifier.PRIORITY.get(x["severity"], WeatherNotifier.PRIORITY["Unknown"]),
        reverse=True
    )
    return notifier

# Fixture to create a NotificationService instance with the mocked notifier
@pytest.fixture
def notification_service(mock_notifier):
    return NotificationService(mock_notifier)

def test_notify_alerts_with_alerts(notification_service, mock_notifier):
    """Test notifying about alerts when there are alerts."""
    alerts = SAMPLE_ALERTS
    count = len(alerts)

    notification_service.notify_alerts(alerts, count)

    mock_notifier.notify_alerts.assert_called_once_with(count, 0, 0)

def test_notify_alerts_no_alerts(notification_service, mock_notifier):
    """Test notifying about alerts when there are no alerts."""
    alerts = []

    notification_service.notify_alerts(alerts)

    mock_notifier.notify_alerts.assert_not_called()

def test_notify_alerts_with_custom_count(notification_service, mock_notifier):
    """Test notifying about alerts with a custom count."""
    alerts = SAMPLE_ALERTS
    custom_count = 1

    notification_service.notify_alerts(alerts, custom_count)

    mock_notifier.notify_alerts.assert_called_once_with(custom_count, 0, 0)

def test_process_alerts(notification_service, mock_notifier):
    """Test processing alerts data."""
    alerts_data = SAMPLE_ALERTS_DATA

    processed_alerts, new_count, updated_count = notification_service.process_alerts(alerts_data)

    assert processed_alerts == SAMPLE_ALERTS
    assert new_count == 2
    assert updated_count == 0
    mock_notifier.process_alerts.assert_called_once_with(alerts_data)

def test_get_sorted_alerts(notification_service, mock_notifier):
    """Test getting sorted alerts."""
    # The mock notifier is set up to return alerts sorted by severity
    result = notification_service.get_sorted_alerts()

    # First alert should be "Severe", second should be "Moderate"
    assert result[0]["severity"] == "Severe"
    assert result[1]["severity"] == "Moderate"
    mock_notifier.get_sorted_alerts.assert_called_once()

def test_clear_expired_alerts(notification_service, mock_notifier):
    """Test clearing expired alerts."""
    notification_service.clear_expired_alerts()

    mock_notifier.clear_expired_alerts.assert_called_once()