"""Aviation weather dialog for fetching and displaying TAF data using gui_builder."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import wx
from gui_builder import fields, forms

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)

_ICAO_RE = re.compile(r"^[A-Z]{4}$")


class AviationDialog(forms.Dialog):
    """Dialog for fetching and displaying aviation weather using gui_builder."""

    # Header
    header_label = fields.StaticText(
        label="Fetch decoded aviation weather by entering a four-letter ICAO airport code."
    )

    # Input section
    code_label = fields.StaticText(label="Airport code:")
    station_input = fields.Text(label="ICAO airport code (e.g., KJFK)")
    fetch_button = fields.Button(label="&Get Aviation Data")

    # Status
    status_label = fields.StaticText(label="Enter a code and press Enter to fetch the latest TAF.")

    # Raw TAF section
    raw_taf_header = fields.StaticText(label="Raw TAF")
    raw_taf_display = fields.Text(
        label="Raw TAF display",
        multiline=True,
        readonly=True,
    )

    # Decoded TAF section
    decoded_taf_header = fields.StaticText(label="Decoded TAF")
    decoded_taf_display = fields.Text(
        label="Decoded TAF display",
        multiline=True,
        readonly=True,
    )

    # Advisories section
    advisories_header = fields.StaticText(label="Advisories")
    advisories_list = fields.ListBox(label="Aviation advisories list")
    advisories_info = fields.StaticText(label="No advisories available.")

    # Close button
    close_button = fields.Button(label="&Close")

    def __init__(self, app: AccessiWeatherApp, **kwargs):
        """
        Initialize the aviation dialog.

        Args:
            app: Application instance
            **kwargs: Additional keyword arguments passed to Dialog

        """
        self.app = app
        self._is_fetching = False
        self._advisories_data: list[tuple[str, str, str, str]] = []

        kwargs.setdefault("title", "Aviation Weather")
        super().__init__(**kwargs)

    def render(self, **kwargs):
        """Render the dialog and set up components."""
        super().render(**kwargs)
        self._setup_initial_state()
        self._setup_accessibility()

    def _setup_initial_state(self) -> None:
        """Set up initial state."""
        self.raw_taf_display.set_value("No TAF loaded.")
        self.decoded_taf_display.set_value("Decoded TAF will appear here.")

    def _setup_accessibility(self) -> None:
        """Set up accessibility labels for screen readers."""
        self.station_input.set_accessible_label("ICAO airport code input")
        self.raw_taf_display.set_accessible_label("Raw TAF display")
        self.decoded_taf_display.set_accessible_label("Decoded TAF display")
        self.advisories_list.set_accessible_label("Aviation advisories list")

    def _set_status(self, message: str, is_error: bool = False) -> None:
        """Update the status label."""
        self.status_label.set_label(message)

    @fetch_button.add_callback
    def on_fetch(self):
        """Handle fetch button press."""
        code = self.station_input.get_value().strip().upper()

        if not code:
            self._set_status("Please enter a four-letter ICAO airport code.", is_error=True)
            return

        if not _ICAO_RE.match(code):
            self._set_status(
                "Airport codes must be exactly four letters (e.g., KJFK).", is_error=True
            )
            return

        if not getattr(self.app, "weather_client", None):
            self._set_status(
                "Weather client is not ready. Try again after initialization.", is_error=True
            )
            return

        if self._is_fetching:
            return

        self._is_fetching = True
        self.fetch_button.disable()
        self._set_status(f"Fetching aviation weather for {code}...")

        # Run async fetch
        self.app.run_async(self._do_fetch(code))

    async def _do_fetch(self, code: str):
        """Perform the aviation data fetch."""
        try:
            aviation = await self.app.weather_client.get_aviation_weather(
                code, include_sigmets=True, include_cwas=True
            )
            wx.CallAfter(self._on_fetch_complete, code, aviation)

        except Exception as e:
            logger.error(f"Aviation fetch failed: {e}")
            wx.CallAfter(self._on_fetch_error, code, str(e))

    def _on_fetch_complete(self, code: str, aviation) -> None:
        """Handle fetch completion."""
        self._is_fetching = False
        self.fetch_button.enable()

        if aviation is None or not aviation.has_taf():
            self._set_status(
                f"No TAF available for {code}. The station may not publish TAF data.",
                is_error=True,
            )
            self.raw_taf_display.set_value("No TAF available.")
            self.decoded_taf_display.set_value("No decoded TAF available.")
            self.advisories_list.set_items([])
            self.advisories_info.set_label("No advisories available.")
            return

        airport_label = aviation.airport_name or aviation.station_id or code
        self._set_status(f"Latest TAF loaded for {airport_label}.")

        self.raw_taf_display.set_value(aviation.raw_taf or "No TAF available.")
        self.decoded_taf_display.set_value(aviation.decoded_taf or "Unable to decode TAF.")

        self._update_advisories(aviation)

    def _on_fetch_error(self, code: str, error: str) -> None:
        """Handle fetch error."""
        self._is_fetching = False
        self.fetch_button.enable()
        self._set_status(f"Failed to retrieve aviation weather: {error}", is_error=True)

    def _update_advisories(self, aviation) -> None:
        """Update the advisories list."""
        self._advisories_data = []
        items = []

        if aviation.active_sigmets:
            for sigmet in aviation.active_sigmets[:10]:
                row = self._build_advisory_row("SIGMET", sigmet)
                self._advisories_data.append(row)
                items.append(f"{row[0]}: {row[1]} - {row[3][:50]}...")

        if aviation.active_cwas:
            for cwa in aviation.active_cwas[:10]:
                row = self._build_advisory_row("CWA", cwa)
                self._advisories_data.append(row)
                items.append(f"{row[0]}: {row[1]} - {row[3][:50]}...")

        self.advisories_list.set_items(items)

        if items:
            self.advisories_info.set_label(f"{len(items)} advisories loaded.")
        else:
            self.advisories_info.set_label("No advisories available.")

    def _build_advisory_row(self, advisory_type: str, entry: dict) -> tuple:
        """Build a row tuple for the advisories list."""
        event_name = entry.get("event") or entry.get("name") or entry.get("hazard") or advisory_type
        summary = (
            entry.get("description") or entry.get("summary") or entry.get("text") or ""
        ).strip()[:200] or "No description provided."

        valid_window = self._format_advisory_window(entry)

        return (advisory_type, event_name, valid_window, summary)

    def _format_advisory_window(self, entry: dict) -> str:
        """Format the advisory validity window."""
        start = (
            entry.get("startTime")
            or entry.get("beginTime")
            or entry.get("validTimeStart")
            or entry.get("issueTime")
        )
        end = (
            entry.get("endTime")
            or entry.get("expires")
            or entry.get("validTimeEnd")
            or entry.get("validUntil")
        )

        if start and end:
            return f"{start} → {end}"
        if end:
            return f"Until {end}"
        if start:
            return str(start)
        return "--"

    @close_button.add_callback
    def on_close(self):
        """Handle close button press."""
        self.widget.control.EndModal(wx.ID_CLOSE)


def show_aviation_dialog(parent, app: AccessiWeatherApp) -> None:
    """
    Show the aviation weather dialog.

    Args:
        parent: Parent window (gui_builder widget)
        app: Application instance

    """
    try:
        # Get the underlying wx control if parent is a gui_builder widget
        parent_ctrl = getattr(parent, "control", parent)

        dlg = AviationDialog(app, parent=parent_ctrl)
        dlg.render()
        dlg.widget.control.ShowModal()
        dlg.widget.control.Destroy()

    except Exception as e:
        logger.error(f"Failed to show aviation dialog: {e}")
        wx.MessageBox(
            f"Failed to open aviation weather: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
