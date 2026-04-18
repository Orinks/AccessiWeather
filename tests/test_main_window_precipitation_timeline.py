from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

from accessiweather.models import MinutelyPrecipitationForecast, MinutelyPrecipitationPoint


class _MenuItemStub:
    def __init__(self) -> None:
        self.enabled: bool | None = None
        self.calls: list[bool] = []

    def Enable(self, value: bool) -> None:
        self.enabled = value
        self.calls.append(value)


def _make_forecast() -> MinutelyPrecipitationForecast:
    return MinutelyPrecipitationForecast(
        summary="Rain",
        points=[
            MinutelyPrecipitationPoint(
                time=datetime(2026, 1, 1, 15, 4, tzinfo=UTC),
                precipitation_intensity=0.1,
                precipitation_type="rain",
            )
        ],
    )


def _make_window(current_weather_data=None, *, all_locations: bool = False):
    from accessiweather.ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self, *args, **kwargs: None):
        win = MainWindow.__new__(MainWindow)

    mutable_win = cast(Any, win)
    mutable_win.app = SimpleNamespace(current_weather_data=current_weather_data)
    mutable_win._all_locations_active = all_locations
    mutable_win._precipitation_timeline_item = _MenuItemStub()
    return win


def test_view_menu_source_includes_precipitation_timeline_item():
    source = Path("src/accessiweather/ui/main_window.py").read_text()

    assert "Precipitation &Timeline..." in source
    assert "_precipitation_timeline_id" in source
    assert "_on_precipitation_timeline" in source


def test_menu_item_enabled_when_minutely_precipitation_exists():
    win = _make_window(SimpleNamespace(minutely_precipitation=_make_forecast()))

    win._update_precipitation_timeline_menu_state()

    assert win._precipitation_timeline_item.enabled is True


def test_menu_item_disabled_without_minutely_precipitation():
    win = _make_window(SimpleNamespace(minutely_precipitation=None))

    win._update_precipitation_timeline_menu_state()

    assert win._precipitation_timeline_item.enabled is False


def test_menu_item_disabled_in_all_locations_view():
    win = _make_window(SimpleNamespace(minutely_precipitation=_make_forecast()), all_locations=True)

    win._update_precipitation_timeline_menu_state()

    assert win._precipitation_timeline_item.enabled is False


def test_precipitation_timeline_handler_opens_dialog():
    from accessiweather.ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self, *args, **kwargs: None):
        win = MainWindow.__new__(MainWindow)

    cast(Any, win).app = MagicMock()

    with patch("accessiweather.ui.dialogs.show_precipitation_timeline_dialog") as show_dialog:
        win._on_precipitation_timeline()

    show_dialog.assert_called_once_with(win, win.app)
