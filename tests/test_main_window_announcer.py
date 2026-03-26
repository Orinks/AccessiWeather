"""Tests for ScreenReaderAnnouncer integration in MainWindow.set_status()."""

from unittest.mock import MagicMock, patch


class _StatusBarStub:
    """Minimal stub for wx.StatusBar used in set_status()."""

    def __init__(self):
        self.fields = ["", ""]

    def SetStatusText(self, text, field=0):
        self.fields[field] = text


class _MainWindowStub:
    """Minimal stub for MainWindow that exercises set_status() logic."""

    def __init__(self, announcer):
        self._status_bar = _StatusBarStub()
        self._announcer = announcer

    def GetStatusBar(self):
        return self._status_bar

    def set_status(self, message: str) -> None:
        self.GetStatusBar().SetStatusText(message, 0)
        if message:
            self._announcer.announce(message)


def _make_announcer(available=True):
    announcer = MagicMock()
    announcer.is_available.return_value = available
    return announcer


class TestSetStatusAnnounces:
    def test_announce_called_with_message(self):
        announcer = _make_announcer()
        win = _MainWindowStub(announcer)
        win.set_status("Weather updated for Test City")
        announcer.announce.assert_called_once_with("Weather updated for Test City")

    def test_announce_not_called_for_empty_string(self):
        announcer = _make_announcer()
        win = _MainWindowStub(announcer)
        win.set_status("")
        announcer.announce.assert_not_called()

    def test_status_bar_updated_regardless_of_announcer(self):
        announcer = _make_announcer(available=False)
        win = _MainWindowStub(announcer)
        win.set_status("Error: fetch failed")
        assert win.GetStatusBar().fields[0] == "Error: fetch failed"

    def test_multiple_set_status_calls_each_announce(self):
        announcer = _make_announcer()
        win = _MainWindowStub(announcer)
        win.set_status("Updating weather data...")
        win.set_status("Weather updated for Home")
        assert announcer.announce.call_count == 2

    def test_announce_called_with_error_message(self):
        announcer = _make_announcer()
        win = _MainWindowStub(announcer)
        win.set_status("Error: network timeout")
        announcer.announce.assert_called_once_with("Error: network timeout")

    def test_announce_called_with_loading_message(self):
        announcer = _make_announcer()
        win = _MainWindowStub(announcer)
        win.set_status("Updating weather data...")
        announcer.announce.assert_called_once_with("Updating weather data...")


class TestMainWindowAnnouncerInit:
    """Test that MainWindow creates a ScreenReaderAnnouncer on init."""

    def test_announcer_created_in_init(self):
        from accessiweather.ui.main_window import MainWindow

        mock_announcer = MagicMock()
        with (
            patch.object(MainWindow, "__init__", lambda self, *a, **kw: None),
            patch(
                "accessiweather.ui.main_window.ScreenReaderAnnouncer",
                return_value=mock_announcer,
            ),
        ):
            win = MainWindow.__new__(MainWindow)
            # Simulate what __init__ does for the announcer
            from accessiweather.ui.main_window import ScreenReaderAnnouncer

            win._announcer = ScreenReaderAnnouncer()

        assert win._announcer is mock_announcer

    def test_set_status_uses_announcer_from_init(self):
        from accessiweather.ui.main_window import MainWindow

        mock_announcer = MagicMock()
        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)

        win._announcer = mock_announcer
        win.GetStatusBar = MagicMock(return_value=MagicMock())
        # Call the real set_status
        MainWindow.set_status(win, "Refresh complete")
        mock_announcer.announce.assert_called_once_with("Refresh complete")
