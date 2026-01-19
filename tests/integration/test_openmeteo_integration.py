"""
Integration tests for OpenMeteo API client.

OpenMeteo is a free API that doesn't require authentication,
making it ideal for integration testing without API key concerns.

These tests verify:
- Current weather data retrieval
- Forecast data retrieval
- Hourly forecast data retrieval
- Proper data parsing and field presence
- Error handling for edge cases
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import integration_vcr


@pytest.mark.integration
class TestOpenMeteoCurrentWeather:
    """Test OpenMeteo current weather API."""

    @integration_vcr.use_cassette("openmeteo/current_weather_nyc.yaml")
    def test_get_current_weather_us_location(self, us_location):
        """Test fetching current weather for a US location."""
        from accessiweather.openmeteo_client import OpenMeteoApiClient

        client = OpenMeteoApiClient(timeout=30.0)
        try:
            data = client.get_current_weather(
                latitude=us_location.latitude,
                longitude=us_location.longitude,
            )

            # Verify response structure
            assert data is not None
            assert "current" in data
            assert "timezone" in data

            # Verify current conditions fields
            current = data["current"]
            assert "temperature_2m" in current
            assert "relative_humidity_2m" in current
            assert "weather_code" in current
            assert "wind_speed_10m" in current

            # Verify reasonable values
            temp = current["temperature_2m"]
            assert -50 < temp < 150  # Reasonable temperature range in F

            humidity = current["relative_humidity_2m"]
            assert 0 <= humidity <= 100
        finally:
            client.close()

    @integration_vcr.use_cassette("openmeteo/current_weather_london.yaml")
    def test_get_current_weather_international_location(self, international_location):
        """Test fetching current weather for an international location."""
        from accessiweather.openmeteo_client import OpenMeteoApiClient

        client = OpenMeteoApiClient(timeout=30.0)
        try:
            data = client.get_current_weather(
                latitude=international_location.latitude,
                longitude=international_location.longitude,
            )

            assert data is not None
            assert "current" in data
            assert data["current"]["temperature_2m"] is not None
        finally:
            client.close()

    @integration_vcr.use_cassette("openmeteo/current_weather_celsius.yaml")
    def test_get_current_weather_celsius(self, us_location):
        """Test fetching current weather in Celsius."""
        from accessiweather.openmeteo_client import OpenMeteoApiClient

        client = OpenMeteoApiClient(timeout=30.0)
        try:
            data = client.get_current_weather(
                latitude=us_location.latitude,
                longitude=us_location.longitude,
                temperature_unit="celsius",
            )

            assert data is not None
            temp = data["current"]["temperature_2m"]
            # Celsius values should be in reasonable range
            assert -50 < temp < 60
        finally:
            client.close()


@pytest.mark.integration
class TestOpenMeteoForecast:
    """Test OpenMeteo forecast API."""

    @integration_vcr.use_cassette("openmeteo/forecast_daily.yaml")
    def test_get_daily_forecast(self, us_location):
        """Test fetching daily forecast."""
        from accessiweather.openmeteo_client import OpenMeteoApiClient

        client = OpenMeteoApiClient(timeout=30.0)
        try:
            data = client.get_forecast(
                latitude=us_location.latitude,
                longitude=us_location.longitude,
                days=7,
            )

            assert data is not None
            assert "daily" in data

            daily = data["daily"]
            assert "time" in daily
            assert "temperature_2m_max" in daily
            assert "temperature_2m_min" in daily
            assert "weather_code" in daily

            # Should have 7 days of data
            assert len(daily["time"]) == 7
            assert len(daily["temperature_2m_max"]) == 7
        finally:
            client.close()

    @integration_vcr.use_cassette("openmeteo/forecast_extended.yaml")
    def test_get_extended_forecast(self, us_location):
        """Test fetching extended 16-day forecast."""
        from accessiweather.openmeteo_client import OpenMeteoApiClient

        client = OpenMeteoApiClient(timeout=30.0)
        try:
            data = client.get_forecast(
                latitude=us_location.latitude,
                longitude=us_location.longitude,
                days=16,
            )

            assert data is not None
            daily = data["daily"]
            # Should have up to 16 days
            assert len(daily["time"]) <= 16
        finally:
            client.close()


@pytest.mark.integration
class TestOpenMeteoHourlyForecast:
    """Test OpenMeteo hourly forecast API."""

    @integration_vcr.use_cassette("openmeteo/hourly_forecast.yaml")
    def test_get_hourly_forecast(self, us_location):
        """Test fetching hourly forecast."""
        from accessiweather.openmeteo_client import OpenMeteoApiClient

        client = OpenMeteoApiClient(timeout=30.0)
        try:
            data = client.get_hourly_forecast(
                latitude=us_location.latitude,
                longitude=us_location.longitude,
                hours=48,
            )

            assert data is not None
            assert "hourly" in data

            hourly = data["hourly"]
            assert "time" in hourly
            assert "temperature_2m" in hourly
            assert "precipitation_probability" in hourly
            assert "weather_code" in hourly

            # Should have hourly data
            assert len(hourly["time"]) > 0
        finally:
            client.close()


@pytest.mark.integration
class TestOpenMeteoWeatherCodes:
    """Test OpenMeteo weather code descriptions."""

    def test_weather_code_descriptions(self):
        """Test that weather codes are properly described."""
        from accessiweather.openmeteo_client import OpenMeteoApiClient

        # Test various weather codes
        test_cases = [
            (0, "Clear sky"),
            (1, "Mainly clear"),
            (2, "Partly cloudy"),
            (3, "Overcast"),
            (61, "Slight rain"),
            (71, "Slight snow fall"),
            (95, "Thunderstorm"),
        ]

        for code, expected_desc in test_cases:
            desc = OpenMeteoApiClient.get_weather_description(code)
            assert expected_desc.lower() in desc.lower(), (
                f"Code {code}: expected '{expected_desc}', got '{desc}'"
            )

    def test_unknown_weather_code(self):
        """Test handling of unknown weather codes."""
        from accessiweather.openmeteo_client import OpenMeteoApiClient

        desc = OpenMeteoApiClient.get_weather_description(999)
        assert "unknown" in desc.lower() or "999" in desc


@pytest.mark.integration
class TestOpenMeteoErrorHandling:
    """Test OpenMeteo error handling."""

    @integration_vcr.use_cassette("openmeteo/error_invalid_coords.yaml")
    def test_invalid_coordinates(self):
        """Test handling of invalid coordinates."""
        from accessiweather.openmeteo_client import OpenMeteoApiClient, OpenMeteoApiError

        client = OpenMeteoApiClient(timeout=30.0)
        try:
            # Latitude out of range (-90 to 90)
            with pytest.raises(OpenMeteoApiError):
                client.get_current_weather(
                    latitude=200.0,  # Invalid
                    longitude=-74.0,
                )
        finally:
            client.close()
