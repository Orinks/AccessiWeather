"""Tests for US-007: Discussion button routing based on selected location."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest


@dataclass
class FakeLocation:
    name: str
    latitude: float = 0.0
    longitude: float = 0.0


@pytest.fixture
def main_window_deps():
    """Create mocked main window with minimal dependencies."""
    app = MagicMock()
    app.config_manager = MagicMock()
    app.weather_client = MagicMock()
    app.current_weather_data = MagicMock(discussion="Sample text")
    app.config_manager.get_settings.return_value = MagicMock(ai_model=None)
    app.run_async = MagicMock()
    return app


class TestDiscussionRouting:
    """Test that _on_discussion routes to the correct dialog."""

    @patch("accessiweather.ui.main_window.NationwideDiscussionDialog", create=True)
    @patch("accessiweather.ui.main_window.NationalDiscussionService", create=True)
    def test_nationwide_opens_nationwide_dialog(
        self, mock_service_cls, mock_dialog_cls, main_window_deps
    ):
        """When current location is Nationwide, NationwideDiscussionDialog should open."""
        from accessiweather.ui.main_window import MainWindow

        main_window_deps.config_manager.get_current_location.return_value = FakeLocation(
            name="Nationwide"
        )

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)
            win.app = main_window_deps

        with (
            patch(
                "accessiweather.ui.dialogs.nationwide_discussion_dialog.NationwideDiscussionDialog"
            ) as mock_dlg_cls,
            patch(
                "accessiweather.services.national_discussion_service.NationalDiscussionService"
            ) as mock_svc_cls,
        ):
            mock_dlg_instance = MagicMock()
            mock_dlg_cls.return_value = mock_dlg_instance

            win._on_discussion()

            mock_svc_cls.assert_called_once()
            mock_dlg_cls.assert_called_once()
            mock_dlg_instance.ShowModal.assert_called_once()
            mock_dlg_instance.Destroy.assert_called_once()

    def test_regular_location_opens_regular_dialog(self, main_window_deps):
        """When current location is not Nationwide, show_discussion_dialog should be called."""
        from accessiweather.ui.main_window import MainWindow

        main_window_deps.config_manager.get_current_location.return_value = FakeLocation(
            name="New York", latitude=40.7, longitude=-74.0
        )

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)
            win.app = main_window_deps

        with patch("accessiweather.ui.dialogs.show_discussion_dialog") as mock_show:
            win._on_discussion()
            mock_show.assert_called_once_with(win, main_window_deps)

    def test_none_location_opens_regular_dialog(self, main_window_deps):
        """When current location is None, show_discussion_dialog should be called."""
        from accessiweather.ui.main_window import MainWindow

        main_window_deps.config_manager.get_current_location.return_value = None

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)
            win.app = main_window_deps

        with patch("accessiweather.ui.dialogs.show_discussion_dialog") as mock_show:
            win._on_discussion()
            mock_show.assert_called_once_with(win, main_window_deps)
