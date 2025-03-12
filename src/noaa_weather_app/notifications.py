"""Notification module for NOAA weather alerts, watches, and warnings.

This module provides functionality to display desktop notifications
for weather alerts.
"""

import logging
from typing import Dict, Any, List
from win10toast import ToastNotifier

logger = logging.getLogger(__name__)

class WeatherNotifier:
    """Class for handling weather notifications"""
    
    # Alert priority levels
    PRIORITY = {
        "Extreme": 3,
        "Severe": 2,
        "Moderate": 1,
        "Minor": 0,
        "Unknown": -1
    }
    
    def __init__(self):
        """Initialize the weather notifier"""
        self.toaster = ToastNotifier()
        self.active_alerts = {}
    
    def process_alerts(self, alerts_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process alerts data from NOAA API
        
        Args:
            alerts_data: Dictionary containing alerts data from NOAA API
            
        Returns:
            List of processed alerts
        """
        features = alerts_data.get("features", [])
        processed_alerts = []
        
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
                "response": properties.get("response")
            }
            
            processed_alerts.append(alert)
            
            # Update our active alerts dictionary
            alert_id = alert["id"]
            if alert_id and alert_id not in self.active_alerts:
                self.active_alerts[alert_id] = alert
                self.show_notification(alert)
                
        return processed_alerts
    
    def show_notification(self, alert: Dict[str, Any]) -> None:
        """Show a desktop notification for an alert
        
        Args:
            alert: Dictionary containing alert information
        """
        try:
            title = f"Weather {alert['event']}"
            message = alert.get('headline', 'Weather alert in your area')
            
            # Show notification
            self.toaster.show_toast(
                title=title,
                msg=message,
                icon_path=None,  # Could use a weather icon here
                duration=10,
                threaded=True  # Run in background thread
            )
            
            logger.info(f"Displayed notification for {alert['event']}")
        except Exception as e:
            logger.error(f"Failed to show notification: {str(e)}")
    
    def clear_expired_alerts(self) -> None:
        """Remove expired alerts from the active alerts list"""
        # In a real implementation, this would check timestamps
        # For now, we'll just keep it simple
        self.active_alerts = {}
        
    def get_sorted_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts sorted by priority
        
        Returns:
            List of alerts sorted by priority (highest first)
        """
        alerts = list(self.active_alerts.values())
        
        # Sort by severity
        return sorted(
            alerts,
            key=lambda x: self.PRIORITY.get(x.get("severity"), self.PRIORITY["Unknown"]),
            reverse=True
        )
