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
        "ICON_INFORMATION",
        "SL_HORIZONTAL",
        "ID_CLOSE",
        "TE_PROCESS_ENTER",
    ]:
        setattr(wx_mock, attr, 0)
    wx_mock.NOT_FOUND = -1
    wx_mock.EVT_CHECKBOX = MagicMock()
    wx_mock.EVT_TEXT_ENTER = MagicMock()
    wx_mock.Window = _FakeWxWindow
    wx_mock.Dialog = _FakeWxDialog

    choice_inst = MagicMock()
    choice_inst.GetSelection.return_value = 0
    wx_mock.Choice.return_value = choice_inst

    slider_inst = MagicMock()
    slider_inst.GetValue.return_value = 100
    wx_mock.Slider.return_value = slider_inst

    checkbox_inst = MagicMock()
    checkbox_inst.GetValue.return_value = False
    wx_mock.CheckBox.return_value = checkbox_inst

    text_ctrl_inst = MagicMock()
    text_ctrl_inst.GetValue.return_value = ""
    wx_mock.TextCtrl.return_value = text_ctrl_inst

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
    dlg._player.get_volume.return_value = 1.0
    dlg._player.is_playing.return_value = False
    dlg._session = MagicMock()
    dlg._session.player = dlg._player
    dlg._session.current_urls = dlg._current_urls = [
        "http://example.com/stream1",
        "http://example.com/stream2",
    ]
    dlg._session.current_url_index = 0
    dlg._session.playing_station = None
    dlg._session.is_playing.return_value = False
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
    dlg._search_ctrl = MagicMock()
    dlg._search_ctrl.GetValue.return_value = ""
    dlg._finder_mode_choice = MagicMock()
    dlg._finder_mode_choice.GetSelection.return_value = module.FINDER_MODE_LABELS.index(
        module.FINDER_MODE_NEAREST
    )
    dlg._state_choice = MagicMock()
    dlg._state_choice.GetSelection.return_value = 0
    dlg._state_choices = (
        "All states and territories",
        "New York (NY)",
        "Pennsylvania (PA)",
        "Texas (TX)",
    )
    dlg._auto_advance_stream = True
    dlg._playing_station = None
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
        dlg._session.stop.assert_called_once()

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
        """Test closing dialog during active playback keeps player running."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg.Destroy = MagicMock()

        # Simulate playing state
        dlg._on_playing()

        # Close
        dlg._on_close(MagicMock())
        dlg._player.stop.assert_not_called()
        dlg._session.unbind_callbacks.assert_called_once()
        dlg.Destroy.assert_called_once()

    def test_close_when_stopped(self, noaa_dialog_module):
        """Test closing dialog when stopped just dismisses the UI."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg.Destroy = MagicMock()
        dlg._on_close(MagicMock())
        dlg._player.stop.assert_not_called()
        dlg._session.unbind_callbacks.assert_called_once()
        dlg.Destroy.assert_called_once()


class TestLoadStations:
    """Test station loading on dialog init."""

    def test_load_stations_uses_availability_service_entries(self, noaa_dialog_module):
        """Test _load_stations_worker uses filtered availability entries."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg._station_choice = MagicMock()
        entry = MagicMock()
        entry.station = Station("TEST1", 162.55, "Test City 1", 40.0, -74.0, "NY")
        entry.label = "TEST1 - Test City 1 (162.55 MHz)"
        dlg._station_availability.build_entries.return_value = [entry]

        test_stations = [
            Station("TEST1", 162.55, "Test City 1", 40.0, -74.0, "NY"),
            Station("TEST2", 162.40, "Test City 2", 41.0, -75.0, "PA"),
        ]
        results = [
            StationResult(station=s, distance_km=10.0 * i) for i, s in enumerate(test_stations)
        ]

        with patch("accessiweather.ui.dialogs.noaa_radio_dialog.StationDatabase") as mock_db_cls:
            mock_db_cls.return_value.find_nearest.return_value = results
            dlg._load_stations_worker()

        mock_db_cls.return_value.find_nearest.assert_called_once_with(40.7, -74.0, limit=10)
        dlg._station_availability.build_entries.assert_called_once_with(
            test_stations,
            show_unavailable=False,
        )

    def test_load_stations_uses_selected_station_limit(self, noaa_dialog_module):
        dlg = _make_dialog(noaa_dialog_module)
        dlg._station_choice = MagicMock()
        entry = MagicMock()
        entry.station = Station("TEST1", 162.55, "Test City 1", 40.0, -74.0, "NY")
        entry.label = "TEST1 - Test City 1 (162.55 MHz)"
        dlg._station_availability.build_entries.return_value = [entry]
        results = [StationResult(station=entry.station, distance_km=0.0)]

        with patch("accessiweather.ui.dialogs.noaa_radio_dialog.StationDatabase") as mock_db_cls:
            mock_db_cls.return_value.find_nearest.return_value = results
            dlg._load_stations_worker(station_limit=100)

        mock_db_cls.return_value.find_nearest.assert_called_once_with(40.7, -74.0, limit=100)

    def test_load_stations_all_uses_unbounded_lookup(self, noaa_dialog_module):
        dlg = _make_dialog(noaa_dialog_module)
        dlg._station_choice = MagicMock()
        entry = MagicMock()
        entry.station = Station("TEST1", 162.55, "Test City 1", 40.0, -74.0, "NY")
        entry.label = "TEST1 - Test City 1 (162.55 MHz)"
        dlg._station_availability.build_entries.return_value = [entry]
        results = [StationResult(station=entry.station, distance_km=0.0)]

        with patch("accessiweather.ui.dialogs.noaa_radio_dialog.StationDatabase") as mock_db_cls:
            mock_db_cls.return_value.find_nearest.return_value = results
            dlg._load_stations_worker(station_limit=None)

        mock_db_cls.return_value.find_nearest.assert_called_once_with(40.7, -74.0, limit=None)

    def test_load_stations_error_sets_status(self, noaa_dialog_module):
        """Test _load_stations_worker handles database errors gracefully."""
        dlg = _make_dialog(noaa_dialog_module)
        dlg._station_choice = MagicMock()
        dlg._status_text = MagicMock()

        with patch("accessiweather.ui.dialogs.noaa_radio_dialog.StationDatabase") as mock_db_cls:
            mock_db_cls.return_value.find_nearest.side_effect = RuntimeError("DB error")
            dlg._load_stations_worker()

        # Worker calls wx.CallAfter for error, verify database was called
        mock_db_cls.return_value.find_nearest.assert_called_once()

    def test_load_stations_can_include_suppressed_entries_when_requested(self, noaa_dialog_module):
        dlg = _make_dialog(noaa_dialog_module)
        dlg._show_unavailable_checkbox.GetValue.return_value = True
        entry = MagicMock()
        entry.station = Station("TEST1", 162.55, "Test City 1", 40.0, -74.0, "NY")
        entry.label = "TEST1 - Test City 1 (162.55 MHz) - temporarily unavailable"
        dlg._station_availability.build_entries.return_value = [entry]
        results = [StationResult(station=entry.station, distance_km=0.0)]

        with patch("accessiweather.ui.dialogs.noaa_radio_dialog.StationDatabase") as mock_db_cls:
            mock_db_cls.return_value.find_nearest.return_value = results
            dlg._load_stations_worker(show_unavailable=True)

        dlg._station_availability.build_entries.assert_called_once_with(
            [entry.station],
            show_unavailable=True,
        )

    def test_load_stations_without_coordinates_browses_station_database(self, noaa_dialog_module):
        dlg = _make_dialog(noaa_dialog_module)
        dlg._lat = None
        dlg._lon = None
        dlg._finder_mode_choice.GetSelection.return_value = (
            noaa_dialog_module.FINDER_MODE_LABELS.index(noaa_dialog_module.FINDER_MODE_SEARCH_ALL)
        )
        entry = MagicMock()
        entry.station = Station("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")
        entry.label = "WXK27 - Austin, TX (162.4 MHz)"
        dlg._station_availability.build_entries.return_value = [entry]

        with patch("accessiweather.ui.dialogs.noaa_radio_dialog.StationDatabase") as mock_db_cls:
            mock_db_cls.return_value.search.return_value = [entry.station]
            dlg._load_stations_worker(station_limit=25)

        mock_db_cls.return_value.search.assert_called_once_with("", limit=25)
        mock_db_cls.return_value.find_nearest.assert_not_called()
        dlg._station_availability.build_entries.assert_called_once_with(
            [entry.station],
            show_unavailable=False,
        )

    def test_load_stations_uses_search_query(self, noaa_dialog_module):
        dlg = _make_dialog(noaa_dialog_module)
        entry = MagicMock()
        entry.station = Station("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")
        entry.label = "WXK27 - Austin, TX (162.4 MHz)"
        dlg._station_availability.build_entries.return_value = [entry]

        with patch("accessiweather.ui.dialogs.noaa_radio_dialog.StationDatabase") as mock_db_cls:
            mock_db_cls.return_value.search.return_value = [entry.station]
            dlg._load_stations_worker(station_limit=10, search_query="Austin")

        mock_db_cls.return_value.search.assert_called_once_with("Austin", limit=10)
        mock_db_cls.return_value.find_nearest.assert_not_called()

    def test_load_stations_browse_by_state_uses_state_database_filter(self, noaa_dialog_module):
        dlg = _make_dialog(noaa_dialog_module)
        tx_station = Station("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")
        entry = MagicMock()
        entry.station = tx_station
        entry.label = "WXK27 - Austin, TX - 162.400 MHz - Available"
        dlg._station_availability.build_entries.return_value = [entry]

        with patch("accessiweather.ui.dialogs.noaa_radio_dialog.StationDatabase") as mock_db_cls:
            mock_db_cls.return_value.get_stations_by_state.return_value = [tx_station]
            dlg._load_stations_worker(
                station_limit=25,
                finder_mode=noaa_dialog_module.FINDER_MODE_BROWSE_STATE,
                state_code="TX",
            )

        mock_db_cls.return_value.get_stations_by_state.assert_called_once_with("TX")
        mock_db_cls.return_value.search.assert_not_called()
        mock_db_cls.return_value.find_nearest.assert_not_called()
        dlg._station_availability.build_entries.assert_called_once_with(
            [tx_station],
            show_unavailable=False,
        )

    def test_load_stations_coordinate_mode_uses_nearest_lookup(self, noaa_dialog_module):
        dlg = _make_dialog(noaa_dialog_module)
        station = Station("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")
        entry = MagicMock()
        entry.station = station
        entry.label = "WXK27 - Austin, TX - 162.400 MHz - Available"
        dlg._station_availability.build_entries.return_value = [entry]
        results = [StationResult(station=station, distance_km=0.0)]

        with patch("accessiweather.ui.dialogs.noaa_radio_dialog.StationDatabase") as mock_db_cls:
            mock_db_cls.return_value.find_nearest.return_value = results
            dlg._load_stations_worker(
                station_limit=10,
                search_query="30.2672, -97.7431",
                finder_mode=noaa_dialog_module.FINDER_MODE_NEAREST,
            )

        mock_db_cls.return_value.find_nearest.assert_called_once_with(
            30.2672,
            -97.7431,
            limit=10,
        )
        mock_db_cls.return_value.search.assert_not_called()

    def test_load_stations_coordinate_mode_rejects_non_coordinate_text(
        self,
        noaa_dialog_module,
    ):
        dlg = _make_dialog(noaa_dialog_module)
        dlg._lat = None
        dlg._lon = None
        dlg._station_availability.build_entries.return_value = []

        with patch("accessiweather.ui.dialogs.noaa_radio_dialog.StationDatabase") as mock_db_cls:
            dlg._load_stations_worker(
                station_limit=10,
                search_query="Austin",
                finder_mode=noaa_dialog_module.FINDER_MODE_NEAREST,
            )

        mock_db_cls.return_value.find_nearest.assert_not_called()
        mock_db_cls.return_value.search.assert_not_called()
        dlg._station_availability.build_entries.assert_called_once_with(
            [],
            show_unavailable=False,
        )


class TestSuppressionIntegration:
    """Test suppression feedback in the dialog flow."""

    def test_playback_success_clears_station_suppression(self, noaa_dialog_module):
        dlg = _make_dialog(noaa_dialog_module)
        dlg._url_provider.get_stream_urls.return_value = ["https://example.com/stream"]
        dlg._prefs.reorder_urls.return_value = ["https://example.com/stream"]

        dlg._on_play(MagicMock())

        dlg._availability_cache.clear.assert_called_with("KEC49")

    def test_all_stream_failure_suppresses_station(self, noaa_dialog_module):
        dlg = _make_dialog(noaa_dialog_module)
        dlg._current_urls = ["https://example.com/1", "https://example.com/2"]
        dlg._player.play.return_value = False
        dlg._playing_station = dlg._stations[0]

        dlg._try_play_current("KEC49")

        dlg._availability_cache.suppress.assert_called_once_with(
            "KEC49",
            ttl_seconds=1800,
            reason="all_streams_failed",
        )


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
