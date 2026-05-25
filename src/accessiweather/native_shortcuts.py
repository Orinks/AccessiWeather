"""Helpers for preserving native window shortcuts when installing accelerators."""

from __future__ import annotations

from collections.abc import Iterable

import wx


def install_accelerator_table_preserving_native_close(frame, entries: Iterable[tuple]) -> None:
    """
    Install an accelerator table without losing the platform close shortcut.

    wx replaces the entire accelerator table each time SetAcceleratorTable() is
    called. On Windows that can swallow Alt+F4 unless we explicitly include it.
    Route it through Close() so the normal EVT_CLOSE handler still decides
    whether to minimize to tray or exit.
    """
    accelerator_entries = list(entries)
    close_id = wx.NewIdRef()
    frame.Bind(wx.EVT_MENU, lambda _event: frame.Close(), id=close_id)

    accel_alt = getattr(wx, "ACCEL_ALT", None)
    wxk_f4 = getattr(wx, "WXK_F4", None)
    if accel_alt is not None and wxk_f4 is not None:
        accelerator_entries.append((accel_alt, wxk_f4, close_id))

    frame.SetAcceleratorTable(wx.AcceleratorTable(accelerator_entries))
