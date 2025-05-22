"""Notification module for NOAA weather alerts, watches, and warnings.

This module provides functionality to display desktop notifications
for weather alerts.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone  # Added
from typing import Any, Dict, List, Optional

from dateutil.parser import isoparse  # type: ignore # requires python-dateutil

# Type checking will report this as missing, but it's a runtime dependency
from plyer import notification  # type: ignore

from accessiweather.config_utils import get_config_dir

logger = logging.getLogger(__name__)


# Create a wrapper for notifications to handle potential errors in test
# environment
class SafeToastNotifier:
    """
    A wrapper around the notification system that handles exceptions.
    Provides cross-platform notification support using plyer.
    """

    def __init__(self):
        """Initialize the safe toast notifier"""
        # No initialization needed for plyer
        pass

    def show_toast(self, **kwargs):
        """Show a toast notification"""
        try:
            # If we're running tests, just log the notification
            if "pytest" in sys.modules:
                # For tests, just log the notification and return success
                title = kwargs.get("title", "")
                msg = kwargs.get("msg", "")
                logger.info(f"Toast notification: {title} - {msg}")
                return True

            # Map win10toast parameters to plyer parameters
            title = kwargs.get("title", "Notification")
            message = kwargs.get("msg", "")
            app_name = "AccessiWeather"
            timeout = kwargs.get("duration", 10)

            # Use plyer's cross-platform notification
            notification.notify(title=title, message=message, app_name=app_name, timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f"Failed to show toast notification: {str(e)}")
            logger.info(
                f"Toast notification would show: {kwargs.get('title')} - " f"{kwargs.get('msg')}"
            )
            return False


class WeatherNotifier:
    """Class for handling weather notifications"""

    # Alert priority levels
    PRIORITY = {"Extreme": 3, "Severe": 2, "Moderate": 1, "Minor": 0, "Unknown": -1}

    def __init__(self, config_dir: Optional[str] = None, enable_persistence: bool = True):
        """Initialize the weather notifier

        Args:
            config_dir: Directory for storing alert state (optional)
            enable_persistence: Whether to enable persistent storage of alert state (default: True)
        """
        self.toaster = SafeToastNotifier()
        self.active_alerts: Dict[str, Dict[str, Any]] = {}
        self.enable_persistence = enable_persistence

        # Set up persistent storage path
        if self.enable_persistence:
            self.config_dir: Optional[str] = config_dir or get_config_dir()
            self.alerts_state_file: Optional[str] = os.path.join(self.config_dir, "alert_state.json")
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

    def process_alerts(self, alerts_data: Dict[str, Any]) -> tuple[List[Dict[str, Any]], int, int]:
        """Process alerts data from NOAA API with change detection

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
        processed_alerts = []

        # Track new and updated alerts for summary notification
        new_alerts_count = 0
        updated_alerts_count = 0

        for feature in features:
            properties = feature.get("properties", {})

            alert = {
                "id": properties.get("id"),
                "event": properties.get("event"),
                "headline": properties.get("headline"),
                "description": properties.get("description"),
                "severity": properties.get("severity"),
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
            }

            processed_alerts.append(alert)

            # Update our active alerts dictionary
            alert_id = alert["id"]

            if alert_id:
                # Check if this is a new alert or an update to an existing alert
                if alert_id not in self.active_alerts:
                    # New alert
                    self.active_alerts[alert_id] = alert
                    self.show_notification(alert, is_update=False)
                    new_alerts_count += 1
                    logger.info(f"New alert detected: {alert['event']}")
                else:
                    # Existing alert - check if it's been updated
                    existing_alert = self.active_alerts[alert_id]
                    if self._is_alert_updated(existing_alert, alert):
                        # Alert has been updated
                        self.active_alerts[alert_id] = alert
                        self.show_notification(alert, is_update=True)
                        updated_alerts_count += 1
                        logger.info(f"Updated alert detected: {alert['event']}")
                    else:
                        # Alert exists but hasn't changed
                        logger.debug(f"Existing alert unchanged: {alert['event']}")

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

    def _is_alert_updated(self, old_alert: Dict[str, Any], new_alert: Dict[str, Any]) -> bool:
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

    def show_notification(self, alert: Dict[str, Any], is_update: bool = False) -> None:
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

    def clear_expired_alerts(self) -> None:
        """Remove expired alerts from the active alerts list"""
        now = datetime.now(timezone.utc)
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
            if alert_id in self.active_alerts:
                del self.active_alerts[alert_id]

        # Save alert state if any alerts were removed
        if expired_alert_ids:
            self._save_alert_state()

    def get_sorted_alerts(self) -> List[Dict[str, Any]]:
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

    def _load_alert_state(self) -> None:
        """Load alert state from persistent storage"""
        if not self.enable_persistence or not self.alerts_state_file:
            return

        try:
            if os.path.exists(self.alerts_state_file):
                with open(self.alerts_state_file, "r") as f:
                    data = json.load(f)

                # Validate the loaded data structure
                if isinstance(data, dict) and "active_alerts" in data:
                    loaded_alerts = data["active_alerts"]
                    if isinstance(loaded_alerts, dict):
                        # Filter out expired alerts during load
                        now = datetime.now(timezone.utc)
                        valid_alerts = {}

                        for alert_id, alert_data in loaded_alerts.items():
                            expires_str = alert_data.get("expires")
                            if expires_str:
                                try:
                                    expiration_time = isoparse(expires_str)
                                    if expiration_time.tzinfo is None:
                                        expiration_time = expiration_time.replace(
                                            tzinfo=timezone.utc
                                        )

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
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "version": "1.0",
            }

            # Write to file
            with open(self.alerts_state_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(self.active_alerts)} active alerts to persistent storage")
        except Exception as e:
            logger.error(f"Failed to save alert state: {str(e)}")
