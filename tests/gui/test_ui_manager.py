"""Tests for UI Manager."""

# This file contains tests for the UIManager class using a patched approach
# that avoids the need to create actual wxPython UI components.

import wx
from unittest.mock import MagicMock, patch, call

import pytest

from accessiweather.gui.ui_manager import UIManager

# --- Test Data ---

SAMPLE_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "name": "Today",
                "temperature": 75,
                "temperatureUnit": "F",
                "detailedForecast": "Sunny with a high near 75."
            },
            {
                "name": "Tonight",
                "temperature": 60,
                "temperatureUnit": "F",
                "detailedForecast": "Clear with a low around 60."
            }
        ]
    }
}

SAMPLE_NATIONAL_FORECAST_DATA = {
    "national_discussion_summaries": {
        "wpc": {
            "short_range_summary": "Rain in the Northeast, sunny in the West.",
            "short_range_full": "Detailed WPC discussion..."
        },
        "spc": {
            "day1_summary": "Severe storms possible in the Plains.",
            "day1_full": "Detailed SPC discussion..."
        },
        "attribution": "National Weather Service"
    }
}

SAMPLE_ALERTS_DATA = {
    "features": [
        {
            "properties": {
                "event": "Severe Thunderstorm Warning",
                "severity": "Severe",
                "headline": "Severe thunderstorm warning until 5 PM"
            }
        },
        {
            "properties": {
                "event": "Flash Flood Watch",
                "severity": "Moderate",
                "headline": "Flash flood watch in effect"
            }
        }
    ]
}

# --- Fixtures ---


@pytest.fixture
def mock_ui_manager():
    """Create a mock UIManager with patched methods."""
    # Create a mock UIManager
    with patch('accessiweather.gui.ui_manager.UIManager._setup_ui'), \
         patch('accessiweather.gui.ui_manager.UIManager._bind_events'):

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

        # Store references for test access
        ui_manager.mock_frame = mock_frame
        ui_manager.mock_notifier = mock_notifier

        yield ui_manager


# --- Tests ---


def test_display_loading_state(mock_ui_manager):
    """Test loading state display."""
    # Test with location name
    mock_ui_manager.display_loading_state("New York")
    mock_ui_manager.mock_frame.refresh_btn.Disable.assert_called_once()
    mock_ui_manager.mock_frame.forecast_text.SetValue.assert_called_with("Loading forecast...")
    mock_ui_manager.mock_frame.current_conditions_text.SetValue.assert_called_with("Loading current conditions...")
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
        "national_discussion_summaries": {
            "wpc": {"short_range_summary": "WPC summary"}
        }
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
            "spc": {"day1_summary": None}
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
    mock_ui_manager.mock_frame.alerts_list.SetItem.assert_has_calls([
        call(0, 1, ""),
        call(0, 2, "Error fetching alerts: API error")
    ])


def test_display_ready_state(mock_ui_manager):
    """Test ready state display."""
    mock_ui_manager.display_ready_state()
    mock_ui_manager.mock_frame.refresh_btn.Enable.assert_called_once()
    mock_ui_manager.mock_frame.SetStatusText.assert_called_with("Ready")
