"""Tests for the LocationService class."""

from unittest.mock import patch

import pytest

from accessiweather.services.location_service import LocationService


@pytest.fixture
def mock_location_manager():
    """Create a mock location manager."""
    # Use patch.object to create a mock with the correct spec
    with patch('accessiweather.location.LocationManager', autospec=True) as mock_manager_class:
        # Create an instance of the mock
        manager = mock_manager_class.return_value

        # Default values, tests can override
        manager.get_current_location.return_value = ("Test City", 35.0, -80.0)
        manager.get_current_location_name.return_value = "Test City"
        manager.get_all_locations.return_value = ["Test City"]
        manager.saved_locations = {"Test City": {"lat": 35.0, "lon": -80.0}}
        manager.is_nationwide_location.return_value = False

        yield manager


@pytest.fixture
def location_service(mock_location_manager):
    """Create a LocationService instance with a mock location manager."""
    return LocationService(mock_location_manager)


class TestLocationService:
    """Test suite for LocationService."""

    def test_get_nationwide_location(self, location_service):
        """Test getting the Nationwide location from the service."""
        result = location_service.get_nationwide_location()
        assert result == ("Nationwide", 39.8283, -98.5795)

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
        # Set up mock saved_locations
        test_locations = {
            "Test City": {"lat": 35.0, "lon": -80.0},
            "Another City": {"lat": 40.0, "lon": -75.0},
        }
        mock_location_manager.saved_locations = test_locations

        # Call the method
        result = location_service.get_location_coordinates("Test City")

        # Verify the result
        assert result == (35.0, -80.0)

    def test_get_location_coordinates_not_found(self, location_service, mock_location_manager):
        """Test getting coordinates for a non-existent location."""
        # Set up mock saved_locations
        test_locations = {"Test City": {"lat": 35.0, "lon": -80.0}}
        mock_location_manager.saved_locations = test_locations

        # Call the method
        result = location_service.get_location_coordinates("Non-existent City")

        # Verify the result
        assert result is None

    def test_is_nationwide_location(self, location_service, mock_location_manager):
        """Test checking if a location is the Nationwide location."""
        # Set up mock return value
        mock_location_manager.is_nationwide_location.return_value = True

        # Call the method
        result = location_service.is_nationwide_location("Nationwide")

        # Verify the result
        assert result is True
        mock_location_manager.is_nationwide_location.assert_called_once_with("Nationwide")
