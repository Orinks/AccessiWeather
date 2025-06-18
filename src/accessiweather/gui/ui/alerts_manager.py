"""Alerts Manager for AccessiWeather UI.

This module provides classes for managing the display of weather alerts
in the user interface.
"""

import logging
from typing import Any, Dict, List, Optional

from .ui_utils import is_weatherapi_data

logger = logging.getLogger(__name__)


class AlertsDisplayManager:
    """Manages the display of weather alerts in UI components."""

    def __init__(self, frame):
        """Initialize the alerts display manager.

        Args:
            frame: The main WeatherApp frame instance.
        """
        self.frame = frame

    def display_alerts(self, alerts_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Display alerts data in the UI and return processed alerts.

        Args:
            alerts_data: Dictionary with alerts data

        Returns:
            List of alert properties dictionaries.
        """
        # Clear current alerts display
        alerts_list_ctrl = self.frame.alerts_list
        alerts_list_ctrl.DeleteAllItems()
        processed_alerts: List[Dict[str, Any]] = []  # List to store alert properties

        # Check if this is WeatherAPI.com data
        if alerts_data and is_weatherapi_data(alerts_data):
            try:
                return self._display_weatherapi_alerts(alerts_data)
            except Exception as e:
                logger.exception("Error displaying WeatherAPI.com alerts")
                # Add error message to alerts list
                index = alerts_list_ctrl.InsertItem(0, "Error")
                alerts_list_ctrl.SetItem(index, 1, "")  # Empty severity
                alerts_list_ctrl.SetItem(index, 2, f"Error displaying alerts: {str(e)}")
                return []

        # Handle NWS API alerts
        if not alerts_data or "features" not in alerts_data:
            # Check if this is an Open-Meteo location (no alerts available)
            generator = alerts_data.get("generator", "") if alerts_data else ""
            if "Open-Meteo" in generator:
                # Show informative message for Open-Meteo locations
                index = alerts_list_ctrl.InsertItem(0, "No Alerts Available")
                alerts_list_ctrl.SetItem(index, 1, "Info")
                alerts_list_ctrl.SetItem(
                    index, 2, "Weather alerts are not available for international locations"
                )

            # Disable the alert button if there are no alerts
            if hasattr(self.frame, "alert_btn"):
                self.frame.alert_btn.Disable()
            return processed_alerts  # Return empty list

        features = alerts_data.get("features", [])
        for feature in features:
            props = feature.get("properties", {})
            event = props.get("event", "Unknown")
            severity = props.get("severity", "Unknown")
            headline = props.get("headline", "No headline")  # Shortened

            index = alerts_list_ctrl.InsertItem(alerts_list_ctrl.GetItemCount(), event)
            alerts_list_ctrl.SetItem(index, 1, severity)
            alerts_list_ctrl.SetItem(index, 2, headline)
            processed_alerts.append(props)  # Save alert data

        # Enable the alert button if there are alerts
        if features and hasattr(self.frame, "alert_btn"):
            self.frame.alert_btn.Enable()
            # Set accessibility properties to ensure it's in the tab order
            self.frame.alert_btn.SetHelpText("View details for the selected alert")
            self.frame.alert_btn.SetToolTip("View details for the selected alert")

        return processed_alerts

    def _display_weatherapi_alerts(self, alerts_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Display WeatherAPI.com alerts data in the UI.

        Args:
            alerts_data: Dictionary with WeatherAPI.com alerts data

        Returns:
            List of processed alert dictionaries
        """
        alerts_list_ctrl = self.frame.alerts_list
        processed_alerts: List[Dict[str, Any]] = []

        # Get alerts from the data
        alerts = alerts_data.get("alerts", [])
        if not alerts:
            # Disable the alert button if there are no alerts
            if hasattr(self.frame, "alert_btn"):
                self.frame.alert_btn.Disable()
            return processed_alerts

        # Process each alert
        for alert in alerts:
            event = alert.get("event", "Unknown")
            severity = alert.get("severity", "Unknown")
            headline = alert.get("headline", "No headline")

            index = alerts_list_ctrl.InsertItem(alerts_list_ctrl.GetItemCount(), event)
            alerts_list_ctrl.SetItem(index, 1, severity)
            alerts_list_ctrl.SetItem(index, 2, headline)
            processed_alerts.append(alert)  # Save alert data

        # Enable the alert button if there are alerts
        if alerts and hasattr(self.frame, "alert_btn"):
            self.frame.alert_btn.Enable()
            # Set accessibility properties to ensure it's in the tab order
            self.frame.alert_btn.SetHelpText("View details for the selected alert")
            self.frame.alert_btn.SetToolTip("View details for the selected alert")

        return processed_alerts

    def display_alerts_processed(self, processed_alerts: List[Dict[str, Any]]) -> None:
        """Display already processed alerts data in the UI.

        Args:
            processed_alerts: List of processed alert dictionaries
        """
        # Clear current alerts display
        alerts_list_ctrl = self.frame.alerts_list
        alerts_list_ctrl.DeleteAllItems()

        if not processed_alerts:
            # Disable the alert button if there are no alerts
            if hasattr(self.frame, "alert_btn"):
                self.frame.alert_btn.Disable()
            return

        for props in processed_alerts:
            event = props.get("event", "Unknown")
            severity = props.get("severity", "Unknown")
            headline = props.get("headline", "No headline")

            index = alerts_list_ctrl.InsertItem(alerts_list_ctrl.GetItemCount(), event)
            alerts_list_ctrl.SetItem(index, 1, severity)
            alerts_list_ctrl.SetItem(index, 2, headline)

        # Enable the alert button if there are alerts
        if hasattr(self.frame, "alert_btn"):
            self.frame.alert_btn.Enable()
            # Set accessibility properties to ensure it's in the tab order
            self.frame.alert_btn.SetHelpText("View details for the selected alert")
            self.frame.alert_btn.SetToolTip("View details for the selected alert")
