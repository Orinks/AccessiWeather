"""Tests for the NotificationService class."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.notifications import WeatherNotifier
from accessiweather.services.notification_service import NotificationService


@pytest.fixture
def mock_notifier():
    """Create a mock notifier."""
    notifier = MagicMock(spec=WeatherNotifier)
    # Default values, tests can override
    notifier.process_alerts.return_value = []
    notifier.get_sorted_alerts.return_value = []
    return notifier


@pytest.fixture
def notification_service(mock_notifier):
    """Create a NotificationService instance with a mock notifier."""
    return NotificationService(mock_notifier)


class TestNotificationService:
    """Test suite for NotificationService."""

    def test_init(self, mock_notifier):
        """Test service initialization."""
        service = NotificationService(mock_notifier)
        assert service.notifier == mock_notifier

    def test_notify_alerts(self, notification_service, mock_notifier):
        """Test notifying about alerts."""
        # Sample alerts
        alerts = [
            {"headline": "Test Alert 1", "severity": "Moderate"},
            {"headline": "Test Alert 2", "severity": "Severe"},
        ]

        # Call the method
        notification_service.notify_alerts(alerts)

        # Verify the method was called with the correct arguments
        mock_notifier.notify_alerts.assert_called_once_with(2)

    def test_notify_alerts_with_count(self, notification_service, mock_notifier):
        """Test notifying about alerts with a specific count."""
        # Sample alerts
        alerts = [
            {"headline": "Test Alert 1", "severity": "Moderate"},
            {"headline": "Test Alert 2", "severity": "Severe"},
            {"headline": "Test Alert 3", "severity": "Extreme"},
        ]

        # Call the method with a specific count
        notification_service.notify_alerts(alerts, count=2)

        # Verify the method was called with the correct arguments
        mock_notifier.notify_alerts.assert_called_once_with(2)

    def test_notify_alerts_empty(self, notification_service, mock_notifier):
        """Test notifying about empty alerts."""
        # Call the method with empty alerts
        notification_service.notify_alerts([])

        # Verify the method was not called
        mock_notifier.notify_alerts.assert_not_called()

    def test_process_alerts(self, notification_service, mock_notifier):
        """Test processing alerts."""
        # Sample alerts data
        alerts_data = {
            "features": [
                {
                    "properties": {
                        "headline": "Test Alert",
                        "severity": "Moderate",
                    }
                }
            ]
        }

        # Set up mock return value
        expected_alerts = [
            {
                "headline": "Test Alert",
                "severity": "Moderate",
            }
        ]
        mock_notifier.process_alerts.return_value = expected_alerts

        # Call the method
        result = notification_service.process_alerts(alerts_data)

        # Verify the result
        assert result == expected_alerts
        mock_notifier.process_alerts.assert_called_once_with(alerts_data)

    def test_get_sorted_alerts(self, notification_service, mock_notifier):
        """Test getting sorted alerts."""
        # Set up mock return value
        expected_alerts = [
            {"headline": "Test Alert 1", "severity": "Extreme"},
            {"headline": "Test Alert 2", "severity": "Severe"},
            {"headline": "Test Alert 3", "severity": "Moderate"},
        ]
        mock_notifier.get_sorted_alerts.return_value = expected_alerts

        # Call the method
        result = notification_service.get_sorted_alerts()

        # Verify the result
        assert result == expected_alerts
        mock_notifier.get_sorted_alerts.assert_called_once()

    def test_clear_expired_alerts(self, notification_service, mock_notifier):
        """Test clearing expired alerts."""
        # Call the method
        notification_service.clear_expired_alerts()

        # Verify the method was called
        mock_notifier.clear_expired_alerts.assert_called_once()
