"""Tests for geocoding service."""

from unittest.mock import MagicMock, patch

import pytest
from geopy.exc import GeocoderServiceError, GeocoderTimedOut

from accessiweather.geocoding import GeocodingService

# --- Test Data ---

SAMPLE_ADDRESS = "123 Main St, Anytown, USA"
SAMPLE_ZIP_5 = "12345"
SAMPLE_ZIP_4 = "12345-6789"
SAMPLE_LAT = 35.123
SAMPLE_LON = -80.456
SAMPLE_DISPLAY_NAME = "123 Main Street, Anytown, State 12345, USA"

# --- Fixtures ---


@pytest.fixture
def mock_location():
    """Create a mock location object with required attributes."""
    location = MagicMock()
    location.latitude = SAMPLE_LAT
    location.longitude = SAMPLE_LON
    location.address = SAMPLE_DISPLAY_NAME
    return location


@pytest.fixture
def mock_nominatim_instance():
    """Create a mock Nominatim instance."""
    instance = MagicMock()
    # Pre-configure the geocode method
    instance.geocode = MagicMock()
    return instance


@pytest.fixture
def geocoding_service(mock_nominatim_instance):
    """Create a GeocodingService instance with mocked Nominatim."""
    # Patch Nominatim where it's used, not where it's defined
    with patch(
        "accessiweather.geocoding.Nominatim", return_value=mock_nominatim_instance
    ) as mock_nominatim_class:
        service = GeocodingService(user_agent="TestApp", timeout=5)
        # Store mocks for assertions as attributes for testing
        # We're adding these attributes just for testing purposes
        # They don't exist in the actual class
        setattr(service, "_mock_nominatim_class", mock_nominatim_class)
        setattr(service, "_mock_geolocator_instance", mock_nominatim_instance)
        yield service


# --- Tests ---


def test_init_mock_call():
    """Test that Nominatim is called with correct arguments during initialization."""
    with patch("accessiweather.geocoding.Nominatim") as mock_nominatim_class:
        service = GeocodingService(user_agent="TestApp", timeout=5)  # noqa: F841
        mock_nominatim_class.assert_called_once_with(user_agent="TestApp", timeout=5)


def test_init_instance_type():
    """Test that geolocator is assigned the mock instance."""
    with patch("accessiweather.geocoding.Nominatim") as mock_nominatim_class:
        service = GeocodingService(user_agent="TestApp", timeout=5)
        assert service.geolocator is mock_nominatim_class.return_value


def test_is_zip_code_valid_5digit():
    """Test ZIP code validation with 5-digit code."""
    service = GeocodingService()
    assert service.is_zip_code("12345") is True


def test_is_zip_code_valid_zip4():
    """Test ZIP code validation with ZIP+4 code."""
    service = GeocodingService()
    assert service.is_zip_code("12345-6789") is True


def test_is_zip_code_invalid_formats():
    """Test ZIP code validation with invalid formats."""
    service = GeocodingService()
    invalid_zips = [
        "1234",  # Too short
        "123456",  # Too long
        "12345-",  # Incomplete ZIP+4
        "12345-678",  # Invalid ZIP+4
        "12345-67890",  # ZIP+4 too long
        "abcde",  # Non-numeric
        "12345-abcd",  # Non-numeric ZIP+4
        "",  # Empty string
        "  12345  ",  # Whitespace
    ]
    for zip_code in invalid_zips:
        assert service.is_zip_code(zip_code) is False


def test_format_zip_code_5digit():
    """Test ZIP code formatting with 5-digit code."""
    service = GeocodingService()
    assert service.format_zip_code("12345") == "12345, USA"


def test_format_zip_code_zip4():
    """Test ZIP code formatting with ZIP+4 code."""
    service = GeocodingService()
    assert service.format_zip_code("12345-6789") == "12345, USA"


def test_geocode_address_success(geocoding_service, mock_location):
    """Test successful address geocoding."""
    geocoding_service._mock_geolocator_instance.geocode.return_value = mock_location

    result = geocoding_service.geocode_address(SAMPLE_ADDRESS)

    assert result == (SAMPLE_LAT, SAMPLE_LON, SAMPLE_DISPLAY_NAME)
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with(SAMPLE_ADDRESS)


def test_geocode_address_zip5(geocoding_service, mock_location):
    """Test successful ZIP code geocoding (5-digit)."""
    geocoding_service._mock_geolocator_instance.geocode.return_value = mock_location

    result = geocoding_service.geocode_address(SAMPLE_ZIP_5)

    assert result == (SAMPLE_LAT, SAMPLE_LON, SAMPLE_DISPLAY_NAME)
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with(
        f"{SAMPLE_ZIP_5}, USA"
    )


def test_geocode_address_zip4(geocoding_service, mock_location):
    """Test successful ZIP code geocoding (ZIP+4)."""
    geocoding_service._mock_geolocator_instance.geocode.return_value = mock_location

    result = geocoding_service.geocode_address(SAMPLE_ZIP_4)

    assert result == (SAMPLE_LAT, SAMPLE_LON, SAMPLE_DISPLAY_NAME)
    # Should use just the 5-digit part
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with("12345, USA")


def test_geocode_address_not_found(geocoding_service):
    """Test address geocoding when no results are found."""
    geocoding_service._mock_geolocator_instance.geocode.return_value = None

    result = geocoding_service.geocode_address(SAMPLE_ADDRESS)

    assert result is None
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with(SAMPLE_ADDRESS)


def test_geocode_address_timeout(geocoding_service):
    """Test address geocoding when timeout occurs."""
    geocoding_service._mock_geolocator_instance.geocode.side_effect = GeocoderTimedOut("Timeout")

    result = geocoding_service.geocode_address(SAMPLE_ADDRESS)

    assert result is None
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with(SAMPLE_ADDRESS)


def test_geocode_address_service_error(geocoding_service):
    """Test address geocoding when service error occurs."""
    geocoding_service._mock_geolocator_instance.geocode.side_effect = GeocoderServiceError(
        "Service Error"
    )

    result = geocoding_service.geocode_address(SAMPLE_ADDRESS)

    assert result is None
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with(SAMPLE_ADDRESS)


def test_geocode_address_unexpected_error(geocoding_service):
    """Test address geocoding when unexpected error occurs."""
    geocoding_service._mock_geolocator_instance.geocode.side_effect = Exception("Unexpected Error")

    result = geocoding_service.geocode_address(SAMPLE_ADDRESS)

    assert result is None
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with(SAMPLE_ADDRESS)


def test_suggest_locations_success(geocoding_service):
    """Test successful location suggestions."""
    mock_locations = [
        MagicMock(address="Location 1"),
        MagicMock(address="Location 2"),
        MagicMock(address="Location 3"),
    ]
    geocoding_service._mock_geolocator_instance.geocode.return_value = mock_locations

    result = geocoding_service.suggest_locations("test query")

    assert result == ["Location 1", "Location 2", "Location 3"]
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with(
        "test query", exactly_one=False, limit=5
    )


def test_suggest_locations_zip(geocoding_service):
    """Test location suggestions with ZIP code."""
    mock_locations = [MagicMock(address="ZIP Location")]
    geocoding_service._mock_geolocator_instance.geocode.return_value = mock_locations

    result = geocoding_service.suggest_locations(SAMPLE_ZIP_5)

    assert result == ["ZIP Location"]
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with(
        f"{SAMPLE_ZIP_5}, USA", exactly_one=False, limit=5
    )


def test_suggest_locations_short_query(geocoding_service):
    """Test location suggestions with short query."""
    result = geocoding_service.suggest_locations("a")

    assert result == []
    geocoding_service._mock_geolocator_instance.geocode.assert_not_called()


def test_suggest_locations_none_found(geocoding_service):
    """Test location suggestions when none are found."""
    geocoding_service._mock_geolocator_instance.geocode.return_value = None

    result = geocoding_service.suggest_locations("test query")

    assert result == []
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with(
        "test query", exactly_one=False, limit=5
    )


def test_suggest_locations_timeout(geocoding_service):
    """Test location suggestions when timeout occurs."""
    geocoding_service._mock_geolocator_instance.geocode.side_effect = GeocoderTimedOut("Timeout")

    result = geocoding_service.suggest_locations("test query")

    assert result == []
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with(
        "test query", exactly_one=False, limit=5
    )


def test_suggest_locations_service_error(geocoding_service):
    """Test location suggestions when service error occurs."""
    geocoding_service._mock_geolocator_instance.geocode.side_effect = GeocoderServiceError(
        "Service Error"
    )

    result = geocoding_service.suggest_locations("test query")

    assert result == []
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with(
        "test query", exactly_one=False, limit=5
    )


def test_suggest_locations_unexpected_error(geocoding_service):
    """Test location suggestions when unexpected error occurs."""
    geocoding_service._mock_geolocator_instance.geocode.side_effect = Exception("Unexpected Error")

    result = geocoding_service.suggest_locations("test query")

    assert result == []
    geocoding_service._mock_geolocator_instance.geocode.assert_called_once_with(
        "test query", exactly_one=False, limit=5
    )
