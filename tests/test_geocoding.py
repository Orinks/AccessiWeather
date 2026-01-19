"""
Tests for GeocodingService.

Tests geocoding functionality including address lookup and coordinate validation.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from accessiweather.geocoding import GeocodingService
from accessiweather.openmeteo_geocoding_client import GeocodingResult


class TestGeocodingServiceInit:
    """Tests for GeocodingService initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        service = GeocodingService()
        assert service.data_source == "nws"

    def test_custom_initialization(self):
        """Test custom initialization."""
        service = GeocodingService(user_agent="TestAgent", timeout=30, data_source="auto")
        assert service.data_source == "auto"


class TestZipCodeDetection:
    """Tests for ZIP code detection."""

    @pytest.fixture
    def service(self):
        return GeocodingService()

    def test_valid_5_digit_zip(self, service):
        """Test valid 5-digit ZIP code detection."""
        assert service.is_zip_code("12345") is True
        assert service.is_zip_code("00000") is True
        assert service.is_zip_code("99999") is True

    def test_valid_zip_plus_4(self, service):
        """Test valid ZIP+4 code detection."""
        assert service.is_zip_code("12345-6789") is True
        assert service.is_zip_code("00000-0000") is True

    def test_invalid_zip_codes(self, service):
        """Test invalid ZIP code detection."""
        assert service.is_zip_code("1234") is False  # Too short
        assert service.is_zip_code("123456") is False  # Too long
        assert service.is_zip_code("12345-678") is False  # Invalid +4
        assert service.is_zip_code("ABCDE") is False  # Letters
        assert service.is_zip_code("") is False  # Empty

    def test_format_zip_code(self, service):
        """Test ZIP code formatting."""
        assert service.format_zip_code("12345") == "12345, USA"
        assert service.format_zip_code("12345-6789") == "12345, USA"


class TestCoordinateValidation:
    """Tests for coordinate validation."""

    @pytest.fixture
    def service(self):
        return GeocodingService()

    def test_valid_global_coordinates(self, service):
        """Test valid global coordinates."""
        # Use non-US restriction
        assert service.validate_coordinates(0, 0, us_only=False) is True
        assert service.validate_coordinates(90, 180, us_only=False) is True
        assert service.validate_coordinates(-90, -180, us_only=False) is True

    def test_invalid_coordinates(self, service):
        """Test invalid coordinates."""
        assert service.validate_coordinates(91, 0, us_only=False) is False
        assert service.validate_coordinates(0, 181, us_only=False) is False
        assert service.validate_coordinates(-91, 0, us_only=False) is False

    def test_us_continental_coordinates(self, service):
        """Test US continental coordinates."""
        # New York
        assert service.validate_coordinates(40.7128, -74.0060, us_only=True) is True
        # Los Angeles
        assert service.validate_coordinates(34.0522, -118.2437, us_only=True) is True

    def test_us_alaska_coordinates(self, service):
        """Test Alaska coordinates."""
        # Anchorage
        assert service.validate_coordinates(61.2181, -149.9003, us_only=True) is True

    def test_us_hawaii_coordinates(self, service):
        """Test Hawaii coordinates."""
        # Honolulu
        assert service.validate_coordinates(21.3069, -157.8583, us_only=True) is True

    def test_non_us_coordinates_rejected(self, service):
        """Test non-US coordinates are rejected with us_only=True."""
        # London
        assert service.validate_coordinates(51.5074, -0.1278, us_only=True) is False
        # Tokyo
        assert service.validate_coordinates(35.6762, 139.6503, us_only=True) is False

    def test_data_source_determines_validation(self, service):
        """Test that data source affects validation."""
        # NWS source restricts to US
        service.data_source = "nws"
        assert service.validate_coordinates(51.5074, -0.1278) is False  # London

        # Auto/other sources allow worldwide
        service.data_source = "auto"
        assert service.validate_coordinates(51.5074, -0.1278) is True


class TestGeocodeAddress:
    """Tests for address geocoding."""

    @pytest.fixture
    def service(self):
        return GeocodingService()

    @pytest.fixture
    def mock_us_result(self):
        """Mock US geocoding result."""
        return GeocodingResult(
            name="New York",
            latitude=40.7128,
            longitude=-74.0060,
            country="United States",
            country_code="US",
            timezone="America/New_York",
            admin1="New York",
        )

    @pytest.fixture
    def mock_uk_result(self):
        """Mock UK geocoding result."""
        return GeocodingResult(
            name="London",
            latitude=51.5074,
            longitude=-0.1278,
            country="United Kingdom",
            country_code="GB",
            timezone="Europe/London",
            admin1="England",
        )

    def test_geocode_us_address_nws_source(self, service, mock_us_result):
        """Test geocoding US address with NWS source."""
        service.data_source = "nws"
        service.client.search = MagicMock(return_value=[mock_us_result])

        result = service.geocode_address("New York")

        assert result is not None
        lat, lon, name = result
        assert abs(lat - 40.7128) < 0.01
        assert abs(lon - (-74.0060)) < 0.01

    def test_geocode_intl_address_nws_source_filtered(self, service, mock_uk_result):
        """Test that international results are filtered with NWS source."""
        service.data_source = "nws"
        service.client.search = MagicMock(return_value=[mock_uk_result])

        result = service.geocode_address("London")

        # Should return None because NWS only supports US
        assert result is None

    def test_geocode_intl_address_auto_source(self, service, mock_uk_result):
        """Test geocoding international address with auto source."""
        service.data_source = "auto"
        service.client.search = MagicMock(return_value=[mock_uk_result])

        result = service.geocode_address("London")

        assert result is not None
        lat, lon, name = result
        assert abs(lat - 51.5074) < 0.01

    def test_geocode_no_results(self, service):
        """Test geocoding with no results."""
        service.client.search = MagicMock(return_value=[])

        result = service.geocode_address("Nonexistent Place XYZ")
        assert result is None

    def test_geocode_zip_code(self, service, mock_us_result):
        """Test geocoding a ZIP code."""
        service.client.search = MagicMock(return_value=[mock_us_result])

        result = service.geocode_address("10001")

        assert result is not None
        # Verify the search was called with formatted ZIP
        service.client.search.assert_called_with("10001, USA", count=5)


class TestSuggestLocations:
    """Tests for location suggestions."""

    @pytest.fixture
    def service(self):
        return GeocodingService()

    @pytest.fixture
    def mock_results(self):
        """Mock multiple geocoding results."""
        return [
            GeocodingResult(
                name="New York City",
                latitude=40.7128,
                longitude=-74.0060,
                country="United States",
                country_code="US",
                timezone="America/New_York",
                admin1="New York",
            ),
            GeocodingResult(
                name="New York",
                latitude=42.8864,
                longitude=-78.8784,
                country="United States",
                country_code="US",
                timezone="America/New_York",
                admin1="New York",
            ),
        ]

    def test_suggest_locations(self, service, mock_results):
        """Test location suggestions."""
        service.client.search = MagicMock(return_value=mock_results)

        suggestions = service.suggest_locations("New York", limit=5)

        assert len(suggestions) == 2
        # display_name is a property that combines name, admin1, country
        assert any("New York" in s for s in suggestions)

    def test_suggest_locations_empty_query(self, service):
        """Test suggestions with empty query."""
        suggestions = service.suggest_locations("")
        assert suggestions == []

    def test_suggest_locations_short_query(self, service):
        """Test suggestions with too-short query."""
        suggestions = service.suggest_locations("N")
        assert suggestions == []

    def test_suggest_locations_respects_limit(self, service, mock_results):
        """Test that suggestions respect the limit."""
        # Add more results
        many_results = mock_results * 5
        service.client.search = MagicMock(return_value=many_results)

        suggestions = service.suggest_locations("New", limit=3)

        assert len(suggestions) <= 3
