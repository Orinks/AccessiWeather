"""NOAA Weather Radio player dialog for AccessiWeather."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import wx

from accessiweather.noaa_radio import (
    Station,
    StationAvailabilityCache,
    StationAvailabilityService,
    StationDatabase,
    StreamURLProvider,
)
from accessiweather.noaa_radio.player import RadioPlayer
from accessiweather.noaa_radio.preferences import DEFAULT_STATION_LIMIT, RadioPreferences

from .noaa_radio_clients import get_clients as _get_clients

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
SUPPRESSION_TTL_SECONDS = 1800
STATION_LIMIT_PRESETS: tuple[int | None, ...] = (10, 25, 50, 100, None)
STATION_LIMIT_LABELS: tuple[str, ...] = ("10", "25", "50", "100", "All")


def show_noaa_radio_dialog(parent: wx.Window, lat: float, lon: float) -> NOAARadioDialog:
    """
    Show the NOAA Weather Radio player dialog.

    Creates and shows a non-modal dialog for streaming NOAA Weather Radio.

    Args:
        parent: Parent window.
        lat: Latitude for finding nearest stations.
        lon: Longitude for finding nearest stations.

    Returns:
        The dialog instance (non-modal, caller may keep a reference).

    """
    dlg = NOAARadioDialog(parent, lat, lon)
    dlg.Show()
    return dlg


class NOAARadioDialog(wx.Dialog):
    """Non-modal dialog for streaming NOAA Weather Radio stations."""

    def __init__(self, parent: wx.Window, lat: float, lon: float) -> None:
        """
        Initialize the NOAA Radio dialog.

        Args:
            parent: Parent window.
            lat: Latitude for station lookup.
            lon: Longitude for station lookup.

        """
        super().__init__(
            parent,
            title="NOAA Weather Radio",
            size=(450, 350),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._lat = lat
        self._lon = lon
        self._stations: list[Station] = []
        self._player = RadioPlayer(
            on_playing=self._on_playing,
            on_stopped=self._on_stopped,
            on_error=self._on_error,
            on_stalled=self._on_stalled,
            on_reconnecting=self._on_reconnecting,
        )
        # Use cached clients to leverage HTTP response caching across dialog opens
        wxradio, weatherindex = _get_clients()
        self._url_provider = StreamURLProvider(
            use_fallback=False,
            wxradio_client=wxradio,
            weatherindex_client=weatherindex,
        )
        app = wx.GetApp()
        prefs_path = (
            getattr(getattr(app, "runtime_paths", None), "noaa_radio_preferences_file", None)
            if app is not None
            else None
        )
        availability_path = (
            getattr(getattr(app, "runtime_paths", None), "noaa_radio_availability_file", None)
            if app is not None
            else None
        )
        self._prefs = RadioPreferences(path=prefs_path)
        self._availability_cache = StationAvailabilityCache(path=availability_path)
        self._station_availability = StationAvailabilityService(
            weatherindex_client=weatherindex,
            availability_cache=self._availability_cache,
        )
        self._current_urls: list[str] = []
        self._current_url_index: int = 0
        self._playing_station: Station | None = None
        self._health_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_health_check, self._health_timer)

        self._init_ui()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        # Start station loading in background thread to not block UI initialization
        self._load_stations_async()

    def _init_ui(self) -> None:
        """Create and layout all UI controls."""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Station selector
        station_label = wx.StaticText(panel, label="Station:")
        sizer.Add(station_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._station_choice = wx.Choice(panel, choices=[])
        self._station_choice.Bind(wx.EVT_CHOICE, self._on_station_changed)
        self._station_choice.Bind(wx.EVT_CHAR_HOOK, self._on_choice_key)
        sizer.Add(self._station_choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        station_limit_label = wx.StaticText(panel, label="Nearby station count:")
        sizer.Add(station_limit_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._station_limit_choice = wx.Choice(panel, choices=list(STATION_LIMIT_LABELS))
        self._station_limit_choice.SetSelection(
            self._get_station_limit_choice_index(self._prefs.get_station_limit())
        )
        self._station_limit_choice.Bind(wx.EVT_CHOICE, self._on_station_limit_changed)
        sizer.Add(self._station_limit_choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._show_unavailable_checkbox = wx.CheckBox(
            panel,
            label="Show unavailable stations",
        )
        self._show_unavailable_checkbox.Bind(
            wx.EVT_CHECKBOX,
            self._on_show_unavailable_changed,
        )
        sizer.Add(
            self._show_unavailable_checkbox,
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            10,
        )

        # Button row
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._play_stop_btn = wx.Button(panel, label="Play")
        self._play_stop_btn.Bind(wx.EVT_BUTTON, self._on_play_stop)
        btn_sizer.Add(self._play_stop_btn, 0, wx.RIGHT, 5)

        self._next_stream_btn = wx.Button(panel, label="Try Next Stream")
        self._next_stream_btn.Bind(wx.EVT_BUTTON, self._on_next_stream)
        self._next_stream_btn.Enable(False)
        btn_sizer.Add(self._next_stream_btn, 0, wx.RIGHT, 5)

        self._prefer_btn = wx.Button(panel, label="Set as Preferred")
        self._prefer_btn.Bind(wx.EVT_BUTTON, self._on_set_preferred)
        self._prefer_btn.Enable(False)
        btn_sizer.Add(self._prefer_btn, 0, wx.RIGHT, 5)

        sizer.Add(btn_sizer, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Volume slider
        volume_label = wx.StaticText(panel, label="Volume:")
        sizer.Add(volume_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._volume_slider = wx.Slider(
            panel,
            value=100,
            minValue=0,
            maxValue=100,
            style=wx.SL_HORIZONTAL,
        )
        self._volume_slider.Bind(wx.EVT_SLIDER, self._on_volume_change)
        sizer.Add(self._volume_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Status text
        self._status_text = wx.StaticText(panel, label="Ready")
        sizer.Add(self._status_text, 0, wx.ALL, 10)

        # Close button
        close_btn = wx.Button(panel, wx.ID_CLOSE, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        sizer.Add(close_btn, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(sizer)

        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _load_stations_async(self) -> None:
        """Load stations in a background thread to not block UI initialization."""
        # Show loading state immediately
        self._station_choice.Set(["Loading stations..."])
        self._set_status("Finding nearest stations...")
        show_unavailable = self._show_unavailable_enabled()
        station_limit = self._get_selected_station_limit()

        # Run station loading in background thread
        thread = threading.Thread(
            target=self._load_stations_worker,
            args=(show_unavailable, station_limit),
            daemon=True,
        )
        thread.start()

    def _load_stations_worker(
        self,
        show_unavailable: bool = False,
        station_limit: int | None = DEFAULT_STATION_LIMIT,
    ) -> None:
        """Worker method that loads stations in background thread."""
        try:
            db = StationDatabase()
            results = db.find_nearest(self._lat, self._lon, limit=station_limit)
            nearby = [r.station for r in results]
            entries = self._station_availability.build_entries(
                nearby,
                show_unavailable=show_unavailable,
            )
            stations = [entry.station for entry in entries]
            choices = [entry.label for entry in entries]

            # Update UI on main thread
            wx.CallAfter(self._on_stations_loaded, stations, choices)

            # Pre-warm the stream cache in background for faster play button response
            # This runs after UI is shown so user sees stations immediately
            wx.CallAfter(self._prewarm_stream_cache, stations)
        except Exception as e:
            logger.error(f"Failed to load stations: {e}")
            wx.CallAfter(self._set_status, f"Error loading stations: {e}")

    def _prewarm_stream_cache(self, stations: list[Station]) -> None:
        """Pre-warm stream URL cache in background for faster play response."""
        thread = threading.Thread(
            target=self._prewarm_stream_cache_worker,
            args=(stations,),
            daemon=True,
        )
        thread.start()

    def _prewarm_stream_cache_worker(self, stations: list[Station]) -> None:
        """Worker that pre-warms stream cache."""
        try:
            self._url_provider.prewarm_cache()
            logger.debug("Pre-warmed stream cache")
        except Exception as e:
            logger.debug(f"Failed to pre-warm stream cache: {e}")

    def _on_stations_loaded(self, stations: list[Station], choices: list[str]) -> None:
        """Handle stations loaded in background thread."""
        # Check if dialog was closed while background thread was running
        if self._station_choice is None:
            return
        previous_station = self._get_selected_station()
        previous_call_sign = previous_station.call_sign if previous_station is not None else None
        self._stations = stations
        self._station_choice.Set(choices)
        if choices:
            selection = 0
            if previous_call_sign is not None:
                for index, station in enumerate(stations):
                    if station.call_sign == previous_call_sign:
                        selection = index
                        break
            self._station_choice.SetSelection(selection)
            self._set_status("Ready")
        else:
            self._set_status("No stations with streams available")

    def _get_selected_station(self) -> Station | None:
        """Return the currently selected station, or None."""
        idx = self._station_choice.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._stations):
            return None
        return self._stations[idx]

    def _on_play_stop(self, event: wx.CommandEvent) -> None:
        """
        Handle Play/Stop/Switch action from button or Enter key on station choice.

        Behaviour:
        - Not playing → start the selected station.
        - Same station already playing → stop it.
        - Different station selected while one is playing → switch immediately.
        """
        if not self._player.is_playing():
            self._on_play(event)
        else:
            selected = self._get_selected_station()
            if (
                selected is not None
                and self._playing_station is not None
                and selected.call_sign == self._playing_station.call_sign
            ):
                self._on_stop(event)
            else:
                # Different station (or unknown) — switch without a second press
                self._on_play(event)

    def _on_play(self, _event: wx.CommandEvent) -> None:
        """Handle Play action."""
        # Stop any currently playing stream
        if self._player.is_playing():
            self._health_timer.Stop()
            self._player.stop()

        station = self._get_selected_station()
        if station is None:
            self._set_status("No station selected")
            return

        urls = self._url_provider.get_stream_urls(station.call_sign)
        if not urls:
            self._set_status(f"No stream available for {station.call_sign}")
            wx.MessageBox(
                f"No online stream is available for station {station.call_sign} ({station.name}).\n\n"
                "Not all NOAA Weather Radio stations have online streams.",
                "Stream Not Available",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        self._playing_station = station
        self._current_urls = self._prefs.reorder_urls(station.call_sign, urls)
        self._current_url_index = 0
        self._try_play_current(station.call_sign)

    def _try_play_current(self, call_sign: str) -> None:
        """Try playing the current URL index, auto-advancing on failure."""
        total = len(self._current_urls)
        idx = self._current_url_index
        self._set_status(f"Connecting to {call_sign} (stream {idx + 1} of {total})...")
        url = self._current_urls[idx]
        if self._player.play(url):
            self._clear_station_suppression()
            self._health_timer.Start(5000)
            self._next_stream_btn.Enable(total > 1)
            self._prefer_btn.Enable(True)
        elif total > 1:
            # Auto-advance to next stream on connection failure
            self._current_url_index = (idx + 1) % total
            if self._current_url_index == 0:
                # Wrapped around, all streams failed
                self._mark_current_station_unavailable()
                self._set_status(f"All streams failed for {call_sign}")
                return
            self._try_play_current(call_sign)
        else:
            self._mark_current_station_unavailable()
            self._set_status(f"Stream failed for {call_sign}")

    def _on_stop(self, _event: wx.CommandEvent) -> None:
        """Handle Stop action."""
        self._health_timer.Stop()
        self._player.stop()
        self._play_stop_btn.SetLabel("Play")

    def _on_volume_change(self, _event: wx.CommandEvent) -> None:
        """Handle volume slider change."""
        level = self._volume_slider.GetValue() / 100.0
        self._player.set_volume(level)

    def _on_playing(self) -> None:
        """Handle playback started event."""
        station = self._playing_station or self._get_selected_station()
        self._clear_station_suppression(station)
        name = station.call_sign if station else "Unknown"
        total = len(self._current_urls)
        idx = self._current_url_index + 1
        stream_info = f" (stream {idx} of {total})" if total > 1 else ""
        self._set_status(f"Playing: {name}{stream_info}")
        self._play_stop_btn.Enable(True)
        self._play_stop_btn.SetLabel("Stop")
        self._next_stream_btn.Enable(total > 1)

    def _on_stopped(self) -> None:
        """Handle playback stopped event."""
        self._playing_station = None
        self._set_status("Stopped")
        self._play_stop_btn.Enable(True)
        self._play_stop_btn.SetLabel("Play")
        self._next_stream_btn.Enable(False)
        self._prefer_btn.Enable(False)

    def _on_error(self, message: str) -> None:
        """Handle playback error event."""
        self._playing_station = None
        self._health_timer.Stop()
        self._set_status(f"Error: {message}")
        self._play_stop_btn.Enable(True)
        self._play_stop_btn.SetLabel("Play")
        self._next_stream_btn.Enable(len(self._current_urls) > 1)
        self._prefer_btn.Enable(False)

    def _on_stalled(self) -> None:
        """Handle stream stall (buffering)."""
        self._set_status("Stream stalled, reconnecting...")

    def _on_reconnecting(self, attempt: int) -> None:
        """Handle reconnection attempt."""
        self._set_status(f"Reconnecting (attempt {attempt})...")

    def _on_set_preferred(self, _event: wx.CommandEvent) -> None:
        """Save the current stream as preferred for this station."""
        station = self._get_selected_station()
        if station is None or not self._current_urls:
            return
        url = self._current_urls[self._current_url_index]
        self._prefs.set_preferred_url(station.call_sign, url)
        idx = self._current_url_index + 1
        total = len(self._current_urls)
        self._set_status(f"Preferred stream {idx} of {total} saved for {station.call_sign}")

    def _on_next_stream(self, _event: wx.CommandEvent) -> None:
        """Switch to the next available stream URL for the current station."""
        if not self._current_urls:
            return
        self._health_timer.Stop()
        self._player.stop(notify=False)  # Don't reset button states mid-switch

        self._current_url_index = (self._current_url_index + 1) % len(self._current_urls)
        url = self._current_urls[self._current_url_index]
        station = self._get_selected_station()
        name = station.call_sign if station else "Unknown"
        idx = self._current_url_index + 1
        total = len(self._current_urls)
        self._set_status(f"Switching {name} to stream {idx} of {total}...")
        if self._player.play(url):
            self._health_timer.Start(5000)

    def _on_health_check(self, _event: wx.TimerEvent) -> None:
        """Periodic health check for stream stalls and silence."""
        self._player.check_health(on_auto_advance=self._auto_advance_stream)

    def _auto_advance_stream(self) -> None:
        """Automatically advance to the next stream when current is silent."""
        if not self._current_urls or len(self._current_urls) <= 1:
            self._set_status("Stream has no audio")
            return
        self._current_url_index = (self._current_url_index + 1) % len(self._current_urls)
        url = self._current_urls[self._current_url_index]
        station = self._get_selected_station()
        name = station.call_sign if station else "Unknown"
        idx = self._current_url_index + 1
        total = len(self._current_urls)
        self._set_status(f"No audio detected, trying {name} stream {idx} of {total}...")
        self._player.stop(notify=False)
        if not self._player.play(url):
            self._set_status("All streams failed")
            self._health_timer.Stop()

    def _set_status(self, text: str) -> None:
        """Update the status text."""
        self._status_text.SetLabel(text)

    def _on_show_unavailable_changed(self, _event: wx.CommandEvent) -> None:
        """Reload stations when the unavailable-station filter changes."""
        self._load_stations_async()

    def _on_station_limit_changed(self, event: wx.CommandEvent) -> None:
        """Persist and apply a new nearby-station limit."""
        self._prefs.set_station_limit(self._get_selected_station_limit())
        self._load_stations_async()
        event.Skip()

    def _on_station_changed(self, event: wx.CommandEvent) -> None:
        """Update button label when the user picks a different station."""
        self._update_play_btn_label()
        event.Skip()

    def _on_choice_key(self, event: wx.KeyEvent) -> None:
        """Trigger play/switch when Enter is pressed while the station choice is focused."""
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_play_stop(event)
            return
        event.Skip()

    def _update_play_btn_label(self) -> None:
        """
        Set play/stop button label to reflect current playback state.

        - 'Play'   — nothing is playing.
        - 'Stop'   — the selected station is the one currently playing.
        - 'Switch' — a different station is selected while one is playing.
        """
        if not self._player.is_playing():
            self._play_stop_btn.SetLabel("Play")
            return
        selected = self._get_selected_station()
        if (
            selected is not None
            and self._playing_station is not None
            and selected.call_sign == self._playing_station.call_sign
        ):
            self._play_stop_btn.SetLabel("Stop")
        else:
            self._play_stop_btn.SetLabel("Switch")

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        """Handle keyboard shortcuts for the dialog."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self._on_close(event)
            return
        event.Skip()

    def _on_close(self, _event: wx.Event) -> None:
        """Handle dialog close."""
        self._health_timer.Stop()
        self._player.stop()
        self.Destroy()

    def _show_unavailable_enabled(self) -> bool:
        """Return the current state of the unavailable-station filter."""
        checkbox = getattr(self, "_show_unavailable_checkbox", None)
        return bool(checkbox.GetValue()) if checkbox is not None else False

    def _get_selected_station_limit(self) -> int | None:
        """Return the chosen nearby-station limit, or None for all stations."""
        choice = getattr(self, "_station_limit_choice", None)
        if choice is None:
            return self._prefs.get_station_limit()

        selection = choice.GetSelection()
        if selection == wx.NOT_FOUND or selection >= len(STATION_LIMIT_PRESETS):
            return self._prefs.get_station_limit()
        return STATION_LIMIT_PRESETS[selection]

    def _get_station_limit_choice_index(self, limit: int | None) -> int:
        """Return the choice index matching the saved nearby-station limit."""
        try:
            return STATION_LIMIT_PRESETS.index(limit)
        except ValueError:
            return STATION_LIMIT_PRESETS.index(DEFAULT_STATION_LIMIT)

    def _mark_current_station_unavailable(self, reason: str = "all_streams_failed") -> None:
        """Suppress the current station after all playback options fail."""
        station = self._playing_station or self._get_selected_station()
        if station is None:
            return
        self._availability_cache.suppress(
            station.call_sign,
            ttl_seconds=SUPPRESSION_TTL_SECONDS,
            reason=reason,
        )

    def _clear_station_suppression(self, station: Station | None = None) -> None:
        """Remove temporary suppression for a station after successful playback."""
        current_station = station or self._playing_station or self._get_selected_station()
        if current_station is None:
            return
        self._availability_cache.clear(current_station.call_sign)
