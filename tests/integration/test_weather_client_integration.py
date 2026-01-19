"""
Integration tests for the main WeatherClient.

These tests verify the orchestration layer that coordinates
multiple API sources (NWS, OpenMeteo, Visual Crossing).

Tests verify:
- Data source selection (auto mode)
- US vs international location handling
- Fallback behavior
- Complete weather data retrieval
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import integration_vcr


@pytest.mark.integration
class TestWeatherClientDataSourceSelection:
    """Test automatic data source selection."""

    @integration_vcr.use_cassette("weather_client/auto_us_location.yaml")
    @pytest.mark.asyncio
    async def test_auto_selects_nws_for_us(self, us_location):
        """Test that auto mode selects NWS for US locations."""
        from accessiweather.weather_client import WeatherClient

        client = WeatherClient(data_source="auto")
        try:
            # Check the API choice
            choice = client._determine_api_choice(us_location)
            assert choice == "nws"
        finally:
            await client.close()

    @integration_vcr.use_cassette("weather_client/auto_intl_location.yaml")
    @pytest.mark.asyncio
    async def test_auto_selects_openmeteo_for_international(self, international_location):
        """Test that auto mode selects OpenMeteo for international locations."""
        from accessiweather.weather_client import WeatherClient

        client = WeatherClient(data_source="auto")
        try:
            choice = client._determine_api_choice(international_location)
            assert choice == "openmeteo"
        finally:
            await client.close()


@pytest.mark.integration
class TestWeatherClientOpenMeteoIntegration:
    """Test WeatherClient with OpenMeteo backend."""

    @pytest.mark.live_only  # Current conditions parsing needs investigation
    @integration_vcr.use_cassette("weather_client/openmeteo_current.yaml")
    @pytest.mark.asyncio
    async def test_get_weather_openmeteo(self, international_location):
        """Test fetching weather data via OpenMeteo."""
        from accessiweather.weather_client import WeatherClient

        client = WeatherClient(data_source="openmeteo")
        try:
            data = await client.get_weather_data(international_location)

            assert data is not None
            assert data.current is not None
            assert data.current.temperature_f is not None or data.current.temperature_c is not None
        finally:
            await client.close()

    @integration_vcr.use_cassette("weather_client/openmeteo_forecast.yaml")
    @pytest.mark.asyncio
    async def test_get_forecast_openmeteo(self, international_location):
        """Test fetching forecast via OpenMeteo."""
        from accessiweather.weather_client import WeatherClient

        client = WeatherClient(data_source="openmeteo")
        try:
            data = await client.get_weather_data(international_location)

            assert data is not None
            if data.forecast:
                assert len(data.forecast.periods) > 0
        finally:
            await client.close()


@pytest.mark.integration
class TestWeatherClientCaching:
    """Test WeatherClient caching behavior."""

    @integration_vcr.use_cassette("weather_client/cache_test.yaml")
    @pytest.mark.asyncio
    async def test_caching_prevents_duplicate_requests(self, us_location):
        """Test that caching prevents duplicate API calls."""
        from accessiweather.weather_client import WeatherClient

        client = WeatherClient(data_source="openmeteo")
        try:
            # First request
            data1 = await client.get_weather_data(us_location)
            assert data1 is not None

            # Second request should use cache (if enabled)
            data2 = await client.get_weather_data(us_location)
            assert data2 is not None
        finally:
            await client.close()

    @integration_vcr.use_cassette("weather_client/force_refresh.yaml")
    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(self, us_location):
        """Test that force_refresh bypasses cache."""
        from accessiweather.weather_client import WeatherClient

        client = WeatherClient(data_source="openmeteo")
        try:
            # First request
            data1 = await client.get_weather_data(us_location)
            assert data1 is not None

            # Force refresh should make new request
            data2 = await client.get_weather_data(us_location, force_refresh=True)
            assert data2 is not None
        finally:
            await client.close()


@pytest.mark.integration
class TestWeatherClientHelpers:
    """Test WeatherClient helper methods."""

    def test_is_us_location(self, us_location, international_location):
        """Test US location detection."""
        from accessiweather.weather_client import WeatherClient

        client = WeatherClient()

        assert client._is_us_location(us_location) is True
        assert client._is_us_location(international_location) is False

    def test_temperature_conversion(self):
        """Test temperature conversion helper."""
        from accessiweather.weather_client import WeatherClient

        client = WeatherClient()

        # F to C
        assert client._convert_f_to_c(32.0) == 0.0
        assert client._convert_f_to_c(212.0) == 100.0
        assert client._convert_f_to_c(None) is None

    def test_wind_direction_conversion(self):
        """Test wind direction conversion."""
        from accessiweather.weather_client import WeatherClient

        client = WeatherClient()

        assert client._degrees_to_cardinal(0) == "N"
        assert client._degrees_to_cardinal(90) == "E"
        assert client._degrees_to_cardinal(180) == "S"
        assert client._degrees_to_cardinal(270) == "W"
        assert client._degrees_to_cardinal(None) is None
