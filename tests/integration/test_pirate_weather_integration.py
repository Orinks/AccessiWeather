"""
Integration tests for Pirate Weather API client.

Pirate Weather requires an API key. Tests will use recorded cassettes
unless VCR_RECORD_MODE=all is set (which requires a valid API key).

These tests verify:
- Current conditions parsing
- Forecast data parsing (daily + hourly)
- Alert parsing (WMO global alerts)
- Minutely precipitation data
- Daily summary text
- Error handling
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import integration_vcr


@pytest.mark.integration
class TestPirateWeatherCurrentConditions:
    """Test Pirate Weather current conditions API."""

    @integration_vcr.use_cassette("pirate_weather/current_nyc.yaml")
    @pytest.mark.asyncio
    async def test_get_current_conditions_us(self, us_location, pirate_weather_api_key):
        """Test fetching current conditions for a US location."""
        from accessiweather.pirate_weather_client import PirateWeatherClient

        client = PirateWeatherClient(api_key=pirate_weather_api_key)
        conditions = await client.get_current_conditions(us_location)

        assert conditions is not None
        assert conditions.temperature_f is not None
        assert -60 < conditions.temperature_f < 150
        assert conditions.temperature_c is not None
        assert conditions.condition is not None
        assert conditions.humidity is not None
        assert 0 <= conditions.humidity <= 100

    @integration_vcr.use_cassette("pirate_weather/current_london.yaml")
    @pytest.mark.asyncio
    async def test_get_current_conditions_international(
        self, international_location, pirate_weather_api_key
    ):
        """Test fetching current conditions for an international location."""
        from accessiweather.pirate_weather_client import PirateWeatherClient

        client = PirateWeatherClient(api_key=pirate_weather_api_key)
        conditions = await client.get_current_conditions(international_location)

        assert conditions is not None
        assert conditions.temperature_f is not None
        assert conditions.condition is not None

    @integration_vcr.use_cassette("pirate_weather/current_wind_gust.yaml")
    @pytest.mark.asyncio
    async def test_current_conditions_wind_data(self, us_location, pirate_weather_api_key):
        """Test that wind data is properly parsed."""
        from accessiweather.pirate_weather_client import PirateWeatherClient

        client = PirateWeatherClient(api_key=pirate_weather_api_key)
        conditions = await client.get_current_conditions(us_location)

        assert conditions is not None
        assert conditions.wind_speed_mph is not None
        assert conditions.wind_direction is not None


@pytest.mark.integration
class TestPirateWeatherForecast:
    """Test Pirate Weather forecast API."""

    @integration_vcr.use_cassette("pirate_weather/forecast_nyc.yaml")
    @pytest.mark.asyncio
    async def test_get_forecast_7_days(self, us_location, pirate_weather_api_key):
        """Test fetching 7-day forecast."""
        from accessiweather.pirate_weather_client import PirateWeatherClient

        client = PirateWeatherClient(api_key=pirate_weather_api_key)
        forecast = await client.get_forecast(us_location, days=7)

        assert forecast is not None
        assert forecast.has_data()
        assert len(forecast.periods) <= 7
        assert forecast.periods[0].name == "Today"
        assert forecast.periods[0].temperature is not None

    @integration_vcr.use_cassette("pirate_weather/forecast_daily_summary.yaml")
    @pytest.mark.asyncio
    async def test_daily_summary_present(self, us_location, pirate_weather_api_key):
        """Test that daily summary text is parsed from the response."""
        from accessiweather.pirate_weather_client import PirateWeatherClient

        client = PirateWeatherClient(api_key=pirate_weather_api_key)
        forecast = await client.get_forecast(us_location)

        assert forecast is not None
        # PW returns a daily summary string like "Light rain throughout the week."
        # It may be None if PW doesn't generate one, but should be a string when present
        if forecast.summary is not None:
            assert isinstance(forecast.summary, str)
            assert len(forecast.summary) > 0


@pytest.mark.integration
class TestPirateWeatherHourlyForecast:
    """Test Pirate Weather hourly forecast API."""

    @integration_vcr.use_cassette("pirate_weather/hourly_nyc.yaml")
    @pytest.mark.asyncio
    async def test_get_hourly_forecast(self, us_location, pirate_weather_api_key):
        """Test fetching hourly forecast (extended to 168 hours)."""
        from accessiweather.pirate_weather_client import PirateWeatherClient

        client = PirateWeatherClient(api_key=pirate_weather_api_key)
        hourly = await client.get_hourly_forecast(us_location)

        assert hourly is not None
        assert hourly.has_data()
        # With extend=hourly, should get up to 168 hours
        assert len(hourly.periods) > 24


@pytest.mark.integration
class TestPirateWeatherAlerts:
    """Test Pirate Weather alerts API (WMO global alerts)."""

    @integration_vcr.use_cassette("pirate_weather/alerts_nyc.yaml")
    @pytest.mark.asyncio
    async def test_get_alerts_us(self, us_location, pirate_weather_api_key):
        """Test fetching alerts for a US location."""
        from accessiweather.pirate_weather_client import PirateWeatherClient

        client = PirateWeatherClient(api_key=pirate_weather_api_key)
        alerts = await client.get_alerts(us_location)

        assert alerts is not None
        # NYC may or may not have active alerts
        assert isinstance(alerts.alerts, list)

    @integration_vcr.use_cassette("pirate_weather/alerts_tromso.yaml")
    @pytest.mark.asyncio
    async def test_get_alerts_international(self, norway_location, pirate_weather_api_key):
        """Test fetching WMO alerts for an international location."""
        from accessiweather.pirate_weather_client import PirateWeatherClient

        client = PirateWeatherClient(api_key=pirate_weather_api_key)
        alerts = await client.get_alerts(norway_location)

        assert alerts is not None
        assert isinstance(alerts.alerts, list)
        # Tromsø cassette was recorded with active alerts
        if alerts.alerts:
            alert = alerts.alerts[0]
            assert alert.title is not None
            assert alert.severity is not None
            assert alert.source == "PirateWeather"


@pytest.mark.integration
class TestPirateWeatherMinutely:
    """Test Pirate Weather minutely precipitation data."""

    @integration_vcr.use_cassette("pirate_weather/minutely_nyc.yaml")
    @pytest.mark.asyncio
    async def test_minutely_data_present(self, us_location, pirate_weather_api_key):
        """Test that minutely precipitation data is returned."""
        from accessiweather.pirate_weather_client import PirateWeatherClient

        client = PirateWeatherClient(api_key=pirate_weather_api_key)
        data = await client.get_forecast_data(us_location)

        assert data is not None
        minutely = data.get("minutely", {})
        assert "data" in minutely
        # Should have ~61 data points (current minute + next 60)
        assert len(minutely["data"]) > 0

        # Each data point should have intensity and probability
        point = minutely["data"][0]
        assert "precipIntensity" in point
        assert "precipProbability" in point


@pytest.mark.integration
class TestPirateWeatherErrorHandling:
    """Test Pirate Weather error handling."""

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, us_location):
        """Test that invalid API key raises appropriate error."""
        from accessiweather.pirate_weather_client import (
            PirateWeatherApiError,
            PirateWeatherClient,
        )

        client = PirateWeatherClient(api_key="invalid-key-12345")
        with pytest.raises(PirateWeatherApiError):
            await client.get_current_conditions(us_location)
