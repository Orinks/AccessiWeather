"""
Integration tests for NWS (National Weather Service) API client.

NWS is a free API that doesn't require authentication, making it ideal
for integration testing. Note: NWS only provides data for US locations.

These tests verify:
- Point data retrieval
- Current conditions from observation stations
- Forecast data retrieval
- Hourly forecast data retrieval
- Weather alerts retrieval
- Forecast discussions
- Error handling for invalid/international locations
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import integration_vcr


@pytest.mark.integration
class TestNwsPointData:
    """Test NWS point data API."""

    @integration_vcr.use_cassette("nws/point_nyc.yaml")
    def test_get_point_data_us_location(self, us_location):
        """Test fetching point data for a US location."""
        from accessiweather.api.nws import NwsApiWrapper

        wrapper = NwsApiWrapper()
        data = wrapper.get_point_data(
            lat=us_location.latitude,
            lon=us_location.longitude,
        )

        # Verify response structure
        assert data is not None
        assert "properties" in data

        # Verify essential properties are present
        properties = data["properties"]
        assert properties.get("forecast") is not None
        assert properties.get("forecastHourly") is not None
        assert properties.get("observationStations") is not None

    @integration_vcr.use_cassette("nws/point_alaska.yaml")
    def test_get_point_data_alaska(self, alaska_location):
        """Test fetching point data for Alaska (edge case for NWS coverage)."""
        from accessiweather.api.nws import NwsApiWrapper

        wrapper = NwsApiWrapper()
        data = wrapper.get_point_data(
            lat=alaska_location.latitude,
            lon=alaska_location.longitude,
        )

        assert data is not None
        assert "properties" in data
        # Alaska should still have forecast URLs
        assert data["properties"].get("forecast") is not None

    @pytest.mark.live_only  # Error handling varies between live and recorded responses
    @integration_vcr.use_cassette("nws/point_international_error.yaml")
    def test_get_point_data_international_fails(self, international_location):
        """Test that NWS returns error for international locations."""
        from accessiweather.api.nws import NwsApiWrapper
        from accessiweather.api_client import NoaaApiError

        wrapper = NwsApiWrapper()

        # NWS should return 404 for international locations
        with pytest.raises((NoaaApiError, Exception)):
            wrapper.get_point_data(
                lat=international_location.latitude,
                lon=international_location.longitude,
            )


@pytest.mark.integration
class TestNwsCurrentConditions:
    """Test NWS current conditions API."""

    @integration_vcr.use_cassette("nws/current_nyc.yaml")
    def test_get_current_conditions(self, us_location):
        """Test fetching current conditions for a US location."""
        from accessiweather.api.nws import NwsApiWrapper

        wrapper = NwsApiWrapper()
        data = wrapper.get_current_conditions(
            lat=us_location.latitude,
            lon=us_location.longitude,
        )

        # Verify response structure
        assert data is not None
        # Current conditions should have properties
        assert "properties" in data or "temperature" in str(data).lower()

    @integration_vcr.use_cassette("nws/current_alaska.yaml")
    def test_get_current_conditions_alaska(self, alaska_location):
        """Test fetching current conditions for Alaska."""
        from accessiweather.api.nws import NwsApiWrapper

        wrapper = NwsApiWrapper()
        data = wrapper.get_current_conditions(
            lat=alaska_location.latitude,
            lon=alaska_location.longitude,
        )

        assert data is not None


@pytest.mark.integration
class TestNwsForecast:
    """Test NWS forecast API."""

    @integration_vcr.use_cassette("nws/forecast_nyc.yaml")
    def test_get_forecast(self, us_location):
        """Test fetching forecast for a US location."""
        from accessiweather.api.nws import NwsApiWrapper

        wrapper = NwsApiWrapper()
        data = wrapper.get_forecast(
            lat=us_location.latitude,
            lon=us_location.longitude,
        )

        # Verify response structure
        assert data is not None
        assert "properties" in data

        # Verify forecast periods are present
        properties = data["properties"]
        assert "periods" in properties
        assert len(properties["periods"]) > 0

        # Check first period has expected fields
        first_period = properties["periods"][0]
        assert "name" in first_period
        assert "temperature" in first_period
        assert "shortForecast" in first_period

    @integration_vcr.use_cassette("nws/forecast_alaska.yaml")
    def test_get_forecast_alaska(self, alaska_location):
        """Test fetching forecast for Alaska."""
        from accessiweather.api.nws import NwsApiWrapper

        wrapper = NwsApiWrapper()
        data = wrapper.get_forecast(
            lat=alaska_location.latitude,
            lon=alaska_location.longitude,
        )

        assert data is not None
        assert "properties" in data
        assert "periods" in data["properties"]


@pytest.mark.integration
class TestNwsHourlyForecast:
    """Test NWS hourly forecast API."""

    @integration_vcr.use_cassette("nws/hourly_nyc.yaml")
    def test_get_hourly_forecast(self, us_location):
        """Test fetching hourly forecast for a US location."""
        from accessiweather.api.nws import NwsApiWrapper

        wrapper = NwsApiWrapper()
        data = wrapper.get_hourly_forecast(
            lat=us_location.latitude,
            lon=us_location.longitude,
        )

        # Verify response structure
        assert data is not None
        assert "properties" in data

        # Verify hourly periods are present
        properties = data["properties"]
        assert "periods" in properties
        assert len(properties["periods"]) > 0

        # Check first period has expected fields
        first_period = properties["periods"][0]
        assert "startTime" in first_period
        assert "temperature" in first_period


@pytest.mark.integration
class TestNwsStations:
    """Test NWS observation stations API."""

    @integration_vcr.use_cassette("nws/stations_nyc.yaml")
    def test_get_stations(self, us_location):
        """Test fetching observation stations for a US location."""
        from accessiweather.api.nws import NwsApiWrapper

        wrapper = NwsApiWrapper()
        data = wrapper.get_stations(
            lat=us_location.latitude,
            lon=us_location.longitude,
        )

        # Verify response structure
        assert data is not None
        assert "features" in data
        assert len(data["features"]) > 0

        # Check first station has expected fields
        first_station = data["features"][0]
        assert "properties" in first_station
        assert "stationIdentifier" in first_station["properties"]


@pytest.mark.integration
class TestNwsAlerts:
    """Test NWS alerts API."""

    @integration_vcr.use_cassette("nws/alerts_nyc.yaml")
    def test_get_alerts(self, us_location):
        """Test fetching alerts for a US location."""
        from accessiweather.api.nws import NwsApiWrapper

        wrapper = NwsApiWrapper()
        data = wrapper.get_alerts(
            lat=us_location.latitude,
            lon=us_location.longitude,
        )

        # Verify response structure
        assert data is not None
        # Alerts response should have features array (may be empty if no active alerts)
        assert "features" in data
        assert isinstance(data["features"], list)

    @integration_vcr.use_cassette("nws/alerts_alaska.yaml")
    def test_get_alerts_alaska(self, alaska_location):
        """Test fetching alerts for Alaska."""
        from accessiweather.api.nws import NwsApiWrapper

        wrapper = NwsApiWrapper()
        data = wrapper.get_alerts(
            lat=alaska_location.latitude,
            lon=alaska_location.longitude,
        )

        assert data is not None
        assert "features" in data


@pytest.mark.integration
class TestNwsDiscussion:
    """Test NWS forecast discussion API."""

    @integration_vcr.use_cassette("nws/discussion_nyc.yaml")
    def test_get_discussion(self, us_location):
        """Test fetching forecast discussion for a US location."""
        from accessiweather.api.nws import NwsApiWrapper

        wrapper = NwsApiWrapper()
        discussion = wrapper.get_discussion(
            lat=us_location.latitude,
            lon=us_location.longitude,
        )

        # Discussion should be a string or None
        # It may be None if no discussion is available
        assert discussion is None or isinstance(discussion, str)

        # If we got a discussion, it should have some content
        if discussion:
            assert len(discussion) > 100  # Discussions are typically lengthy


@pytest.mark.integration
class TestNwsLocationIdentification:
    """Test NWS location type identification."""

    @integration_vcr.use_cassette("nws/location_type_nyc.yaml")
    def test_identify_location_type(self, us_location):
        """Test identifying location type for a US location."""
        from accessiweather.api.nws import NwsApiWrapper

        wrapper = NwsApiWrapper()
        location_type, location_id = wrapper.identify_location_type(
            lat=us_location.latitude,
            lon=us_location.longitude,
        )

        # Should identify as county, forecast, fire, or state
        assert location_type in ("county", "forecast", "fire", "state", None)
        # If we got a type, we should have an ID
        if location_type:
            assert location_id is not None


@pytest.mark.integration
class TestNwsErrorHandling:
    """Test NWS error handling."""

    @pytest.mark.live_only  # Error handling varies between live and recorded responses
    @integration_vcr.use_cassette("nws/error_invalid_coords.yaml")
    def test_invalid_coordinates(self):
        """Test handling of coordinates outside NWS coverage."""
        from accessiweather.api.nws import NwsApiWrapper
        from accessiweather.api_client import ApiClientError, NoaaApiError

        wrapper = NwsApiWrapper()

        # Ocean coordinates (no NWS coverage)
        with pytest.raises((NoaaApiError, ApiClientError, Exception)):
            wrapper.get_point_data(
                lat=0.0,  # Equator
                lon=0.0,  # Prime meridian (Atlantic Ocean)
            )
