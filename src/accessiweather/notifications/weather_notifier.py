"""Main weather notifier class that combines all notification functionality.

This module provides the main WeatherNotifier class that orchestrates
alert processing, display, and persistence.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from .alert_persistence import AlertPersistenceManager
from .alert_processor import AlertProcessor
from .notification_display import NotificationDisplayManager

logger = logging.getLogger(__name__)


class WeatherNotifier:
    """Class for handling weather notifications with processing, display, and persistence."""

    def __init__(self, config_dir: Optional[str] = None, enable_persistence: bool = True):
        """Initialize the weather notifier

        Args:
            config_dir: Directory for storing alert state (optional)
            enable_persistence: Whether to enable persistent storage of alert state (default: True)
        """
        # Initialize components
        self.display_manager = NotificationDisplayManager()
        self.processor = AlertProcessor()
        self.persistence_manager = AlertPersistenceManager(config_dir, enable_persistence)

        # Active alerts storage
        self.active_alerts: Dict[str, Dict[str, Any]] = {}

        # Load existing alert state if persistence is enabled
        if enable_persistence:
            self.active_alerts = self.persistence_manager.load_alert_state()

        # Expose toaster for backward compatibility
        self.toaster = self.display_manager.toaster

    def notify_alerts(self, alert_count, new_count=0, updated_count=0):
        """Notify the user about new alerts

        Args:
            alert_count: Number of active alerts
            new_count: Number of new alerts (default: 0)
            updated_count: Number of updated alerts (default: 0)
        """
        self.display_manager.notify_alerts(alert_count, new_count, updated_count)

    def process_alerts(self, alerts_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int, int]:
        """Process alerts data from NOAA API with change detection and deduplication

        Args:
            alerts_data: Dictionary containing alerts data from NOAA API

        Returns:
            Tuple containing:
            - List of processed alerts
            - Number of new alerts
            - Number of updated alerts
        """
        # Clear expired alerts before processing new ones
        self.clear_expired_alerts()

        # Process the raw alerts data
        processed_alerts = self.processor.process_alerts_data(alerts_data)

        # Track new and updated alerts for summary notification
        new_alerts_count = 0
        updated_alerts_count = 0

        # Group alerts by deduplication key to handle multiple offices issuing the same alert
        alert_groups: Dict[str, List[Dict[str, Any]]] = {}

        # Group processed alerts by deduplication key
        for alert in processed_alerts:
            dedup_key = self.processor._generate_deduplication_key(alert)
            if dedup_key not in alert_groups:
                alert_groups[dedup_key] = []
            alert_groups[dedup_key].append(alert)

        # Process each group and track changes
        final_processed_alerts = []
        for dedup_key, alerts_in_group in alert_groups.items():
            # Choose the representative alert
            representative_alert = self.processor._choose_representative_alert(alerts_in_group)
            final_processed_alerts.append(representative_alert)

            # Use deduplication key as the tracking ID instead of the original alert ID
            tracking_id = f"dedup:{dedup_key}"

            # Check if this is a new alert or an update to an existing alert
            if tracking_id not in self.active_alerts:
                # New alert (or new weather event)
                self.active_alerts[tracking_id] = representative_alert
                self.show_notification(representative_alert, is_update=False)
                new_alerts_count += 1
                logger.info(
                    f"New weather event detected: {representative_alert['event']} (deduplicated from {len(alerts_in_group)} alerts)"
                )
            else:
                # Existing alert - check if it's been updated
                existing_alert = self.active_alerts[tracking_id]
                if self.processor.is_alert_updated(existing_alert, representative_alert):
                    # Alert has been updated
                    self.active_alerts[tracking_id] = representative_alert
                    self.show_notification(representative_alert, is_update=True)
                    updated_alerts_count += 1
                    logger.info(
                        f"Updated weather event detected: {representative_alert['event']} (deduplicated from {len(alerts_in_group)} alerts)"
                    )
                else:
                    # Alert exists but hasn't changed
                    logger.debug(
                        f"Existing weather event unchanged: {representative_alert['event']} (deduplicated from {len(alerts_in_group)} alerts)"
                    )

        # Log summary of changes
        total_alerts = len(final_processed_alerts)
        if new_alerts_count > 0 or updated_alerts_count > 0:
            logger.info(
                f"Alert processing complete: {total_alerts} total, {new_alerts_count} new, "
                f"{updated_alerts_count} updated, {total_alerts - new_alerts_count - updated_alerts_count} unchanged"
            )
        else:
            logger.info(f"Alert processing complete: {total_alerts} total alerts, all unchanged")

        # Save alert state to persistent storage if there were any changes
        if new_alerts_count > 0 or updated_alerts_count > 0:
            self.persistence_manager.save_alert_state(self.active_alerts)

        return final_processed_alerts, new_alerts_count, updated_alerts_count

    def show_notification(self, alert: Dict[str, Any], is_update: bool = False) -> None:
        """Show a desktop notification for an alert

        Args:
            alert: Dictionary containing alert information
            is_update: Whether this is an update to an existing alert (default: False)
        """
        self.display_manager.show_notification(alert, is_update)

    def clear_expired_alerts(self) -> None:
        """Remove expired alerts from the active alerts list"""
        expired_alert_ids = self.processor.clear_expired_alerts(self.active_alerts)

        # Save alert state if any alerts were removed
        if expired_alert_ids:
            self.persistence_manager.save_alert_state(self.active_alerts)

    def get_sorted_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts sorted by priority

        Returns:
            List of alerts sorted by priority (highest first)
        """
        return self.processor.get_sorted_alerts(self.active_alerts)

    # Expose internal methods for backward compatibility
    def _is_alert_updated(self, old_alert: Dict[str, Any], new_alert: Dict[str, Any]) -> bool:
        """Check if an alert has been updated (backward compatibility method)"""
        return self.processor.is_alert_updated(old_alert, new_alert)

    def _load_alert_state(self) -> None:
        """Load alert state from persistent storage (backward compatibility method)"""
        self.active_alerts = self.persistence_manager.load_alert_state()

    def _save_alert_state(self) -> None:
        """Save alert state to persistent storage (backward compatibility method)"""
        self.persistence_manager.save_alert_state(self.active_alerts)

    # Expose PRIORITY constant for backward compatibility
    @property
    def PRIORITY(self):
        """Alert priority levels (backward compatibility property)"""
        return self.processor.PRIORITY
