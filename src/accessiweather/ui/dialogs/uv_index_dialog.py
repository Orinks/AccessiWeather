"""UV index dialog for UV information."""

from __future__ import annotations

import wx


def show_uv_index_dialog(parent: wx.Window, app) -> None:
    """
    Show the UV index dialog.

    Args:
        parent: Parent window
        app: Application instance

    """
    # TODO: Implement UV index dialog with gui_builder
    wx.MessageBox(
        "UV index dialog not yet implemented for wxPython version.",
        "UV Index",
        wx.OK | wx.ICON_INFORMATION,
    )
