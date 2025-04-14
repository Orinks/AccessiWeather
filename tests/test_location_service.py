"""Tests for the LocationService class."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.location import LocationManager
from accessiweather.services.location_service import LocationService


@pytest.fixture
def mock_location_manager():
    """Create a mock location manager."""
    manager = MagicMock(spec=LocationManager)
    # Default values, tests can override
    manager.get_current_location.return_value = ("Test City", 35.0, -80.0)
    manager.get_current_location_name.return_value = "Test City"
    manager.get_all_locations.return_value = ["Test City"]
    manager.locations = {"Test City": (35.0, -80.0)}
    return manager


@pytest.fixture
def location_service(mock_location_manager):
    """Create a LocationService instance with a mock location manager."""
    return LocationService(mock_location_manager)


class TestLocationService:
    """Test suite for LocationService."""

    def test_init(self, mock_location_manager):
        """Test service initialization."""
        service = LocationService(mock_location_manager)
        assert service.location_manager == mock_location_manager

    def test_get_current_location(self, location_service, mock_location_manager):
        """Test getting the current location."""
        # Set up mock return value
        expected_location = ("Test City", 35.0, -80.0)
        mock_location_manager.get_current_location.return_value = expected_location

        # Call the method
        result = location_service.get_current_location()

        # Verify the result
        assert result == expected_location
        mock_location_manager.get_current_location.assert_called_once()

    def test_get_current_location_name(self, location_service, mock_location_manager):
        """Test getting the current location name."""
        # Set up mock return value
        expected_name = "Test City"
        mock_location_manager.get_current_location_name.return_value = expected_name

        # Call the method
        result = location_service.get_current_location_name()

        # Verify the result
        assert result == expected_name
        mock_location_manager.get_current_location_name.assert_called_once()

    def test_get_all_locations(self, location_service, mock_location_manager):
        """Test getting all locations."""
        # Set up mock return value
        expected_locations = ["Test City", "Another City"]
        mock_location_manager.get_all_locations.return_value = expected_locations

        # Call the method
        result = location_service.get_all_locations()

        # Verify the result
        assert result == expected_locations
        mock_location_manager.get_all_locations.assert_called_once()

    def test_add_location(self, location_service, mock_location_manager):
        """Test adding a location."""
        # Call the method
        location_service.add_location("New City", 40.0, -75.0)

        # Verify the method was called with the correct arguments
        mock_location_manager.add_location.assert_called_once_with("New City", 40.0, -75.0)

    def test_remove_location(self, location_service, mock_location_manager):
        """Test removing a location."""
        # Call the method
        location_service.remove_location("Test City")

        # Verify the method was called with the correct arguments
        mock_location_manager.remove_location.assert_called_once_with("Test City")

    def test_set_current_location(self, location_service, mock_location_manager):
        """Test setting the current location."""
        # Call the method
        location_service.set_current_location("Test City")

        # Verify the method was called with the correct arguments
        mock_location_manager.set_current_location.assert_called_once_with("Test City")

    def test_get_location_coordinates(self, location_service, mock_location_manager):
        """Test getting location coordinates."""
        # Set up mock locations
        mock_location_manager.locations = {
            "Test City": (35.0, -80.0),
            "Another City": (40.0, -75.0),
        }

        # Call the method
        result = location_service.get_location_coordinates("Test City")

        # Verify the result
        assert result == (35.0, -80.0)

    def test_get_location_coordinates_not_found(self, location_service, mock_location_manager):
        """Test getting coordinates for a non-existent location."""
        # Set up mock locations
        mock_location_manager.locations = {"Test City": (35.0, -80.0)}

        # Call the method
        result = location_service.get_location_coordinates("Non-existent City")

        # Verify the result
        assert result is None
