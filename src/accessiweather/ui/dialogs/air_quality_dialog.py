"""Air quality dialog for AQI information."""

from __future__ import annotations

import wx


def show_air_quality_dialog(parent: wx.Window, app) -> None:
    """
    Show the air quality dialog.

    Args:
        parent: Parent window
        app: Application instance

    """
    # TODO: Implement air quality dialog with gui_builder
    wx.MessageBox(
        "Air quality dialog not yet implemented for wxPython version.",
        "Air Quality",
        wx.OK | wx.ICON_INFORMATION,
    )
