"""Location dialog for adding new locations."""

from __future__ import annotations

import wx


def show_add_location_dialog(parent: wx.Window, app) -> bool:
    """
    Show dialog to add a new location.

    Args:
        parent: Parent window
        app: Application instance

    Returns:
        True if location was added, False otherwise

    """
    dialog = wx.TextEntryDialog(
        parent,
        "Enter a location (city name or zip code):",
        "Add Location",
        "",
    )

    if dialog.ShowModal() == wx.ID_OK:
        location_query = dialog.GetValue().strip()
        dialog.Destroy()

        if not location_query:
            wx.MessageBox(
                "Please enter a location.",
                "Invalid Input",
                wx.OK | wx.ICON_WARNING,
            )
            return False

        # TODO: Implement geocoding and add location
        # For now, show a placeholder message
        wx.MessageBox(
            f"Would add location: {location_query}\n\n(Geocoding not yet implemented)",
            "Add Location",
            wx.OK | wx.ICON_INFORMATION,
        )
        return False

    dialog.Destroy()
    return False
