"""Aviation weather dialog for fetching and displaying TAF data using wxPython."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)

_ICAO_RE = re.compile(r"^[A-Z]{4}$")


def show_aviation_dialog(parent, app: AccessiWeatherApp) -> None:
    """
    Show the aviation weather dialog.

    Args:
        parent: Parent window
        app: Application instance

    """
    try:
        parent_ctrl = parent

        dlg = AviationDialog(parent_ctrl, app)
        dlg.ShowModal()
        dlg.Destroy()

    except Exception as e:
        logger.error(f"Failed to show aviation dialog: {e}")
        wx.MessageBox(
            f"Failed to open aviation weather: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )


class AviationDialog(wx.Dialog):
    """Dialog for fetching and displaying aviation weather."""

    def __init__(self, parent, app: AccessiWeatherApp):
        """
        Initialize the aviation dialog.

        Args:
            parent: Parent window
            app: Application instance

        """
        super().__init__(
            parent,
            title="Aviation Weather",
            size=(900, 620),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.app = app
        self._is_fetching = False

        self._create_ui()
        self._setup_accessibility()

    def _create_ui(self):
        """Create the dialog UI."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        header = wx.StaticText(
            panel,
            label="Fetch decoded aviation weather by entering a four-letter ICAO airport code.",
        )
        header.SetForegroundColour(wx.Colour(85, 85, 85))
        main_sizer.Add(header, 0, wx.ALL, 15)

        # Input row
        input_row = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(panel, label="Airport code:")
        label.SetFont(label.GetFont().Bold())
        input_row.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.station_input = wx.TextCtrl(panel, size=(100, -1), style=wx.TE_PROCESS_ENTER)
        self.station_input.SetHint("e.g., KJFK")
        self.station_input.Bind(wx.EVT_TEXT_ENTER, self._on_fetch)
        input_row.Add(self.station_input, 0, wx.RIGHT, 10)

        self.fetch_button = wx.Button(panel, label="Get Aviation Data")
        self.fetch_button.Bind(wx.EVT_BUTTON, self._on_fetch)
        input_row.Add(self.fetch_button, 0)

        main_sizer.Add(input_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Status
        self.status_label = wx.StaticText(
            panel, label="Enter a code and press Enter to fetch the latest TAF."
        )
        self.status_label.SetForegroundColour(wx.Colour(85, 85, 85))
        main_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Content area with two columns
        content_row = wx.BoxSizer(wx.HORIZONTAL)

        # Raw TAF column
        raw_sizer = wx.BoxSizer(wx.VERTICAL)
        raw_label = wx.StaticText(panel, label="Raw TAF")
        raw_label.SetFont(raw_label.GetFont().Bold())
        raw_sizer.Add(raw_label, 0, wx.BOTTOM, 5)

        self.raw_taf_display = wx.TextCtrl(
            panel,
            value="No TAF loaded.",
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        self.raw_taf_display.SetFont(
            wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        )
        raw_sizer.Add(self.raw_taf_display, 1, wx.EXPAND)

        content_row.Add(raw_sizer, 1, wx.EXPAND | wx.RIGHT, 10)

        # Decoded TAF column
        decoded_sizer = wx.BoxSizer(wx.VERTICAL)
        decoded_label = wx.StaticText(panel, label="Decoded TAF")
        decoded_label.SetFont(decoded_label.GetFont().Bold())
        decoded_sizer.Add(decoded_label, 0, wx.BOTTOM, 5)

        self.decoded_taf_display = wx.TextCtrl(
            panel,
            value="Decoded TAF will appear here.",
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        decoded_sizer.Add(self.decoded_taf_display, 1, wx.EXPAND)

        content_row.Add(decoded_sizer, 1, wx.EXPAND)

        main_sizer.Add(content_row, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        # Advisories section
        advisories_label = wx.StaticText(panel, label="Advisories")
        advisories_label.SetFont(advisories_label.GetFont().Bold())
        main_sizer.Add(advisories_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)

        self.advisories_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
            size=(-1, 150),
        )
        self.advisories_list.InsertColumn(0, "Type", width=80)
        self.advisories_list.InsertColumn(1, "Event", width=150)
        self.advisories_list.InsertColumn(2, "Valid", width=200)
        self.advisories_list.InsertColumn(3, "Summary", width=350)
        main_sizer.Add(self.advisories_list, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 15)

        self.advisories_info = wx.StaticText(panel, label="No advisories available.")
        self.advisories_info.SetForegroundColour(wx.Colour(128, 128, 128))
        main_sizer.Add(self.advisories_info, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)

        # Close button
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        close_btn = wx.Button(panel, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        button_sizer.Add(close_btn, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)

        panel.SetSizer(main_sizer)

        # Set initial focus
        self.station_input.SetFocus()

    def _setup_accessibility(self):
        """Set up accessibility labels."""
        self.station_input.SetName("ICAO airport code input")
        self.raw_taf_display.SetName("Raw TAF display")
        self.decoded_taf_display.SetName("Decoded TAF display")
        self.advisories_list.SetName("Aviation advisories list")

    def _set_status(self, message: str, is_error: bool = False):
        """Update the status label."""
        self.status_label.SetLabel(message)
        if is_error:
            self.status_label.SetForegroundColour(wx.Colour(198, 40, 40))
        else:
            self.status_label.SetForegroundColour(wx.Colour(46, 125, 50))

    def _on_fetch(self, event):
        """Handle fetch button press."""
        code = self.station_input.GetValue().strip().upper()

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
        self.fetch_button.Disable()
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

    def _on_fetch_complete(self, code: str, aviation):
        """Handle fetch completion."""
        self._is_fetching = False
        self.fetch_button.Enable()

        if aviation is None or not aviation.has_taf():
            self._set_status(
                f"No TAF available for {code}. The station may not publish TAF data.",
                is_error=True,
            )
            self.raw_taf_display.SetValue("No TAF available.")
            self.decoded_taf_display.SetValue("No decoded TAF available.")
            self.advisories_list.DeleteAllItems()
            self.advisories_info.SetLabel("No advisories available.")
            return

        airport_label = aviation.airport_name or aviation.station_id or code
        self._set_status(f"Latest TAF loaded for {airport_label}.")

        self.raw_taf_display.SetValue(aviation.raw_taf or "No TAF available.")
        self.decoded_taf_display.SetValue(aviation.decoded_taf or "Unable to decode TAF.")

        self._update_advisories(aviation)

    def _on_fetch_error(self, code: str, error: str):
        """Handle fetch error."""
        self._is_fetching = False
        self.fetch_button.Enable()
        self._set_status(f"Failed to retrieve aviation weather: {error}", is_error=True)

    def _update_advisories(self, aviation):
        """Update the advisories list."""
        self.advisories_list.DeleteAllItems()

        rows = []
        if aviation.active_sigmets:
            for sigmet in aviation.active_sigmets[:10]:
                rows.append(self._build_advisory_row("SIGMET", sigmet))

        if aviation.active_cwas:
            for cwa in aviation.active_cwas[:10]:
                rows.append(self._build_advisory_row("CWA", cwa))

        for row in rows:
            index = self.advisories_list.InsertItem(self.advisories_list.GetItemCount(), row[0])
            self.advisories_list.SetItem(index, 1, row[1])
            self.advisories_list.SetItem(index, 2, row[2])
            self.advisories_list.SetItem(index, 3, row[3])

        if rows:
            self.advisories_info.SetLabel(f"{len(rows)} advisories loaded.")
        else:
            self.advisories_info.SetLabel("No advisories available.")

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

    def _on_close(self, event):
        """Handle close button press."""
        self.EndModal(wx.ID_CLOSE)
