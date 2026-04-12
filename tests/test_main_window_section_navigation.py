from __future__ import annotations

from unittest.mock import MagicMock, patch


class _FocusableWidget:
    def __init__(self, name: str):
        self.name = name
        self.focused = False
        self.shown = True

    def SetFocus(self) -> None:
        self.focused = True

    def Show(self, visible: bool = True) -> None:
        self.shown = visible


def _make_window():
    from accessiweather.ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
        win = MainWindow.__new__(MainWindow)

    win.current_conditions = _FocusableWidget("current")
    win.hourly_forecast_display = _FocusableWidget("hourly")
    win.daily_forecast_display = _FocusableWidget("daily")
    win.alerts_list = _FocusableWidget("alerts")
    win.event_center_display = _FocusableWidget("event-center")
    win._event_center_label = _FocusableWidget("event-label")
    win._event_center_visible = True
    win.Layout = MagicMock()
    return win


def test_get_visible_top_level_sections_returns_canonical_order():
    win = _make_window()

    sections = win.get_visible_top_level_sections()

    assert [label for label, _widget in sections] == [
        "Current conditions",
        "Hourly / near-term",
        "Daily forecast",
        "Alerts",
        "Event Center",
    ]


def test_get_visible_top_level_sections_skips_hidden_event_center():
    win = _make_window()
    win._event_center_visible = False

    sections = win.get_visible_top_level_sections()

    assert [label for label, _widget in sections] == [
        "Current conditions",
        "Hourly / near-term",
        "Daily forecast",
        "Alerts",
    ]


def test_focus_section_by_number_reveals_and_focuses_hidden_event_center():
    win = _make_window()
    win._event_center_visible = False
    win._event_center_label.shown = False
    win.event_center_display.shown = False

    win.focus_section_by_number(5)

    assert win._event_center_visible is True
    assert win.event_center_display.shown is True
    assert win.event_center_display.focused is True


def test_cycle_section_focus_advances_and_wraps_visible_sections():
    win = _make_window()

    win.cycle_section_focus()
    assert win.current_conditions.focused is True

    win.current_conditions.focused = False
    win.cycle_section_focus()
    assert win.hourly_forecast_display.focused is True

    win.hourly_forecast_display.focused = False
    win._section_focus_index = 4
    win.cycle_section_focus()
    assert win.current_conditions.focused is True


def test_cycle_section_focus_skips_hidden_event_center():
    win = _make_window()
    win._event_center_visible = False
    win._section_focus_index = 3

    win.cycle_section_focus()

    assert win.current_conditions.focused is True
    assert win.event_center_display.focused is False
