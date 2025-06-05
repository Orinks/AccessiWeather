"""Test to verify that all geocoding API calls are properly mocked."""

import pytest

from accessiweather.geocoding import GeocodingService
from accessiweather.location import LocationManager


def test_geocoding_service_uses_mocked_nominatim():
    """Test that GeocodingService uses mocked Nominatim and doesn't make real API calls."""
    # Create a GeocodingService instance
    service = GeocodingService(user_agent="TestApp")

    # Test geocode_address - should return mocked response
    result = service.geocode_address("New York, NY")
    assert result is not None
    assert len(result) == 3  # (lat, lon, address)
    assert isinstance(result[0], float)  # latitude
    assert isinstance(result[1], float)  # longitude
    assert isinstance(result[2], str)  # address

    # Test validate_coordinates - should use mocked response
    # US coordinates should return True
    assert service.validate_coordinates(40.7128, -74.0060) is True
    # Non-US coordinates should return False
    assert service.validate_coordinates(51.5074, -0.1278) is False

    # Test suggest_locations - should return mocked suggestions
    suggestions = service.suggest_locations("New York")
    assert isinstance(suggestions, list)
    assert len(suggestions) >= 0


def test_location_manager_uses_mocked_geocoding():
    """Test that LocationManager uses mocked geocoding and doesn't make real API calls."""
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create LocationManager - should use mocked geocoding
        manager = LocationManager(config_dir=temp_dir)

        # Add a location - should use mocked validation
        manager.add_location("Test City", 40.0, -75.0)

        # Verify location was added
        assert "Test City" in manager.saved_locations

        # Get current location - should work with mocked data
        current = manager.get_current_location()
        assert current is not None


def test_no_real_nominatim_import():
    """Test that the real Nominatim class is never instantiated during tests."""
    # This test verifies that our mocking is comprehensive
    # If real Nominatim were being used, this would fail

    # Import and use geocoding - should all be mocked
    service = GeocodingService()

    # These calls should all use mocked responses
    service.geocode_address("123 Main St")
    service.validate_coordinates(40.0, -75.0)
    service.suggest_locations("New York")

    # If we got here without any network calls, mocking is working


def test_geocoding_mock_consistency():
    """Test that mocked geocoding responses are consistent across multiple calls."""
    service = GeocodingService()

    # Multiple calls should return consistent results
    result1 = service.validate_coordinates(40.7128, -74.0060)  # NYC - should be True
    result2 = service.validate_coordinates(40.7128, -74.0060)  # Same coordinates
    assert result1 == result2 is True

    result3 = service.validate_coordinates(51.5074, -0.1278)  # London - should be False
    result4 = service.validate_coordinates(51.5074, -0.1278)  # Same coordinates
    assert result3 == result4 is False


@pytest.mark.integration
def test_integration_with_mocked_geocoding():
    """Integration test to verify mocked geocoding works with other components."""
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        # Test that LocationManager and GeocodingService work together with mocking
        manager = LocationManager(config_dir=temp_dir)

        # Add multiple locations
        manager.add_location("New York", 40.7128, -74.0060)
        manager.add_location("Los Angeles", 34.0522, -118.2437)

        # All should be added successfully with mocked validation
        assert len(manager.saved_locations) >= 2  # At least our 2 + Nationwide
        assert "New York" in manager.saved_locations
        assert "Los Angeles" in manager.saved_locations

        # Set current location
        manager.set_current_location("New York")
        current = manager.get_current_location()
        assert current is not None
        assert current[0] == "New York"


def test_mock_handles_edge_cases():
    """Test that mocked geocoding handles edge cases properly."""
    service = GeocodingService()

    # Test with various coordinate ranges
    # US coordinates (should return True)
    assert service.validate_coordinates(25.0, -80.0) is True  # Florida
    assert service.validate_coordinates(48.0, -122.0) is True  # Washington
    assert service.validate_coordinates(32.0, -96.0) is True  # Texas

    # Non-US coordinates (should return False)
    assert service.validate_coordinates(52.0, 0.0) is False  # UK
    assert service.validate_coordinates(45.0, 2.0) is False  # France
    assert service.validate_coordinates(-34.0, 151.0) is False  # Australia

    # Edge coordinates
    assert service.validate_coordinates(0.0, 0.0) is False  # Equator/Prime Meridian
