"""Tests for WeatherService initialization."""

from unittest.mock import MagicMock

import pytest

from accessiweather.services.weather_service import WeatherService


@pytest.mark.unit
def test_weather_service_initialization_with_config():
    """Test WeatherService initialization with different configurations."""
    config = {
        "settings": {"data_source": "nws"},
        "api_settings": {"api_contact": "test@example.com"},
    }

    mock_nws_client = MagicMock()
    service = WeatherService(nws_client=mock_nws_client, config=config)

    assert service.config == config
    assert service.nws_client == mock_nws_client
    assert service.openmeteo_client is not None


@pytest.mark.unit
def test_weather_service_initialization_with_clients():
    """Test WeatherService initialization with provided clients."""
    mock_nws_client = MagicMock()
    mock_openmeteo_client = MagicMock()

    service = WeatherService(nws_client=mock_nws_client, openmeteo_client=mock_openmeteo_client)

    assert service.nws_client == mock_nws_client
    assert service.openmeteo_client == mock_openmeteo_client
