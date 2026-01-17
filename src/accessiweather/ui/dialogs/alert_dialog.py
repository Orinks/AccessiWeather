"""Alert dialog for displaying weather alert details."""

from __future__ import annotations

import wx


def show_alert_dialog(parent: wx.Window, alert) -> None:
    """
    Show details for a weather alert.

    Args:
        parent: Parent window
        alert: Weather alert object

    """
    event = getattr(alert, "event", "Unknown Alert")
    severity = getattr(alert, "severity", "Unknown")
    headline = getattr(alert, "headline", "No headline available")
    description = getattr(alert, "description", "No description available")
    instruction = getattr(alert, "instruction", "")

    message = f"Event: {event}\nSeverity: {severity}\n\n{headline}\n\n{description}"
    if instruction:
        message += f"\n\nInstructions:\n{instruction}"

    wx.MessageBox(
        message,
        f"Alert: {event}",
        wx.OK | wx.ICON_WARNING,
    )
