"""Tests for WeatherService configuration utilities."""

import pytest

from tests.services.weather_service_test_utils import weather_service


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
