"""Weather notification module for AccessiWeather.

This module provides functionality to process and display weather alerts
with deduplication, persistence, and change detection.
"""

import json
import logging
import os
from datetime import datetime

# For Python 3.10 compatibility
try:
    from datetime import UTC
except ImportError:
    UTC = UTC
from typing import Any

from dateutil.parser import isoparse  # type: ignore # requires python-dateutil

from accessiweather.config_utils import get_config_dir

from .toast_notifier import SafeToastNotifier

logger = logging.getLogger(__name__)


class WeatherNotifier:
    """Class for handling weather notifications"""

    # Alert priority levels
    PRIORITY = {"Extreme": 3, "Severe": 2, "Moderate": 1, "Minor": 0, "Unknown": -1}

    def __init__(self, config_dir: str | None = None, enable_persistence: bool = True):
        """Initialize the weather notifier

        Args:
            config_dir: Directory for storing alert state (optional)
            enable_persistence: Whether to enable persistent storage of alert state (default: True)

        """
        self.toaster = SafeToastNotifier()
        self.active_alerts: dict[str, dict[str, Any]] = {}
        self.enable_persistence = enable_persistence

        # Set up persistent storage path
        if self.enable_persistence:
            self.config_dir: str | None = config_dir or get_config_dir()
            self.alerts_state_file: str | None = os.path.join(self.config_dir, "alert_state.json")
            # Load existing alert state
            self._load_alert_state()
        else:
            self.config_dir = None
            self.alerts_state_file = None

    def notify_alerts(self, alert_count, new_count=0, updated_count=0):
        """Notify the user about new alerts

        Args:
            alert_count: Number of active alerts
            new_count: Number of new alerts (default: 0)
            updated_count: Number of updated alerts (default: 0)

        """
        if alert_count > 0:
            title = "Weather Alerts"

            # Create a more detailed message if we have information about new/updated alerts
            if new_count > 0 or updated_count > 0:
                parts = []
                if new_count > 0:
                    new_plural = "alert" if new_count == 1 else "alerts"
                    parts.append(f"{new_count} new {new_plural}")
                if updated_count > 0:
                    updated_plural = "alert" if updated_count == 1 else "alerts"
                    parts.append(f"{updated_count} updated {updated_plural}")

                if parts:
                    message = f"{', '.join(parts)} in your area"
                else:
                    # Fallback to the original message
                    plural = "alert" if alert_count == 1 else "alerts"
                    message = f"{alert_count} active weather {plural} in your area"
            else:
                # Use the original message format if no new/updated counts provided
                plural = "alert" if alert_count == 1 else "alerts"
                message = f"{alert_count} active weather {plural} in your area"

            # Show notification
            self.toaster.show_toast(
                title=title,
                msg=message,
                timeout=10,
                app_name="AccessiWeather",
            )

            logger.info(f"Displayed summary notification: {message}")

    def show_notification(self, alert: dict[str, Any], is_update: bool = False) -> None:
        """Show a desktop notification for an alert

        Args:
            alert: Dictionary containing alert information
            is_update: Whether this is an update to an existing alert (default: False)

        """
        try:
            # Customize title based on whether this is a new alert or an update
            if is_update:
                title = f"Updated: Weather {alert['event']}"
            else:
                title = f"Weather {alert['event']}"

            message = alert.get("headline", "Weather alert in your area")

            # Show notification
            self.toaster.show_toast(
                title=title,
                # 'msg' parameter is mapped to 'message' in SafeToastNotifier
                msg=message,
                # 'timeout' instead of 'duration'
                timeout=10,
                app_name="AccessiWeather",
            )

            if is_update:
                logger.info(f"Displayed notification for updated alert: {alert['event']}")
            else:
                logger.info(f"Displayed notification for new alert: {alert['event']}")
        except Exception as e:
            logger.error(f"Failed to show notification: {str(e)}")

    def get_sorted_alerts(self) -> list[dict[str, Any]]:
        """Get all active alerts sorted by priority

        Returns:
            List of alerts sorted by priority (highest first)

        """
        alerts = list(self.active_alerts.values())

        # Sort by severity
        return sorted(
            alerts,
            key=lambda x: self.PRIORITY.get(x.get("severity", "Unknown"), self.PRIORITY["Unknown"]),
            reverse=True,
        )

    def process_alerts(self, alerts_data: dict[str, Any]) -> tuple[list[dict[str, Any]], int, int]:
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

        features = alerts_data.get("features", [])
        processed_alerts: list[dict[str, Any]] = []

        # Track new and updated alerts for summary notification
        new_alerts_count = 0
        updated_alerts_count = 0

        # Group alerts by deduplication key to handle multiple offices issuing the same alert
        alert_groups: dict[str, list[dict[str, Any]]] = {}

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
                if self._is_alert_updated(existing_alert, representative_alert):
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
        total_alerts = len(processed_alerts)
        if new_alerts_count > 0 or updated_alerts_count > 0:
            logger.info(
                f"Alert processing complete: {total_alerts} total, {new_alerts_count} new, "
                f"{updated_alerts_count} updated, {total_alerts - new_alerts_count - updated_alerts_count} unchanged"
            )
        else:
            logger.info(f"Alert processing complete: {total_alerts} total alerts, all unchanged")

        # Save alert state to persistent storage if there were any changes
        if new_alerts_count > 0 or updated_alerts_count > 0:
            self._save_alert_state()

        return processed_alerts, new_alerts_count, updated_alerts_count

    def _is_alert_updated(self, old_alert: dict[str, Any], new_alert: dict[str, Any]) -> bool:
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

    def _generate_deduplication_key(self, alert: dict[str, Any]) -> str:
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

    def _choose_representative_alert(self, alerts: list[dict[str, Any]]) -> dict[str, Any]:
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
                sent_time = isoparse(sent_str) if sent_str else datetime.min.replace(tzinfo=UTC)
            except Exception:
                sent_time = datetime.min.replace(tzinfo=UTC)

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

    def clear_expired_alerts(self) -> None:
        """Remove expired alerts from the active alerts list"""
        now = datetime.now(UTC)
        expired_alert_ids = []

        # Iterate over a copy of items to allow modification during iteration
        for alert_id, alert_data in list(self.active_alerts.items()):
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
                    expiration_time = expiration_time.replace(tzinfo=UTC)

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
            if alert_id in self.active_alerts:
                del self.active_alerts[alert_id]

        # Save alert state if any alerts were removed
        if expired_alert_ids:
            self._save_alert_state()

    def _load_alert_state(self) -> None:
        """Load alert state from persistent storage"""
        if not self.enable_persistence or not self.alerts_state_file:
            return

        try:
            if os.path.exists(self.alerts_state_file):
                with open(self.alerts_state_file) as f:
                    data = json.load(f)

                # Validate the loaded data structure
                if isinstance(data, dict) and "active_alerts" in data:
                    loaded_alerts = data["active_alerts"]
                    if isinstance(loaded_alerts, dict):
                        # Filter out expired alerts during load
                        now = datetime.now(UTC)
                        valid_alerts = {}

                        for alert_id, alert_data in loaded_alerts.items():
                            expires_str = alert_data.get("expires")
                            if expires_str:
                                try:
                                    expiration_time = isoparse(expires_str)
                                    if expiration_time.tzinfo is None:
                                        expiration_time = expiration_time.replace(tzinfo=UTC)

                                    # Only keep non-expired alerts
                                    if expiration_time >= now:
                                        valid_alerts[alert_id] = alert_data
                                    else:
                                        logger.debug(
                                            f"Filtered out expired alert during load: {alert_id}"
                                        )
                                except Exception as e:
                                    logger.warning(
                                        f"Error parsing expiration for alert {alert_id}: {e}"
                                    )
                            else:
                                # Keep alerts without expiration (shouldn't happen with NWS data)
                                valid_alerts[alert_id] = alert_data

                        self.active_alerts = valid_alerts
                        logger.info(
                            f"Loaded {len(valid_alerts)} active alerts from persistent storage"
                        )
                    else:
                        logger.warning("Invalid alert state format in storage file")
                else:
                    logger.warning("Invalid alert state file format")
        except Exception as e:
            logger.error(f"Failed to load alert state: {str(e)}")
            # Continue with empty alerts if loading fails
            self.active_alerts = {}

    def _save_alert_state(self) -> None:
        """Save alert state to persistent storage"""
        if not self.enable_persistence or not self.alerts_state_file:
            return

        try:
            # Ensure config directory exists
            if self.config_dir:
                os.makedirs(self.config_dir, exist_ok=True)

            # Prepare data to save
            data = {
                "active_alerts": self.active_alerts,
                "last_updated": datetime.now(UTC).isoformat(),
                "version": "1.0",
            }

            # Write to file
            with open(self.alerts_state_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(self.active_alerts)} active alerts to persistent storage")
        except Exception as e:
            logger.error(f"Failed to save alert state: {str(e)}")
