"""Tests for the LocationManager class."""

import json
import os
from unittest.mock import patch

import pytest

from accessiweather.location import (
    NATIONWIDE_LAT,
    NATIONWIDE_LOCATION_NAME,
    NATIONWIDE_LON,
    LocationManager,
)

# Sample test data
SAMPLE_LOCATIONS = {
    "Test City": {"lat": 40.0, "lon": -75.0},
    "Another Place": {"lat": 35.0, "lon": -80.0},
    NATIONWIDE_LOCATION_NAME: {"lat": NATIONWIDE_LAT, "lon": NATIONWIDE_LON},
}

SAMPLE_CONFIG = {"locations": SAMPLE_LOCATIONS, "current": "Test City"}


@pytest.fixture
def mock_config_dir(tmp_path):
    """Create a temporary directory for config files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return str(config_dir)


@pytest.fixture
def location_manager(mock_config_dir):
    """Create a LocationManager instance with a mock config directory."""
    return LocationManager(config_dir=mock_config_dir)


def test_init_creates_config_dir(mock_config_dir):
    """Test that initialization creates the config directory."""
    # Remove the directory created by the fixture
    os.rmdir(mock_config_dir)

    # Initialize LocationManager
    LocationManager(config_dir=mock_config_dir)

    # Check that directory was created
    assert os.path.exists(mock_config_dir)


def test_init_loads_existing_config(mock_config_dir):
    """Test loading existing configuration."""
    # Create a locations file with test data
    locations_file = os.path.join(mock_config_dir, "locations.json")
    with open(locations_file, "w") as f:
        json.dump(SAMPLE_CONFIG, f)

    # Initialize LocationManager
    manager = LocationManager(config_dir=mock_config_dir)

    # Check that data was loaded correctly
    assert manager.saved_locations == SAMPLE_CONFIG["locations"]
    assert manager.current_location == SAMPLE_CONFIG["current"]


def test_init_ensures_nationwide_location():
    """Test that initialization always includes the Nationwide location."""
    manager = LocationManager()

    assert NATIONWIDE_LOCATION_NAME in manager.saved_locations
    assert manager.saved_locations[NATIONWIDE_LOCATION_NAME] == {
        "lat": NATIONWIDE_LAT,
        "lon": NATIONWIDE_LON,
    }


def test_add_location(location_manager):
    """Test adding a new location."""
    name = "New City"
    lat, lon = 45.0, -70.0

    location_manager.add_location(name, lat, lon)

    assert name in location_manager.saved_locations
    assert location_manager.saved_locations[name] == {"lat": lat, "lon": lon}
    assert location_manager.current_location == name


def test_add_location_cannot_overwrite_nationwide(location_manager):
    """Test that adding a location cannot overwrite the Nationwide location."""
    lat, lon = 45.0, -70.0

    location_manager.add_location(NATIONWIDE_LOCATION_NAME, lat, lon)

    # Check that Nationwide location remains unchanged
    assert location_manager.saved_locations[NATIONWIDE_LOCATION_NAME] == {
        "lat": NATIONWIDE_LAT,
        "lon": NATIONWIDE_LON,
    }


def test_remove_location(location_manager):
    """Test removing a location."""
    # Add a location first
    name = "Test City"
    lat, lon = 40.0, -75.0
    location_manager.add_location(name, lat, lon)

    # Remove it
    result = location_manager.remove_location(name)

    assert result is True
    assert name not in location_manager.saved_locations


def test_remove_location_updates_current(location_manager):
    """Test that removing the current location updates the current location."""
    # Add two locations
    location_manager.add_location("City1", 40.0, -75.0)
    location_manager.add_location("City2", 35.0, -80.0)
    location_manager.set_current_location("City1")

    # Remove the current location
    location_manager.remove_location("City1")

    # Current location should be updated to City2
    assert location_manager.current_location == "City2"


def test_remove_location_cannot_remove_nationwide(location_manager):
    """Test that the Nationwide location cannot be removed."""
    result = location_manager.remove_location(NATIONWIDE_LOCATION_NAME)

    assert result is False
    assert NATIONWIDE_LOCATION_NAME in location_manager.saved_locations


def test_set_current_location(location_manager):
    """Test setting the current location."""
    # Add a location first
    name = "Test City"
    lat, lon = 40.0, -75.0
    location_manager.add_location(name, lat, lon)

    # Set it as current
    result = location_manager.set_current_location(name)

    assert result is True
    assert location_manager.current_location == name


def test_set_current_location_nonexistent(location_manager):
    """Test setting a nonexistent location as current."""
    result = location_manager.set_current_location("Nonexistent")

    assert result is False
    assert location_manager.current_location != "Nonexistent"


def test_get_current_location(location_manager):
    """Test getting the current location."""
    # Add a location and set it as current
    name = "Test City"
    lat, lon = 40.0, -75.0
    location_manager.add_location(name, lat, lon)
    location_manager.set_current_location(name)

    result = location_manager.get_current_location()

    assert result == (name, lat, lon)


def test_get_current_location_none(location_manager):
    """Test getting current location when none is set."""
    result = location_manager.get_current_location()

    assert result is None


def test_get_current_location_name(location_manager):
    """Test getting the current location name."""
    # Add a location and set it as current
    name = "Test City"
    lat, lon = 40.0, -75.0
    location_manager.add_location(name, lat, lon)
    location_manager.set_current_location(name)

    result = location_manager.get_current_location_name()

    assert result == name


def test_get_all_locations(location_manager):
    """Test getting all location names."""
    # Add some locations
    location_manager.add_location("City1", 40.0, -75.0)
    location_manager.add_location("City2", 35.0, -80.0)

    result = location_manager.get_all_locations()

    assert set(result) == {"City1", "City2", NATIONWIDE_LOCATION_NAME}


def test_set_locations(location_manager):
    """Test setting all locations at once."""
    locations = {"City1": {"lat": 40.0, "lon": -75.0}, "City2": {"lat": 35.0, "lon": -80.0}}
    current = "City1"

    location_manager.set_locations(locations, current)

    # Check that locations were set (including Nationwide)
    assert "City1" in location_manager.saved_locations
    assert "City2" in location_manager.saved_locations
    assert NATIONWIDE_LOCATION_NAME in location_manager.saved_locations
    assert location_manager.current_location == current


def test_set_locations_ensures_nationwide(location_manager):
    """Test that set_locations always includes the Nationwide location."""
    locations = {"City1": {"lat": 40.0, "lon": -75.0}}

    location_manager.set_locations(locations)

    assert NATIONWIDE_LOCATION_NAME in location_manager.saved_locations
    assert location_manager.saved_locations[NATIONWIDE_LOCATION_NAME] == {
        "lat": NATIONWIDE_LAT,
        "lon": NATIONWIDE_LON,
    }


def test_is_nationwide_location(location_manager):
    """Test checking if a location is the Nationwide location."""
    assert location_manager.is_nationwide_location(NATIONWIDE_LOCATION_NAME) is True
    assert location_manager.is_nationwide_location("Some Other City") is False


def test_save_and_load_locations(mock_config_dir):
    """Test saving and loading locations from file."""
    # Create a manager and add some locations
    manager = LocationManager(config_dir=mock_config_dir)
    manager.add_location("City1", 40.0, -75.0)
    manager.add_location("City2", 35.0, -80.0)
    manager.set_current_location("City1")

    # Create a new manager to load the saved data
    new_manager = LocationManager(config_dir=mock_config_dir)

    # Check that data was saved and loaded correctly
    assert new_manager.saved_locations == manager.saved_locations
    assert new_manager.current_location == manager.current_location


def test_update_data_source():
    """Test updating the data source and geocoding service."""
    from unittest.mock import patch

    # Create a manager with NWS data source
    manager = LocationManager(data_source="nws")
    assert manager.data_source == "nws"

    # Update to WeatherAPI data source
    with patch("accessiweather.location.GeocodingService") as mock_geocoding_service:
        mock_new_service = mock_geocoding_service.return_value

        manager.update_data_source("weatherapi")

        # Verify data source was updated
        assert manager.data_source == "weatherapi"

        # Verify new geocoding service was created with correct parameters
        mock_geocoding_service.assert_called_once_with(
            user_agent="AccessiWeather-LocationManager", data_source="weatherapi"
        )

        # Verify the geocoding service was replaced
        assert manager.geocoding_service == mock_new_service


def test_save_locations_handles_error(location_manager):
    """Test that saving locations handles file write errors gracefully."""
    with patch("builtins.open", side_effect=IOError("Test error")):
        # This should not raise an exception
        location_manager._save_locations()


def test_load_locations_handles_error(mock_config_dir):
    """Test that loading locations handles file read errors gracefully."""
    # Create an invalid JSON file
    locations_file = os.path.join(mock_config_dir, "locations.json")
    with open(locations_file, "w") as f:
        f.write("invalid json")

    # This should not raise an exception
    manager = LocationManager(config_dir=mock_config_dir)

    # Check that default values were used
    assert NATIONWIDE_LOCATION_NAME in manager.saved_locations
    assert manager.current_location is None


def test_load_locations_filters_non_us_locations(mock_config_dir):
    """Test that loading locations filters out non-US locations."""
    # Create a locations file with both US and non-US locations
    locations_file = os.path.join(mock_config_dir, "locations.json")

    # Sample data with US and non-US locations
    sample_data = {
        "locations": {
            "US City": {"lat": 40.0, "lon": -75.0},  # US location
            "London": {"lat": 51.5074, "lon": -0.1278},  # UK location
            "Toronto": {"lat": 43.6532, "lon": -79.3832},  # Canada location
            NATIONWIDE_LOCATION_NAME: {"lat": NATIONWIDE_LAT, "lon": NATIONWIDE_LON},
        },
        "current": "US City",
    }

    with open(locations_file, "w") as f:
        json.dump(sample_data, f)

    # Mock the validate_coordinates method to simulate validation
    with patch("accessiweather.geocoding.GeocodingService.validate_coordinates") as mock_validate:
        # Set up the mock to return True for US locations and False for non-US
        def validate_side_effect(lat, lon, us_only=True):
            # Return True for US City and Nationwide, False for others
            if (lat == 40.0 and lon == -75.0) or (lat == NATIONWIDE_LAT and lon == NATIONWIDE_LON):
                return True
            return False

        mock_validate.side_effect = validate_side_effect

        # Initialize LocationManager which will load and validate locations
        manager = LocationManager(config_dir=mock_config_dir)

        # Check that only US locations were kept
        assert "US City" in manager.saved_locations
        assert NATIONWIDE_LOCATION_NAME in manager.saved_locations
        assert "London" not in manager.saved_locations
        assert "Toronto" not in manager.saved_locations

        # Check that current location is still set to the US location
        assert manager.current_location == "US City"

        # Verify the validate_coordinates method was called for each location
        assert mock_validate.call_count == 3  # Called for all except Nationwide


def test_load_locations_resets_current_if_non_us(mock_config_dir):
    """Test that loading locations resets current location if it's non-US."""
    # Create a locations file with a non-US current location
    locations_file = os.path.join(mock_config_dir, "locations.json")

    # Sample data with US and non-US locations, current set to non-US
    sample_data = {
        "locations": {
            "US City": {"lat": 40.0, "lon": -75.0},  # US location
            "London": {"lat": 51.5074, "lon": -0.1278},  # UK location (current)
            NATIONWIDE_LOCATION_NAME: {"lat": NATIONWIDE_LAT, "lon": NATIONWIDE_LON},
        },
        "current": "London",
    }

    with open(locations_file, "w") as f:
        json.dump(sample_data, f)

    # Mock the validate_coordinates method
    with patch("accessiweather.geocoding.GeocodingService.validate_coordinates") as mock_validate:
        # Set up the mock to return True for US locations and False for non-US
        def validate_side_effect(lat, lon, us_only=True):
            # Return True for US City and Nationwide, False for others
            if (lat == 40.0 and lon == -75.0) or (lat == NATIONWIDE_LAT and lon == NATIONWIDE_LON):
                return True
            return False

        mock_validate.side_effect = validate_side_effect

        # Initialize LocationManager which will load and validate locations
        manager = LocationManager(config_dir=mock_config_dir)

        # Check that only US locations were kept
        assert "US City" in manager.saved_locations
        assert NATIONWIDE_LOCATION_NAME in manager.saved_locations
        assert "London" not in manager.saved_locations

        # Check that current location was reset to a valid location
        # When current is invalid, it defaults to Nationwide first
        assert manager.current_location == NATIONWIDE_LOCATION_NAME
