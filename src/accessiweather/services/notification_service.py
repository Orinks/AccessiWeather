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

    def notify_alerts(self, alerts: List[Dict], count: Optional[int] = None,
                      new_count: int = 0, updated_count: int = 0) -> None:
        """Notify the user of weather alerts.

        Args:
            alerts: List of alert objects.
            count: Optional count of alerts to notify about. If None, all alerts are notified.
            new_count: Number of new alerts (default: 0)
            updated_count: Number of updated alerts (default: 0)
        """
        if not alerts:
            logger.info("No alerts to notify about")
            return

        if count is None:
            count = len(alerts)

        logger.info(f"Notifying about {count} alerts (new: {new_count}, updated: {updated_count})")
        self.notifier.notify_alerts(count, new_count, updated_count)

    def process_alerts(self, alerts_data: Dict) -> List[Dict]:
        """Process alerts data and notify the user.

        Args:
            alerts_data: Raw alerts data from the API.

        Returns:
            List of processed alert objects.
        """
        processed_alerts, new_count, updated_count = self.notifier.process_alerts(alerts_data)

        # If there are new or updated alerts, notify the user
        if new_count > 0 or updated_count > 0:
            self.notify_alerts(processed_alerts, len(processed_alerts), new_count, updated_count)

        return processed_alerts

    def get_sorted_alerts(self) -> List[Dict]:
        """Get a sorted list of active alerts.

        Returns:
            List of alert objects sorted by severity.
        """
        return self.notifier.get_sorted_alerts()

    def clear_expired_alerts(self) -> None:
        """Clear expired alerts."""
        self.notifier.clear_expired_alerts()
