"""Notification service for AccessiWeather.

This module provides a service layer for notification-related operations,
separating business logic from UI concerns.
"""

import logging
from typing import Dict, List, Optional

from accessiweather.notifications import WeatherNotifier

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for notification-related operations."""

    def __init__(self, notifier: WeatherNotifier):
        """Initialize the notification service.

        Args:
            notifier: The notifier to use for notification operations.
        """
        self.notifier = notifier

    def notify_alerts(self, alerts: List[Dict], count: Optional[int] = None) -> None:
        """Notify the user of weather alerts.

        Args:
            alerts: List of alert objects.
            count: Optional count of alerts to notify about. If None, all alerts are notified.
        """
        if not alerts:
            logger.info("No alerts to notify about")
            return

        if count is None:
            count = len(alerts)

        logger.info(f"Notifying about {count} alerts")
        self.notifier.notify_alerts(count)

    def process_alerts(self, alerts_data: Dict) -> List[Dict]:
        """Process alerts data and notify the user.

        Args:
            alerts_data: Raw alerts data from the API.

        Returns:
            List of processed alert objects.
        """
        return self.notifier.process_alerts(alerts_data)

    def get_sorted_alerts(self) -> List[Dict]:
        """Get a sorted list of active alerts.

        Returns:
            List of alert objects sorted by severity.
        """
        return self.notifier.get_sorted_alerts()

    def clear_expired_alerts(self) -> None:
        """Clear expired alerts."""
        self.notifier.clear_expired_alerts()
