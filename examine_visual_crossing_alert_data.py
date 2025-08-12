#!/usr/bin/env python3
"""Examine real Visual Crossing alert data to understand geographic specificity."""

import asyncio
import json
import logging
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from accessiweather.models import Location
from accessiweather.visual_crossing_client import VisualCrossingClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def examine_alert_data():
    """Examine Visual Crossing alert data from multiple locations."""
    # Get API key
    api_key = os.getenv("VISUAL_CROSSING_API_KEY")
    if not api_key:
        print("Please set VISUAL_CROSSING_API_KEY environment variable")
        return

    print("EXAMINING VISUAL CROSSING ALERT DATA")
    print("=" * 60)
    print("This will help us understand geographic specificity for area-based filtering")
    print("=" * 60)

    # Test locations with different geographic scopes
    test_locations = [
        # UK locations - different areas within London and UK
        Location(name="Central London, UK", latitude=51.5074, longitude=-0.1278),
        Location(name="Greenwich, London, UK", latitude=51.4769, longitude=-0.0005),
        Location(name="Camden, London, UK", latitude=51.5290, longitude=-0.1255),
        Location(name="Westminster, London, UK", latitude=51.4994, longitude=-0.1244),
        Location(name="Birmingham, UK", latitude=52.4862, longitude=-1.8904),
        Location(name="Manchester, UK", latitude=53.4808, longitude=-2.2426),
        # US locations for comparison
        Location(name="Manhattan, NYC", latitude=40.7831, longitude=-73.9712),
        Location(name="Brooklyn, NYC", latitude=40.6782, longitude=-73.9442),
        Location(name="Miami, FL", latitude=25.7617, longitude=-80.1918),
        # International locations
        Location(name="Paris, France", latitude=48.8566, longitude=2.3522),
        Location(name="Tokyo, Japan", latitude=35.6762, longitude=139.6503),
        Location(name="Sydney, Australia", latitude=-33.8688, longitude=151.2093),
    ]

    client = VisualCrossingClient(api_key)

    all_alert_data = {}

    for location in test_locations:
        print(f"\n{'=' * 50}")
        print(f"EXAMINING: {location.name}")
        print(f"Coordinates: {location.latitude}, {location.longitude}")
        print(f"{'=' * 50}")

        try:
            # Get alerts for this location
            alerts = await client.get_alerts(location)

            location_data = {
                "location": {
                    "name": location.name,
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                },
                "alert_count": len(alerts.alerts) if alerts else 0,
                "alerts": [],
            }

            if alerts and alerts.has_alerts():
                print(f"✅ Found {len(alerts.alerts)} alert(s)")

                for i, alert in enumerate(alerts.alerts, 1):
                    print(f"\n--- Alert {i} ---")
                    print(f"Event: {alert.event}")
                    print(f"Severity: {alert.severity}")
                    print(f"Headline: {alert.headline}")
                    print(f"Areas: {alert.areas}")
                    print(f"ID: {alert.id}")
                    if alert.onset:
                        print(f"Onset: {alert.onset}")
                    if alert.expires:
                        print(f"Expires: {alert.expires}")

                    # Store detailed alert data
                    alert_data = {
                        "event": alert.event,
                        "severity": alert.severity,
                        "headline": alert.headline,
                        "description": alert.description,
                        "areas": alert.areas,
                        "id": alert.id,
                        "onset": alert.onset.isoformat() if alert.onset else None,
                        "expires": alert.expires.isoformat() if alert.expires else None,
                        "urgency": alert.urgency,
                        "certainty": alert.certainty,
                        "instruction": alert.instruction,
                    }
                    location_data["alerts"].append(alert_data)

                    # Analyze geographic specificity
                    if alert.areas:
                        print(f"Geographic Analysis:")
                        print(f"  Number of areas: {len(alert.areas)}")
                        print(f"  Area types: {[area for area in alert.areas]}")

                        # Check for hierarchical relationships
                        area_analysis = analyze_area_hierarchy(alert.areas, location.name)
                        if area_analysis:
                            print(f"  Hierarchy analysis: {area_analysis}")

            else:
                print("ℹ️  No active alerts for this location")

            all_alert_data[location.name] = location_data

        except Exception as e:
            print(f"❌ Error fetching alerts for {location.name}: {e}")
            all_alert_data[location.name] = {
                "location": {
                    "name": location.name,
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                },
                "error": str(e),
                "alert_count": 0,
                "alerts": [],
            }

    # Save all data to JSON file for analysis
    output_file = "visual_crossing_alert_analysis.json"
    with open(output_file, "w") as f:
        json.dump(all_alert_data, f, indent=2, default=str)

    print(f"\n{'=' * 60}")
    print("ANALYSIS SUMMARY")
    print(f"{'=' * 60}")

    total_locations = len(test_locations)
    locations_with_alerts = sum(
        1 for data in all_alert_data.values() if data.get("alert_count", 0) > 0
    )
    total_alerts = sum(data.get("alert_count", 0) for data in all_alert_data.values())

    print(f"Locations tested: {total_locations}")
    print(f"Locations with alerts: {locations_with_alerts}")
    print(f"Total alerts found: {total_alerts}")

    # Analyze area patterns
    all_areas = []
    for data in all_alert_data.values():
        for alert in data.get("alerts", []):
            if alert.get("areas"):
                all_areas.extend(alert["areas"])

    if all_areas:
        print(f"\nArea Analysis:")
        print(f"Total area references: {len(all_areas)}")
        print(f"Unique areas: {len(set(all_areas))}")

        # Show most common areas
        from collections import Counter

        area_counts = Counter(all_areas)
        print(f"Most common areas:")
        for area, count in area_counts.most_common(10):
            print(f"  {area}: {count} times")

    print(f"\nDetailed data saved to: {output_file}")
    print("Use this data to design area-specific filtering!")


def analyze_area_hierarchy(areas, location_name):
    """Analyze if areas show hierarchical relationships."""
    analysis = {}

    # Extract location components
    location_parts = [part.strip() for part in location_name.split(",")]

    # Check if location parts appear in areas
    matching_areas = []
    for area in areas:
        for part in location_parts:
            if part.lower() in area.lower() or area.lower() in part.lower():
                matching_areas.append(area)
                break

    if matching_areas:
        analysis["matching_location"] = matching_areas

    # Check for common hierarchical keywords
    hierarchical_keywords = ["county", "borough", "district", "region", "state", "province"]
    hierarchical_areas = []
    for area in areas:
        for keyword in hierarchical_keywords:
            if keyword.lower() in area.lower():
                hierarchical_areas.append(area)
                break

    if hierarchical_areas:
        analysis["hierarchical"] = hierarchical_areas

    # Check area scope (local vs regional vs national)
    local_keywords = ["street", "road", "avenue", "district", "neighborhood"]
    regional_keywords = ["county", "borough", "city", "town"]
    national_keywords = ["state", "province", "region", "country"]

    scope_analysis = {"local": [], "regional": [], "national": []}
    for area in areas:
        area_lower = area.lower()
        if any(kw in area_lower for kw in local_keywords):
            scope_analysis["local"].append(area)
        elif any(kw in area_lower for kw in regional_keywords):
            scope_analysis["regional"].append(area)
        elif any(kw in area_lower for kw in national_keywords):
            scope_analysis["national"].append(area)

    if any(scope_analysis.values()):
        analysis["scope"] = {k: v for k, v in scope_analysis.items() if v}

    return analysis if analysis else None


if __name__ == "__main__":
    asyncio.run(examine_alert_data())
