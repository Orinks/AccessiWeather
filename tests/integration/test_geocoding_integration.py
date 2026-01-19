"""
Integration tests for Geocoding service.

These tests verify:
- Address geocoding via geocode_address()
- Zip code lookup
- Location suggestions via suggest_locations()
- Coordinate validation via validate_coordinates()
- Zip code detection via is_zip_code()
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import integration_vcr


@pytest.mark.integration
class TestGeocodingAddressLookup:
    """
    Test address geocoding.

    Note: These tests require live API access to record cassettes.
    Mark as live_only if the API is rate-limited or unavailable.
    """

    @pytest.mark.live_only
    @integration_vcr.use_cassette("geocoding/geocode_nyc.yaml")
    def test_geocode_us_city(self):
        """Test geocoding a US city."""
        from accessiweather.geocoding import GeocodingService

        service = GeocodingService(data_source="nws")
        result = service.geocode_address("New York, NY")

        assert result is not None
        lat, lon, display_name = result

        # Should find NYC
        assert "New York" in display_name or "NYC" in display_name
        assert 40.0 < lat < 41.0
        assert -75.0 < lon < -73.0

    @pytest.mark.live_only
    @integration_vcr.use_cassette("geocoding/geocode_london.yaml")
    def test_geocode_international_city(self):
        """Test geocoding an international city with auto data source."""
        from accessiweather.geocoding import GeocodingService

        # Use "auto" data source to allow international locations
        service = GeocodingService(data_source="auto")
        result = service.geocode_address("London, UK")

        assert result is not None
        lat, lon, display_name = result

        # Should find London
        assert 51.0 < lat < 52.0
        assert -1.0 < lon < 1.0

    @integration_vcr.use_cassette("geocoding/geocode_no_results.yaml")
    def test_geocode_no_results(self):
        """Test geocoding with no results."""
        from accessiweather.geocoding import GeocodingService

        service = GeocodingService()
        result = service.geocode_address("XYZNONEXISTENT12345")

        assert result is None


@pytest.mark.integration
class TestGeocodingZipCode:
    """Test zip code geocoding."""

    @pytest.mark.live_only
    @integration_vcr.use_cassette("geocoding/zipcode_10001.yaml")
    def test_geocode_zipcode(self):
        """Test geocoding a US zip code."""
        from accessiweather.geocoding import GeocodingService

        service = GeocodingService(data_source="nws")
        result = service.geocode_address("10001")

        assert result is not None
        lat, lon, display_name = result

        # Should find Manhattan area
        assert 40.0 < lat < 41.0
        assert -75.0 < lon < -73.0

    @pytest.mark.live_only
    @integration_vcr.use_cassette("geocoding/zipcode_plus4.yaml")
    def test_geocode_zipcode_plus4(self):
        """Test geocoding a ZIP+4 code."""
        from accessiweather.geocoding import GeocodingService

        service = GeocodingService(data_source="nws")
        result = service.geocode_address("10001-1234")

        # Should still find the location (base zip)
        assert result is not None


@pytest.mark.integration
class TestGeocodingSuggestions:
    """Test location suggestions."""

    @integration_vcr.use_cassette("geocoding/suggest_new.yaml")
    def test_suggest_locations(self):
        """Test location suggestions."""
        from accessiweather.geocoding import GeocodingService

        service = GeocodingService(data_source="nws")
        suggestions = service.suggest_locations("New York")

        # Suggestions may be empty if cassette has no results - just check type
        assert isinstance(suggestions, list)

    @integration_vcr.use_cassette("geocoding/suggest_limit.yaml")
    def test_suggest_respects_limit(self):
        """Test that suggestion limit is respected."""
        from accessiweather.geocoding import GeocodingService

        service = GeocodingService(data_source="nws")
        suggestions = service.suggest_locations("New York", limit=3)

        assert len(suggestions) <= 3


@pytest.mark.integration
class TestGeocodingCoordinateValidation:
    """Test coordinate validation."""

    def test_validate_us_coordinates(self):
        """Test validating US coordinates."""
        from accessiweather.geocoding import GeocodingService

        service = GeocodingService(data_source="nws")

        # Continental US - should be valid for NWS
        assert service.validate_coordinates(40.7, -74.0)  # NYC
        assert service.validate_coordinates(34.0, -118.2)  # LA

        # Alaska - should be valid for NWS
        assert service.validate_coordinates(61.2, -149.9)

        # Hawaii - should be valid for NWS
        assert service.validate_coordinates(21.3, -157.8)

        # International (should be False for NWS data source)
        assert not service.validate_coordinates(51.5, -0.1)  # London

    def test_validate_global_coordinates(self):
        """Test validating global coordinates."""
        from accessiweather.geocoding import GeocodingService

        # Use "auto" data source to allow any valid global coordinates
        service = GeocodingService(data_source="auto")

        # Valid coordinates
        assert service.validate_coordinates(40.7, -74.0)
        assert service.validate_coordinates(0, 0)
        assert service.validate_coordinates(-90, 180)
        assert service.validate_coordinates(90, -180)

        # Invalid coordinates (out of range)
        assert not service.validate_coordinates(91, 0)
        assert not service.validate_coordinates(0, 181)
        assert not service.validate_coordinates(-91, 0)


@pytest.mark.integration
class TestGeocodingZipCodeDetection:
    """Test zip code detection."""

    def test_detect_zip_codes(self):
        """Test detecting US zip codes."""
        from accessiweather.geocoding import GeocodingService

        service = GeocodingService()

        # Valid zip codes
        assert service.is_zip_code("10001")
        assert service.is_zip_code("10001-1234")
        assert service.is_zip_code("90210")

        # Invalid zip codes
        assert not service.is_zip_code("1000")  # Too short
        assert not service.is_zip_code("100001")  # Too long
        assert not service.is_zip_code("abcde")
        assert not service.is_zip_code("New York")
