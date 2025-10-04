"""Visual Crossing alert processing and notification integration for AccessiWeather."""

from __future__ import annotations

import logging
import os
import tempfile

from .alert_manager import AlertManager, AlertSettings
from .alert_notification_system import AlertNotificationSystem
from .models import Location, WeatherAlerts

logger = logging.getLogger(__name__)


async def process_visual_crossing_alerts(alerts: WeatherAlerts, location: Location) -> None:
    """Process Visual Crossing alerts and dispatch notifications."""
    try:
        config_dir = os.path.join(tempfile.gettempdir(), "accessiweather_alerts")

        settings = AlertSettings()
        settings.min_severity_priority = 1
        settings.notifications_enabled = True

        alert_manager = AlertManager(config_dir, settings)
        notification_system = AlertNotificationSystem(alert_manager)

        logger.info(f"Processing Visual Crossing alerts for {location.name}")
        logger.info(f"Number of alerts to process: {len(alerts.alerts)}")

        for i, alert in enumerate(alerts.alerts):
            logger.info(f"Alert {i + 1}: {alert.event} - {alert.severity} - {alert.headline}")

        system_settings = notification_system.get_settings()
        logger.info(
            "Notification settings - enabled: %s, min_severity: %s",
            system_settings.notifications_enabled,
            system_settings.min_severity_priority,
        )

        notifications_sent = await notification_system.process_and_notify(alerts)

        if notifications_sent > 0:
            logger.info(
                "✅ Sent %s Visual Crossing alert notifications for %s",
                notifications_sent,
                location.name,
            )
        else:
            logger.warning("⚠️ No Visual Crossing alert notifications sent for %s", location.name)
            stats = notification_system.get_statistics()
            logger.info("Alert statistics: %s", stats)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to process Visual Crossing alerts for notifications: {exc}")
