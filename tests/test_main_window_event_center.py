from __future__ import annotations

from unittest.mock import MagicMock, patch


class _EventCenterCtrl:
    def __init__(self):
        self.chunks: list[str] = []
        self.focused = False
        self.shown = True

    def AppendText(self, text: str) -> None:
        self.chunks.append(text)

    def SetFocus(self) -> None:
        self.focused = True

    def Show(self, visible: bool = True) -> None:
        self.shown = visible


class _WidgetStub:
    def __init__(self):
        self.shown = True

    def Show(self, visible: bool = True) -> None:
        self.shown = visible


def _make_window():
    from accessiweather.ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
        win = MainWindow.__new__(MainWindow)

    win.event_center_display = _EventCenterCtrl()
    win._event_center_label = _WidgetStub()
    win._event_center_visible = True
    win.Layout = MagicMock()
    return win


def test_append_event_center_entry_adds_timestamped_line():
    win = _make_window()

    win.append_event_center_entry("Briefing: Dry for 30 minutes.")

    output = "".join(win.event_center_display.chunks)
    assert "Briefing: Dry for 30 minutes." in output
    assert output.startswith("[")
    assert "] " in output


def test_toggle_event_center_hides_and_shows_widgets():
    win = _make_window()

    win.toggle_event_center()
    assert win._event_center_visible is False
    assert win._event_center_label.shown is False
    assert win.event_center_display.shown is False

    win.toggle_event_center()
    assert win._event_center_visible is True
    assert win._event_center_label.shown is True
    assert win.event_center_display.shown is True


def test_focus_event_center_reveals_hidden_panel_and_focuses_text_control():
    win = _make_window()
    win._event_center_visible = False
    win._event_center_label.shown = False
    win.event_center_display.shown = False

    win.focus_event_center()

    assert win._event_center_visible is True
    assert win._event_center_label.shown is True
    assert win.event_center_display.shown is True
    assert win.event_center_display.focused is True
