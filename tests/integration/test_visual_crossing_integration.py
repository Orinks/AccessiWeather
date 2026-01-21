"""
Integration tests for Visual Crossing API client.

Visual Crossing requires an API key. Tests will use recorded cassettes
unless RECORD_MODE=all is set (which requires a valid API key).

These tests verify:
- Current conditions parsing
- Forecast data parsing
- Hourly forecast parsing
- Alert parsing
- Historical data retrieval
- Error handling
"""

from __future__ import annotations

from datetime import datetime

import pytest

from tests.integration.conftest import integration_vcr


@pytest.mark.integration
class TestVisualCrossingCurrentConditions:
    """
    Test Visual Crossing current conditions API.

    These tests require a valid API key to record cassettes.
    Run with VCR_RECORD_MODE=all and VISUAL_CROSSING_API_KEY set.
    """

    @pytest.mark.live_only
    @integration_vcr.use_cassette("visual_crossing/current_nyc.yaml")
    @pytest.mark.asyncio
    async def test_get_current_conditions(self, us_location, visual_crossing_api_key):
        """Test fetching current conditions."""
        from accessiweather.visual_crossing_client import VisualCrossingClient

        client = VisualCrossingClient(api_key=visual_crossing_api_key)
        conditions = await client.get_current_conditions(us_location)

        assert conditions is not None
        # Temperature should be present and reasonable
        assert conditions.temperature_f is not None
        assert -50 < conditions.temperature_f < 150

        # Basic fields should be populated
        assert conditions.condition is not None
        assert conditions.humidity is not None
        assert 0 <= conditions.humidity <= 100

    @pytest.mark.live_only
    @integration_vcr.use_cassette("visual_crossing/current_london.yaml")
    @pytest.mark.asyncio
    async def test_get_current_conditions_international(
        self, international_location, visual_crossing_api_key
    ):
        """Test fetching current conditions for international location."""
        from accessiweather.visual_crossing_client import VisualCrossingClient

        client = VisualCrossingClient(api_key=visual_crossing_api_key)
        conditions = await client.get_current_conditions(international_location)

        assert conditions is not None
        assert conditions.temperature_f is not None
        assert conditions.temperature_c is not None


@pytest.mark.integration
class TestVisualCrossingForecast:
    """Test Visual Crossing forecast API."""

    @pytest.mark.live_only
    @integration_vcr.use_cassette("visual_crossing/forecast_nyc.yaml")
    @pytest.mark.asyncio
    async def test_get_forecast(self, us_location, visual_crossing_api_key):
        """Test fetching forecast."""
        from accessiweather.visual_crossing_client import VisualCrossingClient

        client = VisualCrossingClient(api_key=visual_crossing_api_key)
        forecast = await client.get_forecast(us_location)

        assert forecast is not None
        assert len(forecast.periods) > 0

        # Check first period
        first_period = forecast.periods[0]
        assert first_period.name is not None
        assert first_period.temperature is not None
        assert first_period.short_forecast is not None

    @pytest.mark.live_only
    @integration_vcr.use_cassette("visual_crossing/forecast_fields.yaml")
    @pytest.mark.asyncio
    async def test_forecast_has_all_fields(self, us_location, visual_crossing_api_key):
        """Test that forecast periods have expected fields."""
        from accessiweather.visual_crossing_client import VisualCrossingClient

        client = VisualCrossingClient(api_key=visual_crossing_api_key)
        forecast = await client.get_forecast(us_location)

        for period in forecast.periods[:3]:  # Check first 3 days
            assert period.name is not None
            assert period.temperature is not None
            # Optional fields may be None but shouldn't error
            _ = period.wind_speed
            _ = period.wind_direction
            _ = period.precipitation_probability


@pytest.mark.integration
class TestVisualCrossingHourlyForecast:
    """Test Visual Crossing hourly forecast API."""

    @pytest.mark.live_only
    @integration_vcr.use_cassette("visual_crossing/hourly_nyc.yaml")
    @pytest.mark.asyncio
    async def test_get_hourly_forecast(self, us_location, visual_crossing_api_key):
        """Test fetching hourly forecast."""
        from accessiweather.visual_crossing_client import VisualCrossingClient

        client = VisualCrossingClient(api_key=visual_crossing_api_key)
        hourly = await client.get_hourly_forecast(us_location)

        assert hourly is not None
        assert len(hourly.periods) > 0

        # Check first hour
        first_hour = hourly.periods[0]
        assert first_hour.start_time is not None
        assert first_hour.temperature is not None


@pytest.mark.integration
class TestVisualCrossingAlerts:
    """Test Visual Crossing alerts API."""

    @integration_vcr.use_cassette("visual_crossing/alerts_nyc.yaml")
    @pytest.mark.asyncio
    async def test_get_alerts(self, us_location, visual_crossing_api_key):
        """Test fetching weather alerts."""
        from accessiweather.visual_crossing_client import VisualCrossingClient

        client = VisualCrossingClient(api_key=visual_crossing_api_key)
        alerts = await client.get_alerts(us_location)

        # Alerts may or may not be present, but should return valid object
        assert alerts is not None
        assert hasattr(alerts, "alerts")
        assert isinstance(alerts.alerts, list)


@pytest.mark.integration
class TestVisualCrossingHistory:
    """Test Visual Crossing historical data API."""

    @pytest.mark.live_only
    @integration_vcr.use_cassette("visual_crossing/history_nyc.yaml")
    @pytest.mark.asyncio
    async def test_get_history(self, us_location, visual_crossing_api_key):
        """Test fetching historical weather data."""
        from accessiweather.visual_crossing_client import VisualCrossingClient

        client = VisualCrossingClient(api_key=visual_crossing_api_key)

        # Use fixed dates matching the recorded cassette
        # When recording new cassettes, use current dates and update these
        start_date = datetime(2026, 1, 18)
        end_date = datetime(2026, 1, 20)

        history = await client.get_history(us_location, start_date, end_date)

        assert history is not None
        assert len(history.periods) > 0


@pytest.mark.integration
class TestVisualCrossingErrorHandling:
    """Test Visual Crossing error handling."""

    @pytest.mark.live_only
    @integration_vcr.use_cassette("visual_crossing/error_invalid_key.yaml")
    @pytest.mark.asyncio
    async def test_invalid_api_key(self, us_location):
        """Test handling of invalid API key."""
        from accessiweather.visual_crossing_client import (
            VisualCrossingApiError,
            VisualCrossingClient,
        )

        client = VisualCrossingClient(api_key="invalid-key")

        with pytest.raises(VisualCrossingApiError) as exc_info:
            await client.get_current_conditions(us_location)

        assert exc_info.value.status_code == 401 or "Invalid" in str(exc_info.value)


@pytest.mark.integration
class TestVisualCrossingSeverityMapping:
    """Test Visual Crossing severity mapping."""

    def test_severity_mapping(self):
        """Test that severity levels are mapped correctly."""
        from accessiweather.visual_crossing_client import VisualCrossingClient

        client = VisualCrossingClient(api_key="test")

        # Test mapping function
        assert client._map_visual_crossing_severity("extreme") == "Extreme"
        assert client._map_visual_crossing_severity("severe") == "Severe"
        assert client._map_visual_crossing_severity("moderate") == "Moderate"
        assert client._map_visual_crossing_severity("minor") == "Minor"
        assert client._map_visual_crossing_severity("unknown") == "Unknown"
        assert client._map_visual_crossing_severity(None) == "Unknown"

        # Test case insensitivity
        assert client._map_visual_crossing_severity("EXTREME") == "Extreme"
        assert client._map_visual_crossing_severity("Severe") == "Severe"
