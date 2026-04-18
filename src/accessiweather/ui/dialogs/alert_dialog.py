"""Alert dialog for displaying weather alert details using wxPython."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx

from ...display.presentation.formatters import format_datetime

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def show_alert_dialog(parent, alert, settings=None) -> None:
    """
    Show the alert details dialog.

    Args:
        parent: Parent window
        alert: Weather alert object
        settings: Optional application settings (for combined-mode dispatch)

    """
    try:
        parent_ctrl = parent

        dlg = AlertDialog(parent_ctrl, alert, settings)
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

    def __init__(self, parent, alert, settings=None):
        """
        Initialize the alert dialog.

        Args:
            parent: Parent window
            alert: Weather alert object
            settings: Optional application settings (for combined-mode dispatch)

        """
        event = getattr(alert, "event", "Weather Alert")
        super().__init__(
            parent,
            title=f"Alert: {event}",
            size=(700, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.alert = alert
        self.settings = settings

        self._create_ui()
        self._setup_accessibility()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    def _create_ui(self):
        """Create the dialog UI, dispatching to separate or combined mode."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        style = (
            getattr(self.settings, "alert_display_style", "separate")
            if self.settings is not None
            else "separate"
        )
        if style == "combined":
            self._create_combined_ui(panel, main_sizer)
        else:
            self._create_separate_ui(panel, main_sizer)

        panel.SetSizer(main_sizer)
        self._focus_target.SetFocus()

    def _create_combined_ui(self, panel, main_sizer):
        """Create a single TextCtrl containing the full alert, with a Close button."""
        label = wx.StaticText(panel, label="Alert:")
        label.SetFont(label.GetFont().Bold())
        main_sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)

        text = self._build_combined_text(self.alert, self.settings)
        self.combined_ctrl = wx.TextCtrl(
            panel,
            value=text,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
        )
        main_sizer.Add(self.combined_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self._add_action_buttons(panel, main_sizer)

        self._focus_target = self.combined_ctrl

    def _create_separate_ui(self, panel, main_sizer):
        """Build the classic separate-field UI into the provided panel/sizer."""
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

        self._add_action_buttons(panel, main_sizer)

        # Set initial focus to subject field
        self._focus_target = self.subject_ctrl

    def _add_action_buttons(self, panel, main_sizer):
        """
        Add the right-aligned Close button to the provided sizer.

        Shared by both display modes. The button row is constructed once here
        so that future additions (e.g. a Copy button) only need one change site.
        """
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        close_btn = wx.Button(panel, wx.ID_CLOSE, "&Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        button_sizer.Add(close_btn, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)

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

    @staticmethod
    def _build_combined_text(alert, settings) -> str:
        """Assemble the combined-view text block. Pure function; settings is AppSettings-like."""
        date_style = getattr(settings, "date_format", "iso")
        time_12h = getattr(settings, "time_format_12hour", True)

        blocks: list[str] = []

        headline = (
            getattr(alert, "headline", None) or getattr(alert, "event", None) or "Weather Alert"
        )
        blocks.append(headline)

        description = getattr(alert, "description", None)
        if description:
            blocks.append(description)

        instruction = getattr(alert, "instruction", None)
        if instruction:
            blocks.append(instruction)

        times: list[str] = []
        sent = getattr(alert, "sent", None)
        if sent is not None:
            times.append(f"Issued: {format_datetime(sent, date_style, time_12h)}")
        expires = getattr(alert, "expires", None)
        if expires is not None:
            times.append(f"Expires: {format_datetime(expires, date_style, time_12h)}")
        if times:
            blocks.append("\n".join(times))

        return "\n\n".join(blocks)

    @staticmethod
    def _copy_payload(alert, settings) -> str:
        """
        Text placed on the clipboard when the Copy button is pressed.

        Identical in both display styles (separate and combined).
        """
        return AlertDialog._build_combined_text(alert, settings)

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
        if hasattr(self, "subject_ctrl"):
            self.subject_ctrl.SetName("Subject with alert headline")

        if hasattr(self, "info_ctrl"):
            self.info_ctrl.SetName("Alert information with severity, urgency, and certainty")

        if hasattr(self, "details_ctrl"):
            self.details_ctrl.SetName("Alert details")

        if hasattr(self, "instr_ctrl"):
            self.instr_ctrl.SetName("Instructions")

        if hasattr(self, "combined_ctrl"):
            self.combined_ctrl.SetName("Full alert text")

    def _on_key(self, event):
        """Handle key press - close dialog on Escape."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def _on_close(self, event):
        """Handle close button press."""
        self.EndModal(wx.ID_CLOSE)
