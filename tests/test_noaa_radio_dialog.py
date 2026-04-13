"""Tests for NOAA Weather Radio player dialog."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
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
        "ICON_INFORMATION",
        "SL_HORIZONTAL",
        "ID_CLOSE",
    ]:
        setattr(wx_mock, attr, 0)
    wx_mock.NOT_FOUND = -1
    wx_mock.EVT_CHECKBOX = MagicMock()

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

    checkbox_inst = MagicMock()
    checkbox_inst.GetValue.return_value = False
    wx_mock.CheckBox.return_value = checkbox_inst

    return wx_mock


@pytest.fixture
def noaa_dialog_module():
    """Import noaa_radio_dialog with wx fully mocked in sys.modules."""
    wx_mock = _create_wx_mock()
    bs4_mock = MagicMock()
    bs4_mock.BeautifulSoup = MagicMock()

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
        "bs4": bs4_mock,
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
    dlg._station_limit_choice = MagicMock()
    dlg._station_limit_choice.GetSelection.return_value = 0
    dlg._play_stop_btn = MagicMock()
    dlg._volume_slider = MagicMock()
    dlg._volume_slider.GetValue.return_value = 100
    dlg._status_text = MagicMock()
    dlg._health_timer = MagicMock()
    dlg._prefs = MagicMock()
    dlg._availability_cache = MagicMock()
    dlg._station_availability = MagicMock()
    dlg._current_urls = ["http://example.com/stream1", "http://example.com/stream2"]
    dlg._current_url_index = 0
    dlg._next_stream_btn = MagicMock()
    dlg._prefer_btn = MagicMock()
    dlg._show_unavailable_checkbox = MagicMock()
    dlg._show_unavailable_checkbox.GetValue.return_value = False
    dlg._auto_advance_stream = True
    dlg._playing_station = None
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

    def test_dialog_uses_app_runtime_prefs_path(self, noaa_dialog_module):
        fake_app = MagicMock()
        fake_app.runtime_paths.noaa_radio_preferences_file = Path(
            "/tmp/config/noaa_radio_prefs.json"
        )

        with (
            patch.object(noaa_dialog_module.wx, "GetApp", return_value=fake_app),
            patch.object(noaa_dialog_module, "RadioPlayer"),
            patch.object(noaa_dialog_module, "StreamURLProvider"),
            patch.object(
                noaa_dialog_module, "_get_clients", return_value=(MagicMock(), MagicMock())
            ),
            patch.object(noaa_dialog_module, "RadioPreferences") as mock_prefs,
            patch.object(noaa_dialog_module.NOAARadioDialog, "_init_ui"),
            patch.object(noaa_dialog_module.NOAARadioDialog, "_load_stations_async"),
        ):
            noaa_dialog_module.NOAARadioDialog(MagicMock(), 40.7, -74.0)

        mock_prefs.assert_called_once_with(path=fake_app.runtime_paths.noaa_radio_preferences_file)

    def test_dialog_uses_app_runtime_availability_path(self, noaa_dialog_module):
        fake_app = MagicMock()
        fake_app.runtime_paths.noaa_radio_preferences_file = Path(
            "/tmp/config/noaa_radio_prefs.json"
        )
        fake_app.runtime_paths.noaa_radio_availability_file = Path(
            "/tmp/config/noaa_radio_availability.json"
        )

        with (
            patch.object(noaa_dialog_module.wx, "GetApp", return_value=fake_app),
            patch.object(noaa_dialog_module, "RadioPlayer"),
            patch.object(noaa_dialog_module, "StreamURLProvider"),
            patch.object(
                noaa_dialog_module, "_get_clients", return_value=(MagicMock(), MagicMock())
            ),
            patch.object(noaa_dialog_module, "RadioPreferences"),
            patch.object(noaa_dialog_module, "StationAvailabilityCache") as mock_cache,
            patch.object(noaa_dialog_module, "StationAvailabilityService"),
            patch.object(noaa_dialog_module.NOAARadioDialog, "_init_ui"),
            patch.object(noaa_dialog_module.NOAARadioDialog, "_load_stations_async"),
        ):
            noaa_dialog_module.NOAARadioDialog(MagicMock(), 40.7, -74.0)

        mock_cache.assert_called_once_with(path=fake_app.runtime_paths.noaa_radio_availability_file)


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
        dlg._prefs.reorder_urls.return_value = ["https://example.com/stream"]
        dlg._on_play(MagicMock())
        dlg._player.play.assert_called_once_with("https://example.com/stream")

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
        dlg._play_stop_btn.Enable.assert_called_with(True)
        dlg._play_stop_btn.SetLabel.assert_called_with("Stop")
        assert "KEC49" in dlg._status_text.SetLabel.call_args[0][0]

    def test_on_playing_clears_station_suppression(self, noaa_dialog_module):
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._playing_station = dlg._stations[0]

        dlg._on_playing()

        dlg._availability_cache.clear.assert_called_once_with("KEC49")

    def test_on_stopped_updates_ui(self, noaa_dialog_module):
        """Test stopped callback updates buttons and status."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._on_stopped()
        dlg._play_stop_btn.Enable.assert_called_with(True)
        dlg._play_stop_btn.SetLabel.assert_called_with("Play")
        dlg._status_text.SetLabel.assert_called_with("Stopped")

    def test_on_error_updates_ui(self, noaa_dialog_module):
        """Test error callback updates buttons and status."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._on_error("Connection failed")
        dlg._play_stop_btn.Enable.assert_called_with(True)
        dlg._play_stop_btn.SetLabel.assert_called_with("Play")
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


class TestUnavailableStations:
    """Tests for unavailable-station UI behavior."""

    def test_show_unavailable_checkbox_is_created(self, noaa_dialog_module):
        dlg = object.__new__(noaa_dialog_module.NOAARadioDialog)
        dlg.Bind = MagicMock()
        dlg._on_health_check = MagicMock()
        dlg._on_station_changed = MagicMock()
        dlg._on_choice_key = MagicMock()
        dlg._on_play_stop = MagicMock()
        dlg._on_next_stream = MagicMock()
        dlg._on_set_preferred = MagicMock()
        dlg._on_volume_change = MagicMock()
        dlg._on_close = MagicMock()
        dlg._on_show_unavailable_changed = MagicMock()
        dlg._prefs = MagicMock()
        dlg._prefs.get_station_limit.return_value = 10

        noaa_dialog_module.NOAARadioDialog._init_ui(dlg)

        noaa_dialog_module.wx.CheckBox.assert_called_once()
        assert (
            noaa_dialog_module.wx.CheckBox.call_args.kwargs["label"] == "Show unavailable stations"
        )

    def test_station_limit_choice_is_created(self, noaa_dialog_module):
        dlg = object.__new__(noaa_dialog_module.NOAARadioDialog)
        dlg.Bind = MagicMock()
        dlg._on_health_check = MagicMock()
        dlg._on_station_changed = MagicMock()
        dlg._on_choice_key = MagicMock()
        dlg._on_play_stop = MagicMock()
        dlg._on_next_stream = MagicMock()
        dlg._on_set_preferred = MagicMock()
        dlg._on_volume_change = MagicMock()
        dlg._on_close = MagicMock()
        dlg._on_show_unavailable_changed = MagicMock()
        dlg._on_station_limit_changed = MagicMock()
        dlg._prefs = MagicMock()
        dlg._prefs.get_station_limit.return_value = 25

        noaa_dialog_module.NOAARadioDialog._init_ui(dlg)

        assert noaa_dialog_module.wx.Choice.call_count == 2
        station_limit_choice = noaa_dialog_module.wx.Choice.call_args_list[1]
        assert station_limit_choice.kwargs["choices"] == ["10", "25", "50", "100", "All"]

    def test_show_unavailable_toggle_refreshes_station_list(self, noaa_dialog_module):
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._load_stations_async = MagicMock()

        dlg._on_show_unavailable_changed(MagicMock())

        dlg._load_stations_async.assert_called_once()

    def test_station_limit_toggle_persists_and_refreshes_station_list(self, noaa_dialog_module):
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._station_limit_choice.GetSelection.return_value = 2
        dlg._load_stations_async = MagicMock()
        event = MagicMock()

        dlg._on_station_limit_changed(event)

        dlg._prefs.set_station_limit.assert_called_once_with(50)
        dlg._load_stations_async.assert_called_once()
        event.Skip.assert_called_once()

    def test_on_stations_loaded_sets_no_available_status_when_empty(self, noaa_dialog_module):
        dlg = _make_dialog_instance(noaa_dialog_module)

        dlg._on_stations_loaded([], [])

        dlg._status_text.SetLabel.assert_called_with("No stations with streams available")

    def test_suppressed_station_label_is_preserved_in_loaded_choices(self, noaa_dialog_module):
        dlg = _make_dialog_instance(noaa_dialog_module)
        station = Station("WXK27", 162.4, "Austin", 0.0, 0.0, "TX")

        dlg._on_stations_loaded(
            [station],
            ["WXK27 - Austin (162.4 MHz) - temporarily unavailable"],
        )

        dlg._station_choice.Set.assert_called_with(
            ["WXK27 - Austin (162.4 MHz) - temporarily unavailable"]
        )


class TestPlayStopSwitch:
    """Tests for the 3-way play/stop/switch logic in _on_play_stop."""

    def test_not_playing_triggers_play(self, noaa_dialog_module):
        """When nothing is playing, _on_play_stop should start playback."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._player.is_playing.return_value = False
        dlg._url_provider.get_stream_urls.return_value = ["https://example.com/s"]
        dlg._prefs.reorder_urls.return_value = ["https://example.com/s"]
        dlg._on_play_stop(MagicMock())
        dlg._player.play.assert_called()

    def test_same_station_playing_triggers_stop(self, noaa_dialog_module):
        """When the selected station is already playing, _on_play_stop should stop."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._player.is_playing.return_value = True
        # Playing station matches selection (index 0 = KEC49)
        dlg._playing_station = dlg._stations[0]
        dlg._station_choice.GetSelection.return_value = 0
        dlg._on_play_stop(MagicMock())
        dlg._player.stop.assert_called()
        dlg._player.play.assert_not_called()

    def test_different_station_playing_triggers_switch(self, noaa_dialog_module):
        """When a different station is selected while one plays, switch immediately."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._player.is_playing.return_value = True
        # Playing KEC49 (index 0) but user selected WXJ76 (index 1)
        dlg._playing_station = dlg._stations[0]
        dlg._station_choice.GetSelection.return_value = 1
        dlg._url_provider.get_stream_urls.return_value = ["https://example.com/s2"]
        dlg._prefs.reorder_urls.return_value = ["https://example.com/s2"]
        dlg._on_play_stop(MagicMock())
        # Should have stopped old and started new in one action
        dlg._player.stop.assert_called()
        dlg._player.play.assert_called_with("https://example.com/s2")

    def test_playing_station_set_on_play(self, noaa_dialog_module):
        """_playing_station is set when _on_play is called."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._player.is_playing.return_value = False
        dlg._url_provider.get_stream_urls.return_value = ["https://example.com/s"]
        dlg._prefs.reorder_urls.return_value = ["https://example.com/s"]
        dlg._on_play(MagicMock())
        assert dlg._playing_station is dlg._stations[0]

    def test_playing_station_cleared_on_stopped(self, noaa_dialog_module):
        """_playing_station is cleared when _on_stopped fires."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._playing_station = dlg._stations[0]
        dlg._on_stopped()
        assert dlg._playing_station is None

    def test_playing_station_cleared_on_error(self, noaa_dialog_module):
        """_playing_station is cleared when _on_error fires."""
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._playing_station = dlg._stations[0]
        dlg._on_error("Connection failed")
        assert dlg._playing_station is None


class TestUpdatePlayBtnLabel:
    """Tests for _update_play_btn_label."""

    def test_label_play_when_not_playing(self, noaa_dialog_module):
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._player.is_playing.return_value = False
        dlg._update_play_btn_label()
        dlg._play_stop_btn.SetLabel.assert_called_with("Play")

    def test_label_stop_when_same_station_playing(self, noaa_dialog_module):
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._player.is_playing.return_value = True
        dlg._playing_station = dlg._stations[0]
        dlg._station_choice.GetSelection.return_value = 0
        dlg._update_play_btn_label()
        dlg._play_stop_btn.SetLabel.assert_called_with("Stop")

    def test_label_switch_when_different_station_selected(self, noaa_dialog_module):
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._player.is_playing.return_value = True
        dlg._playing_station = dlg._stations[0]  # KEC49 playing
        dlg._station_choice.GetSelection.return_value = 1  # WXJ76 selected
        dlg._update_play_btn_label()
        dlg._play_stop_btn.SetLabel.assert_called_with("Switch")


class TestChoiceKeyHandler:
    """Tests for Enter key on the station choice widget."""

    def test_enter_triggers_play_stop(self, noaa_dialog_module):
        """Pressing Enter on the choice calls _on_play_stop."""
        import wx

        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._player.is_playing.return_value = False
        dlg._url_provider.get_stream_urls.return_value = ["https://example.com/s"]
        dlg._prefs.reorder_urls.return_value = ["https://example.com/s"]

        key_event = MagicMock()
        key_event.GetKeyCode.return_value = wx.WXK_RETURN
        dlg._on_choice_key(key_event)
        dlg._player.play.assert_called()
        key_event.Skip.assert_not_called()

    def test_other_keys_are_skipped(self, noaa_dialog_module):
        """Non-Enter keys are passed through via Skip."""
        import wx

        dlg = _make_dialog_instance(noaa_dialog_module)
        key_event = MagicMock()
        key_event.GetKeyCode.return_value = wx.WXK_TAB
        dlg._on_choice_key(key_event)
        key_event.Skip.assert_called_once()


class TestSuppressionFeedback:
    """Tests for playback-driven suppression updates."""

    def test_try_play_current_suppresses_station_after_all_streams_fail(self, noaa_dialog_module):
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._current_urls = ["https://example.com/1", "https://example.com/2"]
        dlg._player.play.return_value = False
        dlg._playing_station = dlg._stations[0]

        dlg._try_play_current("KEC49")

        dlg._availability_cache.suppress.assert_called_once_with(
            "KEC49",
            ttl_seconds=1800,
            reason="all_streams_failed",
        )

    def test_try_play_current_does_not_suppress_when_fallback_succeeds(self, noaa_dialog_module):
        dlg = _make_dialog_instance(noaa_dialog_module)
        dlg._current_urls = ["https://example.com/1", "https://example.com/2"]
        dlg._player.play.side_effect = [False, True]
        dlg._playing_station = dlg._stations[0]

        dlg._try_play_current("KEC49")

        dlg._availability_cache.suppress.assert_not_called()
        dlg._availability_cache.clear.assert_called_with("KEC49")
