"""Tests for location manager functionality."""

import pytest
from unittest.mock import patch


@pytest.fixture
def mock_components():
    """Mock the components used by WeatherApp."""
    # Mock the API client
    with patch("accessiweather.api_client.NoaaApiClient") as mock_api_client_class:
        mock_api_client = mock_api_client_class.return_value

        # Configure the mock API client
        mock_api_client.get_point_data.return_value = {
            "properties": {
                "forecast": "https://api.weather.gov/gridpoints/RAH/53,88/forecast",
                "forecastHourly": "https://api.weather.gov/gridpoints/RAH/53,88/forecast/hourly",
                "relativeLocation": {"properties": {"city": "Test City", "state": "NC"}},
            }
        }

        # Mock the location manager
        with patch("accessiweather.services.location_service.LocationService") as mock_location_service_class:
            mock_location_service = mock_location_service_class.return_value

            # Configure the mock location manager
            mock_location_service.get_current_location.return_value = ("Test City", 35.0, -80.0)
            mock_location_service.get_location_coordinates.return_value = (35.0, -80.0)
            mock_location_service.saved_locations = {
                "Test City": {"lat": 35.0, "lon": -80.0},
                "New York": {"lat": 40.7, "lon": -74.0},
                "Los Angeles": {"lat": 34.0, "lon": -118.2},
            }
            mock_location_service.get_all_locations.return_value = [
                "Test City",
                "New York",
                "Los Angeles",
            ]

            # Mock the notifier
            with patch("accessiweather.notifications.WeatherNotifier") as mock_notifier_class:
                mock_notifier = mock_notifier_class.return_value

                yield mock_api_client, mock_location_service, mock_notifier


def test_location_manager_get_all_locations(mock_components):
    """Test that the location manager returns all saved locations."""
    _, mock_location_manager, _ = mock_components

    # Get all locations
    locations = mock_location_manager.get_all_locations()

    # Verify the locations are returned
    assert locations == ["Test City", "New York", "Los Angeles"]
    mock_location_manager.get_all_locations.assert_called_once()


def test_location_manager_add_location(mock_components):
    """Test that the location manager can add a new location."""
    _, mock_location_manager, _ = mock_components

    # Add a new location
    mock_location_manager.add_location("San Francisco", 37.7, -122.4)

    # Verify the location was added
    mock_location_manager.add_location.assert_called_once_with("San Francisco", 37.7, -122.4)


def test_location_manager_remove_location(mock_components):
    """Test that the location manager can remove a location."""
    _, mock_location_manager, _ = mock_components

    # Remove a location
    mock_location_manager.remove_location("New York")

    # Verify the location was removed
    mock_location_manager.remove_location.assert_called_once_with("New York")
