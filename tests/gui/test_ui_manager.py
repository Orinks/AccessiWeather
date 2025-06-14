"""Tests for UI Manager."""

# This file contains tests for the UIManager class using a patched approach
# that avoids the need to create actual wxPython UI components.

from unittest.mock import MagicMock, call, patch

import pytest
import wx

from accessiweather.gui.ui_manager import UIManager
from accessiweather.utils.temperature_utils import TemperatureUnit

# --- Test Data ---

SAMPLE_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "name": "Today",
                "temperature": 75,
                "temperatureUnit": "F",
                "detailedForecast": "Sunny with a high near 75.",
            },
            {
                "name": "Tonight",
                "temperature": 60,
                "temperatureUnit": "F",
                "detailedForecast": "Clear with a low around 60.",
            },
        ]
    }
}

SAMPLE_NATIONAL_FORECAST_DATA = {
    "national_discussion_summaries": {
        "wpc": {
            "short_range_summary": "Rain in the Northeast, sunny in the West.",
            "short_range_full": "Detailed WPC discussion...",
        },
        "spc": {
            "day1_summary": "Severe storms possible in the Plains.",
            "day1_full": "Detailed SPC discussion...",
        },
        "attribution": "National Weather Service",
    }
}

SAMPLE_ALERTS_DATA = {
    "features": [
        {
            "properties": {
                "event": "Severe Thunderstorm Warning",
                "severity": "Severe",
                "headline": "Severe thunderstorm warning until 5 PM",
            }
        },
        {
            "properties": {
                "event": "Flash Flood Watch",
                "severity": "Moderate",
                "headline": "Flash flood watch in effect",
            }
        },
    ]
}

# Sample WeatherAPI.com data
SAMPLE_WEATHERAPI_FORECAST_DATA = {
    "forecast": [
        {
            "date": "2023-06-01",
            "high": 75,
            "low": 60,
            "condition": "Sunny",
            "precipitation_probability": 10,
            "max_wind_speed": 15,
        },
        {
            "date": "2023-06-02",
            "high": 80,
            "low": 65,
            "condition": "Partly cloudy",
            "precipitation_probability": 20,
            "max_wind_speed": 12,
        },
    ],
    "location": {"name": "London", "region": "City of London", "country": "United Kingdom"},
    "hourly": [
        {"time": "2023-06-01 12:00", "temperature": 72, "condition": "Sunny"},
        {"time": "2023-06-01 13:00", "temperature": 74, "condition": "Sunny"},
    ],
}

SAMPLE_WEATHERAPI_CURRENT_DATA = {
    "temperature": 72,
    "temperature_c": 22.2,
    "condition": "Sunny",
    "humidity": 45,
    "wind_speed": 10,
    "wind_speed_kph": 16.1,
    "wind_direction": "NW",
    "pressure": 30.1,
    "pressure_mb": 1019,
    "feelslike": 70,
    "feelslike_c": 21.1,
}

SAMPLE_WEATHERAPI_ALERTS_DATA = {
    "alerts": [
        {
            "event": "Flood Warning",
            "severity": "Moderate",
            "headline": "Flood warning for London area",
        },
        {
            "event": "Wind Advisory",
            "severity": "Minor",
            "headline": "Wind advisory in effect until evening",
        },
    ]
}

# --- Fixtures ---


@pytest.fixture
def mock_ui_manager():
    """Create a mock UIManager with patched methods."""
    # Create a mock UIManager
    with (
        patch("accessiweather.gui.ui_manager.UIManager._setup_ui"),
        patch("accessiweather.gui.ui_manager.UIManager._bind_events"),
    ):

        # Create a mock weather app frame
        mock_frame = MagicMock(spec=wx.Frame)
        mock_frame.location_choice = MagicMock()
        mock_frame.add_btn = MagicMock()
        mock_frame.remove_btn = MagicMock()
        mock_frame.refresh_btn = MagicMock()
        mock_frame.settings_btn = MagicMock()
        mock_frame.minimize_to_tray_btn = MagicMock()
        mock_frame.forecast_text = MagicMock()
        mock_frame.current_conditions_text = MagicMock()  # Add the current_conditions_text mock
        mock_frame.discussion_btn = MagicMock()
        mock_frame.alerts_list = MagicMock()
        mock_frame.alerts_list.InsertItem.return_value = 0
        mock_frame.alert_btn = MagicMock()
        mock_frame.SetStatusText = MagicMock()

        # Create a mock notifier
        mock_notifier = MagicMock()

        # Create the UIManager instance
        ui_manager = UIManager(mock_frame, mock_notifier)

        # Store references for test access using setattr to avoid type checking issues
        setattr(ui_manager, "mock_frame", mock_frame)
        setattr(ui_manager, "mock_notifier", mock_notifier)

        yield ui_manager


# --- Tests ---


def test_display_loading_state(mock_ui_manager):
    """Test loading state display."""
    # Test with location name
    mock_ui_manager.display_loading_state("New York")
    mock_ui_manager.mock_frame.refresh_btn.Disable.assert_called_once()
    mock_ui_manager.mock_frame.forecast_text.SetValue.assert_called_with("Loading forecast...")
    mock_ui_manager.mock_frame.current_conditions_text.SetValue.assert_called_with(
        "Loading current conditions..."
    )
    mock_ui_manager.mock_frame.alerts_list.DeleteAllItems.assert_called_once()
    mock_ui_manager.mock_frame.alerts_list.InsertItem.assert_called_with(0, "Loading alerts...")
    mock_ui_manager.mock_frame.SetStatusText.assert_called_with(
        "Updating weather data for New York..."
    )

    # Reset mocks
    mock_ui_manager.mock_frame.reset_mock()

    # Test nationwide
    mock_ui_manager.display_loading_state(is_nationwide=True)
    mock_ui_manager.mock_frame.forecast_text.SetValue.assert_called_with(
        "Loading nationwide forecast..."
    )
    mock_ui_manager.mock_frame.current_conditions_text.SetValue.assert_called_with(
        "Current conditions not available for nationwide view"
    )
    mock_ui_manager.mock_frame.SetStatusText.assert_called_with("Updating weather data...")


def test_display_forecast(mock_ui_manager):
    """Test forecast display."""
    # Test with regular forecast data
    mock_ui_manager.display_forecast(SAMPLE_FORECAST_DATA)
    forecast_text = mock_ui_manager.mock_frame.forecast_text.SetValue.call_args[0][0]
    # Sample data uses integer temperatures (75, 60), smart precision removes decimals for whole numbers
    assert "Today: 75°F" in forecast_text
    assert "Sunny with a high near 75" in forecast_text
    assert "Tonight: 60°F" in forecast_text
    assert "Clear with a low around 60" in forecast_text

    # Test with empty data
    mock_ui_manager.mock_frame.reset_mock()
    mock_ui_manager.display_forecast({})
    mock_ui_manager.mock_frame.forecast_text.SetValue.assert_called_with(
        "No forecast data available"
    )


def test_display_national_forecast(mock_ui_manager):
    """Test national forecast display."""
    # Test with national forecast data
    mock_ui_manager.display_forecast(SAMPLE_NATIONAL_FORECAST_DATA)
    forecast_text = mock_ui_manager.mock_frame.forecast_text.SetValue.call_args[0][0]
    assert "National Weather Overview" in forecast_text
    assert "Weather Prediction Center (WPC) Summary:" in forecast_text
    assert "Rain in the Northeast" in forecast_text
    assert "Storm Prediction Center (SPC) Summary:" in forecast_text
    assert "Severe storms possible" in forecast_text
    assert "National Weather Service" in forecast_text

    # Check that current conditions text is set correctly for nationwide view
    mock_ui_manager.mock_frame.current_conditions_text.SetValue.assert_called_with(
        "Current conditions not available for nationwide view"
    )

    # Test with partial data (WPC only)
    mock_ui_manager.mock_frame.reset_mock()
    partial_data = {
        "national_discussion_summaries": {"wpc": {"short_range_summary": "WPC summary"}}
    }
    mock_ui_manager.display_forecast(partial_data)
    forecast_text = mock_ui_manager.mock_frame.forecast_text.SetValue.call_args[0][0]
    assert "WPC summary" in forecast_text


def test_format_national_forecast(mock_ui_manager):
    """Test national forecast formatting."""
    # Test with None values
    data_with_none = {
        "national_discussion_summaries": {
            "wpc": {"short_range_summary": None},
            "spc": {"day1_summary": None},
        }
    }
    result = mock_ui_manager._format_national_forecast(data_with_none)
    assert "No WPC summary available" in result
    assert "No SPC summary available" in result

    # Test with empty data
    result = mock_ui_manager._format_national_forecast({})
    assert result == "No national forecast data available"


def test_display_alerts(mock_ui_manager):
    """Test alerts display."""
    # Test with alerts data
    processed_alerts = mock_ui_manager.display_alerts(SAMPLE_ALERTS_DATA)

    mock_ui_manager.mock_frame.alerts_list.DeleteAllItems.assert_called_once()
    assert len(processed_alerts) == 2
    assert mock_ui_manager.mock_frame.alerts_list.InsertItem.call_count == 2
    # 2 alerts * 2 additional columns
    assert mock_ui_manager.mock_frame.alerts_list.SetItem.call_count == 4

    # Test with empty data
    mock_ui_manager.mock_frame.reset_mock()
    mock_ui_manager.mock_frame.alerts_list.reset_mock()  # Also reset the alerts_list mock
    # Re-configure InsertItem after reset
    mock_ui_manager.mock_frame.alerts_list.InsertItem.return_value = 0

    processed_alerts = mock_ui_manager.display_alerts({})
    assert len(processed_alerts) == 0
    mock_ui_manager.mock_frame.alerts_list.DeleteAllItems.assert_called_once()


def test_display_forecast_error(mock_ui_manager):
    """Test forecast error display."""
    mock_ui_manager.display_forecast_error("API error")
    mock_ui_manager.mock_frame.forecast_text.SetValue.assert_called_with(
        "Error fetching forecast: API error"
    )
    mock_ui_manager.mock_frame.current_conditions_text.SetValue.assert_called_with(
        "Error fetching current conditions"
    )


def test_display_alerts_error(mock_ui_manager):
    """Test alerts error display."""
    mock_ui_manager.display_alerts_error("API error")
    mock_ui_manager.mock_frame.alerts_list.DeleteAllItems.assert_called_once()
    mock_ui_manager.mock_frame.alerts_list.InsertItem.assert_called_with(0, "Error")
    mock_ui_manager.mock_frame.alerts_list.SetItem.assert_has_calls(
        [call(0, 1, ""), call(0, 2, "Error fetching alerts: API error")]
    )


def test_display_ready_state(mock_ui_manager):
    """Test ready state display."""
    mock_ui_manager.display_ready_state()
    mock_ui_manager.mock_frame.refresh_btn.Enable.assert_called_once()
    mock_ui_manager.mock_frame.SetStatusText.assert_called_with("Ready")


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
    assert "Pressure: 30.10 inHg" in conditions_text


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

    empty_alerts = {"alerts": []}
    processed_alerts = mock_ui_manager.display_alerts(empty_alerts)
    assert len(processed_alerts) == 0
    mock_ui_manager.mock_frame.alert_btn.Disable.assert_called_once()


@pytest.mark.unit
def test_get_temperature_unit_preference_celsius(mock_ui_manager):
    """Test getting temperature unit preference for Celsius."""
    mock_ui_manager.frame.config = {"settings": {"temperature_unit": "celsius"}}

    result = mock_ui_manager._get_temperature_unit_preference()
    assert result == TemperatureUnit.CELSIUS


@pytest.mark.unit
def test_get_temperature_unit_preference_fahrenheit(mock_ui_manager):
    """Test getting temperature unit preference for Fahrenheit."""
    mock_ui_manager.frame.config = {"settings": {"temperature_unit": "fahrenheit"}}

    result = mock_ui_manager._get_temperature_unit_preference()
    assert result == TemperatureUnit.FAHRENHEIT


@pytest.mark.unit
def test_get_temperature_unit_preference_both(mock_ui_manager):
    """Test getting temperature unit preference for both."""
    mock_ui_manager.frame.config = {"settings": {"temperature_unit": "both"}}

    result = mock_ui_manager._get_temperature_unit_preference()
    assert result == TemperatureUnit.BOTH


@pytest.mark.unit
def test_get_temperature_unit_preference_default(mock_ui_manager):
    """Test getting temperature unit preference with default."""
    mock_ui_manager.frame.config = {"settings": {}}

    result = mock_ui_manager._get_temperature_unit_preference()
    assert result == TemperatureUnit.FAHRENHEIT


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
    assert result["location"] == "Test City"


@pytest.mark.unit
def test_extract_nws_data_for_taskbar(mock_ui_manager):
    """Test extracting NWS data for taskbar."""
    conditions_data = {
        "properties": {
            "temperature": {"value": 22.2, "unitCode": "degC"},
            "textDescription": "Sunny",
            "relativeHumidity": {"value": 45},
            "windSpeed": {"value": 16.1},
            "windDirection": {"value": 180},
            "apparentTemperature": {"value": 24.0, "unitCode": "degC"},
        }
    }

    result = mock_ui_manager._extract_nws_data_for_taskbar(conditions_data)

    assert "temp" in result
    assert result["temp_f"] is not None  # Should be converted from Celsius
    assert result["temp_c"] == 22.2
    assert result["condition"] == "Sunny"
    assert result["humidity"] == 45
    assert "wind_speed" in result
    assert "feels_like" in result
    assert result["feels_like_c"] == 24.0
    assert result["feels_like_f"] is not None  # Should be converted from Celsius
    assert "wind" in result  # Combined wind placeholder
    assert "location" in result


@pytest.mark.unit
def test_extract_nws_data_for_taskbar_with_wind_combination(mock_ui_manager):
    """Test extracting NWS data for taskbar with wind combination."""
    conditions_data = {
        "properties": {
            "temperature": {"value": 72.0, "unitCode": "degF"},
            "textDescription": "Partly Cloudy",
            "windSpeed": {"value": 10.0},  # km/h
            "windDirection": {"value": 225},  # SW
        }
    }

    result = mock_ui_manager._extract_nws_data_for_taskbar(conditions_data)

    # Check wind combination
    assert result["wind_dir"] == "SW"
    assert result["wind_speed"] is not None
    assert "SW" in result["wind"]
    assert "mph" in result["wind"]


@pytest.mark.unit
def test_extract_nws_data_for_taskbar_missing_apparent_temperature(mock_ui_manager):
    """Test extracting NWS data for taskbar when apparent temperature is missing."""
    conditions_data = {
        "properties": {
            "temperature": {"value": 72.0, "unitCode": "degF"},
            "textDescription": "Clear",
            # No apparentTemperature field
        }
    }

    result = mock_ui_manager._extract_nws_data_for_taskbar(conditions_data)

    # Feels like should be None when apparent temperature is missing
    assert result["feels_like"] is None
    assert result["feels_like_f"] is None
    assert result["feels_like_c"] is None


@pytest.mark.unit
def test_extract_nws_data_for_taskbar_malformed_data(mock_ui_manager):
    """Test extracting NWS data for taskbar with malformed data."""
    # Test with completely invalid data
    result = mock_ui_manager._extract_nws_data_for_taskbar(None)
    assert isinstance(result, dict)
    assert result["temp"] is None
    assert result["condition"] == ""
    assert result["location"] == ""

    # Test with missing properties
    result = mock_ui_manager._extract_nws_data_for_taskbar({})
    assert isinstance(result, dict)
    assert result["temp"] is None

    # Test with invalid temperature values
    conditions_data = {
        "properties": {
            "temperature": {"value": "invalid", "unitCode": "degF"},
            "textDescription": "Clear",
        }
    }
    result = mock_ui_manager._extract_nws_data_for_taskbar(conditions_data)
    assert result["temp"] is None
    assert result["condition"] == "Clear"


@pytest.mark.unit
def test_extract_nws_data_for_taskbar_error_handling(mock_ui_manager):
    """Test error handling in NWS data extraction."""
    # Test with data that will cause conversion errors
    conditions_data = {
        "properties": {
            "temperature": {"value": None, "unitCode": "degF"},
            "windSpeed": {"value": "not_a_number"},
            "windDirection": {"value": "invalid_direction"},
            "barometricPressure": {"value": "invalid_pressure"},
            "relativeHumidity": {"value": "invalid_humidity"},
            "textDescription": "Test Condition",
        }
    }

    result = mock_ui_manager._extract_nws_data_for_taskbar(conditions_data)

    # Should handle errors gracefully and return standardized structure
    assert isinstance(result, dict)
    assert result["temp"] is None
    assert result["wind_speed"] is None
    assert result["wind_dir"] == ""
    assert result["pressure"] is None
    assert result["humidity"] is None
    assert result["condition"] == "Test Condition"


@pytest.mark.unit
def test_wind_direction_conversion_utility():
    """Test the wind direction conversion utility function."""
    from accessiweather.gui.ui_manager import _convert_wind_direction_to_cardinal

    # Test normal conversions
    assert _convert_wind_direction_to_cardinal(0) == "N"
    assert _convert_wind_direction_to_cardinal(90) == "E"
    assert _convert_wind_direction_to_cardinal(180) == "S"
    assert _convert_wind_direction_to_cardinal(270) == "W"
    assert _convert_wind_direction_to_cardinal(45) == "NE"

    # Test edge cases
    assert _convert_wind_direction_to_cardinal(None) == ""
    assert _convert_wind_direction_to_cardinal("invalid") == ""
    assert _convert_wind_direction_to_cardinal(360) == "N"  # Should normalize
    assert _convert_wind_direction_to_cardinal(450) == "E"  # Should normalize


@pytest.mark.unit
def test_wind_formatting_utility():
    """Test the wind formatting utility function."""
    from accessiweather.gui.ui_manager import _format_combined_wind

    # Test normal formatting
    assert _format_combined_wind(15, 270, "mph") == "15 mph W"
    assert _format_combined_wind(0, 180, "mph") == "Calm"
    assert _format_combined_wind(10.7, "NE", "mph") == "11 mph NE"

    # Test edge cases
    assert _format_combined_wind(None, 180, "mph") == ""
    assert _format_combined_wind("invalid", 180, "mph") == ""
    assert _format_combined_wind(15, None, "mph") == "15 mph"
