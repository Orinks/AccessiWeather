"""Integration tests for weather history tracking feature.

These tests verify the weather history feature works with the rest of the system.
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from accessiweather.models import CurrentConditions, Location
from accessiweather.weather_history import WeatherHistoryTracker


class TestWeatherHistoryIntegration:
    """Integration tests for weather history."""

    def test_full_workflow(self):
        """Test complete workflow: add, save, load, compare."""
        # Create a temporary file for history
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_file = f.name

        try:
            # Initialize tracker
            tracker = WeatherHistoryTracker(history_file=temp_file, max_days=30)

            # Create location and conditions
            location = Location(
                name="Test City",
                latitude=40.7128,
                longitude=-74.0060,
                timezone="America/New_York",
            )

            # Add historical entry (yesterday)
            yesterday_conditions = CurrentConditions(
                temperature=70.0,
                condition="Cloudy",
                humidity=70,
                wind_speed=8.0,
                wind_direction="N",
                pressure=30.2,
            )
            yesterday = datetime.now() - timedelta(days=1)
            tracker.add_entry(location, yesterday_conditions, yesterday)

            # Save to file
            tracker.save()

            # Verify file was created
            assert Path(temp_file).exists()

            # Load in a new tracker instance
            new_tracker = WeatherHistoryTracker(history_file=temp_file, max_days=30)
            new_tracker.load()

            # Verify data was loaded
            assert len(new_tracker.history) == 1
            assert new_tracker.history[0].location_name == "Test City"
            assert new_tracker.history[0].temperature == 70.0

            # Add today's conditions and compare
            today_conditions = CurrentConditions(
                temperature=75.0,
                condition="Sunny",
                humidity=60,
                wind_speed=10.0,
                wind_direction="NW",
                pressure=30.1,
            )

            # Get comparison
            comparison = new_tracker.get_comparison_for_yesterday(
                "Test City", today_conditions
            )

            assert comparison is not None
            assert comparison.temperature_difference == 5.0
            assert "warmer" in comparison.temperature_description
            assert comparison.condition_changed is True

            # Get accessible summary
            summary = comparison.get_accessible_summary()
            assert "yesterday" in summary.lower()
            assert "warmer" in summary.lower()

        finally:
            # Cleanup
            Path(temp_file).unlink(missing_ok=True)

    def test_history_cleanup_on_load(self):
        """Test that old entries are removed when loading history."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_file = f.name

        try:
            # Create tracker with short retention
            tracker = WeatherHistoryTracker(history_file=temp_file, max_days=7)

            location = Location(
                name="Test City",
                latitude=40.7128,
                longitude=-74.0060,
                timezone="America/New_York",
            )

            # Add old entry (10 days ago)
            old_conditions = CurrentConditions(
                temperature=65.0,
                condition="Rainy",
                humidity=80,
                wind_speed=15.0,
                wind_direction="E",
                pressure=29.8,
            )
            old_date = datetime.now() - timedelta(days=10)
            tracker.add_entry(location, old_conditions, old_date)

            # Add recent entry (3 days ago)
            recent_conditions = CurrentConditions(
                temperature=72.0,
                condition="Sunny",
                humidity=55,
                wind_speed=5.0,
                wind_direction="W",
                pressure=30.3,
            )
            recent_date = datetime.now() - timedelta(days=3)
            tracker.add_entry(location, recent_conditions, recent_date)

            # Save
            tracker.save()

            # Load in new tracker
            new_tracker = WeatherHistoryTracker(history_file=temp_file, max_days=7)
            new_tracker.load()

            # Old entry should be cleaned up
            assert len(new_tracker.history) == 1
            assert new_tracker.history[0].temperature == 72.0

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_multiple_locations(self):
        """Test tracking history for multiple locations."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_file = f.name

        try:
            tracker = WeatherHistoryTracker(history_file=temp_file, max_days=30)

            # Add entries for two different locations
            location1 = Location(
                name="New York",
                latitude=40.7128,
                longitude=-74.0060,
                timezone="America/New_York",
            )
            location2 = Location(
                name="Los Angeles",
                latitude=34.0522,
                longitude=-118.2437,
                timezone="America/Los_Angeles",
            )

            conditions1 = CurrentConditions(
                temperature=70.0, condition="Cloudy", humidity=65, 
                wind_speed=10.0, wind_direction="E", pressure=30.0
            )
            conditions2 = CurrentConditions(
                temperature=85.0, condition="Sunny", humidity=40,
                wind_speed=5.0, wind_direction="W", pressure=29.9
            )

            yesterday = datetime.now() - timedelta(days=1)
            tracker.add_entry(location1, conditions1, yesterday)
            tracker.add_entry(location2, conditions2, yesterday)

            # Verify we can retrieve each location's history
            ny_entry = tracker.get_entry_for_location_and_day("New York", yesterday.date())
            la_entry = tracker.get_entry_for_location_and_day("Los Angeles", yesterday.date())

            assert ny_entry is not None
            assert ny_entry.temperature == 70.0
            assert la_entry is not None
            assert la_entry.temperature == 85.0

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_comparison_methods(self):
        """Test convenience comparison methods."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_file = f.name

        try:
            tracker = WeatherHistoryTracker(history_file=temp_file, max_days=30)

            location = Location(
                name="Test City",
                latitude=40.7128,
                longitude=-74.0060,
                timezone="America/New_York",
            )

            # Add entries for yesterday and last week
            conditions = CurrentConditions(
                temperature=70.0, condition="Cloudy", humidity=60,
                wind_speed=8.0, wind_direction="N", pressure=30.1
            )

            yesterday = datetime.now() - timedelta(days=1)
            last_week = datetime.now() - timedelta(days=7)

            tracker.add_entry(location, conditions, yesterday)
            tracker.add_entry(location, conditions, last_week)

            # Test comparison methods
            current = CurrentConditions(
                temperature=75.0, condition="Sunny", humidity=55,
                wind_speed=10.0, wind_direction="NW", pressure=30.2
            )

            yesterday_comp = tracker.get_comparison_for_yesterday("Test City", current)
            assert yesterday_comp is not None
            assert yesterday_comp.temperature_difference == 5.0

            week_comp = tracker.get_comparison_for_last_week("Test City", current)
            assert week_comp is not None
            assert week_comp.temperature_difference == 5.0

        finally:
            Path(temp_file).unlink(missing_ok=True)
