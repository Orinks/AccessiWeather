"""Tests for UI Manager display methods."""

from unittest.mock import call

from .fixtures import mock_ui_manager
from .test_data import SAMPLE_ALERTS_DATA, SAMPLE_FORECAST_DATA, SAMPLE_NATIONAL_FORECAST_DATA


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
