"""
UV Index Dialog for displaying comprehensive UV index information.

This dialog provides detailed UV index data including current UV index,
hourly forecasts with peak times, and sun safety recommendations.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from ..models import AppSettings, EnvironmentalConditions, HourlyUVIndex

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..app import AccessiWeatherApp


logger = logging.getLogger(__name__)


class UVIndexDialog:
    """Modal dialog for comprehensive UV index information."""

    def __init__(
        self,
        app: AccessiWeatherApp,
        location_name: str,
        environmental: EnvironmentalConditions,
        settings: AppSettings | None = None,
    ) -> None:
        """
        Initialize the UV index dialog.

        Args:
            app: The main application instance.
            location_name: Name of the current location.
            environmental: Environmental conditions data.
            settings: Application settings for formatting preferences.

        """
        self.app = app
        self.location_name = location_name
        self.environmental = environmental
        self.settings = settings
        self.window: toga.Window | None = None
        self._close_button: toga.Button | None = None

    def _build_ui(self) -> None:
        """Construct the dialog layout."""
        title = f"UV Index - {self.location_name}"
        self.window = toga.Window(
            title=title,
            size=(600, 500),
        )
        self.window.on_close = self._on_close

        main_box = toga.Box(
            style=Pack(direction=COLUMN, margin=15),
        )

        # Check if we have data
        if not self.environmental.has_data():
            no_data_label = toga.Label(
                "UV index data is not available for this location.",
                style=Pack(font_size=14, margin=20),
            )
            no_data_label.aria_label = "UV index data unavailable"
            no_data_label.aria_description = (
                "No UV index information is currently available for this location."
            )
            main_box.add(no_data_label)
        else:
            # Summary section
            summary_box = self._build_summary_section()
            main_box.add(summary_box)

            # Hourly forecast section
            hourly_box = self._build_hourly_section()
            main_box.add(hourly_box)

            # Sun safety recommendations section
            sun_safety_box = self._build_sun_safety_section()
            main_box.add(sun_safety_box)

        # Close button
        button_box = toga.Box(
            style=Pack(direction=ROW, margin_top=15, align_items="center"),
        )
        self._close_button = toga.Button(
            "Close",
            on_press=self._on_close_button,
            style=Pack(width=100),
        )
        self._close_button.aria_label = "Close dialog"
        self._close_button.aria_description = (
            "Close the UV index dialog and return to main window"
        )
        button_box.add(self._close_button)
        main_box.add(button_box)

        self.window.content = main_box

    def _build_summary_section(self) -> toga.Box:
        """Build the current UV index summary section."""
        # TODO: Implement in subtask 3.3
        box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=15))
        return box

    def _build_hourly_section(self) -> toga.Box:
        """Build the hourly UV forecast section."""
        # TODO: Implement in subtask 3.4
        box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=15))
        return box

    def _build_sun_safety_section(self) -> toga.Box:
        """Build the sun safety recommendations section."""
        # TODO: Implement in subtask 3.5
        box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))
        return box

    def _on_close(self, widget: toga.Widget) -> None:
        """Handle dialog close via window close button."""
        # TODO: Implement in subtask 3.6
        if self.window:
            self.window.close()

    def _on_close_button(self, widget: toga.Widget) -> None:
        """Handle Close button press."""
        # TODO: Implement in subtask 3.6
        if self.window:
            self.window.close()
