"""Tests for WeatherService data source routing functionality."""

from unittest.mock import patch

import pytest

from tests.services.weather_service_test_utils import SAMPLE_FORECAST_DATA, weather_service


@pytest.mark.unit
def test_get_forecast_nws_success(weather_service):
    """Test successful forecast retrieval using NWS."""
    lat, lon = 40.0, -75.0

    with patch.object(weather_service, "_should_use_openmeteo", return_value=False):
        with patch.object(
            weather_service.nws_client, "get_forecast", return_value=SAMPLE_FORECAST_DATA
        ):
            result = weather_service.get_forecast(lat, lon)

            assert result == SAMPLE_FORECAST_DATA
            weather_service.nws_client.get_forecast.assert_called_once_with(
                lat, lon, force_refresh=False
            )


@pytest.mark.unit
def test_get_forecast_openmeteo_success(weather_service):
    """Test successful forecast retrieval using Open-Meteo."""
    lat, lon = 51.5074, -0.1278  # London

    with patch.object(weather_service, "_should_use_openmeteo", return_value=True):
        with patch.object(
            weather_service.openmeteo_client, "get_forecast", return_value={"test": "data"}
        ):
            with patch.object(
                weather_service.openmeteo_mapper, "map_forecast", return_value=SAMPLE_FORECAST_DATA
            ):
                result = weather_service.get_forecast(lat, lon)

                assert result == SAMPLE_FORECAST_DATA
                weather_service.openmeteo_client.get_forecast.assert_called_once()
                weather_service.openmeteo_mapper.map_forecast.assert_called_once()


@pytest.mark.unit
def test_get_hourly_forecast_nws_success(weather_service):
    """Test successful hourly forecast retrieval using NWS."""
    lat, lon = 40.0, -75.0

    with patch.object(weather_service, "_should_use_openmeteo", return_value=False):
        with patch.object(
            weather_service.nws_client, "get_hourly_forecast", return_value=SAMPLE_FORECAST_DATA
        ):
            result = weather_service.get_hourly_forecast(lat, lon)

            assert result == SAMPLE_FORECAST_DATA
            weather_service.nws_client.get_hourly_forecast.assert_called_once_with(
                lat, lon, force_refresh=False
            )


@pytest.mark.unit
def test_get_hourly_forecast_openmeteo_success(weather_service):
    """Test successful hourly forecast retrieval using Open-Meteo."""
    lat, lon = 51.5074, -0.1278  # London

    with patch.object(weather_service, "_should_use_openmeteo", return_value=True):
        with patch.object(
            weather_service.openmeteo_client, "get_hourly_forecast", return_value={"test": "data"}
        ):
            with patch.object(
                weather_service.openmeteo_mapper,
                "map_hourly_forecast",
                return_value=SAMPLE_FORECAST_DATA,
            ):
                result = weather_service.get_hourly_forecast(lat, lon)

                assert result == SAMPLE_FORECAST_DATA
                weather_service.openmeteo_client.get_hourly_forecast.assert_called_once()
                weather_service.openmeteo_mapper.map_hourly_forecast.assert_called_once()


@pytest.mark.unit
def test_get_current_conditions_nws_success(weather_service):
    """Test successful current conditions retrieval using NWS."""
    lat, lon = 40.0, -75.0

    with patch.object(weather_service, "_should_use_openmeteo", return_value=False):
        with patch.object(
            weather_service.nws_client, "get_current_conditions", return_value=SAMPLE_FORECAST_DATA
        ):
            result = weather_service.get_current_conditions(lat, lon)

            assert result == SAMPLE_FORECAST_DATA
            weather_service.nws_client.get_current_conditions.assert_called_once_with(
                lat, lon, force_refresh=False
            )


@pytest.mark.unit
def test_get_current_conditions_openmeteo_success(weather_service):
    """Test successful current conditions retrieval using Open-Meteo."""
    lat, lon = 51.5074, -0.1278  # London

    with patch.object(weather_service, "_should_use_openmeteo", return_value=True):
        with patch.object(
            weather_service.openmeteo_client, "get_current_weather", return_value={"test": "data"}
        ):
            with patch.object(
                weather_service.openmeteo_mapper,
                "map_current_conditions",
                return_value=SAMPLE_FORECAST_DATA,
            ):
                result = weather_service.get_current_conditions(lat, lon)

                assert result == SAMPLE_FORECAST_DATA
                weather_service.openmeteo_client.get_current_weather.assert_called_once()
                weather_service.openmeteo_mapper.map_current_conditions.assert_called_once()
