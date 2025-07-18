#!/usr/bin/env python3
"""Debug script for Visual Crossing weather alerts.

This script helps debug why Visual Crossing alerts are not being sent as notifications.
It tests the entire pipeline from API fetch to notification delivery.
"""

import asyncio
import logging
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from accessiweather.simple.alert_manager import AlertManager
from accessiweather.simple.alert_notification_system import AlertNotificationSystem
from accessiweather.simple.models import Location
from accessiweather.simple.visual_crossing_client import VisualCrossingClient
from accessiweather.simple.weather_client import WeatherClient

# Set up logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_visual_crossing_alerts():
    """Test Visual Crossing alerts end-to-end."""
    # Get API key from environment or prompt user
    api_key = os.getenv("VISUAL_CROSSING_API_KEY")
    if not api_key:
        api_key = input("Enter your Visual Crossing API key: ").strip()
        if not api_key:
            print("No API key provided. Exiting.")
            return

    print("=" * 80)
    print("VISUAL CROSSING ALERTS DEBUG TEST")
    print("=" * 80)

    # Test locations - choose areas that commonly have weather alerts
    # Include both US and international locations
    test_locations = [
        # US locations (for comparison with NWS)
        Location(name="Miami, FL", latitude=25.7617, longitude=-80.1918),  # Hurricane prone
        Location(name="Oklahoma City, OK", latitude=35.4676, longitude=-97.5164),  # Tornado alley
        Location(name="Denver, CO", latitude=39.7392, longitude=-104.9903),  # Winter weather
        Location(name="Phoenix, AZ", latitude=33.4484, longitude=-112.0740),  # Heat warnings
        # International locations (Visual Crossing only - NWS doesn't cover these)
        Location(name="London, UK", latitude=51.5074, longitude=-0.1278),  # European weather
        Location(
            name="Tokyo, Japan", latitude=35.6762, longitude=139.6503
        ),  # Typhoons, earthquakes
        Location(
            name="Sydney, Australia", latitude=-33.8688, longitude=151.2093
        ),  # Bushfires, storms
        Location(name="Mumbai, India", latitude=19.0760, longitude=72.8777),  # Monsoons, cyclones
        Location(name="Toronto, Canada", latitude=43.6532, longitude=-79.3832),  # Winter storms
        Location(
            name="Mexico City, Mexico", latitude=19.4326, longitude=-99.1332
        ),  # Air quality, storms
    ]

    for location in test_locations:
        print(f"\n{'=' * 60}")
        print(f"Testing location: {location.name}")
        print(f"Coordinates: {location.latitude}, {location.longitude}")
        print(f"{'=' * 60}")

        # Step 1: Test direct Visual Crossing API call
        print("\n1. Testing direct Visual Crossing API call...")
        try:
            vc_client = VisualCrossingClient(api_key)
            alerts = await vc_client.get_alerts(location)

            print(f"   ✓ API call successful")
            print(f"   ✓ Alerts object type: {type(alerts)}")
            print(f"   ✓ Has alerts: {alerts.has_alerts() if alerts else False}")

            if alerts and alerts.has_alerts():
                print(f"   ✓ Number of alerts: {len(alerts.alerts)}")
                for i, alert in enumerate(alerts.alerts[:3]):  # Show first 3
                    print(f"     Alert {i + 1}:")
                    print(f"       Event: {alert.event}")
                    print(f"       Severity: {alert.severity}")
                    print(f"       Headline: {alert.headline}")
                    print(f"       ID: {alert.id}")
            else:
                print("   ℹ No alerts found for this location")

        except Exception as e:
            print(f"   ✗ API call failed: {e}")
            continue

        # Step 2: Test weather client integration
        print("\n2. Testing weather client integration...")
        try:
            weather_client = WeatherClient(
                data_source="visualcrossing", visual_crossing_api_key=api_key
            )

            weather_data = await weather_client.get_weather_data(location)

            print(f"   ✓ Weather client call successful")
            print(f"   ✓ Weather data alerts: {type(weather_data.alerts)}")
            print(
                f"   ✓ Has alerts: {weather_data.alerts.has_alerts() if weather_data.alerts else False}"
            )

            if weather_data.alerts and weather_data.alerts.has_alerts():
                print(f"   ✓ Number of alerts in weather data: {len(weather_data.alerts.alerts)}")
            else:
                print("   ℹ No alerts in weather data")

        except Exception as e:
            print(f"   ✗ Weather client failed: {e}")
            continue

        # Step 3: Test notification system directly
        if alerts and alerts.has_alerts():
            print("\n3. Testing notification system...")
            try:
                alert_manager = AlertManager()
                notification_system = AlertNotificationSystem(alert_manager)

                # Test notification system
                notifications_sent = await notification_system.process_and_notify(alerts)

                print(f"   ✓ Notification system processed alerts")
                print(f"   ✓ Notifications sent: {notifications_sent}")

                if notifications_sent > 0:
                    print("   ✓ SUCCESS: Notifications were sent!")
                else:
                    print("   ⚠ WARNING: No notifications were sent")

                    # Get alert manager statistics for debugging
                    stats = notification_system.get_statistics()
                    print(f"   Debug - Alert statistics: {stats}")

                    # Get current settings
                    settings = notification_system.get_settings()
                    print(f"   Debug - Notification settings:")
                    print(f"     Notifications enabled: {settings.notifications_enabled}")
                    print(f"     Min severity priority: {settings.min_severity_priority}")
                    print(f"     Ignored categories: {settings.ignored_categories}")

            except Exception as e:
                print(f"   ✗ Notification system failed: {e}")
                import traceback

                traceback.print_exc()

        # Step 4: Test a manual notification
        print("\n4. Testing manual notification...")
        try:
            alert_manager = AlertManager()
            notification_system = AlertNotificationSystem(alert_manager)

            success = await notification_system.test_notification("Severe")

            if success:
                print("   ✓ Manual test notification sent successfully")
            else:
                print("   ✗ Manual test notification failed")

        except Exception as e:
            print(f"   ✗ Manual notification test failed: {e}")

    print(f"\n{'=' * 80}")
    print("DEBUG TEST COMPLETE")
    print(f"{'=' * 80}")


async def compare_alert_sources():
    """Compare alerts from different sources for the same location."""
    api_key = os.getenv("VISUAL_CROSSING_API_KEY")
    if not api_key:
        api_key = input("Enter your Visual Crossing API key: ").strip()
        if not api_key:
            print("No API key provided. Exiting.")
            return

    # Test with a US location that should have alerts from both sources
    location = Location(name="Miami, FL", latitude=25.7617, longitude=-80.1918)

    print(f"\n{'=' * 80}")
    print("COMPARING ALERT SOURCES")
    print(f"Location: {location.name}")
    print(f"{'=' * 80}")

    # Test NWS alerts
    print("\n1. Testing NWS alerts...")
    try:
        nws_client = WeatherClient(data_source="nws")
        nws_weather = await nws_client.get_weather_data(location)

        print(
            f"   NWS alerts found: {nws_weather.alerts.has_alerts() if nws_weather.alerts else False}"
        )
        if nws_weather.alerts and nws_weather.alerts.has_alerts():
            print(f"   Number of NWS alerts: {len(nws_weather.alerts.alerts)}")
            for alert in nws_weather.alerts.alerts[:2]:
                print(f"     - {alert.event}: {alert.headline}")

    except Exception as e:
        print(f"   NWS alerts failed: {e}")

    # Test Visual Crossing alerts
    print("\n2. Testing Visual Crossing alerts...")
    try:
        vc_client = WeatherClient(data_source="visualcrossing", visual_crossing_api_key=api_key)
        vc_weather = await vc_client.get_weather_data(location)

        print(
            f"   Visual Crossing alerts found: {vc_weather.alerts.has_alerts() if vc_weather.alerts else False}"
        )
        if vc_weather.alerts and vc_weather.alerts.has_alerts():
            print(f"   Number of Visual Crossing alerts: {len(vc_weather.alerts.alerts)}")
            for alert in vc_weather.alerts.alerts[:2]:
                print(f"     - {alert.event}: {alert.headline}")

    except Exception as e:
        print(f"   Visual Crossing alerts failed: {e}")


if __name__ == "__main__":
    print("Visual Crossing Alerts Debug Tool")
    print("=" * 50)
    print("1. Test Visual Crossing alerts end-to-end (US + International)")
    print("2. Compare alert sources (NWS vs Visual Crossing)")
    print("3. Run international alerts test (dedicated script)")
    print("4. Run simple test (basic functionality)")

    choice = input("\nEnter choice (1-4): ").strip()

    if choice == "1":
        asyncio.run(test_visual_crossing_alerts())
    elif choice == "2":
        asyncio.run(compare_alert_sources())
    elif choice == "3":
        print("Running dedicated international alerts test...")
        os.system("python test_international_alerts.py")
    elif choice == "4":
        print("Running simple test...")
        os.system("python test_visual_crossing_alerts_simple.py")
    else:
        print("Invalid choice. Exiting.")
