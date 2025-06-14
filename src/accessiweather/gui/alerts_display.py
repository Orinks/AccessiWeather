"""Alerts display utilities for AccessiWeather.

This module provides functions for displaying weather alerts in the UI.
"""

import logging

from .weather_formatting import is_weatherapi_data

logger = logging.getLogger(__name__)


def display_alerts(frame, alerts_data):
    """Display alerts data in the UI and return processed alerts.

    Args:
        frame: The main WeatherApp frame instance
        alerts_data: Dictionary with alerts data

    Returns:
        List[Dict[str, Any]]: Processed alerts data
    """
    logger.debug(f"display_alerts received: {alerts_data}")

    # Clear existing alerts
    frame.alerts_list.DeleteAllItems()

    if not alerts_data:
        frame.alert_btn.Disable()
        return []

    # Check if this is WeatherAPI.com data
    if is_weatherapi_data(alerts_data):
        return display_weatherapi_alerts(frame, alerts_data)

    # Handle NWS API alerts
    features = alerts_data.get("features", [])
    if not features:
        frame.alert_btn.Disable()
        return []

    processed_alerts = []
    for i, feature in enumerate(features):
        properties = feature.get("properties", {})
        
        alert_type = properties.get("event", "Unknown")
        severity = properties.get("severity", "Unknown")
        headline = properties.get("headline", "No headline available")

        # Add to list control
        index = frame.alerts_list.InsertItem(i, alert_type)
        frame.alerts_list.SetItem(index, 1, severity)
        frame.alerts_list.SetItem(index, 2, headline)

        # Store the full alert data for later use
        processed_alerts.append(properties)

    # Enable alert button if there are alerts
    if processed_alerts:
        frame.alert_btn.Enable()
    else:
        frame.alert_btn.Disable()

    return processed_alerts


def display_weatherapi_alerts(frame, alerts_data):
    """Display WeatherAPI.com alerts data in the UI.

    Args:
        frame: The main WeatherApp frame instance
        alerts_data: WeatherAPI.com alerts data

    Returns:
        List[Dict[str, Any]]: Processed alerts data
    """
    alerts = alerts_data.get("alerts", {}).get("alert", [])
    if not alerts:
        frame.alert_btn.Disable()
        return []

    processed_alerts = []
    for i, alert in enumerate(alerts):
        alert_type = alert.get("event", "Unknown")
        severity = alert.get("severity", "Unknown")
        headline = alert.get("headline", "No headline available")

        # Add to list control
        index = frame.alerts_list.InsertItem(i, alert_type)
        frame.alerts_list.SetItem(index, 1, severity)
        frame.alerts_list.SetItem(index, 2, headline)

        # Store the full alert data for later use
        processed_alerts.append(alert)

    # Enable alert button if there are alerts
    if processed_alerts:
        frame.alert_btn.Enable()
    else:
        frame.alert_btn.Disable()

    return processed_alerts


def display_alerts_processed(frame, processed_alerts):
    """Display already processed alerts data in the UI.

    Args:
        frame: The main WeatherApp frame instance
        processed_alerts: List of processed alert dictionaries
    """
    # Clear existing alerts
    frame.alerts_list.DeleteAllItems()

    if not processed_alerts:
        frame.alert_btn.Disable()
        return

    for i, alert in enumerate(processed_alerts):
        alert_type = alert.get("event", "Unknown")
        severity = alert.get("severity", "Unknown")
        headline = alert.get("headline", "No headline available")

        # Add to list control
        index = frame.alerts_list.InsertItem(i, alert_type)
        frame.alerts_list.SetItem(index, 1, severity)
        frame.alerts_list.SetItem(index, 2, headline)

    # Enable alert button if there are alerts
    frame.alert_btn.Enable()


def display_alerts_error(frame, error):
    """Display alerts error in the UI.

    Args:
        frame: The main WeatherApp frame instance
        error: Error message or exception object
    """
    from .weather_source_detection import format_error_message
    
    # Clear alerts list
    frame.alerts_list.DeleteAllItems()

    # Format the error message
    error_msg = format_error_message(error)

    # Add error message to alerts list
    index = frame.alerts_list.InsertItem(0, "Error")
    frame.alerts_list.SetItem(index, 1, "")  # Empty severity
    frame.alerts_list.SetItem(index, 2, f"Error fetching alerts: {error_msg}")

    # Disable the alert button since there are no valid alerts
    if hasattr(frame, "alert_btn"):
        frame.alert_btn.Disable()
