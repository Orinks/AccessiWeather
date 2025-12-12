"""
Tests for OpenMeteoGeocodingClient.

Includes unit tests and property-based tests for the Open-Meteo Geocoding API client.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from hypothesis import (
    HealthCheck,
    given,
    settings,
    strategies as st,
)

from accessiweather.openmeteo_geocoding_client import (
    GeocodingResult,
    OpenMeteoGeocodingApiError,
    OpenMeteoGeocodingClient,
    OpenMeteoGeocodingNetworkError,
)


# Strategies for generating valid geocoding API responses
@st.composite
def geocoding_result_dict(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a valid geocoding result dictionary matching Open-Meteo API format."""
    return {
        "id": draw(st.integers(min_value=1, max_value=10000000)),
        "name": draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip())),
        "latitude": draw(st.floats(min_value=-90, max_value=90, allow_nan=False)),
        "longitude": draw(st.floats(min_value=-180, max_value=180, allow_nan=False)),
        "country": draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip())),
        "country_code": draw(st.from_regex(r"^[A-Z]{2}$", fullmatch=True)),
        "timezone": draw(
            st.sampled_from(
                [
                    "America/New_York",
                    "America/Los_Angeles",
                    "Europe/London",
                    "Asia/Tokyo",
                    "Australia/Sydney",
                    "UTC",
                ]
            )
        ),
        "admin1": draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        "admin2": draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        "admin3": draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        "elevation": draw(st.one_of(st.none(), st.floats(min_value=-500, max_value=9000))),
        "population": draw(st.one_of(st.none(), st.integers(min_value=0, max_value=50000000))),
    }


@st.composite
def geocoding_api_response(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a valid Open-Meteo Geocoding API response."""
    num_results = draw(st.integers(min_value=0, max_value=10))
    results = [draw(geocoding_result_dict()) for _ in range(num_results)]
    return {
        "results": results,
        "generationtime_ms": draw(st.floats(min_value=0, max_value=100)),
    }


@pytest.mark.unit
class TestGeocodingResultDataclass:
    """Tests for the GeocodingResult dataclass."""

    def test_display_name_with_admin1(self) -> None:
        """Display name should include name, admin1, and country."""
        result = GeocodingResult(
            name="New York",
            latitude=40.71,
            longitude=-74.01,
            country="United States",
            country_code="US",
            timezone="America/New_York",
            admin1="New York",
        )
        assert result.display_name == "New York, New York, United States"

    def test_display_name_without_admin1(self) -> None:
        """Display name should include name and country when admin1 is None."""
        result = GeocodingResult(
            name="London",
            latitude=51.51,
            longitude=-0.13,
            country="United Kingdom",
            country_code="GB",
            timezone="Europe/London",
        )
        assert result.display_name == "London, United Kingdom"


@pytest.mark.unit
class TestApiResponseParsingProperties:
    """
    Property-based tests for API response parsing.

    **Feature: openmeteo-geocoding, Property 1: API response parsing extracts all required fields**
    """

    @given(response=geocoding_api_response())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_parsing_preserves_required_fields(self, response: dict[str, Any]) -> None:
        """
        Verify API response parsing extracts all required fields.

        **Feature: openmeteo-geocoding, Property 1: API response parsing extracts all required fields**
        **Validates: Requirements 1.2**

        For any valid Open-Meteo Geocoding API response JSON, parsing it into
        GeocodingResult objects SHALL preserve all required fields (name, latitude,
        longitude, country, country_code, timezone) without data loss.
        """
        client = OpenMeteoGeocodingClient()
        try:
            results = client._parse_results(response)

            # Verify we got the expected number of results
            assert len(results) == len(response.get("results", []))

            # Verify each result preserves required fields
            for i, result in enumerate(results):
                raw = response["results"][i]
                assert result.name == raw["name"]
                assert result.latitude == raw["latitude"]
                assert result.longitude == raw["longitude"]
                assert result.country == raw.get("country", "")
                assert result.country_code == raw.get("country_code", "")
                assert result.timezone == raw.get("timezone", "")
                # Optional fields
                assert result.admin1 == raw.get("admin1")
                assert result.admin2 == raw.get("admin2")
                assert result.admin3 == raw.get("admin3")
                assert result.elevation == raw.get("elevation")
                assert result.population == raw.get("population")
        finally:
            client.close()

    def test_empty_results_returns_empty_list(self) -> None:
        """Parsing response with no results returns empty list."""
        client = OpenMeteoGeocodingClient()
        try:
            results = client._parse_results({"results": [], "generationtime_ms": 0.5})
            assert results == []
        finally:
            client.close()

    def test_missing_results_key_returns_empty_list(self) -> None:
        """Parsing response without 'results' key returns empty list."""
        client = OpenMeteoGeocodingClient()
        try:
            results = client._parse_results({"generationtime_ms": 0.5})
            assert results == []
        finally:
            client.close()

    def test_result_missing_required_field_skipped(self) -> None:
        """Results missing required fields are skipped."""
        client = OpenMeteoGeocodingClient()
        try:
            response = {
                "results": [
                    {"name": "Valid", "latitude": 40.0, "longitude": -74.0},  # Valid
                    {"name": "Missing lat", "longitude": -74.0},  # Missing latitude
                    {"latitude": 40.0, "longitude": -74.0},  # Missing name
                ],
                "generationtime_ms": 0.5,
            }
            results = client._parse_results(response)
            # Only the first result should be parsed
            assert len(results) == 1
            assert results[0].name == "Valid"
        finally:
            client.close()


@pytest.mark.unit
class TestOpenMeteoGeocodingClientRequests:
    """Unit tests for OpenMeteoGeocodingClient request handling."""

    def test_search_constructs_correct_url(self) -> None:
        """Search method should construct correct API URL and parameters."""
        client = OpenMeteoGeocodingClient()
        try:
            with patch.object(client, "_make_request") as mock_request:
                mock_request.return_value = {"results": []}
                client.search("New York", count=5, language="en")

                mock_request.assert_called_once_with(
                    "search",
                    {"name": "New York", "count": 5, "language": "en", "format": "json"},
                )
        finally:
            client.close()

    def test_search_limits_count_to_100(self) -> None:
        """Search should cap count at API maximum of 100."""
        client = OpenMeteoGeocodingClient()
        try:
            with patch.object(client, "_make_request") as mock_request:
                mock_request.return_value = {"results": []}
                client.search("Test", count=200)

                call_args = mock_request.call_args[0][1]
                assert call_args["count"] == 100
        finally:
            client.close()

    def test_client_uses_custom_user_agent(self) -> None:
        """Client should use custom user agent in requests."""
        client = OpenMeteoGeocodingClient(user_agent="TestAgent/1.0")
        try:
            assert client.client.headers["User-Agent"] == "TestAgent/1.0"
        finally:
            client.close()

    def test_client_uses_custom_timeout(self) -> None:
        """Client should use custom timeout."""
        client = OpenMeteoGeocodingClient(timeout=15.0)
        try:
            assert client.timeout == 15.0
        finally:
            client.close()


@pytest.mark.unit
class TestOpenMeteoGeocodingClientErrors:
    """Unit tests for OpenMeteoGeocodingClient error handling."""

    def test_http_400_raises_api_error(self) -> None:
        """HTTP 400 should raise OpenMeteoGeocodingApiError."""
        client = OpenMeteoGeocodingClient(max_retries=0)
        try:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.content = b'{"reason": "Invalid parameter"}'
            mock_response.json.return_value = {"reason": "Invalid parameter"}

            with patch.object(client.client, "get", return_value=mock_response):
                with pytest.raises(OpenMeteoGeocodingApiError) as exc_info:
                    client.search("test")
                assert "Invalid parameter" in str(exc_info.value)
        finally:
            client.close()

    def test_http_429_raises_rate_limit_error(self) -> None:
        """HTTP 429 should raise OpenMeteoGeocodingApiError with rate limit message."""
        client = OpenMeteoGeocodingClient(max_retries=0)
        try:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.content = b""

            with patch.object(client.client, "get", return_value=mock_response):
                with pytest.raises(OpenMeteoGeocodingApiError) as exc_info:
                    client.search("test")
                assert "Rate limit" in str(exc_info.value)
        finally:
            client.close()

    def test_http_500_raises_server_error(self) -> None:
        """HTTP 500 should raise OpenMeteoGeocodingApiError."""
        client = OpenMeteoGeocodingClient(max_retries=0)
        try:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.content = b""

            with patch.object(client.client, "get", return_value=mock_response):
                with pytest.raises(OpenMeteoGeocodingApiError) as exc_info:
                    client.search("test")
                assert "Server error" in str(exc_info.value)
        finally:
            client.close()

    def test_timeout_raises_network_error_after_retries(self) -> None:
        """Timeout should raise OpenMeteoGeocodingNetworkError after retries exhausted."""
        client = OpenMeteoGeocodingClient(max_retries=1, retry_delay=0.01)
        try:
            with patch.object(client.client, "get", side_effect=httpx.TimeoutException("Timeout")):
                with pytest.raises(OpenMeteoGeocodingNetworkError) as exc_info:
                    client.search("test")
                assert "timeout" in str(exc_info.value).lower()
        finally:
            client.close()

    def test_network_error_raises_after_retries(self) -> None:
        """Network error should raise OpenMeteoGeocodingNetworkError after retries."""
        client = OpenMeteoGeocodingClient(max_retries=1, retry_delay=0.01)
        try:
            with patch.object(
                client.client, "get", side_effect=httpx.NetworkError("Connection failed")
            ):
                with pytest.raises(OpenMeteoGeocodingNetworkError) as exc_info:
                    client.search("test")
                assert "Network error" in str(exc_info.value)
        finally:
            client.close()


@pytest.mark.unit
class TestOpenMeteoGeocodingClientRetry:
    """Unit tests for retry logic."""

    def test_retries_on_timeout(self) -> None:
        """Client should retry on timeout up to max_retries."""
        client = OpenMeteoGeocodingClient(max_retries=2, retry_delay=0.01)
        try:
            call_count = 0

            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise httpx.TimeoutException("Timeout")
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"results": []}
                return mock_resp

            with patch.object(client.client, "get", side_effect=side_effect):
                results = client.search("test")
                assert results == []
                assert call_count == 3  # Initial + 2 retries
        finally:
            client.close()

    def test_retries_on_network_error(self) -> None:
        """Client should retry on network error up to max_retries."""
        client = OpenMeteoGeocodingClient(max_retries=2, retry_delay=0.01)
        try:
            call_count = 0

            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise httpx.NetworkError("Connection failed")
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"results": []}
                return mock_resp

            with patch.object(client.client, "get", side_effect=side_effect):
                results = client.search("test")
                assert results == []
                assert call_count == 3
        finally:
            client.close()


@pytest.mark.unit
class TestGeocodingServiceFiltering:
    """
    Property-based tests for GeocodingService filtering.

    **Feature: openmeteo-geocoding, Property 5: NWS data source filters to US-only locations**
    **Feature: openmeteo-geocoding, Property 6: Non-NWS data source returns worldwide locations**
    """

    @given(
        results=st.lists(
            st.builds(
                GeocodingResult,
                name=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
                latitude=st.floats(min_value=-90, max_value=90, allow_nan=False),
                longitude=st.floats(min_value=-180, max_value=180, allow_nan=False),
                country=st.text(min_size=1, max_size=30).filter(lambda x: x.strip()),
                country_code=st.sampled_from(["US", "CA", "MX", "GB", "DE", "FR", "JP", "AU"]),
                timezone=st.sampled_from(["America/New_York", "Europe/London", "Asia/Tokyo"]),
            ),
            min_size=0,
            max_size=10,
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_nws_filters_to_us_only(self, results: list[GeocodingResult]) -> None:
        """
        Verify NWS data source filters to US-only locations.

        **Feature: openmeteo-geocoding, Property 5: NWS data source filters to US-only locations**
        **Validates: Requirements 2.3**

        For any set of geocoding results containing mixed country codes, when
        data_source is "nws", filtering SHALL return only results where
        country_code is "US".
        """
        from accessiweather.geocoding import GeocodingService

        service = GeocodingService(data_source="nws")
        filtered = service._filter_results_by_country(results)

        # All filtered results should have US country code
        for result in filtered:
            assert result.country_code == "US", (
                f"NWS filtering should only return US locations, got {result.country_code}"
            )

        # Count of US results should match filtered count
        us_count = sum(1 for r in results if r.country_code == "US")
        assert len(filtered) == us_count

    @given(
        results=st.lists(
            st.builds(
                GeocodingResult,
                name=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
                latitude=st.floats(min_value=-90, max_value=90, allow_nan=False),
                longitude=st.floats(min_value=-180, max_value=180, allow_nan=False),
                country=st.text(min_size=1, max_size=30).filter(lambda x: x.strip()),
                country_code=st.sampled_from(["US", "CA", "MX", "GB", "DE", "FR", "JP", "AU"]),
                timezone=st.sampled_from(["America/New_York", "Europe/London", "Asia/Tokyo"]),
            ),
            min_size=0,
            max_size=10,
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_non_nws_returns_worldwide(self, results: list[GeocodingResult]) -> None:
        """
        Verify non-NWS data source returns worldwide locations.

        **Feature: openmeteo-geocoding, Property 6: Non-NWS data source returns worldwide locations**
        **Validates: Requirements 2.4**

        For any set of geocoding results, when data_source is not "nws",
        filtering SHALL return all results regardless of country code.
        """
        from accessiweather.geocoding import GeocodingService

        service = GeocodingService(data_source="auto")
        filtered = service._filter_results_by_country(results)

        # All results should be returned
        assert len(filtered) == len(results)
        assert filtered == results


@pytest.mark.unit
class TestSuggestionLimitProperty:
    """
    Property-based tests for suggestion limits.

    **Feature: openmeteo-geocoding, Property 3: Suggestion count respects limit parameter**
    """

    @given(limit=st.integers(min_value=1, max_value=20))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_suggestion_count_respects_limit(self, limit: int) -> None:
        """
        Verify suggestion count respects limit parameter.

        **Feature: openmeteo-geocoding, Property 3: Suggestion count respects limit parameter**
        **Validates: Requirements 2.1**

        For any search query and positive integer limit, suggest_locations()
        SHALL return at most `limit` results.
        """
        from unittest.mock import patch

        from accessiweather.geocoding import GeocodingService

        service = GeocodingService(data_source="auto")

        # Create mock results exceeding the limit
        mock_results = [
            GeocodingResult(
                name=f"City{i}",
                latitude=40.0 + i,
                longitude=-74.0 + i,
                country="United States",
                country_code="US",
                timezone="America/New_York",
            )
            for i in range(limit * 3)
        ]

        with patch.object(service.client, "search", return_value=mock_results):
            suggestions = service.suggest_locations("test", limit=limit)
            assert len(suggestions) <= limit


@pytest.mark.unit
class TestDisplayNameProperty:
    """
    Property-based tests for display name generation.

    **Feature: openmeteo-geocoding, Property 4: Display text contains required components**
    """

    @given(
        name=st.text(min_size=1, max_size=30).filter(lambda x: x.strip()),
        country=st.text(min_size=1, max_size=30).filter(lambda x: x.strip()),
        admin1=st.one_of(st.none(), st.text(min_size=1, max_size=30).filter(lambda x: x.strip())),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_display_name_contains_required_components(
        self, name: str, country: str, admin1: str | None
    ) -> None:
        """
        Verify display name contains required components.

        **Feature: openmeteo-geocoding, Property 4: Display text contains required components**
        **Validates: Requirements 2.2**

        For any GeocodingResult with non-null name and country, the display_name
        property SHALL contain both the name and country.
        """
        result = GeocodingResult(
            name=name,
            latitude=40.0,
            longitude=-74.0,
            country=country,
            country_code="US",
            timezone="America/New_York",
            admin1=admin1,
        )

        display = result.display_name
        assert name in display, f"Display name should contain name '{name}'"
        assert country in display, f"Display name should contain country '{country}'"
        if admin1:
            assert admin1 in display, f"Display name should contain admin1 '{admin1}'"


@pytest.mark.unit
class TestCoordinateValidationProperty:
    """
    Property-based tests for coordinate validation.

    **Feature: openmeteo-geocoding, Property 7: Coordinate validation bounds check**
    **Feature: openmeteo-geocoding, Property 8: Non-NWS accepts any valid global coordinates**
    """

    @given(
        lat=st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
        lon=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_valid_coordinates_accepted_globally(self, lat: float, lon: float) -> None:
        """
        Verify valid coordinates are accepted with us_only=False.

        **Feature: openmeteo-geocoding, Property 7: Coordinate validation bounds check**
        **Validates: Requirements 4.1, 4.2**

        For any latitude and longitude values, validate_coordinates() with
        us_only=False SHALL return True if and only if -90 <= latitude <= 90
        AND -180 <= longitude <= 180.
        """
        from accessiweather.geocoding import GeocodingService

        service = GeocodingService(data_source="auto")
        result = service.validate_coordinates(lat, lon, us_only=False)
        assert result is True

    @given(
        lat=st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
        lon=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_non_nws_accepts_valid_global_coordinates(self, lat: float, lon: float) -> None:
        """
        Verify non-NWS accepts any valid global coordinates.

        **Feature: openmeteo-geocoding, Property 8: Non-NWS accepts any valid global coordinates**
        **Validates: Requirements 4.4**

        For any coordinates within valid bounds (-90 to 90 lat, -180 to 180 lon)
        and data_source not equal to "nws", validate_coordinates() SHALL return
        True without performing reverse geocoding.
        """
        from accessiweather.geocoding import GeocodingService

        service = GeocodingService(data_source="auto")
        # With us_only=None, it should use data_source to determine (auto = not us_only)
        result = service.validate_coordinates(lat, lon)
        assert result is True
