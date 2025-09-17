#!/usr/bin/env python3
"""Simple test for Visual Crossing alerts functionality."""

import asyncio
import logging
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from accessiweather.models import Location
from accessiweather.weather_client import WeatherClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_visual_crossing_alerts():
    """Simple test for Visual Crossing alerts."""
    # Get API key
    api_key = os.getenv("VISUAL_CROSSING_API_KEY")
    if not api_key:
        print("Please set VISUAL_CROSSING_API_KEY environment variable")
        return

    # Test locations - both US and international
    test_locations = [
        Location(name="Miami, FL", latitude=25.7617, longitude=-80.1918),  # US location
        Location(name="London, UK", latitude=51.5074, longitude=-0.1278),  # International
        Location(name="Tokyo, Japan", latitude=35.6762, longitude=139.6503),  # International
    ]

    for location in test_locations:
        print(f"\n{'=' * 50}")
        print(f"Testing Visual Crossing alerts for {location.name}")
        print(f"Coordinates: {location.latitude}, {location.longitude}")
        print(f"{'=' * 50}")

        try:
            # Create weather client with Visual Crossing
            client = WeatherClient(data_source="visualcrossing", visual_crossing_api_key=api_key)

            # Get weather data
            weather_data = await client.get_weather_data(location)

            print(f"✓ Weather data retrieved successfully")
            print(f"  Current conditions: {weather_data.current is not None}")
            print(f"  Forecast: {weather_data.forecast is not None}")
            print(f"  Alerts: {weather_data.alerts is not None}")

            if weather_data.alerts:
                print(f"  Has alerts: {weather_data.alerts.has_alerts()}")
                if weather_data.alerts.has_alerts():
                    print(f"  Number of alerts: {len(weather_data.alerts.alerts)}")
                    for i, alert in enumerate(weather_data.alerts.alerts):
                        print(f"    Alert {i + 1}: {alert.event} - {alert.severity}")
                        print(f"      Headline: {alert.headline}")
                        if alert.areas:
                            print(f"      Areas: {', '.join(alert.areas[:3])}")
                else:
                    print("  ℹ No active alerts for this location")

            print(f"✓ Test completed successfully for {location.name}")

        except Exception as e:
            print(f"✗ Test failed for {location.name}: {e}")
            import traceback

            traceback.print_exc()

    print(f"\n{'=' * 50}")
    print("All tests completed")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    asyncio.run(test_visual_crossing_alerts())
