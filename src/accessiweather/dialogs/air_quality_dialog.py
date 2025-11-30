"""
Air Quality Dialog for displaying comprehensive air quality information.

This dialog provides detailed air quality data including current AQI,
hourly forecasts with trend analysis, and pollutant breakdowns.
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
    _AIR_QUALITY_GUIDANCE,
    _DEFAULT_GUIDANCE,
    _POLLUTANT_LABELS,
    format_hourly_air_quality,
)
from ..models import AppSettings, EnvironmentalConditions, HourlyAirQuality

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..app import AccessiWeatherApp


logger = logging.getLogger(__name__)


class AirQualityDialog:
    """Modal dialog for comprehensive air quality information."""

    def __init__(
        self,
        app: AccessiWeatherApp,
        location_name: str,
        environmental: EnvironmentalConditions,
        settings: AppSettings | None = None,
    ) -> None:
        """
        Initialize the air quality dialog.

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
        title = f"Air Quality - {self.location_name}"
        self.window = toga.Window(
            title=title,
            size=(600, 500),
        )
        self.window.on_close = self._on_close

        main_box = toga.Box(
            style=Pack(direction=COLUMN, padding=15),
        )

        # Check if we have data
        if not self.environmental.has_data():
            no_data_label = toga.Label(
                "Air quality data is not available for this location.",
                style=Pack(font_size=14, padding=20),
            )
            no_data_label.aria_label = "Air quality data unavailable"
            no_data_label.aria_description = (
                "No air quality information is currently available for this location."
            )
            main_box.add(no_data_label)
        else:
            # Summary section
            summary_box = self._build_summary_section()
            main_box.add(summary_box)

            # Hourly forecast section
            hourly_box = self._build_hourly_section()
            main_box.add(hourly_box)

            # Pollutant details section
            pollutant_box = self._build_pollutant_section()
            main_box.add(pollutant_box)

        # Close button
        button_box = toga.Box(
            style=Pack(direction=ROW, padding_top=15, alignment="center"),
        )
        self._close_button = toga.Button(
            "Close",
            on_press=self._on_close_button,
            style=Pack(width=100),
        )
        self._close_button.aria_label = "Close dialog"
        self._close_button.aria_description = (
            "Close the air quality dialog and return to main window"
        )
        button_box.add(self._close_button)
        main_box.add(button_box)

        self.window.content = main_box

    def _build_summary_section(self) -> toga.Box:
        """Build the current AQI summary section."""
        box = toga.Box(
            style=Pack(direction=COLUMN, padding_bottom=15),
        )

        # Section header
        header = toga.Label(
            "Current Air Quality",
            style=Pack(font_weight="bold", font_size=14, padding_bottom=8),
        )
        header.aria_label = "Current air quality section"
        box.add(header)

        # AQI value and category
        aqi = self.environmental.air_quality_index
        category = self.environmental.air_quality_category

        if aqi is not None or category:
            aqi_text = ""
            if aqi is not None:
                aqi_text = f"AQI: {int(round(aqi))}"
            if category:
                if aqi_text:
                    aqi_text += f" ({category})"
                else:
                    aqi_text = category

            aqi_label = toga.Label(
                aqi_text,
                style=Pack(font_size=13, padding_bottom=4),
            )
            aqi_label.aria_label = f"Air quality index: {aqi_text}"
            aqi_label.aria_description = "Current air quality index value and category"
            box.add(aqi_label)

        # Dominant pollutant
        pollutant = self.environmental.air_quality_pollutant
        if pollutant:
            pollutant_name = _get_pollutant_name(pollutant)
            pollutant_label = toga.Label(
                f"Dominant pollutant: {pollutant_name}",
                style=Pack(font_size=12, padding_bottom=4),
            )
            pollutant_label.aria_label = f"Dominant pollutant is {pollutant_name}"
            pollutant_label.aria_description = (
                "The primary pollutant contributing to the current air quality index"
            )
            box.add(pollutant_label)

        # Health guidance
        guidance = _AIR_QUALITY_GUIDANCE.get(category or "", _DEFAULT_GUIDANCE)
        guidance_label = toga.Label(
            f"Health guidance: {guidance}",
            style=Pack(font_size=11, font_style="italic", padding_bottom=4),
        )
        guidance_label.aria_label = f"Health guidance: {guidance}"
        guidance_label.aria_description = "Health recommendations based on current air quality"
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
            updated_label.aria_description = "When the air quality data was last updated"
            box.add(updated_label)

        return box

    def _build_hourly_section(self) -> toga.Box:
        """Build the hourly forecast section."""
        box = toga.Box(
            style=Pack(direction=COLUMN, padding_bottom=15),
        )

        # Section header
        header = toga.Label(
            "Hourly Forecast",
            style=Pack(font_weight="bold", font_size=14, padding_bottom=8),
        )
        header.aria_label = "Hourly air quality forecast section"
        box.add(header)

        hourly_data = self.environmental.hourly_air_quality
        if not hourly_data:
            no_data = toga.Label(
                "Hourly forecast data is not available.",
                style=Pack(font_size=12, font_style="italic"),
            )
            no_data.aria_label = "No hourly forecast data available"
            box.add(no_data)
            return box

        # Use the existing format function
        forecast_text = format_hourly_air_quality(hourly_data, self.settings, max_hours=24)
        if forecast_text:
            forecast_display = toga.MultilineTextInput(
                value=forecast_text,
                readonly=True,
                style=Pack(height=120, font_size=11),
            )
            forecast_display.aria_label = "Hourly air quality forecast"
            forecast_display.aria_description = (
                "Detailed hourly air quality forecast including trend, peak times, "
                "and best times for outdoor activities"
            )
            box.add(forecast_display)

        return box

    def _build_pollutant_section(self) -> toga.Box:
        """Build the pollutant details section."""
        box = toga.Box(
            style=Pack(direction=COLUMN, padding_bottom=10),
        )

        # Section header
        header = toga.Label(
            "Current Pollutant Levels",
            style=Pack(font_weight="bold", font_size=14, padding_bottom=8),
        )
        header.aria_label = "Current pollutant levels section"
        box.add(header)

        hourly_data = self.environmental.hourly_air_quality
        if not hourly_data:
            no_data = toga.Label(
                "Pollutant data is not available.",
                style=Pack(font_size=12, font_style="italic"),
            )
            no_data.aria_label = "No pollutant data available"
            box.add(no_data)
            return box

        # Get the most recent hour's pollutant data
        current = hourly_data[0]
        dominant = self.environmental.air_quality_pollutant

        pollutant_lines = _format_pollutant_details(current, dominant)
        if pollutant_lines:
            pollutant_text = "\n".join(pollutant_lines)
            pollutant_display = toga.MultilineTextInput(
                value=pollutant_text,
                readonly=True,
                style=Pack(height=100, font_size=11),
            )
            pollutant_display.aria_label = "Pollutant measurements"
            pollutant_display.aria_description = (
                "Individual pollutant measurements with the dominant pollutant indicated"
            )
            box.add(pollutant_display)
        else:
            no_data = toga.Label(
                "No pollutant measurements available.",
                style=Pack(font_size=12, font_style="italic"),
            )
            no_data.aria_label = "No pollutant measurements available"
            box.add(no_data)

        return box

    async def show_and_focus(self) -> None:
        """Display the dialog and set focus for accessibility."""
        if self.window is None:
            self._build_ui()

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


def _get_pollutant_name(pollutant_code: str) -> str:
    """Convert pollutant code to human-readable name."""
    code = pollutant_code.strip().upper()
    if code in _POLLUTANT_LABELS:
        return _POLLUTANT_LABELS[code]
    # Handle variations
    if code == "PM2.5":
        return "PM2.5"
    if code == "OZONE":
        return "Ozone"
    # Fallback: clean up the code
    return code.replace("_", " ").title() if "_" in code else code


def _format_pollutant_details(
    hourly: HourlyAirQuality,
    dominant_pollutant: str | None = None,
) -> list[str]:
    """Format pollutant measurements into readable lines."""
    lines = []
    dominant_code = dominant_pollutant.strip().upper() if dominant_pollutant else None

    pollutants = [
        ("PM2_5", hourly.pm2_5, "µg/m³"),
        ("PM10", hourly.pm10, "µg/m³"),
        ("O3", hourly.ozone, "µg/m³"),
        ("NO2", hourly.nitrogen_dioxide, "µg/m³"),
        ("SO2", hourly.sulphur_dioxide, "µg/m³"),
        ("CO", hourly.carbon_monoxide, "µg/m³"),
    ]

    for code, value, unit in pollutants:
        if value is not None:
            name = _POLLUTANT_LABELS.get(code, code)
            line = f"{name}: {value:.1f} {unit}"
            # Mark dominant pollutant
            if dominant_code and code == dominant_code:
                line += " (dominant)"
            lines.append(line)

    return lines
