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
        """Create the dialog UI with accessible text controls."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Subject field (headline + times) - gets initial focus
        subject_text = self._build_subject_text()
        subject_label = wx.StaticText(panel, label="Subject:")
        subject_label.SetFont(subject_label.GetFont().Bold())
        main_sizer.Add(subject_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)

        self.subject_ctrl = wx.TextCtrl(
            panel,
            value=subject_text,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 60),
        )
        main_sizer.Add(self.subject_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Alert info field (severity, urgency, certainty, areas)
        info_text = self._build_info_text()
        if info_text:
            info_label = wx.StaticText(panel, label="Alert Info:")
            info_label.SetFont(info_label.GetFont().Bold())
            main_sizer.Add(info_label, 0, wx.LEFT | wx.RIGHT, 15)

            self.info_ctrl = wx.TextCtrl(
                panel,
                value=info_text,
                style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
                size=(-1, 60),
            )
            main_sizer.Add(self.info_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Details field (description)
        description = getattr(self.alert, "description", None)
        if description:
            details_label = wx.StaticText(panel, label="Details:")
            details_label.SetFont(details_label.GetFont().Bold())
            main_sizer.Add(details_label, 0, wx.LEFT | wx.RIGHT, 15)

            self.details_ctrl = wx.TextCtrl(
                panel,
                value=description,
                style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            )
            main_sizer.Add(self.details_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Instructions field
        instruction = getattr(self.alert, "instruction", None)
        if instruction:
            instr_label = wx.StaticText(panel, label="Instructions:")
            instr_label.SetFont(instr_label.GetFont().Bold())
            main_sizer.Add(instr_label, 0, wx.LEFT | wx.RIGHT, 15)

            self.instr_ctrl = wx.TextCtrl(
                panel,
                value=instruction,
                style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
                size=(-1, 80),
            )
            main_sizer.Add(self.instr_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Close button
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        close_btn = wx.Button(panel, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        button_sizer.Add(close_btn, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)

        panel.SetSizer(main_sizer)

        # Set initial focus to subject field
        self.subject_ctrl.SetFocus()

    def _build_subject_text(self) -> str:
        """
        Build the subject text with headline.

        Note: Time information (effective/expires) is intentionally omitted
        as the headline already contains human-readable timing information.
        The API's 'expires' field refers to message validity, not when the
        weather event ends, which would be confusing to display.
        """
        # Headline or event name
        headline = getattr(self.alert, "headline", None)
        event = getattr(self.alert, "event", None)

        if headline:
            return headline
        if event:
            return event
        return "Weather Alert"

    def _build_info_text(self) -> str:
        """
        Build the alert info text with severity, urgency, and certainty.

        Note: Areas are intentionally omitted as the Details section
        already contains location information.
        """
        metadata = []
        severity = getattr(self.alert, "severity", None)
        urgency = getattr(self.alert, "urgency", None)
        certainty = getattr(self.alert, "certainty", None)

        if severity:
            metadata.append(f"Severity: {severity}")
        if urgency:
            metadata.append(f"Urgency: {urgency}")
        if certainty:
            metadata.append(f"Certainty: {certainty}")

        return ", ".join(metadata)

    def _setup_accessibility(self):
        """Set up accessibility labels for screen readers."""
        self.subject_ctrl.SetName("Subject with alert headline")

        if hasattr(self, "info_ctrl"):
            self.info_ctrl.SetName("Alert information with severity, urgency, and certainty")

        if hasattr(self, "details_ctrl"):
            self.details_ctrl.SetName("Alert details")

        if hasattr(self, "instr_ctrl"):
            self.instr_ctrl.SetName("Instructions")

    def _on_close(self, event):
        """Handle close button press."""
        self.EndModal(wx.ID_CLOSE)
