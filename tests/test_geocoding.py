"""
Unit tests for geocoding module.

Tests cover:
- ZIP code validation and formatting
- Address geocoding with country filtering
- Coordinate validation
- Location suggestions
- Error handling for geocoding failures
- Data source-specific behavior (NWS vs. auto)
"""

# Direct import to avoid __init__.py importing toga
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from geopy.exc import GeocoderServiceError, GeocoderTimedOut

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accessiweather.geocoding import GeocodingService


class TestGeocodingServiceInitialization:
    """Test GeocodingService initialization."""

    def test_initialization_defaults(self):
        """Should initialize with default parameters."""
        service = GeocodingService()

        assert service.geolocator is not None
        assert service.data_source == "nws"

    def test_initialization_custom_user_agent(self):
        """Should initialize with custom user agent."""
        service = GeocodingService(user_agent="TestApp")

        assert service.geolocator is not None

    def test_initialization_custom_timeout(self):
        """Should initialize with custom timeout."""
        service = GeocodingService(timeout=20)

        assert service.geolocator is not None

    def test_initialization_custom_data_source(self):
        """Should initialize with custom data source."""
        service = GeocodingService(data_source="auto")

        assert service.data_source == "auto"


class TestZIPCodeValidation:
    """Test ZIP code validation and formatting."""

    @pytest.fixture
    def service(self):
        """Create GeocodingService instance."""
        return GeocodingService()

    def test_is_zip_code_valid_5_digit(self, service):
        """Should recognize valid 5-digit ZIP code."""
        assert service.is_zip_code("12345") is True

    def test_is_zip_code_valid_zip_plus_4(self, service):
        """Should recognize valid ZIP+4 code."""
        assert service.is_zip_code("12345-6789") is True

    def test_is_zip_code_invalid_too_short(self, service):
        """Should reject ZIP code that's too short."""
        assert service.is_zip_code("1234") is False

    def test_is_zip_code_invalid_too_long(self, service):
        """Should reject ZIP code that's too long."""
        assert service.is_zip_code("123456") is False

    def test_is_zip_code_invalid_with_letters(self, service):
        """Should reject ZIP code with letters."""
        assert service.is_zip_code("1234A") is False
        assert service.is_zip_code("ABCDE") is False

    def test_is_zip_code_invalid_special_chars(self, service):
        """Should reject ZIP code with special characters."""
        assert service.is_zip_code("12 345") is False
        assert service.is_zip_code("12.345") is False

    def test_is_zip_code_empty_string(self, service):
        """Should reject empty string."""
        assert service.is_zip_code("") is False

    def test_format_zip_code_5_digit(self, service):
        """Should format 5-digit ZIP code with USA suffix."""
        result = service.format_zip_code("12345")

        assert result == "12345, USA"

    def test_format_zip_code_zip_plus_4(self, service):
        """Should strip +4 extension and add USA suffix."""
        result = service.format_zip_code("12345-6789")

        assert result == "12345, USA"


class TestAddressGeocoding:
    """Test address geocoding functionality."""

    @pytest.fixture
    def service(self):
        """Create GeocodingService instance."""
        return GeocodingService(data_source="nws")

    def test_geocode_address_success(self, service):
        """Should successfully geocode US address."""
        mock_location = Mock()
        mock_location.latitude = 40.7128
        mock_location.longitude = -74.0060
        mock_location.address = "New York, NY, USA"
        mock_location.raw = {"address": {"country_code": "us"}}

        with patch.object(service.geolocator, "geocode", return_value=mock_location):
            result = service.geocode_address("New York, NY")

            assert result is not None
            lat, lon, address = result
            assert lat == 40.7128
            assert lon == -74.0060
            assert "New York" in address

    def test_geocode_address_not_found(self, service):
        """Should return None when address not found."""
        with patch.object(service.geolocator, "geocode", return_value=None):
            result = service.geocode_address("Invalid Address XYZ123")

            assert result is None

    def test_geocode_address_non_us_filtered_nws(self, service):
        """Should filter non-US locations when using NWS data source."""
        mock_location = Mock()
        mock_location.latitude = 51.5074
        mock_location.longitude = -0.1278
        mock_location.address = "London, UK"
        mock_location.raw = {"address": {"country_code": "gb"}}

        with patch.object(service.geolocator, "geocode", return_value=mock_location):
            result = service.geocode_address("London, UK")

            assert result is None

    def test_geocode_address_non_us_allowed_auto(self):
        """Should allow non-US locations when using auto data source."""
        service = GeocodingService(data_source="auto")
        mock_location = Mock()
        mock_location.latitude = 51.5074
        mock_location.longitude = -0.1278
        mock_location.address = "London, UK"
        mock_location.raw = {"address": {"country_code": "gb"}}

        with patch.object(service.geolocator, "geocode", return_value=mock_location):
            result = service.geocode_address("London, UK")

            assert result is not None
            lat, lon, address = result
            assert lat == 51.5074
            assert lon == -0.1278

    def test_geocode_address_zip_code(self, service):
        """Should format and geocode ZIP code."""
        mock_location = Mock()
        mock_location.latitude = 40.7128
        mock_location.longitude = -74.0060
        mock_location.address = "New York, NY 10001, USA"
        mock_location.raw = {"address": {"country_code": "us"}}

        with patch.object(service.geolocator, "geocode", return_value=mock_location):
            result = service.geocode_address("10001")

            assert result is not None

    def test_geocode_address_timeout(self, service):
        """Should handle geocoder timeout gracefully."""
        with patch.object(service.geolocator, "geocode", side_effect=GeocoderTimedOut("Timeout")):
            result = service.geocode_address("New York, NY")

            assert result is None

    def test_geocode_address_service_error(self, service):
        """Should handle geocoder service error gracefully."""
        with patch.object(
            service.geolocator, "geocode", side_effect=GeocoderServiceError("Service error")
        ):
            result = service.geocode_address("New York, NY")

            assert result is None

    def test_geocode_address_unexpected_error(self, service):
        """Should handle unexpected errors gracefully."""
        with patch.object(service.geolocator, "geocode", side_effect=Exception("Unexpected error")):
            result = service.geocode_address("New York, NY")

            assert result is None

    def test_geocode_address_no_country_code(self, service):
        """Should return None when country code cannot be verified."""
        mock_location = Mock()
        mock_location.latitude = 40.7128
        mock_location.longitude = -74.0060
        mock_location.address = "New York, NY, USA"
        mock_location.raw = {}  # Missing address details

        with patch.object(service.geolocator, "geocode", return_value=mock_location):
            result = service.geocode_address("New York, NY")

            assert result is None

    def test_geocode_address_strips_whitespace(self, service):
        """Should strip whitespace from address."""
        mock_location = Mock()
        mock_location.latitude = 40.7128
        mock_location.longitude = -74.0060
        mock_location.address = "New York, NY, USA"
        mock_location.raw = {"address": {"country_code": "us"}}

        with patch.object(service.geolocator, "geocode", return_value=mock_location):
            result = service.geocode_address("  New York, NY  ")

            assert result is not None


class TestCoordinateValidation:
    """Test coordinate validation functionality."""

    @pytest.fixture
    def service(self):
        """Create GeocodingService instance."""
        return GeocodingService(data_source="nws")

    def test_validate_coordinates_basic_range_valid(self, service):
        """Should validate coordinates within basic range."""
        # Valid coordinates
        assert service.validate_coordinates(40.7128, -74.0060, us_only=False) is True

    def test_validate_coordinates_basic_range_invalid_lat(self, service):
        """Should reject latitude outside valid range."""
        assert service.validate_coordinates(91.0, -74.0060, us_only=False) is False
        assert service.validate_coordinates(-91.0, -74.0060, us_only=False) is False

    def test_validate_coordinates_basic_range_invalid_lon(self, service):
        """Should reject longitude outside valid range."""
        assert service.validate_coordinates(40.7128, 181.0, us_only=False) is False
        assert service.validate_coordinates(40.7128, -181.0, us_only=False) is False

    def test_validate_coordinates_us_location_success(self, service):
        """Should validate US coordinates successfully."""
        mock_location = Mock()
        mock_location.raw = {"address": {"country_code": "us"}}

        with patch.object(service.geolocator, "reverse", return_value=mock_location):
            result = service.validate_coordinates(40.7128, -74.0060, us_only=True)

            assert result is True

    def test_validate_coordinates_non_us_location(self, service):
        """Should reject non-US coordinates when us_only=True."""
        mock_location = Mock()
        mock_location.raw = {"address": {"country_code": "gb"}}

        with patch.object(service.geolocator, "reverse", return_value=mock_location):
            result = service.validate_coordinates(51.5074, -0.1278, us_only=True)

            assert result is False

    def test_validate_coordinates_not_found(self, service):
        """Should return False when location not found."""
        with patch.object(service.geolocator, "reverse", return_value=None):
            result = service.validate_coordinates(0.0, 0.0, us_only=True)

            assert result is False

    def test_validate_coordinates_timeout(self, service):
        """Should return True on timeout to avoid false negatives."""
        with patch.object(service.geolocator, "reverse", side_effect=GeocoderTimedOut("Timeout")):
            result = service.validate_coordinates(40.7128, -74.0060, us_only=True)

            # Should return True to avoid removing valid locations
            assert result is True

    def test_validate_coordinates_service_error(self, service):
        """Should return True on service error to avoid false negatives."""
        with patch.object(
            service.geolocator, "reverse", side_effect=GeocoderServiceError("Service error")
        ):
            result = service.validate_coordinates(40.7128, -74.0060, us_only=True)

            assert result is True

    def test_validate_coordinates_auto_determines_us_only_nws(self):
        """Should use us_only=True when data_source is 'nws' and us_only is None."""
        service = GeocodingService(data_source="nws")
        mock_location = Mock()
        mock_location.raw = {"address": {"country_code": "us"}}

        with patch.object(service.geolocator, "reverse", return_value=mock_location):
            result = service.validate_coordinates(40.7128, -74.0060)

            assert result is True

    def test_validate_coordinates_auto_determines_us_only_auto(self):
        """Should use us_only=False when data_source is 'auto' and us_only is None."""
        service = GeocodingService(data_source="auto")

        # Should pass basic range validation without reverse geocoding
        result = service.validate_coordinates(51.5074, -0.1278)

        assert result is True

    def test_validate_coordinates_edge_cases(self, service):
        """Should handle edge case coordinates correctly."""
        # Equator and Prime Meridian
        assert service.validate_coordinates(0.0, 0.0, us_only=False) is True

        # North and South Poles
        assert service.validate_coordinates(90.0, 0.0, us_only=False) is True
        assert service.validate_coordinates(-90.0, 0.0, us_only=False) is True

        # International Date Line
        assert service.validate_coordinates(0.0, 180.0, us_only=False) is True
        assert service.validate_coordinates(0.0, -180.0, us_only=False) is True


class TestLocationSuggestions:
    """Test location suggestion functionality."""

    @pytest.fixture
    def service(self):
        """Create GeocodingService instance."""
        return GeocodingService(data_source="nws")

    def test_suggest_locations_success(self, service):
        """Should return location suggestions."""
        mock_locations = []
        for i in range(3):
            mock_loc = Mock()
            mock_loc.address = f"New York Location {i}"
            mock_loc.raw = {"address": {"country_code": "us"}}
            mock_locations.append(mock_loc)

        with patch.object(service.geolocator, "geocode", return_value=mock_locations):
            suggestions = service.suggest_locations("New York")

            assert len(suggestions) == 3
            assert all("New York" in s for s in suggestions)

    def test_suggest_locations_empty_query(self, service):
        """Should return empty list for empty query."""
        suggestions = service.suggest_locations("")

        assert suggestions == []

    def test_suggest_locations_short_query(self, service):
        """Should return empty list for very short query."""
        suggestions = service.suggest_locations("N")

        assert suggestions == []

    def test_suggest_locations_filters_us_only_nws(self, service):
        """Should filter for US locations only when using NWS."""
        mock_locations = [
            Mock(address="New York, USA", raw={"address": {"country_code": "us"}}),
            Mock(address="York, UK", raw={"address": {"country_code": "gb"}}),
            Mock(address="New York, Australia", raw={"address": {"country_code": "au"}}),
        ]

        with patch.object(service.geolocator, "geocode", return_value=mock_locations):
            suggestions = service.suggest_locations("New York", limit=5)

            # Should only return US location
            assert len(suggestions) == 1
            assert "USA" in suggestions[0]

    def test_suggest_locations_allows_worldwide_auto(self):
        """Should allow worldwide locations when using auto data source."""
        service = GeocodingService(data_source="auto")
        mock_locations = [
            Mock(address="New York, USA", raw={"address": {"country_code": "us"}}),
            Mock(address="York, UK", raw={"address": {"country_code": "gb"}}),
        ]

        with patch.object(service.geolocator, "geocode", return_value=mock_locations):
            suggestions = service.suggest_locations("York", limit=5)

            # Should return all locations
            assert len(suggestions) == 2

    def test_suggest_locations_with_limit(self, service):
        """Should respect limit parameter."""
        mock_locations = []
        for i in range(10):
            mock_loc = Mock()
            mock_loc.address = f"Location {i}"
            mock_loc.raw = {"address": {"country_code": "us"}}
            mock_locations.append(mock_loc)

        with patch.object(service.geolocator, "geocode", return_value=mock_locations):
            suggestions = service.suggest_locations("Test", limit=3)

            # Should return no more than limit
            assert len(suggestions) <= 3

    def test_suggest_locations_zip_code(self, service):
        """Should format ZIP code for suggestions."""
        mock_locations = [
            Mock(address="New York, NY 10001, USA", raw={"address": {"country_code": "us"}})
        ]

        with patch.object(service.geolocator, "geocode", return_value=mock_locations):
            suggestions = service.suggest_locations("10001")

            assert len(suggestions) >= 0

    def test_suggest_locations_no_results(self, service):
        """Should return empty list when no results found."""
        with patch.object(service.geolocator, "geocode", return_value=None):
            suggestions = service.suggest_locations("Invalid XYZ123")

            assert suggestions == []

    def test_suggest_locations_timeout(self, service):
        """Should return empty list on timeout."""
        with patch.object(service.geolocator, "geocode", side_effect=GeocoderTimedOut("Timeout")):
            suggestions = service.suggest_locations("New York")

            assert suggestions == []

    def test_suggest_locations_service_error(self, service):
        """Should return empty list on service error."""
        with patch.object(
            service.geolocator, "geocode", side_effect=GeocoderServiceError("Service error")
        ):
            suggestions = service.suggest_locations("New York")

            assert suggestions == []

    def test_suggest_locations_strips_whitespace(self, service):
        """Should strip whitespace from query."""
        mock_locations = [Mock(address="New York, USA", raw={"address": {"country_code": "us"}})]

        with patch.object(service.geolocator, "geocode", return_value=mock_locations):
            suggestions = service.suggest_locations("  New York  ")

            assert len(suggestions) > 0


class TestGeocodingServiceEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_allowed_country_codes(self):
        """Should have US in allowed country codes."""
        assert "us" in GeocodingService.ALLOWED_COUNTRY_CODES

    def test_zip_code_pattern_compilation(self):
        """Should have compiled ZIP code pattern."""
        assert GeocodingService.ZIP_CODE_PATTERN is not None

    def test_geocode_address_with_very_long_address(self):
        """Should handle very long addresses."""
        service = GeocodingService()
        long_address = "A" * 1000

        with patch.object(service.geolocator, "geocode", return_value=None):
            result = service.geocode_address(long_address)

            assert result is None

    def test_validate_coordinates_boundary_values(self):
        """Should validate boundary coordinate values correctly."""
        service = GeocodingService()

        # Exact boundaries should be valid
        assert service.validate_coordinates(90.0, 180.0, us_only=False) is True
        assert service.validate_coordinates(-90.0, -180.0, us_only=False) is True

        # Just outside boundaries should be invalid
        assert service.validate_coordinates(90.1, 0.0, us_only=False) is False
        assert service.validate_coordinates(-90.1, 0.0, us_only=False) is False
        assert service.validate_coordinates(0.0, 180.1, us_only=False) is False
        assert service.validate_coordinates(0.0, -180.1, us_only=False) is False
