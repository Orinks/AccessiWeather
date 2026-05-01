"""Widget construction helpers for the NOAA radio dialog."""

from __future__ import annotations

from typing import Any

import wx


def create_noaa_radio_widgets(dialog: Any, station_limit_labels: tuple[str, ...]) -> None:
    """Create and layout all NOAA radio dialog controls."""
    panel = wx.Panel(dialog)
    sizer = wx.BoxSizer(wx.VERTICAL)

    sizer.Add(wx.StaticText(panel, label="Station:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

    dialog._station_choice = wx.Choice(panel, choices=[])
    dialog._station_choice.Bind(wx.EVT_CHOICE, dialog._on_station_changed)
    dialog._station_choice.Bind(wx.EVT_CHAR_HOOK, dialog._on_choice_key)
    sizer.Add(dialog._station_choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

    sizer.Add(
        wx.StaticText(panel, label="Nearby station count:"),
        0,
        wx.LEFT | wx.RIGHT | wx.TOP,
        10,
    )

    dialog._station_limit_choice = wx.Choice(panel, choices=list(station_limit_labels))
    dialog._station_limit_choice.SetSelection(
        dialog._get_station_limit_choice_index(dialog._prefs.get_station_limit())
    )
    dialog._station_limit_choice.Bind(wx.EVT_CHOICE, dialog._on_station_limit_changed)
    sizer.Add(dialog._station_limit_choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

    dialog._show_unavailable_checkbox = wx.CheckBox(
        panel,
        label="Show unavailable stations",
    )
    dialog._show_unavailable_checkbox.Bind(
        wx.EVT_CHECKBOX,
        dialog._on_show_unavailable_changed,
    )
    sizer.Add(dialog._show_unavailable_checkbox, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

    _add_button_row(dialog, panel, sizer)

    sizer.Add(wx.StaticText(panel, label="Volume:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
    dialog._volume_slider = wx.Slider(
        panel,
        value=100,
        minValue=0,
        maxValue=100,
        style=wx.SL_HORIZONTAL,
    )
    dialog._volume_slider.Bind(wx.EVT_SLIDER, dialog._on_volume_change)
    sizer.Add(dialog._volume_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

    dialog._status_text = wx.StaticText(panel, label="Ready")
    sizer.Add(dialog._status_text, 0, wx.ALL, 10)

    close_btn = wx.Button(panel, wx.ID_CLOSE, label="Close")
    close_btn.Bind(wx.EVT_BUTTON, dialog._on_close)
    sizer.Add(close_btn, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)

    panel.SetSizer(sizer)
    dialog.Bind(wx.EVT_CLOSE, dialog._on_close)


def _add_button_row(dialog: Any, panel: wx.Panel, sizer: wx.BoxSizer) -> None:
    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

    dialog._play_stop_btn = wx.Button(panel, label="Play")
    dialog._play_stop_btn.Bind(wx.EVT_BUTTON, dialog._on_play_stop)
    btn_sizer.Add(dialog._play_stop_btn, 0, wx.RIGHT, 5)

    dialog._next_stream_btn = wx.Button(panel, label="Try Next Stream")
    dialog._next_stream_btn.Bind(wx.EVT_BUTTON, dialog._on_next_stream)
    dialog._next_stream_btn.Enable(False)
    btn_sizer.Add(dialog._next_stream_btn, 0, wx.RIGHT, 5)

    dialog._prefer_btn = wx.Button(panel, label="Set as Preferred")
    dialog._prefer_btn.Bind(wx.EVT_BUTTON, dialog._on_set_preferred)
    dialog._prefer_btn.Enable(False)
    btn_sizer.Add(dialog._prefer_btn, 0, wx.RIGHT, 5)

    sizer.Add(btn_sizer, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
