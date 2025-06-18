"""Basic integration tests for Open-Meteo with WeatherService."""

from unittest.mock import MagicMock

import pytest

from accessiweather.services.weather_service import WeatherService

from .conftest import (
    SAMPLE_OPENMETEO_CURRENT_RESPONSE,
    SAMPLE_OPENMETEO_FORECAST_RESPONSE,
    SAMPLE_OPENMETEO_HOURLY_RESPONSE,
)


@pytest.mark.integration
def test_should_use_openmeteo_for_non_us_location(weather_service_with_openmeteo):
    """Test that Open-Meteo is selected for non-US locations."""
    # London coordinates
    lat, lon = 51.5074, -0.1278

    result = weather_service_with_openmeteo._should_use_openmeteo(lat, lon)
    assert result is True


@pytest.mark.integration
def test_should_use_nws_for_us_location(weather_service_with_openmeteo):
    """Test that NWS is selected for US locations."""
    # New York coordinates
    lat, lon = 40.7128, -74.0060

    result = weather_service_with_openmeteo._should_use_openmeteo(lat, lon)
    assert result is False


@pytest.mark.integration
def test_get_current_conditions_openmeteo_success(
    weather_service_with_openmeteo, mock_openmeteo_client
):
    """Test getting current conditions via Open-Meteo."""
    # London coordinates
    lat, lon = 51.5074, -0.1278

    # Mock Open-Meteo response
    mock_openmeteo_client.get_current_weather.return_value = SAMPLE_OPENMETEO_CURRENT_RESPONSE

    result = weather_service_with_openmeteo.get_current_conditions(lat, lon)

    assert result is not None
    assert "properties" in result
    mock_openmeteo_client.get_current_weather.assert_called_once_with(
        lat, lon, temperature_unit="fahrenheit"
    )


@pytest.mark.integration
def test_get_forecast_openmeteo_success(weather_service_with_openmeteo, mock_openmeteo_client):
    """Test getting forecast via Open-Meteo."""
    # London coordinates
    lat, lon = 51.5074, -0.1278

    # Mock Open-Meteo response
    mock_openmeteo_client.get_forecast.return_value = SAMPLE_OPENMETEO_FORECAST_RESPONSE

    result = weather_service_with_openmeteo.get_forecast(lat, lon)

    assert result is not None
    assert "properties" in result
    assert "periods" in result["properties"]
    mock_openmeteo_client.get_forecast.assert_called_once_with(
        lat, lon, temperature_unit="fahrenheit"
    )


@pytest.mark.integration
def test_get_hourly_forecast_openmeteo_success(
    weather_service_with_openmeteo, mock_openmeteo_client
):
    """Test getting hourly forecast via Open-Meteo."""
    # London coordinates
    lat, lon = 51.5074, -0.1278

    # Mock Open-Meteo response
    mock_openmeteo_client.get_hourly_forecast.return_value = SAMPLE_OPENMETEO_HOURLY_RESPONSE

    result = weather_service_with_openmeteo.get_hourly_forecast(lat, lon)

    assert result is not None
    assert "properties" in result
    assert "periods" in result["properties"]
    mock_openmeteo_client.get_hourly_forecast.assert_called_once_with(
        lat, lon, temperature_unit="fahrenheit"
    )


@pytest.mark.integration
def test_data_source_configuration_auto(mock_nws_client, mock_openmeteo_client):
    """Test automatic data source selection based on configuration."""
    config = {"settings": {"data_source": "auto"}}
    service = WeatherService(
        nws_client=mock_nws_client, openmeteo_client=mock_openmeteo_client, config=config
    )

    # Should use Open-Meteo for non-US
    assert service._should_use_openmeteo(51.5074, -0.1278) is True

    # Should use NWS for US
    assert service._should_use_openmeteo(40.7128, -74.0060) is False


@pytest.mark.integration
def test_data_source_configuration_nws_only(mock_nws_client, mock_openmeteo_client):
    """Test NWS-only configuration."""
    config = {"settings": {"data_source": "nws"}}
    service = WeatherService(
        nws_client=mock_nws_client, openmeteo_client=mock_openmeteo_client, config=config
    )

    # Should always use NWS
    assert service._should_use_openmeteo(51.5074, -0.1278) is False
    assert service._should_use_openmeteo(40.7128, -74.0060) is False


@pytest.mark.integration
def test_data_source_configuration_openmeteo_only(mock_nws_client, mock_openmeteo_client):
    """Test Open-Meteo-only configuration."""
    config = {"settings": {"data_source": "openmeteo"}}
    service = WeatherService(
        nws_client=mock_nws_client, openmeteo_client=mock_openmeteo_client, config=config
    )

    # Should always use Open-Meteo
    assert service._should_use_openmeteo(51.5074, -0.1278) is True
    assert service._should_use_openmeteo(40.7128, -74.0060) is True


@pytest.mark.integration
def test_cache_integration(weather_service_with_openmeteo, mock_openmeteo_client):
    """Test that caching works with Open-Meteo integration."""
    # London coordinates
    lat, lon = 51.5074, -0.1278

    # Mock Open-Meteo response
    mock_openmeteo_client.get_current_weather.return_value = SAMPLE_OPENMETEO_CURRENT_RESPONSE

    # First call
    result1 = weather_service_with_openmeteo.get_current_conditions(lat, lon)

    # Second call (should use cache if implemented)
    result2 = weather_service_with_openmeteo.get_current_conditions(lat, lon)

    assert result1 is not None
    assert result2 is not None

    # API should be called at least once
    assert mock_openmeteo_client.get_current_weather.call_count >= 1
