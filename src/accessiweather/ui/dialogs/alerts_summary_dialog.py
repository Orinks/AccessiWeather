"""Combined dialog for multiple newly eligible weather alerts."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(__name__)


def show_alerts_summary_dialog(parent, alerts) -> None:
    """Show a combined summary dialog for multiple alerts."""
    try:
        dlg = AlertsSummaryDialog(parent, alerts)
        dlg.ShowModal()
        dlg.Destroy()
    except Exception as exc:
        logger.error("Failed to show alerts summary dialog: %s", exc)
        wx.MessageBox(
            f"Failed to open the alerts summary: {exc}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )


class AlertsSummaryDialog(wx.Dialog):
    """Dialog listing multiple newly eligible alerts in one place."""

    def __init__(self, parent, alerts):
        """Initialize the dialog with the current batch of newly eligible alerts."""
        super().__init__(
            parent,
            title="New Weather Alerts",
            size=(720, 480),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.alerts = list(alerts)
        self._create_ui()
        self._setup_accessibility()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    def _create_ui(self) -> None:
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        intro = wx.StaticText(
            panel,
            label="Multiple new alerts arrived in this update. Review the summaries below.",
        )
        main_sizer.Add(intro, 0, wx.ALL, 15)

        self.summary_ctrl = wx.TextCtrl(
            panel,
            value=self._build_summary_text(),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
        )
        main_sizer.Add(self.summary_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        close_btn = wx.Button(panel, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        button_sizer.Add(close_btn, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)
        panel.SetSizer(main_sizer)
        self.summary_ctrl.SetFocus()

    def _build_summary_text(self) -> str:
        sections: list[str] = []
        for index, alert in enumerate(self.alerts, start=1):
            header = (
                getattr(alert, "headline", None) or getattr(alert, "event", None) or "Weather Alert"
            )
            details = [
                f"{index}. {header}",
                f"Severity: {getattr(alert, 'severity', 'Unknown')}",
            ]
            urgency = getattr(alert, "urgency", None)
            if urgency:
                details.append(f"Urgency: {urgency}")
            certainty = getattr(alert, "certainty", None)
            if certainty:
                details.append(f"Certainty: {certainty}")
            description = getattr(alert, "description", None)
            if description:
                details.append(f"Details: {description}")
            sections.append("\n".join(details))
        return "\n\n".join(sections)

    def _setup_accessibility(self) -> None:
        self.summary_ctrl.SetName("New alert summaries")

    def _on_key(self, event) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
            return
        event.Skip()

    def _on_close(self, _event) -> None:
        self.EndModal(wx.ID_CLOSE)
