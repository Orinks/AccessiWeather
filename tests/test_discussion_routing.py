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

    def test_stale_nationwide_location_opens_forecast_products_dialog(self, main_window_deps):
        """Even a legacy Nationwide current location routes through Forecaster Notes."""
        from accessiweather.ui.main_window import MainWindow

        main_window_deps.config_manager.get_current_location.return_value = FakeLocation(
            name="Nationwide"
        )

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)
            win.app = main_window_deps
            win._on_forecast_products = MagicMock()

        win._on_discussion()
        win._on_forecast_products.assert_called_once()

    def test_regular_location_opens_forecast_products_dialog(self, main_window_deps):
        """
        When current location is set, _on_forecast_products should run.

        Unit 8 rerouted this branch from the old single-AFD DiscussionDialog to
        the tabbed ForecastProductsDialog.
        """
        from accessiweather.ui.main_window import MainWindow

        main_window_deps.config_manager.get_current_location.return_value = FakeLocation(
            name="New York", latitude=40.7, longitude=-74.0
        )

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)
            win.app = main_window_deps
            win._on_forecast_products = MagicMock()

        win._on_discussion()
        win._on_forecast_products.assert_called_once()

    def test_none_location_opens_forecast_products_dialog(self, main_window_deps):
        """
        When current location is None, _on_forecast_products should still run.

        ``_on_forecast_products`` itself handles the None-location case by
        showing a "No Location Selected" message box.
        """
        from accessiweather.ui.main_window import MainWindow

        main_window_deps.config_manager.get_current_location.return_value = None

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)
            win.app = main_window_deps
            win._on_forecast_products = MagicMock()

        win._on_discussion()
        win._on_forecast_products.assert_called_once()
