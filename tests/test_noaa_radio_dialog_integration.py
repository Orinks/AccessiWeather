"""
Integration tests for NOAA Radio dialog-player wiring (US-005).

These tests verify that the dialog correctly wires up RadioPlayer,
StationDatabase, and StreamURLProvider — the full integration path
from UI controls through to player actions.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.noaa_radio import Station
from accessiweather.noaa_radio.station_db import StationResult


class _FakeWxWindow:
    """Fake wx.Window base for testing."""

    def __init__(self, *args, **kwargs):
        """Initialize fake window."""

    def Bind(self, *args, **kwargs):
        """Fake Bind."""

    def Destroy(self):
        """Fake Destroy."""


class _FakeWxDialog(_FakeWxWindow):
    """Fake wx.Dialog base for testing."""


def _create_wx_mock():
    """Create a comprehensive wx mock."""
    wx_mock = MagicMock()
    for attr in [
        "DEFAULT_DIALOG_STYLE",
        "RESIZE_BORDER",
        "VERTICAL",
        "HORIZONTAL",
        "ALL",
        "EXPAND",
        "LEFT",
        "RIGHT",
        "TOP",
        "BOTTOM",
        "ALIGN_RIGHT",
        "OK",
        "ICON_ERROR",
        "SL_HORIZONTAL",
        "ID_CLOSE",
    ]:
        setattr(wx_mock, attr, 0)
    wx_mock.NOT_FOUND = -1
    wx_mock.Window = _FakeWxWindow
    wx_mock.Dialog = _FakeWxDialog

    choice_inst = MagicMock()
    choice_inst.GetSelection.return_value = 0
    wx_mock.Choice.return_value = choice_inst

    slider_inst = MagicMock()
    slider_inst.GetValue.return_value = 100
    wx_mock.Slider.return_value = slider_inst

    return wx_mock


@pytest.fixture
def noaa_dialog_module():
    """Import noaa_radio_dialog with wx fully mocked."""
    wx_mock = _create_wx_mock()

    wx_modules_to_mock = {
        "wx": wx_mock,
        "wx.lib": MagicMock(),
        "wx.lib.sized_controls": MagicMock(),
        "wx.lib.scrolledpanel": MagicMock(),
        "wx.adv": MagicMock(),
        "wx.html": MagicMock(),
        "wx.html2": MagicMock(),
    }

    saved = {}
    for m in wx_modules_to_mock:
        if m in sys.modules:
            saved[m] = sys.modules[m]

    for m, mock_obj in wx_modules_to_mock.items():
        sys.modules[m] = mock_obj

    to_remove = [k for k in sys.modules if "accessiweather.ui" in k]
    removed = {k: sys.modules.pop(k) for k in to_remove}

    try:
        from accessiweather.ui.dialogs import noaa_radio_dialog

        importlib.reload(noaa_radio_dialog)
        yield noaa_radio_dialog
    finally:
        for k, v in removed.items():
            sys.modules[k] = v
        for m in wx_modules_to_mock:
            if m in saved:
                sys.modules[m] = saved[m]
            elif m in sys.modules:
                del sys.modules[m]


def _make_dialog(module):
    """Create a dialog instance with mocked dependencies."""
    dlg = object.__new__(module.NOAARadioDialog)
    dlg._lat = 40.7
    dlg._lon = -74.0
    dlg._stations = [
        Station("KEC49", 162.55, "New York", 40.75, -73.98, "NY"),
        Station("WXJ76", 162.40, "Philadelphia", 39.95, -75.17, "PA"),
    ]
    dlg._player = MagicMock()
    dlg._player.is_playing.return_value = False
    dlg._url_provider = MagicMock()
    dlg._station_choice = MagicMock()
    dlg._station_choice.GetSelection.return_value = 0
    dlg._play_stop_btn = MagicMock()
    dlg._volume_slider = MagicMock()
    dlg._volume_slider.GetValue.return_value = 100
    dlg._status_text = MagicMock()
    dlg._health_timer = MagicMock()
    dlg._prefs = MagicMock()
    dlg._current_urls = ["http://example.com/stream1", "http://example.com/stream2"]
    dlg._current_url_index = 0
    dlg._next_stream_btn = MagicMock()
    dlg._prefer_btn = MagicMock()
    dlg._auto_advance_stream = True
    return dlg


class TestFullPlaybackFlow:
    """Test complete play → status → stop flow."""

    def test_play_stop_cycle(self, noaa_dialog_module):
        """Test full play then stop cycle updates all UI elements."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg._url_provider.get_stream_urls.return_value = ["https://example.com/stream"]
        dlg._prefs.reorder_urls.return_value = ["https://example.com/stream"]

        # Play
        dlg._on_play(MagicMock())
        dlg._player.play.assert_called_once_with("https://example.com/stream")

        # Simulate player callback
        dlg._on_playing()
        dlg._play_stop_btn.Enable.assert_called_with(True)
        dlg._play_stop_btn.SetLabel.assert_called_with("Stop")

        # Stop
        dlg._on_stop(MagicMock())
        dlg._player.stop.assert_called_once()

        # Simulate stopped callback
        dlg._on_stopped()
        dlg._play_stop_btn.Enable.assert_called_with(True)
        dlg._play_stop_btn.SetLabel.assert_called_with("Play")

    def test_play_error_recovery(self, noaa_dialog_module):
        """Test error during play allows retry."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg._url_provider.get_stream_urls.return_value = ["https://example.com/stream"]
        dlg._prefs.reorder_urls.return_value = ["https://example.com/stream"]

        # Play triggers error callback
        dlg._on_play(MagicMock())
        dlg._on_error("Connection refused")

        # Buttons should allow retry
        dlg._play_stop_btn.Enable.assert_called_with(True)
        dlg._play_stop_btn.SetLabel.assert_called_with("Play")
        assert "Error: Connection refused" in dlg._status_text.SetLabel.call_args[0][0]

    def test_volume_change_during_playback(self, noaa_dialog_module):
        """Test adjusting volume while playing."""
        dlg = _make_dialog(noaa_dialog_module)

        dlg._volume_slider.GetValue.return_value = 50
        dlg._on_volume_change(MagicMock())
        dlg._player.set_volume.assert_called_with(0.5)

        dlg._volume_slider.GetValue.return_value = 0
        dlg._on_volume_change(MagicMock())
        dlg._player.set_volume.assert_called_with(0.0)

        dlg._volume_slider.GetValue.return_value = 100
        dlg._on_volume_change(MagicMock())
        dlg._player.set_volume.assert_called_with(1.0)


class TestStationSelection:
    """Test station selection impacts playback."""

    def test_play_second_station(self, noaa_dialog_module):
        """Test selecting and playing a different station."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg._station_choice.GetSelection.return_value = 1
        dlg._url_provider.get_stream_urls.return_value = ["https://example.com/wxj76"]
        dlg._prefs.reorder_urls.return_value = ["https://example.com/wxj76"]

        dlg._on_play(MagicMock())
        dlg._url_provider.get_stream_urls.assert_called_with("WXJ76")
        dlg._player.play.assert_called_with("https://example.com/wxj76")

    def test_playing_callback_shows_selected_station_name(self, noaa_dialog_module):
        """Test that playing callback shows the selected station call sign."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg._station_choice.GetSelection.return_value = 1
        dlg._on_playing()
        assert "WXJ76" in dlg._status_text.SetLabel.call_args[0][0]


class TestDialogCleanup:
    """Test dialog close cleanup."""

    def test_close_during_playback(self, noaa_dialog_module):
        """Test closing dialog during active playback stops player."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg.Destroy = MagicMock()

        # Simulate playing state
        dlg._on_playing()

        # Close
        dlg._on_close(MagicMock())
        dlg._player.stop.assert_called_once()
        dlg.Destroy.assert_called_once()

    def test_close_when_stopped(self, noaa_dialog_module):
        """Test closing dialog when not playing still calls stop (safe)."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg.Destroy = MagicMock()
        dlg._on_close(MagicMock())
        dlg._player.stop.assert_called_once()
        dlg.Destroy.assert_called_once()


class TestLoadStations:
    """Test station loading on dialog init."""

    def test_load_stations_populates_choice(self, noaa_dialog_module):
        """Test _load_stations populates the station choice control."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg._station_choice = MagicMock()

        test_stations = [
            Station("TEST1", 162.55, "Test City 1", 40.0, -74.0, "NY"),
            Station("TEST2", 162.40, "Test City 2", 41.0, -75.0, "PA"),
        ]
        results = [
            StationResult(station=s, distance_km=10.0 * i) for i, s in enumerate(test_stations)
        ]

        with patch("accessiweather.ui.dialogs.noaa_radio_dialog.StationDatabase") as mock_db_cls:
            mock_db_cls.return_value.find_nearest.return_value = results
            dlg._load_stations()

        dlg._station_choice.Set.assert_called_once()
        choices = dlg._station_choice.Set.call_args[0][0]
        assert len(choices) == 2
        assert "TEST1" in choices[0]
        assert "TEST2" in choices[1]
        dlg._station_choice.SetSelection.assert_called_with(0)
        assert dlg._stations == test_stations

    def test_load_stations_error_sets_status(self, noaa_dialog_module):
        """Test _load_stations handles database errors gracefully."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg._station_choice = MagicMock()
        dlg._status_text = MagicMock()

        with patch("accessiweather.ui.dialogs.noaa_radio_dialog.StationDatabase") as mock_db_cls:
            mock_db_cls.return_value.find_nearest.side_effect = RuntimeError("DB error")
            dlg._load_stations()

        assert "Error" in dlg._status_text.SetLabel.call_args[0][0]


class TestErrorStates:
    """Test error handling in dialog-player integration."""

    def test_no_stream_url_available(self, noaa_dialog_module):
        """Test play with no stream URL shows error in status."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg._url_provider.get_stream_urls.return_value = []
        dlg._on_play(MagicMock())
        dlg._player.play.assert_not_called()
        status = dlg._status_text.SetLabel.call_args[0][0]
        assert "No stream" in status

    def test_no_station_selected(self, noaa_dialog_module):
        """Test play with no station selected shows error."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg._station_choice.GetSelection.return_value = -1
        dlg._on_play(MagicMock())
        dlg._player.play.assert_not_called()
        dlg._status_text.SetLabel.assert_called_with("No station selected")

    def test_connection_error_via_callback(self, noaa_dialog_module):
        """Test connection error reported via on_error callback."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg._on_error("Network unreachable")
        dlg._status_text.SetLabel.assert_called_with("Error: Network unreachable")
        dlg._play_stop_btn.Enable.assert_called_with(True)
        dlg._play_stop_btn.SetLabel.assert_called_with("Play")
