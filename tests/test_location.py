"""Tests for the location manager module"""

import pytest
import os
import json
import tempfile
from unittest.mock import patch, mock_open

from noaa_weather_app.location import LocationManager


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for test config files"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def location_manager(temp_config_dir):
    """Create a LocationManager with a temporary config directory"""
    return LocationManager(config_dir=temp_config_dir)


class TestLocationManager:
    """Test suite for LocationManager"""

    def test_init(self, location_manager, temp_config_dir):
        """Test initialization and directory creation"""
        assert location_manager.config_dir == temp_config_dir
        assert location_manager.locations_file == os.path.join(temp_config_dir, "locations.json")
        assert location_manager.current_location is None
        assert location_manager.saved_locations == {}
        assert os.path.exists(temp_config_dir)

    def test_add_location(self, location_manager):
        """Test adding a location"""
        # Add a location
        location_manager.add_location("Home", 35.0, -80.0)
        
        # Check that it was added
        assert "Home" in location_manager.saved_locations
        assert location_manager.saved_locations["Home"] == {"lat": 35.0, "lon": -80.0}
        
        # Check that it was set as current (first location)
        assert location_manager.current_location == "Home"
        
        # Add another location
        location_manager.add_location("Work", 36.0, -81.0)
        
        # Check that it was added
        assert "Work" in location_manager.saved_locations
        assert location_manager.saved_locations["Work"] == {"lat": 36.0, "lon": -81.0}
        
        # Current location should still be Home
        assert location_manager.current_location == "Home"

    def test_remove_location(self, location_manager):
        """Test removing a location"""
        # Add locations
        location_manager.add_location("Home", 35.0, -80.0)
        location_manager.add_location("Work", 36.0, -81.0)
        
        # Remove a non-current location
        result = location_manager.remove_location("Work")
        assert result is True
        assert "Work" not in location_manager.saved_locations
        assert location_manager.current_location == "Home"
        
        # Remove the current location
        result = location_manager.remove_location("Home")
        assert result is True
        assert "Home" not in location_manager.saved_locations
        assert location_manager.current_location is None
        
        # Try to remove a non-existent location
        result = location_manager.remove_location("Nonexistent")
        assert result is False

    def test_set_current_location(self, location_manager):
        """Test setting the current location"""
        # Add locations
        location_manager.add_location("Home", 35.0, -80.0)
        location_manager.add_location("Work", 36.0, -81.0)
        
        # Set current location
        result = location_manager.set_current_location("Work")
        assert result is True
        assert location_manager.current_location == "Work"
        
        # Try to set a non-existent location
        result = location_manager.set_current_location("Nonexistent")
        assert result is False
        assert location_manager.current_location == "Work"  # Unchanged

    def test_get_current_location(self, location_manager):
        """Test getting the current location"""
        # When no location is set
        assert location_manager.get_current_location() is None
        
        # Add a location
        location_manager.add_location("Home", 35.0, -80.0)
        
        # Check current location
        current = location_manager.get_current_location()
        assert current == ("Home", 35.0, -80.0)

    def test_get_all_locations(self, location_manager):
        """Test getting all locations"""
        # When no locations are saved
        assert location_manager.get_all_locations() == []
        
        # Add locations
        location_manager.add_location("Home", 35.0, -80.0)
        location_manager.add_location("Work", 36.0, -81.0)
        
        # Check all locations
        all_locations = location_manager.get_all_locations()
        assert sorted(all_locations) == sorted(["Home", "Work"])

    def test_load_locations(self, temp_config_dir):
        """Test loading locations from file"""
        # Create a locations file
        test_data = {
            "locations": {
                "Home": {"lat": 35.0, "lon": -80.0},
                "Work": {"lat": 36.0, "lon": -81.0}
            },
            "current": "Home"
        }
        
        locations_file = os.path.join(temp_config_dir, "locations.json")
        with open(locations_file, 'w') as f:
            json.dump(test_data, f)
        
        # Create a new location manager to load the file
        manager = LocationManager(config_dir=temp_config_dir)
        
        # Check that locations were loaded
        assert manager.saved_locations == test_data["locations"]
        assert manager.current_location == test_data["current"]

    def test_save_locations(self, location_manager):
        """Test saving locations to file"""
        # Add locations
        location_manager.add_location("Home", 35.0, -80.0)
        location_manager.add_location("Work", 36.0, -81.0)
        
        # Check that the file exists
        assert os.path.exists(location_manager.locations_file)
        
        # Read the file and check contents
        with open(location_manager.locations_file, 'r') as f:
            data = json.load(f)
            
        assert data["locations"] == {
            "Home": {"lat": 35.0, "lon": -80.0},
            "Work": {"lat": 36.0, "lon": -81.0}
        }
        assert data["current"] == "Home"
