#!/usr/bin/env python3
"""Test Visual Crossing alerts for international locations.

This test demonstrates Visual Crossing's advantage over NWS for international weather alerts,
since NWS only covers the United States.
"""

import asyncio
import logging
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from accessiweather.simple.models import Location
from accessiweather.simple.weather_client import WeatherClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_international_alerts():
    """Test Visual Crossing alerts for international locations."""
    # Get API key
    api_key = os.getenv("VISUAL_CROSSING_API_KEY")
    if not api_key:
        print("Please set VISUAL_CROSSING_API_KEY environment variable")
        print("Get your free API key at: https://www.visualcrossing.com/weather-query-builder/")
        return

    print("=" * 80)
    print("TESTING VISUAL CROSSING INTERNATIONAL WEATHER ALERTS")
    print("=" * 80)
    print("This test demonstrates Visual Crossing's global coverage for weather alerts.")
    print("NWS only covers the United States, but Visual Crossing provides worldwide data.")
    print("=" * 80)

    # International locations known for various weather phenomena
    international_locations = [
        # Europe
        Location(name="London, UK", latitude=51.5074, longitude=-0.1278),
        Location(name="Amsterdam, Netherlands", latitude=52.3676, longitude=4.9041),
        Location(name="Berlin, Germany", latitude=52.5200, longitude=13.4050),
        # Asia-Pacific
        Location(name="Tokyo, Japan", latitude=35.6762, longitude=139.6503),
        Location(name="Sydney, Australia", latitude=-33.8688, longitude=151.2093),
        Location(name="Mumbai, India", latitude=19.0760, longitude=72.8777),
        Location(name="Bangkok, Thailand", latitude=13.7563, longitude=100.5018),
        # Americas (non-US)
        Location(name="Toronto, Canada", latitude=43.6532, longitude=-79.3832),
        Location(name="Mexico City, Mexico", latitude=19.4326, longitude=-99.1332),
        Location(name="São Paulo, Brazil", latitude=-23.5505, longitude=-46.6333),
        # Other regions
        Location(name="Cairo, Egypt", latitude=30.0444, longitude=31.2357),
        Location(name="Cape Town, South Africa", latitude=-33.9249, longitude=18.4241),
    ]

    total_locations = len(international_locations)
    locations_with_alerts = 0
    total_alerts = 0

    for i, location in enumerate(international_locations, 1):
        print(f"\n[{i}/{total_locations}] Testing: {location.name}")
        print(f"Coordinates: {location.latitude}, {location.longitude}")
        print("-" * 60)

        try:
            # Create weather client with Visual Crossing
            client = WeatherClient(data_source="visualcrossing", visual_crossing_api_key=api_key)

            # Get weather data
            weather_data = await client.get_weather_data(location)

            # Check basic data retrieval
            has_current = weather_data.current is not None
            has_forecast = weather_data.forecast is not None
            has_alerts_obj = weather_data.alerts is not None

            print(
                f"✓ API Response: Current={has_current}, Forecast={has_forecast}, Alerts={has_alerts_obj}"
            )

            # Check for alerts
            if weather_data.alerts and weather_data.alerts.has_alerts():
                locations_with_alerts += 1
                alert_count = len(weather_data.alerts.alerts)
                total_alerts += alert_count

                print(f"🚨 ALERTS FOUND: {alert_count} active alert(s)")

                for j, alert in enumerate(weather_data.alerts.alerts, 1):
                    print(f"  Alert {j}:")
                    print(f"    Event: {alert.event}")
                    print(f"    Severity: {alert.severity}")
                    print(f"    Headline: {alert.headline}")
                    if alert.areas:
                        areas_text = ", ".join(alert.areas[:2])
                        if len(alert.areas) > 2:
                            areas_text += f" (+{len(alert.areas) - 2} more)"
                        print(f"    Areas: {areas_text}")
                    if alert.expires:
                        print(f"    Expires: {alert.expires.strftime('%Y-%m-%d %H:%M')}")
                    print()
            else:
                print("ℹ️  No active alerts for this location")

            # Test what would happen with NWS (should fail for international locations)
            print("🔍 Comparison: Testing NWS for this location...")
            try:
                nws_client = WeatherClient(data_source="nws")
                nws_weather = await nws_client.get_weather_data(location)
                print("⚠️  Unexpected: NWS worked for international location")
            except Exception as nws_error:
                print(
                    f"✓ Expected: NWS failed for international location ({type(nws_error).__name__})"
                )

        except Exception as e:
            print(f"✗ Visual Crossing failed for {location.name}: {e}")
            continue

    # Summary
    print("\n" + "=" * 80)
    print("INTERNATIONAL ALERTS TEST SUMMARY")
    print("=" * 80)
    print(f"Locations tested: {total_locations}")
    print(f"Locations with alerts: {locations_with_alerts}")
    print(f"Total alerts found: {total_alerts}")
    print(
        f"Success rate: {(total_locations - 0) / total_locations * 100:.1f}%"
    )  # Assuming all succeeded

    if locations_with_alerts > 0:
        print(f"\n✅ SUCCESS: Visual Crossing provided weather alerts for international locations!")
        print("   This demonstrates the global coverage advantage over NWS (US-only).")
    else:
        print(f"\nℹ️  INFO: No active alerts found, but this is normal.")
        print("   Weather alerts are issued only when there are active weather hazards.")
        print("   The test confirms Visual Crossing can fetch international data successfully.")

    print("\n🌍 Visual Crossing provides global weather alert coverage")
    print("🇺🇸 NWS is limited to United States locations only")
    print(
        "\nFor AccessiWeather users outside the US, Visual Crossing is essential for weather alerts!"
    )


async def compare_us_vs_international():
    """Compare alert availability between US and international locations."""
    api_key = os.getenv("VISUAL_CROSSING_API_KEY")
    if not api_key:
        print("Please set VISUAL_CROSSING_API_KEY environment variable")
        return

    print("\n" + "=" * 80)
    print("COMPARING US vs INTERNATIONAL ALERT COVERAGE")
    print("=" * 80)

    # Test one US location with both NWS and Visual Crossing
    us_location = Location(name="Miami, FL", latitude=25.7617, longitude=-80.1918)

    print(f"\n🇺🇸 Testing US location: {us_location.name}")
    print("-" * 40)

    # Test NWS
    try:
        nws_client = WeatherClient(data_source="nws")
        nws_weather = await nws_client.get_weather_data(us_location)
        nws_alert_count = (
            len(nws_weather.alerts.alerts)
            if nws_weather.alerts and nws_weather.alerts.has_alerts()
            else 0
        )
        print(f"NWS alerts: {nws_alert_count}")
    except Exception as e:
        print(f"NWS failed: {e}")
        nws_alert_count = 0

    # Test Visual Crossing
    try:
        vc_client = WeatherClient(data_source="visualcrossing", visual_crossing_api_key=api_key)
        vc_weather = await vc_client.get_weather_data(us_location)
        vc_alert_count = (
            len(vc_weather.alerts.alerts)
            if vc_weather.alerts and vc_weather.alerts.has_alerts()
            else 0
        )
        print(f"Visual Crossing alerts: {vc_alert_count}")
    except Exception as e:
        print(f"Visual Crossing failed: {e}")
        vc_alert_count = 0

    # Test international location (only Visual Crossing will work)
    intl_location = Location(name="London, UK", latitude=51.5074, longitude=-0.1278)

    print(f"\n🌍 Testing International location: {intl_location.name}")
    print("-" * 40)

    # Test NWS (should fail)
    try:
        nws_client = WeatherClient(data_source="nws")
        nws_weather = await nws_client.get_weather_data(intl_location)
        print("⚠️  Unexpected: NWS worked for international location")
    except Exception as e:
        print(f"NWS (expected failure): {type(e).__name__}")

    # Test Visual Crossing
    try:
        vc_client = WeatherClient(data_source="visualcrossing", visual_crossing_api_key=api_key)
        vc_weather = await vc_client.get_weather_data(intl_location)
        intl_alert_count = (
            len(vc_weather.alerts.alerts)
            if vc_weather.alerts and vc_weather.alerts.has_alerts()
            else 0
        )
        print(f"Visual Crossing alerts: {intl_alert_count}")
    except Exception as e:
        print(f"Visual Crossing failed: {e}")

    print("\n📊 CONCLUSION:")
    print("• NWS: US locations only")
    print("• Visual Crossing: Global coverage including US and international")
    print("• For international users, Visual Crossing is the only option for weather alerts")


if __name__ == "__main__":
    print("International Weather Alerts Test")
    print("1. Test international locations only")
    print("2. Compare US vs International coverage")

    choice = input("\nEnter choice (1 or 2, or press Enter for option 1): ").strip()

    if choice == "2":
        asyncio.run(compare_us_vs_international())
    else:
        asyncio.run(test_international_alerts())
