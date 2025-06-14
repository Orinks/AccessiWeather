"""Tests for UIManager forecast display functionality."""

from tests.gui.ui_manager_test_utils import (
    SAMPLE_FORECAST_DATA,
    SAMPLE_NATIONAL_FORECAST_DATA,
    mock_ui_manager,
)


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


def test_display_forecast_error(mock_ui_manager):
    """Test forecast error display."""
    mock_ui_manager.display_forecast_error("API error")
    mock_ui_manager.mock_frame.forecast_text.SetValue.assert_called_with(
        "Error fetching forecast: API error"
    )
    mock_ui_manager.mock_frame.current_conditions_text.SetValue.assert_called_with(
        "Error fetching current conditions"
    )
