"""Tests for UIManager alerts display functionality."""

from unittest.mock import call

from tests.gui.ui_manager_test_utils import SAMPLE_ALERTS_DATA, mock_ui_manager


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


def test_display_alerts_error(mock_ui_manager):
    """Test alerts error display."""
    mock_ui_manager.display_alerts_error("API error")
    mock_ui_manager.mock_frame.alerts_list.DeleteAllItems.assert_called_once()
    mock_ui_manager.mock_frame.alerts_list.InsertItem.assert_called_with(0, "Error")
    mock_ui_manager.mock_frame.alerts_list.SetItem.assert_has_calls(
        [call(0, 1, ""), call(0, 2, "Error fetching alerts: API error")]
    )
