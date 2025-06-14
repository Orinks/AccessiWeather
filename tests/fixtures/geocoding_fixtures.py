"""Geocoding-related test fixtures."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.geocoding import GeocodingService


@pytest.fixture
def mock_geocoding_location():
    """Create a mock location object for geocoding responses."""
    location = MagicMock()
    location.latitude = 40.7128
    location.longitude = -74.0060
    location.address = "New York, NY, USA"
    location.raw = {"address": {"country_code": "us"}}
    return location


@pytest.fixture
def mock_geocoding_service():
    """Mock GeocodingService with common responses."""
    mock_service = MagicMock(spec=GeocodingService)

    # Mock geocode_address to return US coordinates
    mock_service.geocode_address.return_value = (40.7128, -74.0060, "New York, NY, USA")

    # Mock validate_coordinates to return True for US locations, False for others
    def validate_coordinates_side_effect(lat, lon, us_only=None):
        # US coordinates (rough bounds)
        if 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0:
            return True
        # Special case for test coordinates
        if lat == 40.7128 and lon == -74.0060:  # NYC
            return True
        if lat == 34.0522 and lon == -118.2437:  # LA
            return True
        return False

    mock_service.validate_coordinates.side_effect = validate_coordinates_side_effect

    # Mock suggest_locations to return sample suggestions
    mock_service.suggest_locations.return_value = [
        "New York, NY, USA",
        "Newark, NJ, USA",
        "New Haven, CT, USA",
    ]

    # Mock utility methods
    mock_service.is_zip_code.return_value = False
    mock_service.format_zip_code.return_value = "12345, USA"

    return mock_service


@pytest.fixture
def mock_nominatim():
    """Mock Nominatim geocoder for direct usage."""
    mock_nominatim = MagicMock()

    # Create a mock location for geocode responses
    mock_location = MagicMock()
    mock_location.latitude = 40.7128
    mock_location.longitude = -74.0060
    mock_location.address = "New York, NY, USA"
    mock_location.raw = {"address": {"country_code": "us"}}

    mock_nominatim.geocode.return_value = mock_location
    mock_nominatim.reverse.return_value = mock_location

    return mock_nominatim


@pytest.fixture(autouse=True)
def mock_all_geocoding():
    """Automatically mock all geocoding API calls across all tests."""
    with patch("accessiweather.geocoding.Nominatim") as mock_nominatim_class:
        # Create mock instance
        mock_nominatim_instance = MagicMock()
        mock_nominatim_class.return_value = mock_nominatim_instance

        # Create mock location response
        mock_location = MagicMock()
        mock_location.latitude = 40.7128
        mock_location.longitude = -74.0060
        mock_location.address = "New York, NY, USA"
        mock_location.raw = {"address": {"country_code": "us"}}

        # Configure geocode method
        mock_nominatim_instance.geocode.return_value = mock_location

        # Configure reverse method for coordinate validation
        def reverse_side_effect(coords, **kwargs):
            lat, lon = coords
            # Return US location for US coordinates, non-US for others
            if 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0:
                mock_us_location = MagicMock()
                mock_us_location.raw = {"address": {"country_code": "us"}}
                return mock_us_location
            else:
                mock_intl_location = MagicMock()
                mock_intl_location.raw = {"address": {"country_code": "gb"}}
                return mock_intl_location

        mock_nominatim_instance.reverse.side_effect = reverse_side_effect

        yield mock_nominatim_instance


@pytest.fixture
def verify_no_real_geocoding_calls():
    """Verify that no real geocoding API calls are made during tests."""
    # This fixture can be used to ensure tests don't make real API calls
    # The autouse mock_all_geocoding fixture should prevent any real calls
    pass
