"""
Accessible dialog for presenting weather history comparisons.

This dialog mirrors the forecast discussion dialog by providing a dedicated
window with keyboard focus management so screen reader users can review
historical summaries comfortably.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Iterable

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

logger = logging.getLogger(__name__)


class WeatherHistoryDialog:
    """Dialog window for displaying weather history comparisons."""

    def __init__(
        self,
        app,
        location_name: str,
        sections: Iterable[tuple[str, str]],
    ) -> None:
        """Store the application context and history sections to display."""
        self.app = app
        self.location_name = location_name or "Unknown Location"
        self.sections = list(sections)
        self.window: toga.Window | None = None

        self.text_display: toga.MultilineTextInput | None = None
        self.close_button: toga.Button | None = None

    def _create_ui(self) -> None:
        """Build the dialog window content."""
        title = f"Weather History – {self.location_name}"
        self.window = toga.Window(title=title, size=(800, 500))

        main_box = toga.Box(style=Pack(direction=COLUMN, margin=15))

        header_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))
        header_box.add(
            toga.Label(
                f"Weather History for {self.location_name}",
                style=Pack(font_size=16, font_weight="bold", margin_bottom=6),
            )
        )
        header_box.add(
            toga.Label(
                "Comparisons against previous days to provide context for current conditions.",
                style=Pack(font_size=12, font_style="italic"),
            )
        )
        main_box.add(header_box)

        body_lines: list[str] = []
        for heading, content in self.sections or [("No data available", "")]:
            body_lines.append(heading)
            body_lines.append(content or "No historical data available.")
            body_lines.append("")

        history_text = "\n".join(body_lines).strip()

        self.text_display = toga.MultilineTextInput(
            value=history_text or "No historical data available.",
            readonly=True,
            style=Pack(flex=1, margin=(5, 0), font_family="monospace"),
        )
        main_box.add(self.text_display)

        button_row = toga.Box(style=Pack(direction=ROW, margin_top=15))
        button_row.add(toga.Box(style=Pack(flex=1)))

        self.close_button = toga.Button(
            "Close",
            on_press=self._on_close,
            style=Pack(width=100, margin_left=10),
        )
        button_row.add(self.close_button)

        main_box.add(button_row)

        self.window.content = main_box

    async def show_and_focus(self) -> None:
        """Display the dialog and set focus for assistive tech."""
        try:
            if self.window is None:
                self._create_ui()

            self.window.show()

            await asyncio.sleep(0.1)

            if self.text_display:
                try:
                    self.text_display.focus()
                    logger.info("Focused weather history text field")
                    return
                except Exception as exc:  # pragma: no cover - accessibility fallback
                    logger.warning("Failed to focus history text field: %s", exc)

            if self.close_button:
                with contextlib.suppress(Exception):
                    self.close_button.focus()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to show weather history dialog: %s", exc)
            raise

    def _on_close(self, widget) -> None:
        """Close the dialog window."""
        if self.window:
            self.window.close()
