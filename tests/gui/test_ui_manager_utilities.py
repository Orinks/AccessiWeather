"""Tests for UIManager utility functions."""

import pytest


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
