"""Widget construction helpers for the Weather Assistant dialog."""

from __future__ import annotations

from typing import Any

import wx


def create_weather_assistant_widgets(dialog: Any) -> None:
    """Create all Weather Assistant UI widgets."""
    panel = wx.Panel(dialog)
    main_sizer = wx.BoxSizer(wx.VERTICAL)

    main_sizer.Add(wx.StaticText(panel, label="&Conversation:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

    dialog.history_display = wx.TextCtrl(
        panel,
        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP | wx.TE_RICH2,
        name="Conversation history",
    )
    main_sizer.Add(dialog.history_display, 1, wx.ALL | wx.EXPAND, 10)

    dialog.status_label = wx.StaticText(panel, label="")
    main_sizer.Add(dialog.status_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

    _add_input_row(dialog, panel, main_sizer)
    _add_bottom_buttons(dialog, panel, main_sizer)

    panel.SetSizer(main_sizer)


def _add_input_row(dialog: Any, panel: wx.Panel, main_sizer: wx.BoxSizer) -> None:
    input_sizer = wx.BoxSizer(wx.HORIZONTAL)

    input_sizer.Add(
        wx.StaticText(panel, label="&Message:"),
        0,
        wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
        5,
    )

    dialog.input_ctrl = wx.TextCtrl(
        panel,
        style=wx.TE_PROCESS_ENTER,
        name="Type your message",
    )
    input_sizer.Add(dialog.input_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

    dialog.send_button = wx.Button(panel, label="&Send")
    input_sizer.Add(dialog.send_button, 0, wx.ALIGN_CENTER_VERTICAL)

    main_sizer.Add(input_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)


def _add_bottom_buttons(dialog: Any, panel: wx.Panel, main_sizer: wx.BoxSizer) -> None:
    button_sizer = wx.BoxSizer(wx.HORIZONTAL)

    dialog.clear_button = wx.Button(panel, label="C&lear Chat")
    button_sizer.Add(dialog.clear_button, 0, wx.RIGHT, 5)

    dialog.copy_button = wx.Button(panel, label="Cop&y Chat")
    button_sizer.Add(dialog.copy_button, 0, wx.RIGHT, 5)

    button_sizer.AddStretchSpacer()

    close_button = wx.Button(panel, wx.ID_CLOSE, label="&Close")
    button_sizer.Add(close_button, 0)

    main_sizer.Add(button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
