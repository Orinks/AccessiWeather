"""Alert persistence module for weather notifications.

This module provides functionality to save and load weather alert state
to/from persistent storage.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dateutil.parser import isoparse  # type: ignore # requires python-dateutil

from accessiweather.config_utils import get_config_dir

logger = logging.getLogger(__name__)


class AlertPersistenceManager:
    """Manager for persistent storage of weather alert state."""

    def __init__(self, config_dir: Optional[str] = None, enable_persistence: bool = True):
        """Initialize the alert persistence manager.

        Args:
            config_dir: Directory for storing alert state (optional)
            enable_persistence: Whether to enable persistent storage of alert state (default: True)
        """
        self.enable_persistence = enable_persistence

        # Set up persistent storage path
        if self.enable_persistence:
            self.config_dir: Optional[str] = config_dir or get_config_dir()
            self.alerts_state_file: Optional[str] = os.path.join(
                self.config_dir, "alert_state.json"
            )
        else:
            self.config_dir = None
            self.alerts_state_file = None

    def load_alert_state(self) -> Dict[str, Dict[str, Any]]:
        """Load alert state from persistent storage.

        Returns:
            Dictionary of active alerts loaded from storage, or empty dict if none found
        """
        if not self.enable_persistence or not self.alerts_state_file:
            return {}

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

                        logger.info(
                            f"Loaded {len(valid_alerts)} active alerts from persistent storage"
                        )
                        return valid_alerts
                    else:
                        logger.warning("Invalid alert state format in storage file")
                else:
                    logger.warning("Invalid alert state file format")
        except Exception as e:
            logger.error(f"Failed to load alert state: {str(e)}")

        # Return empty dict if loading fails
        return {}

    def save_alert_state(self, active_alerts: Dict[str, Dict[str, Any]]) -> None:
        """Save alert state to persistent storage.

        Args:
            active_alerts: Dictionary of active alerts to save
        """
        if not self.enable_persistence or not self.alerts_state_file:
            return

        try:
            # Ensure config directory exists
            if self.config_dir:
                os.makedirs(self.config_dir, exist_ok=True)

            # Prepare data to save
            data = {
                "active_alerts": active_alerts,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "version": "1.0",
            }

            # Write to file
            with open(self.alerts_state_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(active_alerts)} active alerts to persistent storage")
        except Exception as e:
            logger.error(f"Failed to save alert state: {str(e)}")

    def get_config_dir(self) -> Optional[str]:
        """Get the configuration directory path.

        Returns:
            Configuration directory path, or None if persistence is disabled
        """
        return self.config_dir

    def get_alerts_state_file(self) -> Optional[str]:
        """Get the alerts state file path.

        Returns:
            Alerts state file path, or None if persistence is disabled
        """
        return self.alerts_state_file

    def is_persistence_enabled(self) -> bool:
        """Check if persistence is enabled.

        Returns:
            True if persistence is enabled, False otherwise
        """
        return self.enable_persistence
