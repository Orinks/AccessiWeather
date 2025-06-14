"""Tests for UIManager temperature unit functionality."""

import pytest

from accessiweather.utils.temperature_utils import TemperatureUnit
from tests.gui.ui_manager_test_utils import mock_ui_manager


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
