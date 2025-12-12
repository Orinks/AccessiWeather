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

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accessiweather.geocoding import GeocodingService
from accessiweather.openmeteo_geocoding_client import (
    GeocodingResult,
    OpenMeteoGeocodingError,
    OpenMeteoGeocodingNetworkError,
)


class TestGeocodingServiceInitialization:
    """Test GeocodingService initialization."""

    def test_initialization_defaults(self) -> None:
        """Should initialize with default parameters."""
        service = GeocodingService()

        assert service.client is not None
        assert service.data_source == "nws"

    def test_initialization_custom_user_agent(self) -> None:
        """Should initialize with custom user agent."""
        service = GeocodingService(user_agent="TestApp")

        assert service.client is not None

    def test_initialization_custom_timeout(self) -> None:
        """Should initialize with custom timeout."""
        service = GeocodingService(timeout=20)

        assert service.client is not None

    def test_initialization_custom_data_source(self) -> None:
        """Should initialize with custom data source."""
        service = GeocodingService(data_source="auto")

        assert service.data_source == "auto"


class TestZIPCodeValidation:
    """Test ZIP code validation and formatting."""

    @pytest.fixture
    def service(self) -> GeocodingService:
        """Create GeocodingService instance."""
        return GeocodingService()

    def test_is_zip_code_valid_5_digit(self, service: GeocodingService) -> None:
        """Should recognize valid 5-digit ZIP code."""
        assert service.is_zip_code("12345") is True

    def test_is_zip_code_valid_zip_plus_4(self, service: GeocodingService) -> None:
        """Should recognize valid ZIP+4 code."""
        assert service.is_zip_code("12345-6789") is True

    def test_is_zip_code_invalid_too_short(self, service: GeocodingService) -> None:
        """Should reject ZIP code that's too short."""
        assert service.is_zip_code("1234") is False

    def test_is_zip_code_invalid_too_long(self, service: GeocodingService) -> None:
        """Should reject ZIP code that's too long."""
        assert service.is_zip_code("123456") is False

    def test_is_zip_code_invalid_with_letters(self, service: GeocodingService) -> None:
        """Should reject ZIP code with letters."""
        assert service.is_zip_code("1234A") is False
        assert service.is_zip_code("ABCDE") is False

    def test_is_zip_code_invalid_special_chars(self, service: GeocodingService) -> None:
        """Should reject ZIP code with special characters."""
        assert service.is_zip_code("12 345") is False
        assert service.is_zip_code("12.345") is False

    def test_is_zip_code_empty_string(self, service: GeocodingService) -> None:
        """Should reject empty string."""
        assert service.is_zip_code("") is False

    def test_format_zip_code_5_digit(self, service: GeocodingService) -> None:
        """Should format 5-digit ZIP code with USA suffix."""
        result = service.format_zip_code("12345")

        assert result == "12345, USA"

    def test_format_zip_code_zip_plus_4(self, service: GeocodingService) -> None:
        """Should strip +4 extension and add USA suffix."""
        result = service.format_zip_code("12345-6789")

        assert result == "12345, USA"


class TestAddressGeocoding:
    """Test address geocoding functionality."""

    @pytest.fixture
    def service(self) -> GeocodingService:
        """Create GeocodingService instance."""
        return GeocodingService(data_source="nws")

    def test_geocode_address_success(self, service: GeocodingService) -> None:
        """Should successfully geocode US address."""
        mock_result = GeocodingResult(
            name="New York",
            latitude=40.7128,
            longitude=-74.0060,
            country="United States",
            country_code="US",
            timezone="America/New_York",
            admin1="New York",
        )

        with patch.object(service.client, "search", return_value=[mock_result]):
            result = service.geocode_address("New York, NY")

            assert result is not None
            lat, lon, address = result
            assert lat == 40.7128
            assert lon == -74.0060
            assert "New York" in address

    def test_geocode_address_not_found(self, service: GeocodingService) -> None:
        """Should return None when address not found."""
        with patch.object(service.client, "search", return_value=[]):
            result = service.geocode_address("Invalid Address XYZ123")

            assert result is None

    def test_geocode_address_non_us_filtered_nws(self, service: GeocodingService) -> None:
        """Should filter non-US locations when using NWS data source."""
        mock_result = GeocodingResult(
            name="London",
            latitude=51.5074,
            longitude=-0.1278,
            country="United Kingdom",
            country_code="GB",
            timezone="Europe/London",
        )

        with patch.object(service.client, "search", return_value=[mock_result]):
            result = service.geocode_address("London, UK")

            assert result is None

    def test_geocode_address_non_us_allowed_auto(self) -> None:
        """Should allow non-US locations when using auto data source."""
        service = GeocodingService(data_source="auto")
        mock_result = GeocodingResult(
            name="London",
            latitude=51.5074,
            longitude=-0.1278,
            country="United Kingdom",
            country_code="GB",
            timezone="Europe/London",
        )

        with patch.object(service.client, "search", return_value=[mock_result]):
            result = service.geocode_address("London, UK")

            assert result is not None
            lat, lon, address = result
            assert lat == 51.5074
            assert lon == -0.1278

    def test_geocode_address_error_handling(self, service: GeocodingService) -> None:
        """Should handle geocoding errors gracefully."""
        with patch.object(
            service.client, "search", side_effect=OpenMeteoGeocodingError("API error")
        ):
            result = service.geocode_address("Test Address")

            assert result is None

    def test_geocode_address_network_error(self, service: GeocodingService) -> None:
        """Should handle network errors gracefully."""
        with patch.object(
            service.client, "search", side_effect=OpenMeteoGeocodingNetworkError("Timeout")
        ):
            result = service.geocode_address("Test Address")

            assert result is None


class TestCoordinateValidation:
    """Test coordinate validation functionality."""

    @pytest.fixture
    def service_nws(self) -> GeocodingService:
        """Create GeocodingService with NWS data source."""
        return GeocodingService(data_source="nws")

    @pytest.fixture
    def service_auto(self) -> GeocodingService:
        """Create GeocodingService with auto data source."""
        return GeocodingService(data_source="auto")

    def test_validate_coordinates_valid_us(self, service_nws: GeocodingService) -> None:
        """Should validate coordinates within US bounds."""
        # New York City
        assert service_nws.validate_coordinates(40.7128, -74.0060) is True

    def test_validate_coordinates_valid_alaska(self, service_nws: GeocodingService) -> None:
        """Should validate Alaska coordinates."""
        # Anchorage
        assert service_nws.validate_coordinates(61.2181, -149.9003) is True

    def test_validate_coordinates_valid_hawaii(self, service_nws: GeocodingService) -> None:
        """Should validate Hawaii coordinates."""
        # Honolulu
        assert service_nws.validate_coordinates(21.3069, -157.8583) is True

    def test_validate_coordinates_outside_us_nws(self, service_nws: GeocodingService) -> None:
        """Should reject coordinates outside US when using NWS."""
        # London
        assert service_nws.validate_coordinates(51.5074, -0.1278) is False

    def test_validate_coordinates_outside_us_auto(self, service_auto: GeocodingService) -> None:
        """Should accept coordinates outside US when using auto."""
        # London
        assert service_auto.validate_coordinates(51.5074, -0.1278) is True

    def test_validate_coordinates_invalid_latitude(self, service_auto: GeocodingService) -> None:
        """Should reject invalid latitude."""
        assert service_auto.validate_coordinates(91.0, 0.0) is False
        assert service_auto.validate_coordinates(-91.0, 0.0) is False

    def test_validate_coordinates_invalid_longitude(self, service_auto: GeocodingService) -> None:
        """Should reject invalid longitude."""
        assert service_auto.validate_coordinates(0.0, 181.0) is False
        assert service_auto.validate_coordinates(0.0, -181.0) is False

    def test_validate_coordinates_boundary_values(self, service_auto: GeocodingService) -> None:
        """Should accept boundary coordinate values."""
        assert service_auto.validate_coordinates(90.0, 180.0) is True
        assert service_auto.validate_coordinates(-90.0, -180.0) is True
        assert service_auto.validate_coordinates(0.0, 0.0) is True


class TestLocationSuggestions:
    """Test location suggestion functionality."""

    @pytest.fixture
    def service(self) -> GeocodingService:
        """Create GeocodingService instance."""
        return GeocodingService(data_source="nws")

    def test_suggest_locations_success(self, service: GeocodingService) -> None:
        """Should return location suggestions."""
        mock_results = [
            GeocodingResult(
                name="New York",
                latitude=40.7128,
                longitude=-74.0060,
                country="United States",
                country_code="US",
                timezone="America/New_York",
                admin1="New York",
            ),
            GeocodingResult(
                name="New York Mills",
                latitude=43.1056,
                longitude=-75.2915,
                country="United States",
                country_code="US",
                timezone="America/New_York",
                admin1="New York",
            ),
        ]

        with patch.object(service.client, "search", return_value=mock_results):
            suggestions = service.suggest_locations("New York")

            assert len(suggestions) == 2
            assert "New York" in suggestions[0]

    def test_suggest_locations_empty_query(self, service: GeocodingService) -> None:
        """Should return empty list for empty query."""
        suggestions = service.suggest_locations("")

        assert suggestions == []

    def test_suggest_locations_short_query(self, service: GeocodingService) -> None:
        """Should return empty list for query shorter than 2 characters."""
        suggestions = service.suggest_locations("N")

        assert suggestions == []

    def test_suggest_locations_respects_limit(self, service: GeocodingService) -> None:
        """Should respect the limit parameter."""
        mock_results = [
            GeocodingResult(
                name=f"City{i}",
                latitude=40.0 + i,
                longitude=-74.0,
                country="United States",
                country_code="US",
                timezone="America/New_York",
            )
            for i in range(10)
        ]

        with patch.object(service.client, "search", return_value=mock_results):
            suggestions = service.suggest_locations("City", limit=3)

            assert len(suggestions) <= 3

    def test_suggest_locations_filters_non_us_nws(self, service: GeocodingService) -> None:
        """Should filter non-US locations when using NWS."""
        mock_results = [
            GeocodingResult(
                name="London",
                latitude=51.5074,
                longitude=-0.1278,
                country="United Kingdom",
                country_code="GB",
                timezone="Europe/London",
            ),
            GeocodingResult(
                name="London",
                latitude=37.1290,
                longitude=-84.0833,
                country="United States",
                country_code="US",
                timezone="America/New_York",
                admin1="Kentucky",
            ),
        ]

        with patch.object(service.client, "search", return_value=mock_results):
            suggestions = service.suggest_locations("London")

            assert len(suggestions) == 1
            assert "Kentucky" in suggestions[0]

    def test_suggest_locations_error_handling(self, service: GeocodingService) -> None:
        """Should handle errors gracefully."""
        with patch.object(
            service.client, "search", side_effect=OpenMeteoGeocodingError("API error")
        ):
            suggestions = service.suggest_locations("Test")

            assert suggestions == []
