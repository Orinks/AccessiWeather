"""Tests for OpenMeteoApiClient API methods."""

from unittest.mock import patch

import pytest

from .conftest import SAMPLE_CURRENT_WEATHER_DATA, SAMPLE_FORECAST_DATA, SAMPLE_HOURLY_FORECAST_DATA


@pytest.mark.unit
def test_get_current_weather_success(openmeteo_client):
    """Test getting current weather successfully."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_CURRENT_WEATHER_DATA

        result = openmeteo_client.get_current_weather(lat, lon)

        assert result == SAMPLE_CURRENT_WEATHER_DATA
        mock_request.assert_called_once_with(
            "forecast",
            {
                "latitude": lat,
                "longitude": lon,
                "current": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "is_day",
                    "precipitation",
                    "weather_code",
                    "cloud_cover",
                    "pressure_msl",
                    "surface_pressure",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "wind_gusts_10m",
                ],
                "daily": [
                    "sunrise",
                    "sunset",
                ],
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "auto",
                "forecast_days": 1,
            },
        )


@pytest.mark.unit
def test_get_current_weather_metric_units(openmeteo_client):
    """Test getting current weather with metric units."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_CURRENT_WEATHER_DATA

        openmeteo_client.get_current_weather(
            lat, lon, temperature_unit="celsius", wind_speed_unit="kmh", precipitation_unit="mm"
        )

        call_args = mock_request.call_args[0][1]
        assert call_args["temperature_unit"] == "celsius"
        assert call_args["wind_speed_unit"] == "kmh"
        assert call_args["precipitation_unit"] == "mm"


@pytest.mark.unit
def test_get_forecast_success(openmeteo_client):
    """Test getting forecast successfully."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_FORECAST_DATA

        result = openmeteo_client.get_forecast(lat, lon)

        assert result == SAMPLE_FORECAST_DATA
        call_args = mock_request.call_args[0][1]
        assert call_args["latitude"] == lat
        assert call_args["longitude"] == lon
        assert call_args["forecast_days"] == 7  # default


@pytest.mark.unit
def test_get_forecast_custom_days(openmeteo_client):
    """Test getting forecast with custom number of days."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_FORECAST_DATA

        openmeteo_client.get_forecast(lat, lon, days=10)

        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_days"] == 10


@pytest.mark.unit
def test_get_forecast_max_days_limit(openmeteo_client):
    """Test that forecast days are limited to API maximum."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_FORECAST_DATA

        openmeteo_client.get_forecast(lat, lon, days=20)  # Over limit

        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_days"] == 16  # API max


@pytest.mark.unit
def test_get_hourly_forecast_success(openmeteo_client):
    """Test getting hourly forecast successfully."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_HOURLY_FORECAST_DATA

        result = openmeteo_client.get_hourly_forecast(lat, lon)

        assert result == SAMPLE_HOURLY_FORECAST_DATA
        call_args = mock_request.call_args[0][1]
        assert call_args["latitude"] == lat
        assert call_args["longitude"] == lon
        assert call_args["forecast_hours"] == 48  # default


@pytest.mark.unit
def test_get_hourly_forecast_custom_hours(openmeteo_client):
    """Test getting hourly forecast with custom hours."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_HOURLY_FORECAST_DATA

        openmeteo_client.get_hourly_forecast(lat, lon, hours=72)

        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_hours"] == 72


@pytest.mark.unit
def test_get_hourly_forecast_max_hours_limit(openmeteo_client):
    """Test that hourly forecast hours are limited to API maximum."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_HOURLY_FORECAST_DATA

        openmeteo_client.get_hourly_forecast(lat, lon, hours=500)  # Over limit

        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_hours"] == 384  # API max
