"""Tests for UI Manager data formatting and conversion."""

import pytest

from accessiweather.utils.temperature_utils import TemperatureUnit


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
