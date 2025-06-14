"""Tests for UIManager display state functionality."""

from tests.gui.ui_manager_test_utils import mock_ui_manager


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


def test_display_ready_state(mock_ui_manager):
    """Test ready state display."""
    mock_ui_manager.display_ready_state()
    mock_ui_manager.mock_frame.refresh_btn.Enable.assert_called_once()
    mock_ui_manager.mock_frame.SetStatusText.assert_called_with("Ready")
