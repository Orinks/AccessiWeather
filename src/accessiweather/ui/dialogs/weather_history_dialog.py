"""Weather history dialog for displaying historical weather comparisons using gui_builder."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx
from gui_builder import fields, forms

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)


def _build_history_sections(app, weather_data) -> list[tuple[str, str]]:
    """Build history sections from weather data."""
    sections = []

    if not weather_data:
        sections.append(("No Data", "Weather history data is not available."))
        return sections

    # Daily history comparison
    daily_history = getattr(weather_data, "daily_history", None)
    if daily_history:
        history_text = []
        for period in daily_history[:7]:  # Last 7 days
            date_str = getattr(period, "date", "Unknown")
            temp_high = getattr(period, "high_temp", None)
            temp_low = getattr(period, "low_temp", None)
            condition = getattr(period, "condition", "Unknown")

            if temp_high is not None and temp_low is not None:
                history_text.append(
                    f"{date_str}: High {temp_high}°F, Low {temp_low}°F - {condition}"
                )
            else:
                history_text.append(f"{date_str}: {condition}")

        sections.append(("Recent Weather History", "\n".join(history_text)))
    else:
        sections.append(("Recent Weather History", "Historical data not available."))

    # Trend insights if available
    trend_insights = getattr(weather_data, "trend_insights", None)
    if trend_insights:
        trend_text = []
        for insight in trend_insights:
            trend_type = getattr(insight, "trend_type", "")
            description = getattr(insight, "description", "")
            if description:
                trend_text.append(f"{trend_type}: {description}")

        if trend_text:
            sections.append(("Weather Trends", "\n".join(trend_text)))

    # Current vs yesterday comparison
    current = getattr(weather_data, "current", None)
    if current and daily_history:
        yesterday = daily_history[0] if daily_history else None
        if yesterday:
            comparison_text = []
            current_temp = getattr(current, "temperature_f", None)
            yesterday_high = getattr(yesterday, "high_temp", None)

            if current_temp is not None and yesterday_high is not None:
                diff = current_temp - yesterday_high
                direction = "warmer" if diff > 0 else "cooler" if diff < 0 else "about the same"
                comparison_text.append(
                    f"Current temperature ({current_temp}°F) is {abs(diff):.1f}°F {direction} "
                    f"than yesterday's high ({yesterday_high}°F)."
                )

            if comparison_text:
                sections.append(("Today vs Yesterday", "\n".join(comparison_text)))

    if not sections:
        sections.append(("No Data", "Weather history data is not available."))

    return sections


class WeatherHistoryDialog(forms.Dialog):
    """Dialog for displaying weather history comparisons using gui_builder."""

    # Header
    header_label = fields.StaticText(label="")
    description_label = fields.StaticText(
        label="Comparisons against previous days to provide context for current conditions."
    )

    # Text display
    history_display = fields.Text(
        label="Weather history text",
        multiline=True,
        readonly=True,
    )

    # Close button
    close_button = fields.Button(label="&Close")

    def __init__(
        self,
        location_name: str,
        sections: list[tuple[str, str]],
        **kwargs,
    ):
        """
        Initialize the weather history dialog.

        Args:
            location_name: Name of the location
            sections: List of (heading, content) tuples
            **kwargs: Additional keyword arguments passed to Dialog

        """
        self.location_name = location_name
        self.sections = sections

        kwargs.setdefault("title", f"Weather History - {location_name}")
        super().__init__(**kwargs)

    def render(self, **kwargs):
        """Render the dialog and populate with data."""
        super().render(**kwargs)
        self._populate_data()
        self._setup_accessibility()

    def _populate_data(self) -> None:
        """Populate the dialog with history data."""
        self.header_label.set_label(f"Weather History for {self.location_name}")

        # Build content text
        content_lines = []
        for heading, content in self.sections:
            content_lines.append(f"=== {heading} ===")
            content_lines.append(content or "No data available.")
            content_lines.append("")

        history_text = "\n".join(content_lines).strip()
        self.history_display.set_value(history_text or "No historical data available.")

    def _setup_accessibility(self) -> None:
        """Set up accessibility labels for screen readers."""
        self.history_display.set_accessible_label("Weather history text")

    @close_button.add_callback
    def on_close(self):
        """Handle close button press."""
        self.widget.control.EndModal(wx.ID_CLOSE)


def show_weather_history_dialog(parent, app: AccessiWeatherApp) -> None:
    """
    Show the weather history dialog.

    Args:
        parent: Parent window (gui_builder widget)
        app: Application instance

    """
    try:
        # Get the underlying wx control if parent is a gui_builder widget
        parent_ctrl = getattr(parent, "control", parent)

        # Get current location
        location = app.config_manager.get_current_location()
        if not location:
            wx.MessageBox(
                "Please select a location first.",
                "No Location Selected",
                wx.OK | wx.ICON_WARNING,
            )
            return

        # Get weather data
        weather_data = getattr(app, "current_weather_data", None)

        # Build history sections
        sections = _build_history_sections(app, weather_data)

        dlg = WeatherHistoryDialog(location.name, sections, parent=parent_ctrl)
        dlg.render()
        dlg.widget.control.ShowModal()
        dlg.widget.control.Destroy()

    except Exception as e:
        logger.error(f"Failed to show weather history dialog: {e}")
        wx.MessageBox(
            f"Failed to open weather history: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
