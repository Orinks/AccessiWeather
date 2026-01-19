"""Progress Dialog for download/upload operations using gui_builder."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import wx
from gui_builder import fields, forms

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ProgressDialog(forms.Dialog):
    """Progress dialog for long-running operations using gui_builder."""

    # Status message
    status_label = fields.StaticText(label="Please wait...")

    # Detail label
    detail_label = fields.StaticText(label="Initializing...")

    # Cancel button
    cancel_button = fields.Button(label="&Cancel")

    def __init__(
        self,
        title: str = "Progress",
        message: str = "Please wait...",
        can_cancel: bool = True,
        **kwargs,
    ):
        """Initialize the progress dialog."""
        self._initial_message = message
        self._can_cancel = can_cancel
        self.is_cancelled = False
        self._lock = threading.Lock()
        self._gauge = None

        kwargs.setdefault("title", title)
        super().__init__(**kwargs)

    def render(self, **kwargs):
        """Render the dialog and set up components."""
        super().render(**kwargs)
        self._setup_initial_state()

    def _setup_initial_state(self) -> None:
        """Set up initial state."""
        self.status_label.set_label(self._initial_message)

        if not self._can_cancel:
            self.cancel_button.disable()

        # Add a gauge for progress indication (using wx directly)
        parent = self.widget.control
        self._gauge = wx.Gauge(parent, range=100, size=(-1, 25))

    @cancel_button.add_callback
    def on_cancel(self):
        """Handle cancel button click."""
        with self._lock:
            self.is_cancelled = True
        self.status_label.set_label("Cancelling...")
        self.cancel_button.disable()

    def update_progress(self, percent: float, status: str = "", detail: str = "") -> bool:
        """Update progress. Returns False if cancelled."""
        with self._lock:
            if self.is_cancelled:
                return False

        def _update():
            try:
                if self._gauge:
                    self._gauge.SetValue(int(min(100, max(0, percent))))
                if status:
                    self.status_label.set_label(status)
                if detail:
                    self.detail_label.set_label(detail)
            except RuntimeError:
                pass  # Dialog may have been destroyed

        wx.CallAfter(_update)
        return True

    def set_status(self, status: str, detail: str = "") -> None:
        """Set status and detail text."""

        def _update():
            try:
                self.status_label.set_label(status)
                if detail:
                    self.detail_label.set_label(detail)
            except RuntimeError:
                pass

        wx.CallAfter(_update)

    def complete_success(self, message: str = "Completed successfully") -> None:
        """Mark operation as complete with success."""

        def _update():
            try:
                if self._gauge:
                    self._gauge.SetValue(100)
                self.status_label.set_label(message)
                self.detail_label.set_label("")
                self.cancel_button.set_label("Close")
                self.cancel_button.enable()
            except RuntimeError:
                pass

        wx.CallAfter(_update)

    def complete_error(self, message: str) -> None:
        """Mark operation as complete with error."""

        def _update():
            try:
                self.status_label.set_label("Error")
                self.detail_label.set_label(message)
                self.cancel_button.set_label("Close")
                self.cancel_button.enable()
            except RuntimeError:
                pass

        wx.CallAfter(_update)
