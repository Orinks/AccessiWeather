"""
Interactive dialog for fetching and decoding aviation weather products.

This dialog allows users to enter an ICAO airport code, fetch the latest
Terminal Aerodrome Forecast (TAF) from the NWS API, and view both the raw
and decoded versions in an accessible layout.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from typing import TYPE_CHECKING, Any

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from ..models import AviationData

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..app import AccessiWeatherApp


logger = logging.getLogger(__name__)

_ICAO_RE = re.compile(r"^[A-Z]{4}$")


class AviationDialog:
    """Dialog window for retrieving aviation weather by airport code."""

    def __init__(self, app: AccessiWeatherApp) -> None:
        """Store application context and initialize state."""
        self.app = app
        self.window: toga.Window | None = None

        self.station_input: toga.TextInput | None = None
        self.fetch_button: toga.Button | None = None
        self.status_label: toga.Label | None = None
        self.raw_taf_display: toga.MultilineTextInput | None = None
        self.decoded_taf_display: toga.MultilineTextInput | None = None
        self.advisories_table: toga.Table | None = None
        self.advisories_info: toga.Label | None = None

        self._fetch_task: asyncio.Task | None = None

    def _build_ui(self) -> None:
        """Construct the dialog layout."""
        self.window = toga.Window(title="Aviation Weather", size=(900, 620))
        self.window.on_close = self._on_close

        main_box = toga.Box(style=Pack(direction=COLUMN, padding=15, spacing=10))

        header = toga.Label(
            "Fetch decoded aviation weather by entering a four-letter ICAO airport code.",
            style=Pack(font_size=13, font_style="italic"),
        )
        main_box.add(header)

        input_row = toga.Box(style=Pack(direction=ROW, spacing=10, alignment="center"))
        self.station_input = toga.TextInput(
            placeholder="e.g., KJFK",
            style=Pack(width=120),
            on_confirm=self._on_fetch_clicked,
        )
        input_row.add(toga.Label("Airport code:", style=Pack(font_weight="bold")))
        input_row.add(self.station_input)

        self.fetch_button = toga.Button(
            "Get Aviation Data",
            on_press=self._on_fetch_clicked,
            style=Pack(width=160),
        )
        input_row.add(self.fetch_button)
        main_box.add(input_row)

        self.status_label = toga.Label(
            "Enter a code and press Enter to fetch the latest TAF.",
            style=Pack(font_size=12, font_style="italic", color="#555555"),
        )
        main_box.add(self.status_label)

        content_row = toga.Box(style=Pack(direction=ROW, spacing=12, flex=1))

        raw_box = toga.Box(style=Pack(direction=COLUMN, flex=1))
        raw_box.add(toga.Label("Raw TAF", style=Pack(font_weight="bold")))
        self.raw_taf_display = toga.MultilineTextInput(
            value="No TAF loaded.",
            readonly=True,
            style=Pack(flex=1, font_family="monospace"),
        )
        raw_box.add(self.raw_taf_display)
        content_row.add(raw_box)

        decoded_box = toga.Box(style=Pack(direction=COLUMN, flex=1))
        decoded_box.add(toga.Label("Decoded TAF", style=Pack(font_weight="bold")))
        self.decoded_taf_display = toga.MultilineTextInput(
            value="Decoded TAF will appear here.",
            readonly=True,
            style=Pack(flex=1),
        )
        decoded_box.add(self.decoded_taf_display)
        content_row.add(decoded_box)

        main_box.add(content_row)

        advisories_box = toga.Box(style=Pack(direction=COLUMN))
        advisories_box.add(toga.Label("Advisories", style=Pack(font_weight="bold")))
        self.advisories_table = toga.Table(
            headings=["Type", "Event", "Valid", "Summary"],
            data=[],
            style=Pack(height=180),
        )
        advisories_box.add(self.advisories_table)
        self.advisories_info = toga.Label(
            "No advisories available.",
            style=Pack(font_style="italic", margin_top=6),
        )
        advisories_box.add(self.advisories_info)
        main_box.add(advisories_box)

        self.window.content = main_box

    async def show_and_focus(self) -> None:
        """Display the dialog and move focus to the airport code field."""
        if self.window is None:
            self._build_ui()

        self.window.show()

        await asyncio.sleep(0.1)
        if self.station_input:
            try:
                self.station_input.focus()
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.debug("Failed to focus station input: %s", exc)

    def _on_close(self, widget) -> None:
        """Handle dialog close events."""
        if self._fetch_task and not self._fetch_task.done():
            self._fetch_task.cancel()
        self._fetch_task = None

        if self.window:
            self.window.close()

    def _on_fetch_clicked(self, widget) -> None:
        """Schedule an asynchronous aviation fetch operation."""
        if self._fetch_task and not self._fetch_task.done():
            self._fetch_task.cancel()

        self._fetch_task = asyncio.create_task(self._handle_fetch())

    async def _handle_fetch(self) -> None:
        """Validate input, perform the fetch, and update the UI."""
        if not self.station_input:
            return

        code = (self.station_input.value or "").strip().upper()
        if not code:
            self._set_status("Please enter a four-letter ICAO airport code.", is_error=True)
            await self._refocus_input()
            return

        if not _ICAO_RE.match(code):
            self._set_status(
                "Airport codes must be exactly four letters (e.g., KJFK).", is_error=True
            )
            await self._refocus_input()
            return

        if not getattr(self.app, "weather_client", None):
            self._set_status(
                "Weather client is not ready. Try again after initialization.", is_error=True
            )
            return

        if self.fetch_button:
            self.fetch_button.enabled = False

        self._set_status(f"Fetching aviation weather for {code}…")

        try:
            aviation = await self.app.weather_client.get_aviation_weather(
                code, include_sigmets=True, include_cwas=True
            )
        except asyncio.CancelledError:  # pragma: no cover - cooperative cancel
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Aviation fetch failed: %s", exc)
            self._set_status(f"Failed to retrieve aviation weather: {exc}", is_error=True)
            if getattr(self.app, "main_window", None):
                with contextlib.suppress(Exception):
                    await self.app.main_window.error_dialog(
                        "Aviation Weather Error",
                        f"Unable to fetch aviation weather for {code}: {exc}",
                    )
        else:
            self._apply_aviation_data(code, aviation)
        finally:
            if self.fetch_button:
                self.fetch_button.enabled = True

    def _apply_aviation_data(self, code: str, aviation: AviationData | None) -> None:
        """Populate the dialog fields with aviation data."""
        if aviation is None or not aviation.has_taf():
            self._set_status(
                f"No TAF available for {code}. The station may not publish TAF data.",
                is_error=True,
            )
            if self.raw_taf_display:
                self.raw_taf_display.value = "No TAF available."
            if self.decoded_taf_display:
                self.decoded_taf_display.value = "No decoded TAF available."
            if self.advisories_table is not None:
                self.advisories_table.data = []
            if self.advisories_info is not None:
                self.advisories_info.value = "No advisories available."
            return

        airport_label = aviation.airport_name or aviation.station_id or code
        self._set_status(f"Latest TAF loaded for {airport_label}.")

        if self.raw_taf_display:
            self.raw_taf_display.value = aviation.raw_taf or "No TAF available."

        if self.decoded_taf_display:
            self.decoded_taf_display.value = aviation.decoded_taf or "Unable to decode TAF."

        self._update_advisories_table(aviation)

    def _set_status(self, message: str, *, is_error: bool = False) -> None:
        """Update the status label text and color."""
        if not self.status_label:
            return
        self.status_label.value = message
        color = "#c62828" if is_error else "#2e7d32"
        with contextlib.suppress(Exception):  # pragma: no cover - defensive styling
            self.status_label.style.update(color=color)

    async def _refocus_input(self) -> None:
        """Attempt to focus the airport code input field."""
        await asyncio.sleep(0)
        if self.station_input:
            with contextlib.suppress(Exception):
                self.station_input.focus()

    def _update_advisories_table(self, aviation: AviationData) -> None:
        rows: list[dict[str, str]] = []
        rows.extend(self._build_advisory_rows("SIGMET", aviation.active_sigmets))
        rows.extend(self._build_advisory_rows("CWA", aviation.active_cwas))

        if self.advisories_table is not None:
            self.advisories_table.data = rows

        if self.advisories_info is not None:
            if rows:
                self.advisories_info.value = f"{len(rows)} advisories loaded."
            else:
                self.advisories_info.value = "No advisories available."

    def _build_advisory_rows(
        self, advisory_type: str, advisories: list[dict[str, Any]] | None
    ) -> list[dict[str, str]]:
        if not advisories:
            return []

        rows: list[dict[str, str]] = []
        for entry in advisories[:20]:  # cap for readability
            event_name = (
                entry.get("event") or entry.get("name") or entry.get("hazard") or advisory_type
            )
            summary = (
                entry.get("description") or entry.get("summary") or entry.get("text") or ""
            ).strip()
            rows.append(
                {
                    "Type": advisory_type,
                    "Event": event_name,
                    "Valid": self._format_advisory_window(entry),
                    "Summary": summary[:200] or "No description provided.",
                }
            )
        return rows

    def _format_advisory_window(self, entry: dict[str, Any]) -> str:
        start = self._format_aviation_time(
            entry.get("startTime")
            or entry.get("beginTime")
            or entry.get("validTimeStart")
            or entry.get("issueTime")
        )
        end = self._format_aviation_time(
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
            return start
        return "--"
