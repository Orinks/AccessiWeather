"""Tests for the NotificationService class."""
import unittest
from unittest.mock import MagicMock
from accessiweather.services.notification_service import NotificationService


class TestNotificationService(unittest.TestCase):
    def setUp(self):
        # Create a mock notifier with all required methods
        self.mock_notifier = MagicMock()
        self.mock_notifier.process_alerts = MagicMock(return_value=[])
        self.mock_notifier.get_sorted_alerts = MagicMock(return_value=[])
        self.mock_notifier.notify_alerts = MagicMock()
        self.mock_notifier.clear_expired_alerts = MagicMock()

        # Create the service with the mock
        self.notification_service = NotificationService(self.mock_notifier)

    def test_init(self):
        """Test service initialization."""
        # Create a mock notifier directly
        mock_notifier = MagicMock()

        # Create the service with the mock
        service = NotificationService(mock_notifier)

        # Verify the notifier was set correctly
        self.assertEqual(service.notifier, mock_notifier)

    def test_notify_alerts(self):
        """Test notifying about alerts."""
        alerts = [
            {"headline": "Test Alert 1", "severity": "Moderate"},
            {"headline": "Test Alert 2", "severity": "Severe"},
        ]
        self.notification_service.notify_alerts(alerts)
        self.mock_notifier.notify_alerts.assert_called_once_with(2)

    def test_notify_alerts_with_count(self):
        """Test notifying about alerts with a specific count."""
        alerts = [
            {"headline": "Test Alert 1", "severity": "Moderate"},
            {"headline": "Test Alert 2", "severity": "Severe"},
            {"headline": "Test Alert 3", "severity": "Extreme"},
        ]
        self.notification_service.notify_alerts(alerts, count=2)
        self.mock_notifier.notify_alerts.assert_called_once_with(2)

    def test_notify_alerts_empty(self):
        """Test notifying about empty alerts."""
        self.notification_service.notify_alerts([])
        self.mock_notifier.notify_alerts.assert_not_called()

    def test_process_alerts(self):
        """Test processing alerts."""
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
        expected_alerts = [
            {
                "headline": "Test Alert",
                "severity": "Moderate",
            }
        ]
        self.mock_notifier.process_alerts.return_value = expected_alerts
        result = self.notification_service.process_alerts(alerts_data)
        self.assertEqual(result, expected_alerts)
        self.mock_notifier.process_alerts.assert_called_once_with(alerts_data)

    def test_get_sorted_alerts(self):
        """Test getting sorted alerts."""
        expected_alerts = [
            {"headline": "Test Alert 1", "severity": "Extreme"},
            {"headline": "Test Alert 2", "severity": "Severe"},
            {"headline": "Test Alert 3", "severity": "Moderate"},
        ]
        self.mock_notifier.get_sorted_alerts.return_value = expected_alerts
        result = self.notification_service.get_sorted_alerts()
        self.assertEqual(result, expected_alerts)
        self.mock_notifier.get_sorted_alerts.assert_called_once()

    def test_clear_expired_alerts(self):
        """Test clearing expired alerts."""
        self.notification_service.clear_expired_alerts()
        self.mock_notifier.clear_expired_alerts.assert_called_once()
