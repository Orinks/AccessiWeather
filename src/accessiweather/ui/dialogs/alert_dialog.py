"""Alert dialog for displaying weather alert details using gui_builder."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx
from gui_builder import fields, forms

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AlertDialog(forms.Dialog):
    """Dialog for displaying weather alert details using gui_builder."""

    # Header section
    event_label = fields.StaticText(label="")

    # Severity and urgency info
    severity_label = fields.StaticText(label="")
    urgency_label = fields.StaticText(label="")
    certainty_label = fields.StaticText(label="")

    # Time information
    effective_label = fields.StaticText(label="")
    expires_label = fields.StaticText(label="")
    onset_label = fields.StaticText(label="")

    # Areas affected
    areas_header = fields.StaticText(label="Areas Affected:")
    areas_label = fields.StaticText(label="")

    # Headline
    headline_header = fields.StaticText(label="Headline:")
    headline_label = fields.StaticText(label="")

    # Description/Details
    details_header = fields.StaticText(label="Details:")
    description_text = fields.Text(
        label="Alert description",
        multiline=True,
        readonly=True,
    )

    # Instructions
    instructions_header = fields.StaticText(label="Instructions:")
    instructions_text = fields.Text(
        label="Alert instructions",
        multiline=True,
        readonly=True,
    )

    # Close button
    close_button = fields.Button(label="&Close")

    def __init__(self, alert, **kwargs):
        """
        Initialize the alert dialog.

        Args:
            alert: Weather alert object
            **kwargs: Additional keyword arguments passed to Dialog

        """
        self.alert = alert
        event = getattr(alert, "event", "Weather Alert")
        kwargs.setdefault("title", f"Alert: {event}")
        super().__init__(**kwargs)

    def render(self, **kwargs):
        """Render the dialog and populate with alert data."""
        super().render(**kwargs)
        self._populate_alert_data()
        self._setup_accessibility()

    def _populate_alert_data(self) -> None:
        """Populate the dialog with alert information."""
        alert = self.alert

        # Event name
        event = getattr(alert, "event", "Unknown Alert")
        self.event_label.set_label(event)

        # Severity, urgency, certainty
        severity = getattr(alert, "severity", "Unknown")
        self.severity_label.set_label(f"Severity: {severity}")

        urgency = getattr(alert, "urgency", None)
        if urgency:
            self.urgency_label.set_label(f"Urgency: {urgency}")

        certainty = getattr(alert, "certainty", None)
        if certainty:
            self.certainty_label.set_label(f"Certainty: {certainty}")

        # Time information
        effective = getattr(alert, "effective", None)
        if effective:
            self.effective_label.set_label(f"Effective: {self._format_time(effective)}")

        expires = getattr(alert, "expires", None)
        if expires:
            self.expires_label.set_label(f"Expires: {self._format_time(expires)}")

        onset = getattr(alert, "onset", None)
        if onset:
            self.onset_label.set_label(f"Onset: {self._format_time(onset)}")

        # Areas affected
        areas = getattr(alert, "areas", None) or getattr(alert, "area_desc", None)
        if areas:
            areas_text = ", ".join(areas) if isinstance(areas, list) else str(areas)
            self.areas_label.set_label(areas_text)
        else:
            self.areas_header.set_label("")

        # Headline
        headline = getattr(alert, "headline", None)
        if headline:
            self.headline_label.set_label(headline)
        else:
            self.headline_header.set_label("")

        # Description
        description = getattr(alert, "description", None)
        if description:
            self.description_text.set_value(description)
        else:
            self.details_header.set_label("")
            self.description_text.set_value("")

        # Instructions
        instruction = getattr(alert, "instruction", None)
        if instruction:
            self.instructions_text.set_value(instruction)
        else:
            self.instructions_header.set_label("")
            self.instructions_text.set_value("")

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

    def _setup_accessibility(self) -> None:
        """Set up accessibility labels for screen readers."""
        self.description_text.set_accessible_label("Alert description")
        self.instructions_text.set_accessible_label("Alert instructions")

    @close_button.add_callback
    def on_close(self):
        """Handle close button press."""
        self.widget.control.EndModal(wx.ID_CLOSE)


def show_alert_dialog(parent, alert) -> None:
    """
    Show the alert details dialog.

    Args:
        parent: Parent window (gui_builder widget)
        alert: Weather alert object

    """
    try:
        # Get the underlying wx control if parent is a gui_builder widget
        parent_ctrl = getattr(parent, "control", parent)

        dlg = AlertDialog(alert, parent=parent_ctrl)
        dlg.render()
        dlg.widget.control.ShowModal()
        dlg.widget.control.Destroy()

    except Exception as e:
        logger.error(f"Failed to show alert dialog: {e}")
        wx.MessageBox(
            f"Failed to open alert details: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
