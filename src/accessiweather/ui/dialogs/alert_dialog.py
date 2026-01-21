"""Alert dialog for displaying weather alert details using wxPython."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def show_alert_dialog(parent, alert) -> None:
    """
    Show the alert details dialog.

    Args:
        parent: Parent window
        alert: Weather alert object

    """
    try:
        parent_ctrl = parent

        dlg = AlertDialog(parent_ctrl, alert)
        dlg.ShowModal()
        dlg.Destroy()

    except Exception as e:
        logger.error(f"Failed to show alert dialog: {e}")
        wx.MessageBox(
            f"Failed to open alert details: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )


class AlertDialog(wx.Dialog):
    """Dialog for displaying weather alert details."""

    def __init__(self, parent, alert):
        """
        Initialize the alert dialog.

        Args:
            parent: Parent window
            alert: Weather alert object

        """
        event = getattr(alert, "event", "Weather Alert")
        super().__init__(
            parent,
            title=f"Alert: {event}",
            size=(700, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.alert = alert

        self._create_ui()
        self._setup_accessibility()

    def _create_ui(self):
        """Create the dialog UI."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Alert header
        event = getattr(self.alert, "event", "Unknown Alert")
        header = wx.StaticText(panel, label=event)
        header.SetFont(header.GetFont().Bold().Scaled(1.3))
        main_sizer.Add(header, 0, wx.ALL, 15)

        # Severity and urgency row
        info_sizer = wx.BoxSizer(wx.HORIZONTAL)

        severity = getattr(self.alert, "severity", "Unknown")
        severity_label = wx.StaticText(panel, label=f"Severity: {severity}")
        severity_label.SetFont(severity_label.GetFont().Bold())
        self._set_severity_color(severity_label, severity)
        info_sizer.Add(severity_label, 0, wx.RIGHT, 20)

        urgency = getattr(self.alert, "urgency", None)
        if urgency:
            urgency_label = wx.StaticText(panel, label=f"Urgency: {urgency}")
            info_sizer.Add(urgency_label, 0, wx.RIGHT, 20)

        certainty = getattr(self.alert, "certainty", None)
        if certainty:
            certainty_label = wx.StaticText(panel, label=f"Certainty: {certainty}")
            info_sizer.Add(certainty_label, 0)

        main_sizer.Add(info_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Time information
        time_sizer = wx.BoxSizer(wx.VERTICAL)

        effective = getattr(self.alert, "effective", None)
        if effective:
            effective_str = self._format_time(effective)
            effective_label = wx.StaticText(panel, label=f"Effective: {effective_str}")
            time_sizer.Add(effective_label, 0, wx.BOTTOM, 4)

        expires = getattr(self.alert, "expires", None)
        if expires:
            expires_str = self._format_time(expires)
            expires_label = wx.StaticText(panel, label=f"Expires: {expires_str}")
            time_sizer.Add(expires_label, 0, wx.BOTTOM, 4)

        onset = getattr(self.alert, "onset", None)
        if onset:
            onset_str = self._format_time(onset)
            onset_label = wx.StaticText(panel, label=f"Onset: {onset_str}")
            time_sizer.Add(onset_label, 0)

        if time_sizer.GetItemCount() > 0:
            main_sizer.Add(time_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Areas affected
        areas = getattr(self.alert, "areas", None) or getattr(self.alert, "area_desc", None)
        if areas:
            areas_label = wx.StaticText(panel, label="Areas Affected:")
            areas_label.SetFont(areas_label.GetFont().Bold())
            main_sizer.Add(areas_label, 0, wx.LEFT | wx.RIGHT, 15)

            areas_text = ", ".join(areas) if isinstance(areas, list) else str(areas)

            areas_value = wx.StaticText(panel, label=areas_text)
            areas_value.Wrap(650)
            main_sizer.Add(areas_value, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Headline
        headline = getattr(self.alert, "headline", None)
        if headline:
            headline_label = wx.StaticText(panel, label="Headline:")
            headline_label.SetFont(headline_label.GetFont().Bold())
            main_sizer.Add(headline_label, 0, wx.LEFT | wx.RIGHT, 15)

            headline_value = wx.StaticText(panel, label=headline)
            headline_value.Wrap(650)
            main_sizer.Add(headline_value, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Description/Details
        description = getattr(self.alert, "description", None)
        if description:
            desc_label = wx.StaticText(panel, label="Details:")
            desc_label.SetFont(desc_label.GetFont().Bold())
            main_sizer.Add(desc_label, 0, wx.LEFT | wx.RIGHT, 15)

            self.desc_text = wx.TextCtrl(
                panel,
                value=description,
                style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            )
            main_sizer.Add(self.desc_text, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Instructions
        instruction = getattr(self.alert, "instruction", None)
        if instruction:
            instr_label = wx.StaticText(panel, label="Instructions:")
            instr_label.SetFont(instr_label.GetFont().Bold())
            main_sizer.Add(instr_label, 0, wx.LEFT | wx.RIGHT, 15)

            instr_text = wx.TextCtrl(
                panel,
                value=instruction,
                style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
                size=(-1, 80),
            )
            main_sizer.Add(instr_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Close button
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        close_btn = wx.Button(panel, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        button_sizer.Add(close_btn, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)

        panel.SetSizer(main_sizer)

        # Set initial focus
        if hasattr(self, "desc_text"):
            self.desc_text.SetFocus()

    def _set_severity_color(self, label, severity: str):
        """Set the color based on severity level."""
        severity_lower = severity.lower() if severity else ""
        if severity_lower == "extreme":
            label.SetForegroundColour(wx.Colour(139, 0, 0))  # Dark red
        elif severity_lower == "severe":
            label.SetForegroundColour(wx.Colour(255, 69, 0))  # Red-orange
        elif severity_lower == "moderate":
            label.SetForegroundColour(wx.Colour(255, 140, 0))  # Orange
        elif severity_lower == "minor":
            label.SetForegroundColour(wx.Colour(218, 165, 32))  # Goldenrod
        else:
            label.SetForegroundColour(wx.Colour(128, 128, 128))  # Gray

    def _format_time(self, time_value) -> str:
        """Format a time value for display."""
        if time_value is None:
            return "Unknown"

        if isinstance(time_value, str):
            return time_value

        try:
            return time_value.strftime("%B %d, %Y at %I:%M %p")
        except Exception:
            return str(time_value)

    def _setup_accessibility(self):
        """Set up accessibility labels."""
        if hasattr(self, "desc_text"):
            self.desc_text.SetName("Alert description")

    def _on_close(self, event):
        """Handle close button press."""
        self.EndModal(wx.ID_CLOSE)
