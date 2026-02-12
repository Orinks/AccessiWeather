"""Tests for NOAA Weather Radio player dialog."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.noaa_radio import Station


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
    """Create a comprehensive wx mock with all submodules."""
    wx_mock = MagicMock()
    # Set integer constants
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

    # Use real classes for inheritance
    wx_mock.Window = _FakeWxWindow
    wx_mock.Dialog = _FakeWxDialog

    # Choice mock
    choice_inst = MagicMock()
    choice_inst.GetSelection.return_value = 0
    wx_mock.Choice.return_value = choice_inst

    # Slider mock
    slider_inst = MagicMock()
    slider_inst.GetValue.return_value = 100
    wx_mock.Slider.return_value = slider_inst

    return wx_mock


@pytest.fixture
def noaa_dialog_module():
    """Import noaa_radio_dialog with wx fully mocked in sys.modules."""
    wx_mock = _create_wx_mock()

    # Save and replace all wx-related modules
    wx_lib_mock = MagicMock()
    wx_modules_to_mock = {
        "wx": wx_mock,
        "wx.lib": wx_lib_mock,
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

    # Remove cached imports of dialog modules so they re-import with mocked wx
    to_remove = [k for k in sys.modules if "accessiweather.ui" in k]
    removed = {k: sys.modules.pop(k) for k in to_remove}

    try:
        # Import directly, not through ui.__init__
        from accessiweather.ui.dialogs import noaa_radio_dialog

        # Reload to ensure fresh import with mocked wx
        importlib.reload(noaa_radio_dialog)
        yield noaa_radio_dialog
    finally:
        # Restore cached ui modules
        for k, v in removed.items():
            sys.modules[k] = v
        # Restore wx modules
        for m in wx_modules_to_mock:
            if m in saved:
                sys.modules[m] = saved[m]
            elif m in sys.modules:
                del sys.modules[m]


def _make_dialog_instance(module):
    """Create a NOAARadioDialog instance without calling __init__."""
    dlg = object.__new__(module.NOAARadioDialog)
    dlg._lat = 40.7
    dlg._lon = -74.0
    dlg._stations = [
        Station(
            call_sign="KEC49", frequency=162.55, name="New York", lat=40.75, lon=-73.98, state="NY"
        ),
        Station(
            call_sign="WXJ76",
            frequency=162.40,
            name="Philadelphia",
            lat=39.95,
            lon=-75.17,
            state="PA",
        ),
    ]
    dlg._player = MagicMock()
    dlg._url_provider = MagicMock()
    dlg._station_choice = MagicMock()
    dlg._station_choice.GetSelection.return_value = 0
    dlg._play_btn = MagicMock()
    dlg._stop_btn = MagicMock()
    dlg._volume_slider = MagicMock()
    dlg._volume_slider.GetValue.return_value = 100
    dlg._status_text = MagicMock()
    dlg._health_timer = MagicMock()
    return dlg


class TestNOAARadioDialogModule:
    """Tests for dialog module structure."""

    def test_has_dialog_class(self, noaa_dialog_module):
        """Test that NOAARadioDialog class exists."""
        assert hasattr(noaa_dialog_module, "NOAARadioDialog")

    def test_has_show_function(self, noaa_dialog_module):
        """Test that show_noaa_radio_dialog function exists."""
        assert callable(noaa_dialog_module.show_noaa_radio_dialog)

    def test_dialog_inherits_from_wx_dialog(self, noaa_dialog_module):
        """Test NOAARadioDialog inherits from wx.Dialog."""
        import wx

        assert issubclass(noaa_dialog_module.NOAARadioDialog, wx.Dialog)


class TestGetSelectedStation:
    """Tests for station selection logic."""

    def test_returns_station_at_index(self, noaa_dialog_module):
        """Test returns the correct station for a valid selection."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._station_choice.GetSelection.return_value = 0
        assert dlg._get_selected_station().call_sign == "KEC49"

    def test_returns_second_station(self, noaa_dialog_module):
        """Test returns station at index 1."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._station_choice.GetSelection.return_value = 1
        assert dlg._get_selected_station().call_sign == "WXJ76"

    def test_returns_none_for_not_found(self, noaa_dialog_module):
        """Test returns None when nothing selected."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._station_choice.GetSelection.return_value = -1
        assert dlg._get_selected_station() is None

    def test_returns_none_for_out_of_range(self, noaa_dialog_module):
        """Test returns None when index exceeds station list."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._station_choice.GetSelection.return_value = 99
        assert dlg._get_selected_station() is None


class TestPlaybackControls:
    """Tests for play/stop/volume control logic."""

    def test_on_play_calls_player(self, noaa_dialog_module):
        """Test Play triggers player.play with stream URL."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._url_provider.get_stream_urls.return_value = ["https://example.com/stream"]
        dlg._on_play(MagicMock())
        dlg._player.play.assert_called_once_with("https://example.com/stream", fallback_urls=[])

    def test_on_play_no_url_sets_status(self, noaa_dialog_module):
        """Test Play with no URL available sets status."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._url_provider.get_stream_urls.return_value = []
        dlg._on_play(MagicMock())
        dlg._player.play.assert_not_called()
        dlg._status_text.SetLabel.assert_called()

    def test_on_play_no_station_sets_status(self, noaa_dialog_module):
        """Test Play with no station selected sets status."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._station_choice.GetSelection.return_value = -1
        dlg._on_play(MagicMock())
        dlg._player.play.assert_not_called()
        dlg._status_text.SetLabel.assert_called_with("No station selected")

    def test_on_stop_calls_player(self, noaa_dialog_module):
        """Test Stop triggers player.stop."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._on_stop(MagicMock())
        dlg._player.stop.assert_called_once()

    def test_on_volume_change(self, noaa_dialog_module):
        """Test volume slider change updates player."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._volume_slider.GetValue.return_value = 75
        dlg._on_volume_change(MagicMock())
        dlg._player.set_volume.assert_called_once_with(0.75)

    def test_on_volume_change_zero(self, noaa_dialog_module):
        """Test volume slider at zero."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._volume_slider.GetValue.return_value = 0
        dlg._on_volume_change(MagicMock())
        dlg._player.set_volume.assert_called_once_with(0.0)


class TestCallbacks:
    """Tests for player callback handlers."""

    def test_on_playing_updates_ui(self, noaa_dialog_module):
        """Test playing callback updates buttons and status."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._on_playing()
        dlg._play_btn.Enable.assert_called_with(False)
        dlg._stop_btn.Enable.assert_called_with(True)
        assert "KEC49" in dlg._status_text.SetLabel.call_args[0][0]

    def test_on_stopped_updates_ui(self, noaa_dialog_module):
        """Test stopped callback updates buttons and status."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._on_stopped()
        dlg._play_btn.Enable.assert_called_with(True)
        dlg._stop_btn.Enable.assert_called_with(False)
        dlg._status_text.SetLabel.assert_called_with("Stopped")

    def test_on_error_updates_ui(self, noaa_dialog_module):
        """Test error callback updates buttons and status."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._on_error("Connection failed")
        dlg._play_btn.Enable.assert_called_with(True)
        dlg._stop_btn.Enable.assert_called_with(False)
        dlg._status_text.SetLabel.assert_called_with("Error: Connection failed")


class TestDialogLifecycle:
    """Tests for dialog open/close behavior."""

    def test_on_close_stops_and_destroys(self, noaa_dialog_module):
        """Test closing dialog stops player and destroys window."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg.Destroy = MagicMock()
        dlg._on_close(MagicMock())
        dlg._player.stop.assert_called_once()
        dlg.Destroy.assert_called_once()

    def test_show_noaa_radio_dialog_creates_and_shows(self, noaa_dialog_module):
        """Test convenience function creates and shows dialog."""
        mock_dlg = MagicMock()
        with patch.object(noaa_dialog_module, "NOAARadioDialog", return_value=mock_dlg):
            result = noaa_dialog_module.show_noaa_radio_dialog(MagicMock(), 40.7, -74.0)
            mock_dlg.Show.assert_called_once()
            assert result is mock_dlg

    def test_show_noaa_radio_dialog_returns_dialog(self, noaa_dialog_module):
        """Test convenience function returns the dialog (non-modal)."""
        mock_dlg = MagicMock()
        with patch.object(noaa_dialog_module, "NOAARadioDialog", return_value=mock_dlg):
            result = noaa_dialog_module.show_noaa_radio_dialog(MagicMock(), 0, 0)
            assert result is mock_dlg


class TestSetStatus:
    """Tests for status text updates."""

    def test_set_status(self, noaa_dialog_module):
        """Test _set_status updates label."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._set_status("Testing")
        dlg._status_text.SetLabel.assert_called_with("Testing")
