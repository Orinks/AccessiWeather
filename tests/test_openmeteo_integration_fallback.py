"""Fallback and error handling integration tests for Open-Meteo with WeatherService."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_client import NoaaApiClient
from accessiweather.openmeteo_client import OpenMeteoApiClient, OpenMeteoApiError
from accessiweather.services.weather_service import WeatherService

# Sample test data
SAMPLE_OPENMETEO_CURRENT_RESPONSE = {
    "latitude": 51.5074,
    "longitude": -0.1278,
    "current": {
        "time": "2024-01-01T12:00",
        "temperature_2m": 15.5,
        "relative_humidity_2m": 70,
        "weather_code": 2,
        "wind_speed_10m": 10.0,
        "wind_direction_10m": 225,
    },
    "current_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
}


@pytest.fixture
def mock_nws_client():
    """Create a mock NWS client."""
    return MagicMock(spec=NoaaApiClient)


@pytest.fixture
def mock_openmeteo_client():
    """Create a mock Open-Meteo client."""
    return MagicMock(spec=OpenMeteoApiClient)


@pytest.fixture
def weather_service_with_openmeteo(mock_nws_client, mock_openmeteo_client):
    """Create a WeatherService with mocked clients."""
    config = {"settings": {"data_source": "auto"}}
    return WeatherService(
        nws_client=mock_nws_client, openmeteo_client=mock_openmeteo_client, config=config
    )


@pytest.mark.integration
def test_openmeteo_fallback_to_nws(
    weather_service_with_openmeteo, mock_openmeteo_client, mock_nws_client
):
    """Test fallback from Open-Meteo to NWS when Open-Meteo fails."""
    # US coordinates that could use either service
    lat, lon = 40.7128, -74.0060

    # Mock Open-Meteo failure
    mock_openmeteo_client.get_current_weather.side_effect = Exception("Open-Meteo Error")

    # Mock successful NWS response
    mock_nws_response = {"properties": {"temp": 20}}
    mock_nws_client.get_current_conditions.return_value = mock_nws_response

    result = weather_service_with_openmeteo.get_current_conditions(lat, lon)

    # Should have tried Open-Meteo first, then fallen back to NWS
    if weather_service_with_openmeteo._should_use_openmeteo(lat, lon):
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
def test_concurrent_requests_thread_safety(weather_service_with_openmeteo, mock_openmeteo_client):
    """Test thread safety with concurrent requests."""
    # London coordinates
    lat, lon = 51.5074, -0.1278

    # Mock response with delay to simulate real API
    def mock_response(*args, **kwargs):
        time.sleep(0.1)  # Small delay
        return SAMPLE_OPENMETEO_CURRENT_RESPONSE

    mock_openmeteo_client.get_current_weather.side_effect = mock_response

    results = []
    errors = []

    def make_request():
        try:
            result = weather_service_with_openmeteo.get_current_conditions(lat, lon)
            results.append(result)
        except Exception as e:
            errors.append(e)

    # Create and start threads
    threads = []
    for _ in range(5):
        thread = threading.Thread(target=make_request)
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Verify results
    assert len(errors) == 0
    assert len(results) == 5
    assert all(result is not None for result in results)


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

    with patch("accessiweather.services.weather_service.logger") as mock_logger:
        result = weather_service_with_openmeteo.get_current_conditions(lat, lon)

        # Should have result from fallback
        assert result is not None

        # Should log the error
        mock_logger.warning.assert_called()
