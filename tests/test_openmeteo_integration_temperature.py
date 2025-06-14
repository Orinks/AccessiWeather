"""Temperature unit and configuration integration tests for Open-Meteo with WeatherService."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.openmeteo_mapper import OpenMeteoMapper
from accessiweather.services.weather_service import WeatherService
from accessiweather.utils.temperature_utils import TemperatureUnit


@pytest.mark.integration
def test_temperature_unit_preference_fahrenheit():
    """Test that Fahrenheit preference is correctly detected and passed to API."""
    config = {
        "settings": {
            "data_source": "openmeteo",
            "temperature_unit": TemperatureUnit.FAHRENHEIT.value,
        }
    }
    service = WeatherService(nws_client=MagicMock(), openmeteo_client=MagicMock(), config=config)
    temp_unit = service._get_temperature_unit_preference()
    assert temp_unit == "fahrenheit"


@pytest.mark.integration
def test_temperature_unit_preference_celsius():
    """Test that Celsius preference is correctly detected and passed to API."""
    config = {
        "settings": {
            "data_source": "openmeteo",
            "temperature_unit": TemperatureUnit.CELSIUS.value,
        }
    }
    service = WeatherService(nws_client=MagicMock(), openmeteo_client=MagicMock(), config=config)
    temp_unit = service._get_temperature_unit_preference()
    assert temp_unit == "celsius"


@pytest.mark.integration
def test_temperature_values_are_reasonable():
    """Test that temperature values are reasonable for real-world locations (Manchester, UK)."""
    # Sample responses with reasonable temperatures
    fahrenheit_response = {
        "latitude": 53.4808,
        "longitude": -2.2426,
        "current": {
            "time": "2024-01-01T12:00",
            "temperature_2m": 56.0,  # Should be 56°F for Manchester
            "relative_humidity_2m": 70,
            "weather_code": 2,
        },
        "current_units": {"temperature_2m": "°F"},
    }

    celsius_response = {
        "latitude": 53.4808,
        "longitude": -2.2426,
        "current": {
            "time": "2024-01-01T12:00",
            "temperature_2m": 13.3,  # Should be 13.3°C for Manchester (equivalent to 56°F)
            "relative_humidity_2m": 70,
            "weather_code": 2,
        },
        "current_units": {"temperature_2m": "°C"},
    }

    mapper = OpenMeteoMapper()

    # Test with Fahrenheit response (should be around 50-70°F for Manchester)
    result_f = mapper.map_current_conditions(fahrenheit_response)
    temp_value_f = result_f["properties"]["temperature"]["value"]
    unit_code_f = result_f["properties"]["temperature"]["unitCode"]

    # Manchester temperatures should be reasonable (not 130-160°F!)
    assert 30 <= temp_value_f <= 80, f"Temperature {temp_value_f}°F is unreasonable for Manchester"
    assert unit_code_f == "wmoUnit:degF"

    # Test with Celsius response (should be around 10-20°C for Manchester)
    result_c = mapper.map_current_conditions(celsius_response)
    temp_value_c = result_c["properties"]["temperature"]["value"]
    unit_code_c = result_c["properties"]["temperature"]["unitCode"]

    # Should be reasonable Celsius temperature
    assert 0 <= temp_value_c <= 30, f"Temperature {temp_value_c}°C is unreasonable for Manchester"
    assert unit_code_c == "wmoUnit:degC"


@pytest.mark.integration
def test_temperature_unit_passed_to_all_api_calls(mock_nws_client, mock_openmeteo_client):
    """Test that temperature unit preference is passed to all OpenMeteo API calls."""
    config = {
        "settings": {
            "data_source": "openmeteo",
            "temperature_unit": TemperatureUnit.CELSIUS.value,
        }
    }
    service = WeatherService(
        nws_client=mock_nws_client, openmeteo_client=mock_openmeteo_client, config=config
    )

    # Mock mappers to avoid complex mapping logic
    with (
        patch.object(service.openmeteo_mapper, "map_current_conditions") as mock_current,
        patch.object(service.openmeteo_mapper, "map_forecast") as mock_forecast,
        patch.object(service.openmeteo_mapper, "map_hourly_forecast") as mock_hourly,
    ):

        mock_current.return_value = {"properties": {"temperature": {"value": 13.3}}}
        mock_forecast.return_value = {"properties": {"periods": []}}
        mock_hourly.return_value = {"properties": {"periods": []}}

        # Test coordinates (non-US to ensure OpenMeteo is used)
        lat, lon = 53.4808, -2.2426

        # Test current conditions
        service.get_current_conditions(lat, lon)
        mock_openmeteo_client.get_current_weather.assert_called_with(
            lat, lon, temperature_unit="celsius"
        )

        # Test forecast
        service.get_forecast(lat, lon)
        mock_openmeteo_client.get_forecast.assert_called_with(lat, lon, temperature_unit="celsius")

        # Test hourly forecast
        service.get_hourly_forecast(lat, lon)
        mock_openmeteo_client.get_hourly_forecast.assert_called_with(
            lat, lon, temperature_unit="celsius"
        )


@pytest.mark.integration
def test_ui_temperature_unit_code_handling():
    """Test that UI correctly handles temperature unit codes to avoid double conversion."""
    from unittest.mock import MagicMock

    from accessiweather.gui.ui_manager import UIManager

    # Mock frame and config
    mock_frame = MagicMock()
    mock_frame.current_conditions_text = MagicMock()
    mock_frame.taskbar_icon = None

    config = {
        "settings": {
            "temperature_unit": TemperatureUnit.BOTH.value,
        }
    }

    # Create UI manager with mocked frame
    ui_manager = UIManager(mock_frame, config)

    # Test data with proper unit codes
    weather_data = {
        "properties": {
            "temperature": {
                "value": 20.0,
                "unitCode": "wmoUnit:degC",  # Celsius from Open-Meteo
            },
            "textDescription": "Partly cloudy",
        }
    }

    # Should handle the unit code correctly without double conversion
    ui_manager.update_current_conditions(weather_data)

    # Verify the UI was updated (basic check)
    mock_frame.current_conditions_text.SetValue.assert_called()


# Fixtures for the temperature tests
@pytest.fixture
def mock_nws_client():
    """Create a mock NWS client."""
    from accessiweather.api_client import NoaaApiClient

    return MagicMock(spec=NoaaApiClient)


@pytest.fixture
def mock_openmeteo_client():
    """Create a mock Open-Meteo client."""
    from accessiweather.openmeteo_client import OpenMeteoApiClient

    return MagicMock(spec=OpenMeteoApiClient)
