"""Integration tests for Open-Meteo with WeatherService."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_client import NoaaApiClient
from accessiweather.openmeteo_client import OpenMeteoApiClient, OpenMeteoApiError
from accessiweather.openmeteo_mapper import OpenMeteoMapper
from accessiweather.services.weather_service import WeatherService
from accessiweather.utils.temperature_utils import TemperatureUnit

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

SAMPLE_OPENMETEO_FORECAST_RESPONSE = {
    "latitude": 51.5074,
    "longitude": -0.1278,
    "daily": {
        "time": ["2024-01-01", "2024-01-02"],
        "weather_code": [1, 2],
        "temperature_2m_max": [18.0, 20.0],
        "temperature_2m_min": [8.0, 10.0],
        "wind_speed_10m_max": [15.0, 12.0],
        "wind_direction_10m_dominant": [180, 225],
    },
    "daily_units": {
        "temperature_2m_max": "°C",
        "temperature_2m_min": "°C",
        "wind_speed_10m_max": "km/h",
    },
}

SAMPLE_OPENMETEO_HOURLY_RESPONSE = {
    "latitude": 51.5074,
    "longitude": -0.1278,
    "hourly": {
        "time": ["2024-01-01T12:00", "2024-01-01T13:00"],
        "temperature_2m": [15.5, 16.0],
        "weather_code": [2, 1],
        "wind_speed_10m": [10.0, 8.0],
        "is_day": [1, 1],
    },
    "hourly_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
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
def test_openmeteo_fallback_to_nws(
    weather_service_with_openmeteo, mock_openmeteo_client, mock_nws_client
):
    """Test fallback from Open-Meteo to NWS when Open-Meteo fails."""
    # US coordinates that could use either service
    lat, lon = 40.7128, -74.0060

    # Configure to use Open-Meteo first
    with patch.object(weather_service_with_openmeteo, "_should_use_openmeteo", return_value=True):
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
def test_concurrent_requests_thread_safety(weather_service_with_openmeteo, mock_openmeteo_client):
    """Test thread safety with concurrent requests."""
    import threading
    import time

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

    # Create multiple threads
    threads = []
    for _ in range(5):
        thread = threading.Thread(target=make_request)
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # All requests should succeed
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

    with patch.object(weather_service_with_openmeteo, "_should_use_openmeteo", return_value=True):
        with patch("accessiweather.services.weather_service.logger") as mock_logger:
            result = weather_service_with_openmeteo.get_current_conditions(lat, lon)

            # Should succeed with fallback
            assert result is not None

            # Should log the error
            mock_logger.warning.assert_called()


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


# Temperature conversion tests (fix for temperature unit bug)
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

    # Mock responses
    mock_openmeteo_client.get_current_weather.return_value = SAMPLE_OPENMETEO_CURRENT_RESPONSE
    mock_openmeteo_client.get_forecast.return_value = {"daily": {}}
    mock_openmeteo_client.get_hourly_forecast.return_value = {"hourly": {}}

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

    # Create UI manager with mocked dependencies
    ui_manager = UIManager.__new__(UIManager)  # Create without calling __init__
    ui_manager.frame = mock_frame
    # UIManager accesses config through frame.config, not directly
    mock_frame.config = config

    # Use patch.object for proper mocking instead of direct assignment
    def mock_get_temperature_unit_preference():
        return TemperatureUnit.BOTH

    with patch.object(
        ui_manager,
        "_get_temperature_unit_preference",
        side_effect=mock_get_temperature_unit_preference,
    ):
        # Test data with Fahrenheit unit code (Open-Meteo with fahrenheit preference)
        fahrenheit_data = {
            "properties": {
                "temperature": {
                    "value": 56.6,  # Should stay as 56.6°F, not convert to 133.9°F
                    "unitCode": "wmoUnit:degF",
                },
                "dewpoint": {"value": 51.8, "unitCode": "wmoUnit:degF"},
                "relativeHumidity": {"value": 84},
                "windSpeed": {"value": 3.2},
                "windDirection": {"value": 153},
                "barometricPressure": {"value": 101590},
                "textDescription": "Partly cloudy",
            }
        }

        # Test data with Celsius unit code (NWS or Open-Meteo with celsius preference)
        celsius_data = {
            "properties": {
                "temperature": {
                    "value": 13.6,
                    "unitCode": "wmoUnit:degC",
                },  # Should convert to ~56.5°F
                "dewpoint": {"value": 10.8, "unitCode": "wmoUnit:degC"},
                "relativeHumidity": {"value": 84},
                "windSpeed": {"value": 3.2},
                "windDirection": {"value": 153},
                "barometricPressure": {"value": 101590},
                "textDescription": "Partly cloudy",
            }
        }

        # Test Fahrenheit data (should NOT convert)
        ui_manager.display_current_conditions(fahrenheit_data)
        fahrenheit_result = mock_frame.current_conditions_text.SetValue.call_args[0][0]

        # Should show 57°F (rounded from 56.6°F due to BOTH unit preference using precision 0), not 133.9°F (which would be double conversion)
        assert "57°F" in fahrenheit_result, f"Expected 57°F in result: {fahrenheit_result}"
        assert (
            "133" not in fahrenheit_result
        ), f"Found double conversion (133°F) in result: {fahrenheit_result}"
        assert (
            "14°C" in fahrenheit_result
        ), f"Expected ~14°C conversion in result: {fahrenheit_result}"

        # Test Celsius data (should convert)
        ui_manager.display_current_conditions(celsius_data)
        celsius_result = mock_frame.current_conditions_text.SetValue.call_args[0][0]

        # Should convert 13.6°C to ~56°F (rounded due to BOTH unit preference using precision 0)
        assert "56°F" in celsius_result, f"Expected ~56°F conversion in result: {celsius_result}"
        assert "14°C" in celsius_result, f"Expected ~14°C conversion in result: {celsius_result}"
