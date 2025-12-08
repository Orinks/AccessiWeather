"""
Property-based tests for geocoding validation functions.

Uses Hypothesis to verify correctness of ZIP code validation,
coordinate validation, and format functions.

Note: These tests use the Hypothesis profile configured in conftest.py.
Run with HYPOTHESIS_PROFILE=ci for faster CI runs.
"""

from __future__ import annotations

import pytest
from hypothesis import (
    HealthCheck,
    given,
    settings,
    strategies as st,
)

from accessiweather.geocoding import GeocodingService

# Reusable service instance to avoid repeated instantiation overhead
_geocoding_service = GeocodingService(data_source="auto")


@pytest.fixture
def geocoding_service() -> GeocodingService:
    """Create a GeocodingService instance for testing."""
    return _geocoding_service


@pytest.mark.unit
class TestZipCodeValidationProperties:
    """Property tests for ZIP code validation."""

    @given(zip5=st.from_regex(r"^\d{5}$", fullmatch=True))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_five_digit_zip_always_valid(self, zip5: str) -> None:
        """5-digit ZIP codes (XXXXX where X is digit) should always be valid."""
        service = GeocodingService()
        assert service.is_zip_code(zip5) is True

    @given(zip9=st.from_regex(r"^\d{5}-\d{4}$", fullmatch=True))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_zip_plus_four_always_valid(self, zip9: str) -> None:
        """ZIP+4 codes (XXXXX-XXXX) should always be valid."""
        service = GeocodingService()
        assert service.is_zip_code(zip9) is True

    @given(
        non_zip=st.one_of(
            st.from_regex(r"^\d{1,4}$", fullmatch=True),
            st.from_regex(r"^\d{6,}$", fullmatch=True),
            st.from_regex(r"^[a-zA-Z]+$", fullmatch=True),
            st.from_regex(r"^\d{5}\d{4}$", fullmatch=True),
            st.from_regex(r"^\d{4}-\d{4}$", fullmatch=True),
            st.from_regex(r"^\d{5}-\d{3}$", fullmatch=True),
            st.from_regex(r"^\d{5}-\d{5}$", fullmatch=True),
            st.text(min_size=0, max_size=0),
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_non_zip_patterns_invalid(self, non_zip: str) -> None:
        """Non-ZIP patterns should always be invalid."""
        service = GeocodingService()
        assert service.is_zip_code(non_zip) is False

    @given(
        text=st.one_of(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N", "P")),
                min_size=1,
                max_size=20,
            ).filter(lambda x: not x.isdigit() or len(x) != 5),
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_random_text_mostly_invalid(self, text: str) -> None:
        """Random text that doesn't match ZIP pattern should be invalid."""
        service = GeocodingService()
        if not (text.isdigit() and len(text) == 5):
            import re

            pattern = re.compile(r"^\d{5}(?:-\d{4})?$")
            if not pattern.match(text):
                assert service.is_zip_code(text) is False


@pytest.mark.unit
class TestZipCodeBoundaryConditions:
    """Explicit boundary tests for ZIP code validation."""

    def test_minimum_valid_zip(self) -> None:
        """00000 should be valid (boundary case)."""
        service = GeocodingService()
        assert service.is_zip_code("00000") is True

    def test_maximum_valid_zip(self) -> None:
        """99999 should be valid (boundary case)."""
        service = GeocodingService()
        assert service.is_zip_code("99999") is True

    def test_minimum_valid_zip_plus_four(self) -> None:
        """00000-0000 should be valid (boundary case)."""
        service = GeocodingService()
        assert service.is_zip_code("00000-0000") is True

    def test_maximum_valid_zip_plus_four(self) -> None:
        """99999-9999 should be valid (boundary case)."""
        service = GeocodingService()
        assert service.is_zip_code("99999-9999") is True

    def test_four_digits_invalid(self) -> None:
        """4-digit numbers should be invalid."""
        service = GeocodingService()
        assert service.is_zip_code("1234") is False

    def test_six_digits_invalid(self) -> None:
        """6-digit numbers should be invalid."""
        service = GeocodingService()
        assert service.is_zip_code("123456") is False

    def test_empty_string_invalid(self) -> None:
        """Empty string should be invalid."""
        service = GeocodingService()
        assert service.is_zip_code("") is False

    def test_zip_with_space_invalid(self) -> None:
        """ZIP with space instead of dash should be invalid."""
        service = GeocodingService()
        assert service.is_zip_code("12345 6789") is False

    def test_zip_plus_three_invalid(self) -> None:
        """ZIP+3 should be invalid."""
        service = GeocodingService()
        assert service.is_zip_code("12345-123") is False


@pytest.mark.unit
class TestCoordinateValidationProperties:
    """Property tests for coordinate validation."""

    @given(
        lat=st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
        lon=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_valid_coordinates_return_true(self, lat: float, lon: float) -> None:
        """Coordinates within valid ranges should return True (with us_only=False)."""
        service = GeocodingService(data_source="auto")
        assert service.validate_coordinates(lat, lon, us_only=False) is True

    @given(
        lat=st.floats(min_value=90.001, max_value=1000, allow_nan=False, allow_infinity=False),
        lon=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_latitude_above_90_rejected(self, lat: float, lon: float) -> None:
        """Latitude above 90 should be rejected."""
        service = GeocodingService(data_source="auto")
        assert service.validate_coordinates(lat, lon, us_only=False) is False

    @given(
        lat=st.floats(min_value=-1000, max_value=-90.001, allow_nan=False, allow_infinity=False),
        lon=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_latitude_below_minus_90_rejected(self, lat: float, lon: float) -> None:
        """Latitude below -90 should be rejected."""
        service = GeocodingService(data_source="auto")
        assert service.validate_coordinates(lat, lon, us_only=False) is False

    @given(
        lat=st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
        lon=st.floats(min_value=180.001, max_value=1000, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_longitude_above_180_rejected(self, lat: float, lon: float) -> None:
        """Longitude above 180 should be rejected."""
        service = GeocodingService(data_source="auto")
        assert service.validate_coordinates(lat, lon, us_only=False) is False

    @given(
        lat=st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
        lon=st.floats(min_value=-1000, max_value=-180.001, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_longitude_below_minus_180_rejected(self, lat: float, lon: float) -> None:
        """Longitude below -180 should be rejected."""
        service = GeocodingService(data_source="auto")
        assert service.validate_coordinates(lat, lon, us_only=False) is False


@pytest.mark.unit
class TestCoordinateBoundaryConditions:
    """Explicit boundary tests for coordinate validation."""

    def test_north_pole_valid(self) -> None:
        """North pole (90, 0) should be valid."""
        service = GeocodingService(data_source="auto")
        assert service.validate_coordinates(90, 0, us_only=False) is True

    def test_south_pole_valid(self) -> None:
        """South pole (-90, 0) should be valid."""
        service = GeocodingService(data_source="auto")
        assert service.validate_coordinates(-90, 0, us_only=False) is True

    def test_dateline_east_valid(self) -> None:
        """Dateline east (0, 180) should be valid."""
        service = GeocodingService(data_source="auto")
        assert service.validate_coordinates(0, 180, us_only=False) is True

    def test_dateline_west_valid(self) -> None:
        """Dateline west (0, -180) should be valid."""
        service = GeocodingService(data_source="auto")
        assert service.validate_coordinates(0, -180, us_only=False) is True

    def test_origin_valid(self) -> None:
        """Origin (0, 0) should be valid."""
        service = GeocodingService(data_source="auto")
        assert service.validate_coordinates(0, 0, us_only=False) is True

    def test_all_corners_valid(self) -> None:
        """All corner coordinates should be valid."""
        service = GeocodingService(data_source="auto")
        corners = [
            (90, 180),
            (90, -180),
            (-90, 180),
            (-90, -180),
        ]
        for lat, lon in corners:
            assert service.validate_coordinates(lat, lon, us_only=False) is True

    def test_just_outside_lat_boundary(self) -> None:
        """Just outside latitude boundary should be invalid."""
        service = GeocodingService(data_source="auto")
        assert service.validate_coordinates(90.0001, 0, us_only=False) is False
        assert service.validate_coordinates(-90.0001, 0, us_only=False) is False

    def test_just_outside_lon_boundary(self) -> None:
        """Just outside longitude boundary should be invalid."""
        service = GeocodingService(data_source="auto")
        assert service.validate_coordinates(0, 180.0001, us_only=False) is False
        assert service.validate_coordinates(0, -180.0001, us_only=False) is False


@pytest.mark.unit
class TestFormatZipCodeProperties:
    """Property tests for ZIP code formatting."""

    @given(zip5=st.from_regex(r"^\d{5}$", fullmatch=True))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_five_digit_zip_format_adds_usa(self, zip5: str) -> None:
        """5-digit ZIP formatting should append ', USA'."""
        service = GeocodingService()
        result = service.format_zip_code(zip5)
        assert result == f"{zip5}, USA"

    @given(zip9=st.from_regex(r"^\d{5}-\d{4}$", fullmatch=True))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_zip_plus_four_strips_extension(self, zip9: str) -> None:
        """ZIP+4 formatting should strip extension and append ', USA'."""
        service = GeocodingService()
        result = service.format_zip_code(zip9)
        base_zip = zip9.split("-")[0]
        assert result == f"{base_zip}, USA"

    @given(zip5=st.from_regex(r"^\d{5}$", fullmatch=True))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_format_is_idempotent_after_first_call(self, zip5: str) -> None:
        """Formatting the same 5-digit ZIP twice gives same result."""
        service = GeocodingService()
        result1 = service.format_zip_code(zip5)
        result2 = service.format_zip_code(zip5)
        assert result1 == result2

    @given(zip9=st.from_regex(r"^\d{5}-\d{4}$", fullmatch=True))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_format_zip9_then_zip5_equivalent(self, zip9: str) -> None:
        """Formatting ZIP+4 should give same result as formatting its 5-digit base."""
        service = GeocodingService()
        result_from_zip9 = service.format_zip_code(zip9)
        base_zip = zip9.split("-")[0]
        result_from_zip5 = service.format_zip_code(base_zip)
        assert result_from_zip9 == result_from_zip5


@pytest.mark.unit
class TestFormatZipCodeBoundaryConditions:
    """Explicit boundary tests for ZIP code formatting."""

    def test_format_minimum_zip(self) -> None:
        """Format minimum ZIP 00000."""
        service = GeocodingService()
        assert service.format_zip_code("00000") == "00000, USA"

    def test_format_maximum_zip(self) -> None:
        """Format maximum ZIP 99999."""
        service = GeocodingService()
        assert service.format_zip_code("99999") == "99999, USA"

    def test_format_minimum_zip_plus_four(self) -> None:
        """Format minimum ZIP+4 00000-0000."""
        service = GeocodingService()
        assert service.format_zip_code("00000-0000") == "00000, USA"

    def test_format_maximum_zip_plus_four(self) -> None:
        """Format maximum ZIP+4 99999-9999."""
        service = GeocodingService()
        assert service.format_zip_code("99999-9999") == "99999, USA"
