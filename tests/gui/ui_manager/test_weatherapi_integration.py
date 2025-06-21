"""Tests for UI Manager WeatherAPI.com integration."""

import pytest

from .test_data import (
    SAMPLE_FORECAST_DATA,
    SAMPLE_WEATHERAPI_ALERTS_DATA,
    SAMPLE_WEATHERAPI_CURRENT_DATA,
    SAMPLE_WEATHERAPI_FORECAST_DATA,
)


def test_is_weatherapi_data(mock_ui_manager):
    """Test WeatherAPI.com data detection."""
    # Test with WeatherAPI forecast data
    assert mock_ui_manager._is_weatherapi_data(SAMPLE_WEATHERAPI_FORECAST_DATA) is True

    # Test with WeatherAPI current conditions data
    assert mock_ui_manager._is_weatherapi_data(SAMPLE_WEATHERAPI_CURRENT_DATA) is True

    # Test with WeatherAPI alerts data
    assert mock_ui_manager._is_weatherapi_data(SAMPLE_WEATHERAPI_ALERTS_DATA) is True

    # Test with NWS API data
    assert mock_ui_manager._is_weatherapi_data(SAMPLE_FORECAST_DATA) is False

    # Test with empty data
    assert mock_ui_manager._is_weatherapi_data({}) is False
    assert mock_ui_manager._is_weatherapi_data(None) is False


def test_display_weatherapi_forecast(mock_ui_manager):
    """Test WeatherAPI.com forecast display."""
    # Test with WeatherAPI.com forecast data
    mock_ui_manager.display_forecast(SAMPLE_WEATHERAPI_FORECAST_DATA)
    forecast_text = mock_ui_manager.mock_frame.forecast_text.SetValue.call_args[0][0]

    # Check for location info
    assert "Forecast for London, City of London, United Kingdom" in forecast_text

    # Check for hourly data
    assert "Next 6 Hours:" in forecast_text
    # Sample data uses integer temperature (72), smart precision removes decimals for whole numbers
    assert "12:00 PM: 72°F, Sunny" in forecast_text

    # Check for daily forecast
    assert "Extended Forecast:" in forecast_text
    # Sample data uses integer temperatures (75, 60), smart precision removes decimals for whole numbers
    assert "High 75°F, Low 60°F" in forecast_text
    assert "Sunny" in forecast_text
    assert "Chance of precipitation: 10%" in forecast_text
    assert "Wind: 15 mph" in forecast_text


def test_display_weatherapi_current_conditions(mock_ui_manager):
    """Test WeatherAPI.com current conditions display."""
    # Test with WeatherAPI.com current conditions data
    mock_ui_manager.display_current_conditions(SAMPLE_WEATHERAPI_CURRENT_DATA)
    conditions_text = mock_ui_manager.mock_frame.current_conditions_text.SetValue.call_args[0][0]

    # Check for key elements
    assert "Current Conditions: Sunny" in conditions_text
    # Sample data uses integer temperatures (72, 70), smart precision removes decimals for whole numbers
    assert "Temperature: 72°F" in conditions_text
    assert "Feels Like: 70°F" in conditions_text
    assert "Humidity: 45%" in conditions_text
    assert "Wind: NW at 10.0 mph" in conditions_text
    assert "Pressure: 30 inHg" in conditions_text


def test_display_weatherapi_alerts(mock_ui_manager):
    """Test WeatherAPI.com alerts display."""
    # Test with WeatherAPI.com alerts data
    processed_alerts = mock_ui_manager.display_alerts(SAMPLE_WEATHERAPI_ALERTS_DATA)

    # Check that alerts were processed correctly
    assert len(processed_alerts) == 2
    assert mock_ui_manager.mock_frame.alerts_list.InsertItem.call_count == 2

    # Check that the alert button was enabled
    mock_ui_manager.mock_frame.alert_btn.Enable.assert_called_once()

    # Test with empty alerts
    mock_ui_manager.mock_frame.reset_mock()
    mock_ui_manager.mock_frame.alerts_list.reset_mock()
    mock_ui_manager.mock_frame.alerts_list.InsertItem.return_value = 0

    empty_alerts: dict = {"alerts": []}
    processed_alerts = mock_ui_manager.display_alerts(empty_alerts)
    assert len(processed_alerts) == 0
    mock_ui_manager.mock_frame.alert_btn.Disable.assert_called_once()


@pytest.mark.unit
def test_format_weatherapi_forecast_basic(mock_ui_manager):
    """Test basic WeatherAPI forecast formatting."""
    forecast_data = {
        "location": {"name": "Test City", "region": "Test Region", "country": "Test Country"},
        "forecast": [
            {
                "date": "2024-01-15",
                "maxtemp_f": 75.0,
                "maxtemp_c": 23.9,
                "mintemp_f": 60.0,
                "mintemp_c": 15.6,
                "condition": {"text": "Sunny"},
                "daily_chance_of_rain": 10,
                "maxwind_mph": 15.0,
            }
        ],
    }

    result = mock_ui_manager._format_weatherapi_forecast(forecast_data, None)

    assert "Test City, Test Region, Test Country" in result
    assert "High" in result and "Low" in result
    assert "Sunny" in result


@pytest.mark.unit
def test_format_weatherapi_current_conditions_basic(mock_ui_manager):
    """Test basic WeatherAPI current conditions formatting."""
    conditions_data = {
        "temperature": 72.0,
        "temperature_c": 22.2,
        "condition": "Sunny",
        "humidity": 45,
        "wind_direction": "NW",
        "wind_speed": 10.0,
        "wind_speed_kph": 16.1,
        "pressure": 30.10,
        "pressure_mb": 1019.0,
        "feelslike": 70.0,
        "feelslike_c": 21.1,
    }

    result = mock_ui_manager._format_weatherapi_current_conditions(conditions_data)

    assert "Current Conditions: Sunny" in result
    assert "Temperature:" in result
    assert "Humidity: 45%" in result
    assert "Wind: NW at" in result
    assert "Pressure:" in result


@pytest.mark.unit
def test_extract_weatherapi_data_for_taskbar(mock_ui_manager):
    """Test extracting WeatherAPI data for taskbar."""
    conditions_data = {
        "current": {
            "temp_f": 72.0,
            "temp_c": 22.2,
            "condition": {"text": "Sunny"},
            "humidity": 45,
            "wind_mph": 10.0,
        },
        "location": {"name": "Test City"},
    }

    result = mock_ui_manager._extract_weatherapi_data_for_taskbar(conditions_data)

    assert result["temp"] == 72.0
    assert result["temp_f"] == 72.0
    assert result["temp_c"] == 22.2
    assert result["condition"] == "Sunny"
    assert result["humidity"] == 45
    assert result["wind_speed"] == 10.0
