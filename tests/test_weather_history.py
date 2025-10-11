"""Tests for weather history tracking feature."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from accessiweather.models import CurrentConditions, Location
from accessiweather.weather_history import (
    WeatherComparison,
    WeatherHistoryEntry,
    WeatherHistoryTracker,
)


class TestWeatherHistoryEntry:
    """Test WeatherHistoryEntry data model."""

    def test_create_entry_from_current_conditions(self):
        """Test creating a history entry from current conditions."""
        location = Location(
            name="Test City",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York",
        )
        conditions = CurrentConditions(
            temperature=75.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )
        
        entry = WeatherHistoryEntry.from_current_conditions(
            location=location,
            conditions=conditions,
            timestamp=datetime(2025, 1, 1, 12, 0, 0)
        )
        
        assert entry.location_name == "Test City"
        assert entry.temperature == 75.0
        assert entry.condition == "Sunny"
        assert entry.humidity == 60
        assert entry.wind_speed == 10.0
        assert entry.timestamp == datetime(2025, 1, 1, 12, 0, 0)

    def test_entry_to_dict(self):
        """Test converting entry to dictionary for storage."""
        entry = WeatherHistoryEntry(
            location_name="Test City",
            temperature=75.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
        )
        
        data = entry.to_dict()
        
        assert data["location_name"] == "Test City"
        assert data["temperature"] == 75.0
        assert data["condition"] == "Sunny"
        assert "timestamp" in data

    def test_entry_from_dict(self):
        """Test creating entry from dictionary."""
        data = {
            "location_name": "Test City",
            "temperature": 75.0,
            "condition": "Sunny",
            "humidity": 60,
            "wind_speed": 10.0,
            "wind_direction": "NW",
            "pressure": 30.1,
            "timestamp": "2025-01-01T12:00:00",
        }
        
        entry = WeatherHistoryEntry.from_dict(data)
        
        assert entry.location_name == "Test City"
        assert entry.temperature == 75.0
        assert entry.condition == "Sunny"


class TestWeatherHistoryTracker:
    """Test WeatherHistoryTracker functionality."""

    @pytest.fixture
    def temp_history_file(self, tmp_path):
        """Create a temporary history file for testing."""
        history_file = tmp_path / "weather_history.json"
        return str(history_file)

    @pytest.fixture
    def tracker(self, temp_history_file):
        """Create a tracker instance with temporary storage."""
        return WeatherHistoryTracker(
            history_file=temp_history_file,
            max_days=30
        )

    def test_tracker_initialization(self, tracker, temp_history_file):
        """Test tracker initializes correctly."""
        assert tracker.history_file == temp_history_file
        assert tracker.max_days == 30
        assert isinstance(tracker.history, list)

    def test_add_entry(self, tracker):
        """Test adding a weather history entry."""
        location = Location(
            name="Test City",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York",
        )
        conditions = CurrentConditions(
            temperature=75.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )
        
        tracker.add_entry(location=location, conditions=conditions)
        
        assert len(tracker.history) == 1
        assert tracker.history[0].location_name == "Test City"
        assert tracker.history[0].temperature == 75.0

    def test_save_and_load_history(self, tracker, temp_history_file):
        """Test saving and loading history from file."""
        location = Location(
            name="Test City",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York",
        )
        conditions = CurrentConditions(
            temperature=75.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )
        
        # Add entry and save
        tracker.add_entry(location=location, conditions=conditions)
        tracker.save()
        
        # Create new tracker and load
        new_tracker = WeatherHistoryTracker(
            history_file=temp_history_file,
            max_days=30
        )
        new_tracker.load()
        
        assert len(new_tracker.history) == 1
        assert new_tracker.history[0].location_name == "Test City"

    def test_get_entry_for_location_and_day(self, tracker):
        """Test retrieving entry for specific location and day."""
        location = Location(
            name="Test City",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York",
        )
        conditions = CurrentConditions(
            temperature=75.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )
        
        timestamp = datetime(2025, 1, 1, 12, 0, 0)
        tracker.add_entry(location=location, conditions=conditions, timestamp=timestamp)
        
        # Try to get entry for same day
        entry = tracker.get_entry_for_location_and_day("Test City", timestamp.date())
        
        assert entry is not None
        assert entry.location_name == "Test City"
        assert entry.temperature == 75.0

    def test_get_entry_returns_none_for_missing_day(self, tracker):
        """Test that get_entry returns None when no entry exists."""
        entry = tracker.get_entry_for_location_and_day("Test City", datetime(2025, 1, 1).date())
        
        assert entry is None

    def test_cleanup_old_entries(self, tracker):
        """Test cleaning up entries older than max_days."""
        location = Location(
            name="Test City",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York",
        )
        conditions = CurrentConditions(
            temperature=75.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )
        
        # Add old entry (40 days ago)
        old_timestamp = datetime.now() - timedelta(days=40)
        tracker.add_entry(location=location, conditions=conditions, timestamp=old_timestamp)
        
        # Add recent entry (5 days ago)
        recent_timestamp = datetime.now() - timedelta(days=5)
        tracker.add_entry(location=location, conditions=conditions, timestamp=recent_timestamp)
        
        assert len(tracker.history) == 2
        
        # Cleanup old entries (max_days is 30)
        tracker.cleanup_old_entries()
        
        assert len(tracker.history) == 1
        assert (datetime.now() - tracker.history[0].timestamp).days < 30


class TestWeatherComparison:
    """Test weather comparison functionality."""

    def test_compare_temperature_warmer(self):
        """Test comparison shows temperature increase."""
        current = CurrentConditions(
            temperature=80.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )
        
        previous_entry = WeatherHistoryEntry(
            location_name="Test City",
            temperature=75.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
            timestamp=datetime.now() - timedelta(days=1),
        )
        
        comparison = WeatherComparison.compare(current, previous_entry)
        
        assert comparison.temperature_difference == 5.0
        assert "warmer" in comparison.temperature_description.lower()

    def test_compare_temperature_cooler(self):
        """Test comparison shows temperature decrease."""
        current = CurrentConditions(
            temperature=70.0,
            condition="Cloudy",
            humidity=65,
            wind_speed=12.0,
            wind_direction="E",
            pressure=30.0,
        )
        
        previous_entry = WeatherHistoryEntry(
            location_name="Test City",
            temperature=75.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
            timestamp=datetime.now() - timedelta(days=1),
        )
        
        comparison = WeatherComparison.compare(current, previous_entry)
        
        assert comparison.temperature_difference == -5.0
        assert "cooler" in comparison.temperature_description.lower()

    def test_compare_same_temperature(self):
        """Test comparison when temperature is the same."""
        current = CurrentConditions(
            temperature=75.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )
        
        previous_entry = WeatherHistoryEntry(
            location_name="Test City",
            temperature=75.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
            timestamp=datetime.now() - timedelta(days=1),
        )
        
        comparison = WeatherComparison.compare(current, previous_entry)
        
        assert comparison.temperature_difference == 0.0
        assert "same" in comparison.temperature_description.lower()

    def test_compare_condition_changed(self):
        """Test comparison when weather condition changed."""
        current = CurrentConditions(
            temperature=75.0,
            condition="Rainy",
            humidity=80,
            wind_speed=15.0,
            wind_direction="S",
            pressure=29.9,
        )
        
        previous_entry = WeatherHistoryEntry(
            location_name="Test City",
            temperature=75.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
            timestamp=datetime.now() - timedelta(days=1),
        )
        
        comparison = WeatherComparison.compare(current, previous_entry)
        
        assert comparison.condition_changed is True
        assert comparison.previous_condition == "Sunny"
        assert comparison.condition_description is not None

    def test_comparison_summary_accessible(self):
        """Test that comparison summary is screen-reader friendly."""
        current = CurrentConditions(
            temperature=80.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )
        
        previous_entry = WeatherHistoryEntry(
            location_name="Test City",
            temperature=75.0,
            condition="Cloudy",
            humidity=70,
            wind_speed=8.0,
            wind_direction="N",
            pressure=30.2,
            timestamp=datetime.now() - timedelta(days=1),
        )
        
        comparison = WeatherComparison.compare(current, previous_entry)
        summary = comparison.get_accessible_summary()
        
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "degrees" in summary.lower() or "temperature" in summary.lower()
