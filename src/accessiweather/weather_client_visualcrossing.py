"""
Visual Crossing alert processing for AccessiWeather.

Note: Alert notifications are now handled centrally by the main window's
alert_notification_system. This module's process_visual_crossing_alerts
function is kept for backward compatibility but delegates to the central system.
"""

from __future__ import annotations

import logging

from .models import Location, WeatherAlerts

logger = logging.getLogger(__name__)


async def process_visual_crossing_alerts(alerts: WeatherAlerts, location: Location) -> None:
    """
    Process Visual Crossing alerts.

    Note: Alert notifications are now handled centrally by the main window's
    AlertNotificationSystem after weather data is received. This function
    is kept for backward compatibility but no longer creates a separate
    AlertManager instance.

    The central AlertNotificationSystem in main_window.py processes ALL alerts
    (from NWS, Visual Crossing, etc.) through a single AlertManager instance,
    ensuring proper state tracking, rate limiting, and cooldown management.

    Args:
        alerts: Weather alerts from Visual Crossing
        location: The location for the alerts

    """
    if not alerts or not alerts.has_alerts():
        return

    logger.debug(
        "Visual Crossing alerts for %s will be processed by main notification system (%d alerts)",
        location.name,
        len(alerts.alerts),
    )
