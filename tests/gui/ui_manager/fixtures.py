"""Shared fixtures for UI Manager tests."""

from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.ui_manager import UIManager


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
