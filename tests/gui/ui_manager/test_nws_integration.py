"""Tests for UI Manager NWS integration."""

import pytest

from .fixtures import mock_ui_manager


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
