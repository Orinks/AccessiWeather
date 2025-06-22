"""Fallback mechanism tests for Open-Meteo integration."""

from unittest.mock import patch

import pytest

from accessiweather.openmeteo_client import OpenMeteoApiError

from .conftest import SAMPLE_OPENMETEO_CURRENT_RESPONSE


@pytest.mark.integration
def test_openmeteo_fallback_to_nws(
    weather_service_with_openmeteo, mock_openmeteo_client, mock_nws_client
):
    """Test fallback from Open-Meteo to NWS when Open-Meteo fails."""
    # US coordinates that could use either service
    lat, lon = 40.7128, -74.0060

    # Configure to use Open-Meteo first by patching the api_client_manager method
    with patch.object(
        weather_service_with_openmeteo.api_client_manager,
        "_should_use_openmeteo",
        return_value=True,
    ):
        # Mock Open-Meteo failure
        mock_openmeteo_client.get_current_weather.side_effect = OpenMeteoApiError("API Error")

        # Mock successful NWS response
        mock_nws_response = {"properties": {"temperature": {"value": 20}}}
        mock_nws_client.get_current_conditions.return_value = mock_nws_response

        result = weather_service_with_openmeteo.get_current_conditions(lat, lon)

        # Should have tried Open-Meteo first, then fallen back to NWS
        mock_openmeteo_client.get_current_weather.assert_called_once()
        mock_nws_client.get_current_conditions.assert_called_once()
        assert result == mock_nws_response


@pytest.mark.integration
def test_nws_fallback_to_openmeteo(
    weather_service_with_openmeteo, mock_openmeteo_client, mock_nws_client
):
    """Test fallback from NWS to Open-Meteo when NWS fails."""
    # US coordinates
    lat, lon = 40.7128, -74.0060

    # Mock NWS failure
    mock_nws_client.get_current_conditions.side_effect = Exception("NWS Error")

    # Mock successful Open-Meteo response
    mock_openmeteo_client.get_current_weather.return_value = SAMPLE_OPENMETEO_CURRENT_RESPONSE

    result = weather_service_with_openmeteo.get_current_conditions(lat, lon)

    # Should have tried NWS first, then fallen back to Open-Meteo
    mock_nws_client.get_current_conditions.assert_called_once()
    mock_openmeteo_client.get_current_weather.assert_called_once()
    assert result is not None


@pytest.mark.integration
def test_error_propagation_and_logging(weather_service_with_openmeteo, mock_openmeteo_client):
    """Test that errors are properly propagated and logged."""
    # New York coordinates (US location for fallback)
    lat, lon = 40.7128, -74.0060

    # Mock Open-Meteo error
    mock_openmeteo_client.get_current_weather.side_effect = OpenMeteoApiError("API quota exceeded")

    # Mock NWS success for fallback
    weather_service_with_openmeteo.nws_client.get_current_conditions.return_value = {
        "properties": {"temp": 20}
    }

    with patch.object(
        weather_service_with_openmeteo.api_client_manager,
        "_should_use_openmeteo",
        return_value=True,
    ):
        with patch(
            "accessiweather.services.weather_service.weather_data_retrieval.logger"
        ) as mock_logger:
            result = weather_service_with_openmeteo.get_current_conditions(lat, lon)

            # Should succeed with fallback
            assert result is not None

            # Should log the error
            mock_logger.warning.assert_called()
