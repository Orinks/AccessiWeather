"""Weather history dialog for viewing historical weather data."""

from __future__ import annotations

import wx


def show_weather_history_dialog(parent: wx.Window, app) -> None:
    """
    Show the weather history dialog.

    Args:
        parent: Parent window
        app: Application instance

    """
    # TODO: Implement weather history dialog with gui_builder
    wx.MessageBox(
        "Weather history dialog not yet implemented for wxPython version.",
        "Weather History",
        wx.OK | wx.ICON_INFORMATION,
    )
