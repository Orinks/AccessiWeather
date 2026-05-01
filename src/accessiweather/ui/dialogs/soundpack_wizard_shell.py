"""Static shell widgets for the sound pack creation wizard."""

from __future__ import annotations

from typing import Any

import wx


def create_wizard_shell(dialog: Any) -> None:
    """Create the static wizard shell around the per-step content area."""
    dialog.panel = wx.Panel(dialog)
    main_sizer = wx.BoxSizer(wx.VERTICAL)

    dialog.header_label = wx.StaticText(dialog.panel, label="")
    header_font = dialog.header_label.GetFont()
    header_font.SetPointSize(12)
    header_font.SetWeight(wx.FONTWEIGHT_BOLD)
    dialog.header_label.SetFont(header_font)
    main_sizer.Add(dialog.header_label, 0, wx.ALL, 10)

    dialog.content_panel = wx.Panel(dialog.panel)
    dialog.content_sizer = wx.BoxSizer(wx.VERTICAL)
    dialog.content_panel.SetSizer(dialog.content_sizer)
    main_sizer.Add(dialog.content_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

    nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
    nav_sizer.AddStretchSpacer()

    dialog.prev_btn = wx.Button(dialog.panel, label="< Previous")
    dialog.prev_btn.Bind(wx.EVT_BUTTON, dialog._go_previous)
    nav_sizer.Add(dialog.prev_btn, 0, wx.RIGHT, 5)

    dialog.next_btn = wx.Button(dialog.panel, label="Next >")
    dialog.next_btn.Bind(wx.EVT_BUTTON, dialog._go_next)
    nav_sizer.Add(dialog.next_btn, 0, wx.RIGHT, 5)

    dialog.cancel_btn = wx.Button(dialog.panel, wx.ID_CANCEL, label="Cancel")
    dialog.cancel_btn.Bind(wx.EVT_BUTTON, dialog._on_close)
    nav_sizer.Add(dialog.cancel_btn, 0)

    main_sizer.Add(nav_sizer, 0, wx.EXPAND | wx.ALL, 10)
    dialog.panel.SetSizer(main_sizer)
