"""Tests for WeatherService basic API methods."""

from unittest.mock import patch

import pytest

from accessiweather.api_client import ApiClientError
from tests.services.weather_service_test_utils import (
    SAMPLE_ALERTS_DATA,
    SAMPLE_DISCUSSION_TEXT,
    SAMPLE_FORECAST_DATA,
    mock_api_client,
    weather_service,
)


def test_get_forecast_success(weather_service, mock_api_client):
    """Test getting forecast data successfully."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_forecast(lat, lon)

    assert result == SAMPLE_FORECAST_DATA
    mock_api_client.get_forecast.assert_called_once_with(lat, lon, force_refresh=False)


def test_get_forecast_with_force_refresh(weather_service, mock_api_client):
    """Test getting forecast data with force_refresh=True."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_forecast(lat, lon, force_refresh=True)

    assert result == SAMPLE_FORECAST_DATA
    mock_api_client.get_forecast.assert_called_once_with(lat, lon, force_refresh=True)


def test_get_forecast_error(weather_service, mock_api_client):
    """Test getting forecast data when API client raises an error."""
    lat, lon = 40.0, -75.0
    mock_api_client.get_forecast.side_effect = Exception("API Error")

    # Also mock the OpenMeteo client to fail so fallback doesn't work
    with patch.object(weather_service.openmeteo_client, "get_forecast") as mock_openmeteo:
        mock_openmeteo.side_effect = Exception("OpenMeteo Error")

        with pytest.raises(ApiClientError) as exc_info:
            weather_service.get_forecast(lat, lon)

        assert "NWS failed and Open-Meteo fallback failed" in str(exc_info.value)
        mock_api_client.get_forecast.assert_called_once_with(lat, lon, force_refresh=False)


def test_get_alerts_success(weather_service, mock_api_client):
    """Test getting alerts data successfully."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_alerts(lat, lon)

    assert result == SAMPLE_ALERTS_DATA
    mock_api_client.get_alerts.assert_called_once_with(
        lat, lon, radius=50, precise_location=True, force_refresh=False
    )


def test_get_alerts_with_force_refresh(weather_service, mock_api_client):
    """Test getting alerts data with force_refresh=True."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_alerts(lat, lon, force_refresh=True)

    assert result == SAMPLE_ALERTS_DATA
    mock_api_client.get_alerts.assert_called_once_with(
        lat, lon, radius=50, precise_location=True, force_refresh=True
    )


def test_get_alerts_error(weather_service, mock_api_client):
    """Test getting alerts data when API client raises an error."""
    lat, lon = 40.0, -75.0
    mock_api_client.get_alerts.side_effect = Exception("API Error")

    with pytest.raises(ApiClientError) as exc_info:
        weather_service.get_alerts(lat, lon)

    assert "Unable to retrieve alerts data" in str(exc_info.value)
    mock_api_client.get_alerts.assert_called_once()


def test_get_discussion_success(weather_service, mock_api_client):
    """Test getting discussion data successfully."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_discussion(lat, lon)

    assert result == SAMPLE_DISCUSSION_TEXT
    mock_api_client.get_discussion.assert_called_once_with(lat, lon, force_refresh=False)


def test_get_discussion_with_force_refresh(weather_service, mock_api_client):
    """Test getting discussion data with force_refresh=True."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_discussion(lat, lon, force_refresh=True)

    assert result == SAMPLE_DISCUSSION_TEXT
    mock_api_client.get_discussion.assert_called_once_with(lat, lon, force_refresh=True)


def test_get_discussion_error(weather_service, mock_api_client):
    """Test getting discussion data when API client raises an error."""
    lat, lon = 40.0, -75.0
    mock_api_client.get_discussion.side_effect = Exception("API Error")

    with pytest.raises(ApiClientError) as exc_info:
        weather_service.get_discussion(lat, lon)

    assert "Unable to retrieve forecast discussion data" in str(exc_info.value)
    mock_api_client.get_discussion.assert_called_once()
