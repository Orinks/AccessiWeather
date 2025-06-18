"""Tests for WeatherService initialization and configuration."""

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


@pytest.mark.unit
def test_get_temperature_unit_preference_celsius(weather_service):
    """Test getting temperature unit preference for Celsius."""
    weather_service.config = {"settings": {"temperature_unit": "celsius"}}

    result = weather_service._get_temperature_unit_preference()
    assert result == "celsius"


@pytest.mark.unit
def test_get_temperature_unit_preference_fahrenheit(weather_service):
    """Test getting temperature unit preference for Fahrenheit."""
    weather_service.config = {"settings": {"temperature_unit": "fahrenheit"}}

    result = weather_service._get_temperature_unit_preference()
    assert result == "fahrenheit"


@pytest.mark.unit
def test_get_temperature_unit_preference_both(weather_service):
    """Test getting temperature unit preference for both (defaults to fahrenheit)."""
    weather_service.config = {"settings": {"temperature_unit": "both"}}

    result = weather_service._get_temperature_unit_preference()
    assert result == "fahrenheit"


@pytest.mark.unit
def test_get_data_source_nws(weather_service):
    """Test getting data source configuration for NWS."""
    weather_service.config = {"settings": {"data_source": "nws"}}

    result = weather_service._get_data_source()
    assert result == "nws"


@pytest.mark.unit
def test_get_data_source_auto(weather_service):
    """Test getting data source configuration for auto."""
    weather_service.config = {"settings": {"data_source": "auto"}}

    result = weather_service._get_data_source()
    assert result == "auto"


@pytest.mark.unit
def test_get_data_source_default(weather_service):
    """Test getting data source configuration with default."""
    weather_service.config = {"settings": {}}

    result = weather_service._get_data_source()
    assert result == "auto"
