"""wxPython Progress Dialog for download/upload operations."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ProgressDialog(wx.Dialog):
    """Progress dialog for long-running operations."""

    def __init__(
        self,
        parent: wx.Window,
        title: str = "Progress",
        message: str = "Please wait...",
        can_cancel: bool = True,
    ) -> None:
        """Initialize the progress dialog."""
        super().__init__(
            parent,
            title=title,
            size=(450, 180),
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        self.is_cancelled = False
        self._lock = threading.Lock()

        self._create_ui(message, can_cancel)
        self.Centre()

    def _create_ui(self, message: str, can_cancel: bool) -> None:
        """Create the dialog UI."""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Status message
        self.status_label = wx.StaticText(panel, label=message)
        status_font = self.status_label.GetFont()
        status_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.status_label.SetFont(status_font)
        sizer.Add(self.status_label, 0, wx.ALL | wx.EXPAND, 10)

        # Progress gauge
        self.gauge = wx.Gauge(panel, range=100, size=(-1, 25))
        sizer.Add(self.gauge, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        # Detail label
        self.detail_label = wx.StaticText(panel, label="Initializing...")
        sizer.Add(self.detail_label, 0, wx.ALL | wx.EXPAND, 10)

        # Cancel button
        if can_cancel:
            btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
            btn_sizer.AddStretchSpacer()
            self.cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="Cancel")
            self.cancel_btn.Bind(wx.EVT_BUTTON, self._on_cancel)
            btn_sizer.Add(self.cancel_btn, 0)
            btn_sizer.AddStretchSpacer()
            sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)
        else:
            self.cancel_btn = None

        panel.SetSizer(sizer)

    def _on_cancel(self, event) -> None:
        """Handle cancel button click."""
        with self._lock:
            self.is_cancelled = True
        self.status_label.SetLabel("Cancelling...")
        if self.cancel_btn:
            self.cancel_btn.Enable(False)

    def update_progress(self, percent: float, status: str = "", detail: str = "") -> bool:
        """Update progress. Returns False if cancelled."""
        with self._lock:
            if self.is_cancelled:
                return False

        def _update():
            try:
                self.gauge.SetValue(int(min(100, max(0, percent))))
                if status:
                    self.status_label.SetLabel(status)
                if detail:
                    self.detail_label.SetLabel(detail)
            except RuntimeError:
                pass  # Dialog may have been destroyed

        wx.CallAfter(_update)
        return True

    def set_status(self, status: str, detail: str = "") -> None:
        """Set status and detail text."""

        def _update():
            try:
                self.status_label.SetLabel(status)
                if detail:
                    self.detail_label.SetLabel(detail)
            except RuntimeError:
                pass

        wx.CallAfter(_update)

    def complete_success(self, message: str = "Completed successfully") -> None:
        """Mark operation as complete with success."""

        def _update():
            try:
                self.gauge.SetValue(100)
                self.status_label.SetLabel(message)
                self.detail_label.SetLabel("")
                if self.cancel_btn:
                    self.cancel_btn.SetLabel("Close")
                    self.cancel_btn.Enable(True)
            except RuntimeError:
                pass

        wx.CallAfter(_update)

    def complete_error(self, message: str) -> None:
        """Mark operation as complete with error."""

        def _update():
            try:
                self.status_label.SetLabel("Error")
                self.detail_label.SetLabel(message)
                if self.cancel_btn:
                    self.cancel_btn.SetLabel("Close")
                    self.cancel_btn.Enable(True)
            except RuntimeError:
                pass

        wx.CallAfter(_update)
