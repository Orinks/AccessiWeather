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

from ..display.presentation.environmental import (
    _UV_INDEX_GUIDANCE,
    _UV_SUN_SAFETY,
    format_hourly_uv_index,
)
from ..models import AppSettings, EnvironmentalConditions

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
        self._close_button.aria_description = "Close the UV index dialog and return to main window"
        button_box.add(self._close_button)
        main_box.add(button_box)

        self.window.content = main_box

    def _build_summary_section(self) -> toga.Box:
        """Build the current UV index summary section."""
        box = toga.Box(
            style=Pack(direction=COLUMN, margin_bottom=15),
        )

        # Section header
        header = toga.Label(
            "Current UV Index",
            style=Pack(font_weight="bold", font_size=14, margin_bottom=8),
        )
        header.aria_label = "Current UV index section"
        box.add(header)

        # UV index value and category
        uv_index = self.environmental.uv_index
        category = self.environmental.uv_category

        if uv_index is not None or category:
            uv_text = ""
            if uv_index is not None:
                uv_text = f"UV Index: {int(round(uv_index))}"
            if category:
                if uv_text:
                    uv_text += f" ({category})"
                else:
                    uv_text = category

            uv_label = toga.Label(
                uv_text,
                style=Pack(font_size=13, margin_bottom=4),
            )
            uv_label.aria_label = f"UV index: {uv_text}"
            uv_label.aria_description = "Current UV index value and category"
            box.add(uv_label)

        # Health guidance
        guidance = _UV_INDEX_GUIDANCE.get(
            category or "", "Monitor UV levels and use sun protection as needed."
        )
        guidance_label = toga.Label(
            f"Health guidance: {guidance}",
            style=Pack(font_size=11, font_style="italic", margin_bottom=4),
        )
        guidance_label.aria_label = f"Health guidance: {guidance}"
        guidance_label.aria_description = "Health recommendations based on current UV index"
        box.add(guidance_label)

        # Last updated timestamp
        if self.environmental.updated_at:
            time_format_12hour = (
                getattr(self.settings, "time_format_12hour", True) if self.settings else True
            )
            if time_format_12hour:
                timestamp = self.environmental.updated_at.strftime("%I:%M %p").lstrip("0")
            else:
                timestamp = self.environmental.updated_at.strftime("%H:%M")
            date_str = self.environmental.updated_at.strftime("%B %d, %Y")
            updated_text = f"Last updated: {timestamp} on {date_str}"
            updated_label = toga.Label(
                updated_text,
                style=Pack(font_size=10, color="#666666"),
            )
            updated_label.aria_label = updated_text
            updated_label.aria_description = "When the UV index data was last updated"
            box.add(updated_label)

        return box

    def _build_hourly_section(self) -> toga.Box:
        """Build the hourly UV forecast section."""
        box = toga.Box(
            style=Pack(direction=COLUMN, margin_bottom=15),
        )

        # Section header
        header = toga.Label(
            "Hourly Forecast",
            style=Pack(font_weight="bold", font_size=14, margin_bottom=8),
        )
        header.aria_label = "Hourly UV index forecast section"
        box.add(header)

        hourly_data = self.environmental.hourly_uv_index
        if not hourly_data:
            no_data = toga.Label(
                "Hourly forecast data is not available.",
                style=Pack(font_size=12, font_style="italic"),
            )
            no_data.aria_label = "No hourly forecast data available"
            box.add(no_data)
            return box

        # Use the existing format function
        forecast_text = format_hourly_uv_index(hourly_data, self.settings, max_hours=24)
        if forecast_text:
            forecast_display = toga.MultilineTextInput(
                value=forecast_text,
                readonly=True,
                style=Pack(height=120, font_size=11),
            )
            forecast_display.aria_label = "Hourly UV index forecast"
            forecast_display.aria_description = (
                "Detailed hourly UV index forecast including trend, peak times, "
                "and lowest UV times for outdoor activities"
            )
            box.add(forecast_display)

        return box

    def _build_sun_safety_section(self) -> toga.Box:
        """Build the sun safety recommendations section."""
        box = toga.Box(
            style=Pack(direction=COLUMN, margin_bottom=10),
        )

        # Section header
        header = toga.Label(
            "Sun Safety Recommendations",
            style=Pack(font_weight="bold", font_size=14, margin_bottom=8),
        )
        header.aria_label = "Sun safety recommendations section"
        box.add(header)

        category = self.environmental.uv_category
        if not category:
            no_data = toga.Label(
                "Sun safety recommendations are not available.",
                style=Pack(font_size=12, font_style="italic"),
            )
            no_data.aria_label = "No sun safety recommendations available"
            box.add(no_data)
            return box

        # Get recommendations for the current UV category
        recommendations = _UV_SUN_SAFETY.get(category, "")
        if recommendations:
            safety_display = toga.MultilineTextInput(
                value=recommendations,
                readonly=True,
                style=Pack(height=120, font_size=11),
            )
            safety_display.aria_label = f"Sun safety recommendations for {category} UV index"
            safety_display.aria_description = (
                f"Detailed sun protection recommendations for {category} UV conditions, "
                "including sunscreen, clothing, shade, and timing guidance"
            )
            box.add(safety_display)
        else:
            no_data = toga.Label(
                "Sun safety recommendations are not available.",
                style=Pack(font_size=12, font_style="italic"),
            )
            no_data.aria_label = "No sun safety recommendations available"
            box.add(no_data)

        return box

    async def show_and_focus(self) -> None:
        """Display the dialog and set focus for accessibility."""
        if self.window is None:
            self._build_ui()

        # Ensure window is registered with app before showing
        if self.window not in self.app.windows:
            self.app.windows.add(self.window)

        self.window.show()

        # Brief delay to ensure window is rendered
        await asyncio.sleep(0.1)
        if self._close_button:
            with contextlib.suppress(Exception):
                self._close_button.focus()

    def _on_close(self, widget: toga.Widget) -> None:
        """Handle dialog close via window close button."""
        if self.window:
            self.window.close()

    def _on_close_button(self, widget: toga.Widget) -> None:
        """Handle Close button press."""
        if self.window:
            self.window.close()
