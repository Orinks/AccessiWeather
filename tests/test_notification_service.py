"""Tests for the NotificationService class."""
import unittest
from unittest.mock import MagicMock, patch
from accessiweather.notifications import WeatherNotifier
from accessiweather.services.notification_service import NotificationService

class TestNotificationService(unittest.TestCase):
    def setUp(self):
        self.mock_notifier = MagicMock(spec=WeatherNotifier)
        self.mock_notifier.process_alerts.return_value = []
        self.mock_notifier.get_sorted_alerts.return_value = []
        self.notification_service = NotificationService(self.mock_notifier)

    def test_init(self):
        service = NotificationService(self.mock_notifier)
        self.assertEqual(service.notifier, self.mock_notifier)

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
