"""Tests for the LocationService class."""

from unittest.mock import MagicMock

import pytest

from accessiweather.location import NATIONWIDE_LAT, NATIONWIDE_LOCATION_NAME, NATIONWIDE_LON
from accessiweather.services.location_service import LocationService


# Fixture to create a mocked LocationManager
@pytest.fixture
def mock_location_manager():
    manager = MagicMock()
    # Set default return values for methods that return something
    manager.get_current_location.return_value = None
    manager.get_current_location_name.return_value = None
    manager.get_all_locations.return_value = []
    manager.remove_location.return_value = False
    manager.set_current_location.return_value = False
    manager.is_nationwide_location.return_value = False
    manager.saved_locations = {}  # Initialize saved_locations
    return manager


# Fixture to create a LocationService instance with the mocked manager
@pytest.fixture
def location_service(mock_location_manager):
    return LocationService(mock_location_manager)


# --- Test Cases ---


def test_get_current_location(location_service, mock_location_manager):
    """Test getting the current location."""
    expected_location = ("Test City", 40.0, -75.0)
    mock_location_manager.get_current_location.return_value = expected_location

    result = location_service.get_current_location()

    assert result == expected_location
    mock_location_manager.get_current_location.assert_called_once()


def test_get_current_location_name(location_service, mock_location_manager):
    """Test getting the current location name."""
    expected_name = "Test City"
    mock_location_manager.get_current_location_name.return_value = expected_name

    result = location_service.get_current_location_name()

    assert result == expected_name
    mock_location_manager.get_current_location_name.assert_called_once()


def test_get_all_locations(location_service, mock_location_manager):
    """Test getting all location names."""
    expected_locations = ["Test City", "Another Place", NATIONWIDE_LOCATION_NAME]
    mock_location_manager.get_all_locations.return_value = expected_locations

    result = location_service.get_all_locations()

    assert result == expected_locations
    mock_location_manager.get_all_locations.assert_called_once()


def test_add_location(location_service, mock_location_manager):
    """Test adding a new location."""
    name, lat, lon = "New Place", 35.0, -80.0

    location_service.add_location(name, lat, lon)

    mock_location_manager.add_location.assert_called_once_with(name, lat, lon)


def test_remove_location(location_service, mock_location_manager):
    """Test removing a location."""
    name = "Test City"
    mock_location_manager.remove_location.return_value = True  # Simulate successful removal

    result = location_service.remove_location(name)

    assert result is True
    mock_location_manager.remove_location.assert_called_once_with(name)


def test_remove_location_nationwide(location_service, mock_location_manager):
    """Test attempting to remove the Nationwide location (should delegate check)."""
    # LocationManager handles the logic of preventing removal,
    # so the service should just pass the call through.
    mock_location_manager.remove_location.return_value = (
        False  # Simulate manager preventing removal
    )

    result = location_service.remove_location(NATIONWIDE_LOCATION_NAME)

    assert result is False
    mock_location_manager.remove_location.assert_called_once_with(NATIONWIDE_LOCATION_NAME)


def test_set_current_location(location_service, mock_location_manager):
    """Test setting the current location."""
    name = "Test City"
    mock_location_manager.set_current_location.return_value = True  # Simulate success

    location_service.set_current_location(name)

    mock_location_manager.set_current_location.assert_called_once_with(name)


def test_get_location_coordinates_found(location_service, mock_location_manager):
    """Test getting coordinates for an existing location."""
    name = "Test City"
    lat, lon = 40.0, -75.0
    mock_location_manager.saved_locations = {
        name: {"lat": lat, "lon": lon},
        NATIONWIDE_LOCATION_NAME: {"lat": NATIONWIDE_LAT, "lon": NATIONWIDE_LON},
    }

    result = location_service.get_location_coordinates(name)

    assert result == (lat, lon)


def test_get_location_coordinates_not_found(location_service, mock_location_manager):
    """Test getting coordinates for a non-existent location."""
    mock_location_manager.saved_locations = {
        NATIONWIDE_LOCATION_NAME: {"lat": NATIONWIDE_LAT, "lon": NATIONWIDE_LON}
    }

    result = location_service.get_location_coordinates("NonExistent")

    assert result is None


def test_get_nationwide_location(location_service):
    """Test getting the nationwide location details."""
    # This method doesn't use the manager, it uses constants.
    expected_result = (NATIONWIDE_LOCATION_NAME, NATIONWIDE_LAT, NATIONWIDE_LON)
    result = location_service.get_nationwide_location()
    assert result == expected_result


def test_is_nationwide_location_true(location_service, mock_location_manager):
    """Test checking if a location is the Nationwide location (True case)."""
    mock_location_manager.is_nationwide_location.return_value = True

    result = location_service.is_nationwide_location(NATIONWIDE_LOCATION_NAME)

    assert result is True
    mock_location_manager.is_nationwide_location.assert_called_once_with(NATIONWIDE_LOCATION_NAME)


def test_is_nationwide_location_false(location_service, mock_location_manager):
    """Test checking if a location is the Nationwide location (False case)."""
    mock_location_manager.is_nationwide_location.return_value = False
    name = "Test City"

    result = location_service.is_nationwide_location(name)

    assert result is False
    mock_location_manager.is_nationwide_location.assert_called_once_with(name)
