#!/usr/bin/env python3
"""Test Visual Crossing notification manually."""

import asyncio
import logging
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import tempfile
from datetime import datetime

from accessiweather.alert_manager import AlertManager, AlertSettings
from accessiweather.alert_notification_system import AlertNotificationSystem
from accessiweather.models import WeatherAlert, WeatherAlerts

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_visual_crossing_notification():
    """Test Visual Crossing notification manually."""
    print("Testing Visual Crossing Alert Notification")
    print("=" * 50)

    # Create a test Visual Crossing alert
    test_alert = WeatherAlert(
        id="test-vc-alert-001",
        title="Test Visual Crossing Alert",
        description="This is a test alert from Visual Crossing to verify notifications work.",
        severity="Moderate",
        urgency="Expected",
        certainty="Likely",
        event="Weather Advisory",
        headline="Test Weather Advisory - Visual Crossing Alert System",
        instruction="This is a test. No action required.",
        areas=["London", "Greater London"],
        onset=datetime.now(),
        expires=datetime.now().replace(hour=23, minute=59),  # Expires at end of day
    )

    # Create WeatherAlerts object
    alerts = WeatherAlerts(alerts=[test_alert])

    print(f"Created test alert: {test_alert.event} - {test_alert.severity}")
    print(f"Headline: {test_alert.headline}")

    try:
        # Create config directory for alert state
        config_dir = os.path.join(tempfile.gettempdir(), "accessiweather_alerts_test")

        # Create settings that will allow all alerts through
        settings = AlertSettings()
        settings.min_severity_priority = 1  # Allow all severities
        settings.notifications_enabled = True

        print(
            f"Alert settings: enabled={settings.notifications_enabled}, min_severity={settings.min_severity_priority}"
        )

        # Create alert manager and notification system
        alert_manager = AlertManager(config_dir, settings)
        notification_system = AlertNotificationSystem(alert_manager)

        print("Created AlertManager and AlertNotificationSystem")

        # Process and send notifications
        print("Processing alerts for notifications...")
        notifications_sent = await notification_system.process_and_notify(alerts)

        if notifications_sent > 0:
            print(f"✅ SUCCESS: Sent {notifications_sent} notification(s)!")
            print("You should have seen a desktop notification.")
        else:
            print("⚠️ No notifications were sent")

            # Get statistics for debugging
            stats = notification_system.get_statistics()
            print(f"Alert statistics: {stats}")

            # Check settings
            settings_check = notification_system.get_settings()
            print(f"Settings check: enabled={settings_check.notifications_enabled}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_visual_crossing_notification())
