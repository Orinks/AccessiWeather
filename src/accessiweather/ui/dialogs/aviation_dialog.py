"""Aviation weather dialog for METAR/TAF data."""

from __future__ import annotations

import wx


def show_aviation_dialog(parent: wx.Window, app) -> None:
    """
    Show the aviation weather dialog.

    Args:
        parent: Parent window
        app: Application instance

    """
    # TODO: Implement aviation dialog with gui_builder
    wx.MessageBox(
        "Aviation weather dialog not yet implemented for wxPython version.",
        "Aviation Weather",
        wx.OK | wx.ICON_INFORMATION,
    )
