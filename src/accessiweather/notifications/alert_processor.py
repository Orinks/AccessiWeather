"""Alert processing module for weather notifications.

This module provides functionality to process, deduplicate, and compare
weather alerts from NOAA API data.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from dateutil.parser import isoparse  # type: ignore # requires python-dateutil

logger = logging.getLogger(__name__)


class AlertProcessor:
    """Processor for weather alert data with deduplication and change detection."""

    # Alert priority levels
    PRIORITY = {"Extreme": 3, "Severe": 2, "Moderate": 1, "Minor": 0, "Unknown": -1}

    def __init__(self):
        """Initialize the alert processor."""
        pass

    def process_alerts_data(self, alerts_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process raw alerts data from NOAA API into structured format.

        Args:
            alerts_data: Dictionary containing alerts data from NOAA API

        Returns:
            List of processed alerts with deduplication applied
        """
        features = alerts_data.get("features", [])
        processed_alerts: List[Dict[str, Any]] = []

        # Group alerts by deduplication key to handle multiple offices issuing the same alert
        alert_groups: Dict[str, List[Dict[str, Any]]] = {}

        # First pass: group alerts by deduplication key
        for feature in features:
            properties = feature.get("properties", {})

            alert = {
                "id": properties.get("id"),
                "event": properties.get("event", "Unknown Event"),
                "headline": properties.get("headline"),
                "description": properties.get("description", "No description available"),
                "severity": properties.get("severity", "Unknown"),
                "urgency": properties.get("urgency"),
                "sent": properties.get("sent"),
                "effective": properties.get("effective"),
                "expires": properties.get("expires"),
                "status": properties.get("status"),
                "messageType": properties.get("messageType"),
                "category": properties.get("category"),
                "response": properties.get("response"),
                "parameters": properties.get(
                    "parameters", {}
                ),  # Add parameters field for NWSheadline
                "instruction": properties.get("instruction", ""),  # Add instruction field
                "areaDesc": properties.get(
                    "areaDesc", ""
                ),  # Add area description for deduplication
            }

            # Generate deduplication key
            dedup_key = self._generate_deduplication_key(alert)

            # Group alerts by deduplication key
            if dedup_key not in alert_groups:
                alert_groups[dedup_key] = []
            alert_groups[dedup_key].append(alert)

        # Second pass: process deduplicated alerts
        for dedup_key, alerts_in_group in alert_groups.items():
            # Choose the "best" alert from the group (highest severity, most recent)
            representative_alert = self._choose_representative_alert(alerts_in_group)
            processed_alerts.append(representative_alert)

            logger.debug(
                f"Processed weather event: {representative_alert['event']} (deduplicated from {len(alerts_in_group)} alerts)"
            )

        return processed_alerts

    def is_alert_updated(self, old_alert: Dict[str, Any], new_alert: Dict[str, Any]) -> bool:
        """Check if an alert has been updated by comparing key fields

        Args:
            old_alert: The existing alert in our active alerts dictionary
            new_alert: The newly received alert with the same ID

        Returns:
            True if the alert has been meaningfully updated, False otherwise
        """
        # Fields to check for changes (these would indicate a meaningful update)
        key_fields = ["headline", "description", "instruction", "severity", "urgency", "expires"]

        for field in key_fields:
            if old_alert.get(field) != new_alert.get(field):
                logger.debug(f"Alert updated: Field '{field}' changed")
                return True

        return False

    def _generate_deduplication_key(self, alert: Dict[str, Any]) -> str:
        """Generate a deduplication key for an alert to identify duplicate alerts from different offices

        Args:
            alert: Alert dictionary

        Returns:
            String key that uniquely identifies the weather event (not the specific alert)
        """
        # Use event type, effective time, expires time, and a simplified area description
        # to create a key that identifies the same weather phenomenon
        event = (alert.get("event") or "").strip()
        effective = (alert.get("effective") or "").strip()
        expires = (alert.get("expires") or "").strip()

        # Simplify area description by removing office-specific details
        area_desc = (alert.get("areaDesc") or "").strip()
        # Remove common office identifiers and normalize
        area_simplified = (
            area_desc.replace(" County", "").replace(" Parish", "").replace(" Borough", "")
        )

        # Create a normalized key
        key_parts = [event, effective, expires, area_simplified]
        dedup_key = "|".join(part for part in key_parts if part)

        logger.debug(
            f"Generated deduplication key for alert {alert.get('id', 'unknown')}: {dedup_key}"
        )
        return dedup_key

    def _choose_representative_alert(self, alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Choose the best representative alert from a group of duplicate alerts

        Args:
            alerts: List of alerts that represent the same weather event

        Returns:
            The alert that should be used as the representative for the group
        """
        if len(alerts) == 1:
            return alerts[0]

        # Sort by priority: severity first, then by sent time (most recent)
        def alert_priority(alert):
            severity = alert.get("severity", "Unknown")
            severity_score = self.PRIORITY.get(severity, self.PRIORITY["Unknown"])

            # Parse sent time for secondary sorting
            sent_str = alert.get("sent", "")
            try:
                sent_time = (
                    isoparse(sent_str) if sent_str else datetime.min.replace(tzinfo=timezone.utc)
                )
            except Exception:
                sent_time = datetime.min.replace(tzinfo=timezone.utc)

            # Return tuple for sorting: (severity_score, sent_time)
            # Higher severity score and more recent time are preferred
            return (severity_score, sent_time)

        # Sort alerts by priority (highest severity and most recent first)
        sorted_alerts = sorted(alerts, key=alert_priority, reverse=True)
        representative = sorted_alerts[0]

        logger.debug(
            f"Chose representative alert {representative.get('id', 'unknown')} from {len(alerts)} duplicates"
        )
        return representative

    def clear_expired_alerts(self, active_alerts: Dict[str, Dict[str, Any]]) -> List[str]:
        """Remove expired alerts from the active alerts list

        Args:
            active_alerts: Dictionary of active alerts to check for expiration

        Returns:
            List of expired alert IDs that were removed
        """
        now = datetime.now(timezone.utc)
        expired_alert_ids = []

        # Iterate over a copy of items to allow modification during iteration
        for alert_id, alert_data in list(active_alerts.items()):
            expires_str = alert_data.get("expires")
            if not expires_str:
                logger.warning(f"Alert {alert_id} has no 'expires' timestamp. Skipping.")
                continue

            try:
                # Parse the ISO 8601 timestamp string
                expiration_time = isoparse(expires_str)

                # Ensure the parsed time is timezone-aware for comparison
                if expiration_time.tzinfo is None:
                    # This case should ideally not happen with NOAA data,
                    # but handle it defensively. Assuming UTC if naive.
                    logger.warning(
                        f"Alert {alert_id} expiration time '{expires_str}' "
                        f"is timezone-naive. Assuming UTC."
                    )
                    # Ensure the time is timezone-aware before comparison
                    expiration_time = expiration_time.replace(tzinfo=timezone.utc)

                # Compare with current time
                if expiration_time < now:
                    expired_alert_ids.append(alert_id)
                    logger.info(f"Alert {alert_id} expired at {expires_str}. Removing.")

            except ValueError as e:
                logger.warning(
                    f"Could not parse 'expires' timestamp '{expires_str}' "
                    f"for alert {alert_id}: {e}. Skipping."
                )
            except Exception as e:  # Catch other potential parsing errors
                logger.error(
                    f"Unexpected error parsing 'expires' timestamp "
                    f"'{expires_str}' for alert {alert_id}: {e}. Skipping."
                )

        # Remove expired alerts
        for alert_id in expired_alert_ids:
            if alert_id in active_alerts:
                del active_alerts[alert_id]

        return expired_alert_ids

    def get_sorted_alerts(self, active_alerts: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get all active alerts sorted by priority

        Args:
            active_alerts: Dictionary of active alerts

        Returns:
            List of alerts sorted by priority (highest first)
        """
        alerts = list(active_alerts.values())

        # Sort by severity
        return sorted(
            alerts,
            key=lambda x: self.PRIORITY.get(x.get("severity", "Unknown"), self.PRIORITY["Unknown"]),
            reverse=True,
        )
