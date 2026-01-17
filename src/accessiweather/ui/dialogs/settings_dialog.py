"""Settings dialog for application configuration."""

from __future__ import annotations

import wx


def show_settings_dialog(parent: wx.Window, app) -> bool:
    """
    Show the settings dialog.

    Args:
        parent: Parent window
        app: Application instance

    Returns:
        True if settings were changed, False otherwise

    """
    # TODO: Implement full settings dialog with gui_builder
    wx.MessageBox(
        "Settings dialog not yet implemented for wxPython version.",
        "Settings",
        wx.OK | wx.ICON_INFORMATION,
    )
    return False
