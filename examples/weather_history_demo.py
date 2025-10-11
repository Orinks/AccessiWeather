#!/usr/bin/env python3
"""Demo script for Weather History Tracker feature.

This script demonstrates the weather history tracking and comparison functionality.
Run this to see how the feature works without needing a full app setup.
"""

import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "accessiweather"))


@dataclass
class Location:
    """Mock Location model for demo."""

    name: str
    latitude: float
    longitude: float
    timezone: str


@dataclass
class CurrentConditions:
    """Mock CurrentConditions model for demo."""

    temperature: float
    condition: str
    humidity: int
    wind_speed: float
    wind_direction: str
    pressure: float


# Mock the models module so weather_history can import
class MockModels:
    Location = Location
    CurrentConditions = CurrentConditions


sys.modules["accessiweather.models"] = MockModels()

# Now we can import weather_history directly
from weather_history import WeatherHistoryTracker


def main():
    """Run the weather history demo."""
    print("=" * 70)
    print("Weather History Tracker Demo")
    print("=" * 70)
    print()

    # Create a temporary file for this demo
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_file = f.name

    try:
        # Initialize tracker
        print("1. Initializing Weather History Tracker...")
        tracker = WeatherHistoryTracker(history_file=temp_file, max_days=30)
        print(f"   ✓ Tracker created with 30-day retention")
        print()

        # Create a location
        print("2. Creating location...")
        location = Location(
            name="New York City",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York",
        )
        print(f"   ✓ Location: {location.name}")
        print()

        # Simulate adding historical weather data
        print("3. Adding historical weather data...")

        # 7 days ago - Cold and rainy
        week_ago = datetime.now() - timedelta(days=7)
        week_ago_weather = CurrentConditions(
            temperature=55.0,
            condition="Rainy",
            humidity=85,
            wind_speed=15.0,
            wind_direction="E",
            pressure=29.8,
        )
        tracker.add_entry(location, week_ago_weather, week_ago)
        print(f"   ✓ Added entry for {week_ago.strftime('%B %d')}: {week_ago_weather.condition}, {week_ago_weather.temperature}°F")

        # 3 days ago - Cloudy
        three_days_ago = datetime.now() - timedelta(days=3)
        three_days_weather = CurrentConditions(
            temperature=65.0,
            condition="Cloudy",
            humidity=70,
            wind_speed=10.0,
            wind_direction="N",
            pressure=30.0,
        )
        tracker.add_entry(location, three_days_weather, three_days_ago)
        print(f"   ✓ Added entry for {three_days_ago.strftime('%B %d')}: {three_days_weather.condition}, {three_days_weather.temperature}°F")

        # Yesterday - Partly cloudy
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_weather = CurrentConditions(
            temperature=70.0,
            condition="Partly Cloudy",
            humidity=65,
            wind_speed=8.0,
            wind_direction="NW",
            pressure=30.1,
        )
        tracker.add_entry(location, yesterday_weather, yesterday)
        print(f"   ✓ Added entry for {yesterday.strftime('%B %d')}: {yesterday_weather.condition}, {yesterday_weather.temperature}°F")
        print()

        # Save the history
        print("4. Saving history to file...")
        tracker.save()
        print(f"   ✓ History saved to: {temp_file}")
        print(f"   ✓ Total entries: {len(tracker.history)}")
        print()

        # Load history in a new tracker instance
        print("5. Loading history from file...")
        new_tracker = WeatherHistoryTracker(history_file=temp_file, max_days=30)
        new_tracker.load()
        print(f"   ✓ Loaded {len(new_tracker.history)} entries")
        print()

        # Simulate today's weather
        print("6. Today's Weather:")
        today_weather = CurrentConditions(
            temperature=78.0,
            condition="Sunny",
            humidity=55,
            wind_speed=5.0,
            wind_direction="W",
            pressure=30.2,
        )
        print(f"   Temperature: {today_weather.temperature}°F")
        print(f"   Condition: {today_weather.condition}")
        print(f"   Humidity: {today_weather.humidity}%")
        print(f"   Wind: {today_weather.wind_speed} mph {today_weather.wind_direction}")
        print()

        # Compare with yesterday
        print("7. Comparing with Yesterday:")
        yesterday_comp = new_tracker.get_comparison_for_yesterday(location.name, today_weather)
        if yesterday_comp:
            print(f"   Temperature: {yesterday_comp.temperature_description}")
            print(f"   Condition: {'Changed' if yesterday_comp.condition_changed else 'Same'}")
            if yesterday_comp.condition_changed:
                print(f"   Previous: {yesterday_comp.previous_condition}")
            print()
            print("   Accessible Summary:")
            print(f"   \"{yesterday_comp.get_accessible_summary()}\"")
        else:
            print("   No data available for yesterday")
        print()

        # Compare with last week
        print("8. Comparing with Last Week:")
        week_comp = new_tracker.get_comparison_for_last_week(location.name, today_weather)
        if week_comp:
            print(f"   Temperature: {week_comp.temperature_description}")
            print(f"   Condition: {'Changed' if week_comp.condition_changed else 'Same'}")
            if week_comp.condition_changed:
                print(f"   Previous: {week_comp.previous_condition}")
            print()
            print("   Accessible Summary:")
            print(f"   \"{week_comp.get_accessible_summary()}\"")
        else:
            print("   No data available for last week")
        print()

        # Show cleanup functionality
        print("9. Testing Cleanup Functionality:")
        print(f"   Current retention: {new_tracker.max_days} days")
        print(f"   Entries before cleanup: {len(new_tracker.history)}")

        # Add a very old entry (45 days ago)
        old_date = datetime.now() - timedelta(days=45)
        old_weather = CurrentConditions(
            temperature=50.0, condition="Cold", humidity=80,
            wind_speed=20.0, wind_direction="N", pressure=29.5
        )
        new_tracker.add_entry(location, old_weather, old_date)
        print(f"   Added old entry (45 days ago)")
        print(f"   Entries: {len(new_tracker.history)}")

        # Run cleanup
        new_tracker.cleanup_old_entries()
        print(f"   Entries after cleanup: {len(new_tracker.history)}")
        print(f"   ✓ Old entries removed")
        print()

        print("=" * 70)
        print("Demo Complete!")
        print("=" * 70)
        print()
        print("Key Features Demonstrated:")
        print("  ✓ Adding weather history entries")
        print("  ✓ Saving and loading history from file")
        print("  ✓ Comparing current weather with past days")
        print("  ✓ Generating accessible summaries")
        print("  ✓ Automatic cleanup of old entries")
        print()

    finally:
        # Cleanup temp file
        Path(temp_file).unlink(missing_ok=True)
        print(f"Cleaned up temporary file: {temp_file}")


if __name__ == "__main__":
    main()
