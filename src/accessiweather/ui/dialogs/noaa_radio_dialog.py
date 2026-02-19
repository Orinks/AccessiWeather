"""NOAA Weather Radio player dialog for AccessiWeather."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx

from accessiweather.noaa_radio import Station, StationDatabase, StreamURLProvider
from accessiweather.noaa_radio.player import RadioPlayer
from accessiweather.noaa_radio.preferences import RadioPreferences
from accessiweather.noaa_radio.wxradio_client import WxRadioClient
from accessiweather.paths import Paths

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


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
        self._url_provider = StreamURLProvider(use_fallback=False, wxradio_client=WxRadioClient())
        self._prefs = RadioPreferences(config_dir=Paths().data)
        self._current_urls: list[str] = []
        self._current_url_index: int = 0
        self._health_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_health_check, self._health_timer)

        self._init_ui()
        self._load_stations()

    def _init_ui(self) -> None:
        """Create and layout all UI controls."""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Station selector
        station_label = wx.StaticText(panel, label="Station:")
        station_label.SetName("Station Label")
        sizer.Add(station_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._station_choice = wx.Choice(panel, choices=[])
        self._station_choice.SetName("Station")
        sizer.Add(self._station_choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Button row
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._play_stop_btn = wx.Button(panel, label="Play")
        self._play_stop_btn.SetName("Play/Stop")
        self._play_stop_btn.Bind(wx.EVT_BUTTON, self._on_play_stop)
        btn_sizer.Add(self._play_stop_btn, 0, wx.RIGHT, 5)

        self._next_stream_btn = wx.Button(panel, label="Try Next Stream")
        self._next_stream_btn.SetName("Try Next Stream")
        self._next_stream_btn.Bind(wx.EVT_BUTTON, self._on_next_stream)
        self._next_stream_btn.Enable(False)
        btn_sizer.Add(self._next_stream_btn, 0, wx.RIGHT, 5)

        self._prefer_btn = wx.Button(panel, label="Set as Preferred")
        self._prefer_btn.SetName("Set as Preferred")
        self._prefer_btn.Bind(wx.EVT_BUTTON, self._on_set_preferred)
        self._prefer_btn.Enable(False)
        btn_sizer.Add(self._prefer_btn, 0, wx.RIGHT, 5)

        sizer.Add(btn_sizer, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Volume slider
        volume_label = wx.StaticText(panel, label="Volume:")
        volume_label.SetName("Volume Label")
        sizer.Add(volume_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._volume_slider = wx.Slider(
            panel,
            value=100,
            minValue=0,
            maxValue=100,
            style=wx.SL_HORIZONTAL,
        )
        self._volume_slider.SetName("Volume")
        self._volume_slider.Bind(wx.EVT_SLIDER, self._on_volume_change)
        sizer.Add(self._volume_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Status text
        self._status_text = wx.StaticText(panel, label="Ready")
        self._status_text.SetName("Status")
        sizer.Add(self._status_text, 0, wx.ALL, 10)

        # Close button
        close_btn = wx.Button(panel, wx.ID_CLOSE, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        sizer.Add(close_btn, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(sizer)

        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _load_stations(self) -> None:
        """Load nearest stations into the selector."""
        try:
            db = StationDatabase()
            results = db.find_nearest(self._lat, self._lon, limit=25)
            # Only show stations that have online streams available
            self._stations = [
                r.station for r in results if self._url_provider.has_known_url(r.station.call_sign)
            ][:10]

            choices = [f"{s.call_sign} - {s.name} ({s.frequency} MHz)" for s in self._stations]
            self._station_choice.Set(choices)
            if choices:
                self._station_choice.SetSelection(0)
        except Exception as e:
            logger.error(f"Failed to load stations: {e}")
            self._set_status(f"Error loading stations: {e}")

    def _get_selected_station(self) -> Station | None:
        """Return the currently selected station, or None."""
        idx = self._station_choice.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._stations):
            return None
        return self._stations[idx]

    def _on_play_stop(self, event: wx.CommandEvent) -> None:
        """Toggle playback from a single Play/Stop button."""
        if self._player.is_playing():
            self._on_stop(event)
        else:
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
            self._health_timer.Start(5000)
            self._next_stream_btn.Enable(total > 1)
            self._prefer_btn.Enable(True)
        elif total > 1:
            # Auto-advance to next stream on connection failure
            self._current_url_index = (idx + 1) % total
            if self._current_url_index == 0:
                # Wrapped around, all streams failed
                self._set_status(f"All streams failed for {call_sign}")
                return
            self._try_play_current(call_sign)
        else:
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
        station = self._get_selected_station()
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
        self._set_status("Stopped")
        self._play_stop_btn.Enable(True)
        self._play_stop_btn.SetLabel("Play")
        self._next_stream_btn.Enable(False)
        self._prefer_btn.Enable(False)

    def _on_error(self, message: str) -> None:
        """Handle playback error event."""
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

    def _on_close(self, _event: wx.Event) -> None:
        """Handle dialog close."""
        self._health_timer.Stop()
        self._player.stop()
        self.Destroy()
