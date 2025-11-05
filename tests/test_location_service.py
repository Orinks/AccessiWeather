"""Tests for LocationService."""

from unittest.mock import Mock

import pytest

from accessiweather.location import (
    NATIONWIDE_LAT,
    NATIONWIDE_LOCATION_NAME,
    NATIONWIDE_LON,
    LocationManager,
)
from accessiweather.services.location_service import LocationService


@pytest.fixture
def mock_location_manager():
    """Create a mock LocationManager."""
    manager = Mock(spec=LocationManager)
    manager.saved_locations = {
        "New York": {"lat": 40.7128, "lon": -74.0060},
        "Los Angeles": {"lat": 34.0522, "lon": -118.2437},
    }
    return manager


@pytest.fixture
def location_service(mock_location_manager):
    """Create a LocationService instance with mock manager."""
    return LocationService(mock_location_manager)


class TestLocationService:
    """Test LocationService class."""

    def test_initialization(self, mock_location_manager):
        """Test LocationService initialization."""
        service = LocationService(mock_location_manager)
        assert service.location_manager == mock_location_manager

    def test_update_data_source(self, location_service, mock_location_manager):
        """Test updating data source."""
        location_service.update_data_source("weatherapi")
        mock_location_manager.update_data_source.assert_called_once_with("weatherapi")

    def test_update_data_source_nws(self, location_service, mock_location_manager):
        """Test updating data source to NWS."""
        location_service.update_data_source("nws")
        mock_location_manager.update_data_source.assert_called_once_with("nws")

    def test_update_data_source_auto(self, location_service, mock_location_manager):
        """Test updating data source to auto."""
        location_service.update_data_source("auto")
        mock_location_manager.update_data_source.assert_called_once_with("auto")

    def test_get_current_location(self, location_service, mock_location_manager):
        """Test getting current location."""
        expected = ("New York", 40.7128, -74.0060)
        mock_location_manager.get_current_location.return_value = expected
        result = location_service.get_current_location()
        assert result == expected
        mock_location_manager.get_current_location.assert_called_once()

    def test_get_current_location_none(self, location_service, mock_location_manager):
        """Test getting current location when none is set."""
        mock_location_manager.get_current_location.return_value = None
        result = location_service.get_current_location()
        assert result is None

    def test_get_current_location_name(self, location_service, mock_location_manager):
        """Test getting current location name."""
        mock_location_manager.get_current_location_name.return_value = "New York"
        result = location_service.get_current_location_name()
        assert result == "New York"
        mock_location_manager.get_current_location_name.assert_called_once()

    def test_get_current_location_name_none(self, location_service, mock_location_manager):
        """Test getting current location name when none is set."""
        mock_location_manager.get_current_location_name.return_value = None
        result = location_service.get_current_location_name()
        assert result is None

    def test_get_all_locations(self, location_service, mock_location_manager):
        """Test getting all locations."""
        expected = ["New York", "Los Angeles"]
        mock_location_manager.get_all_locations.return_value = expected
        result = location_service.get_all_locations()
        assert result == expected
        mock_location_manager.get_all_locations.assert_called_once()

    def test_get_all_locations_empty(self, location_service, mock_location_manager):
        """Test getting all locations when empty."""
        mock_location_manager.get_all_locations.return_value = []
        result = location_service.get_all_locations()
        assert result == []

    def test_add_location(self, location_service, mock_location_manager):
        """Test adding a new location."""
        mock_location_manager.add_location.return_value = True
        result = location_service.add_location("Chicago", 41.8781, -87.6298)
        assert result is True
        mock_location_manager.add_location.assert_called_once_with("Chicago", 41.8781, -87.6298)

    def test_add_location_outside_us(self, location_service, mock_location_manager):
        """Test adding a location outside US NWS coverage."""
        mock_location_manager.add_location.return_value = False
        result = location_service.add_location("London", 51.5074, -0.1278)
        assert result is False
        mock_location_manager.add_location.assert_called_once_with("London", 51.5074, -0.1278)

    def test_remove_location(self, location_service, mock_location_manager):
        """Test removing a location."""
        mock_location_manager.remove_location.return_value = True
        result = location_service.remove_location("New York")
        assert result is True
        mock_location_manager.remove_location.assert_called_once_with("New York")

    def test_remove_location_not_found(self, location_service, mock_location_manager):
        """Test removing a non-existent location."""
        mock_location_manager.remove_location.return_value = False
        result = location_service.remove_location("NonExistent")
        assert result is False
        mock_location_manager.remove_location.assert_called_once_with("NonExistent")

    def test_set_current_location(self, location_service, mock_location_manager):
        """Test setting current location."""
        location_service.set_current_location("Los Angeles")
        mock_location_manager.set_current_location.assert_called_once_with("Los Angeles")

    def test_get_location_coordinates(self, location_service):
        """Test getting location coordinates."""
        result = location_service.get_location_coordinates("New York")
        assert result == (40.7128, -74.0060)

    def test_get_location_coordinates_not_found(self, location_service):
        """Test getting coordinates for non-existent location."""
        result = location_service.get_location_coordinates("NonExistent")
        assert result is None

    def test_get_nationwide_location(self, location_service):
        """Test getting Nationwide location."""
        result = location_service.get_nationwide_location()
        assert result == (NATIONWIDE_LOCATION_NAME, NATIONWIDE_LAT, NATIONWIDE_LON)
        assert result[0] == "Nationwide"
        assert isinstance(result[1], float)
        assert isinstance(result[2], float)

    def test_is_nationwide_location(self, location_service, mock_location_manager):
        """Test checking if location is Nationwide."""
        mock_location_manager.is_nationwide_location.return_value = True
        result = location_service.is_nationwide_location(NATIONWIDE_LOCATION_NAME)
        assert result is True
        mock_location_manager.is_nationwide_location.assert_called_once_with(
            NATIONWIDE_LOCATION_NAME
        )

    def test_is_nationwide_location_false(self, location_service, mock_location_manager):
        """Test checking if location is not Nationwide."""
        mock_location_manager.is_nationwide_location.return_value = False
        result = location_service.is_nationwide_location("New York")
        assert result is False

    def test_add_location_logging(self, location_service, mock_location_manager, caplog):
        """Test that adding location logs correctly."""
        import logging

        caplog.set_level(logging.INFO)
        mock_location_manager.add_location.return_value = True
        location_service.add_location("Seattle", 47.6062, -122.3321)
        assert "Adding location: Seattle" in caplog.text

    def test_remove_location_logging(self, location_service, mock_location_manager, caplog):
        """Test that removing location logs correctly."""
        import logging

        caplog.set_level(logging.INFO)
        mock_location_manager.remove_location.return_value = True
        location_service.remove_location("Seattle")
        assert "Removing location: Seattle" in caplog.text

    def test_set_current_location_logging(self, location_service, mock_location_manager, caplog):
        """Test that setting current location logs correctly."""
        import logging

        caplog.set_level(logging.INFO)
        location_service.set_current_location("Seattle")
        assert "Setting current location: Seattle" in caplog.text

    def test_get_location_coordinates_multiple_locations(self, mock_location_manager):
        """Test coordinates retrieval with multiple saved locations."""
        mock_location_manager.saved_locations = {
            "Boston": {"lat": 42.3601, "lon": -71.0589},
            "Miami": {"lat": 25.7617, "lon": -80.1918},
            "Denver": {"lat": 39.7392, "lon": -104.9903},
        }
        service = LocationService(mock_location_manager)
        assert service.get_location_coordinates("Boston") == (42.3601, -71.0589)
        assert service.get_location_coordinates("Miami") == (25.7617, -80.1918)
        assert service.get_location_coordinates("Denver") == (39.7392, -104.9903)

    def test_service_with_empty_locations(self, mock_location_manager):
        """Test service behavior with no saved locations."""
        mock_location_manager.saved_locations = {}
        service = LocationService(mock_location_manager)
        assert service.get_location_coordinates("Any") is None
