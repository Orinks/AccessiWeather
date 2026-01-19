"""UV index dialog for displaying UV data and safety recommendations using gui_builder."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx
from gui_builder import fields, forms

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)

# UV index guidance messages
_UV_INDEX_GUIDANCE = {
    "Low": "No protection needed. You can safely stay outside.",
    "Moderate": "Seek shade during midday hours. Wear protective clothing.",
    "High": "Reduce time in the sun between 10am and 4pm. Seek shade, wear protective clothing.",
    "Very High": "Take extra precautions. Minimize sun exposure between 10am and 4pm.",
    "Extreme": "Try to avoid sun exposure between 10am and 4pm. Shirt, sunscreen, and hat are essential.",
}

# Sun safety recommendations
_UV_SUN_SAFETY = {
    "Low": """• SPF 15+ sunscreen for extended outdoor activities
• Sunglasses on bright days
• No special precautions needed for most people""",
    "Moderate": """• SPF 30+ sunscreen, reapply every 2 hours
• Wear sunglasses and a wide-brimmed hat
• Seek shade during midday hours
• Cover up with clothing when possible""",
    "High": """• SPF 30+ sunscreen is essential
• Wear protective clothing, hat, and sunglasses
• Seek shade, especially during midday
• Limit time in direct sun between 10am-4pm
• Stay hydrated""",
    "Very High": """• SPF 50+ sunscreen, reapply frequently
• Protective clothing, wide-brimmed hat, UV-blocking sunglasses
• Stay in shade whenever possible
• Minimize outdoor activities between 10am-4pm
• Extra caution for children and sensitive skin""",
    "Extreme": """• AVOID outdoor activities between 10am-4pm if possible
• SPF 50+ sunscreen is critical, reapply every 1-2 hours
• Full protective clothing, hat, and sunglasses required
• Seek air-conditioned spaces
• Watch for signs of heat illness
• Extremely high risk of skin and eye damage""",
}


class UVIndexDialog(forms.Dialog):
    """Dialog for displaying UV index information using gui_builder."""

    # Summary section
    summary_header = fields.StaticText(label="Current UV Index")
    uv_label = fields.StaticText(label="")
    guidance_label = fields.StaticText(label="")
    updated_label = fields.StaticText(label="")

    # Hourly forecast section
    hourly_header = fields.StaticText(label="Hourly Forecast")
    hourly_display = fields.Text(
        label="Hourly UV forecast",
        multiline=True,
        readonly=True,
    )

    # Sun safety section
    safety_header = fields.StaticText(label="Sun Safety Recommendations")
    safety_display = fields.Text(
        label="Sun safety recommendations",
        multiline=True,
        readonly=True,
    )

    # No data message
    no_data_label = fields.StaticText(label="")

    # Close button
    close_button = fields.Button(label="&Close")

    def __init__(
        self,
        location_name: str,
        environmental,
        app: AccessiWeatherApp,
        **kwargs,
    ):
        """
        Initialize the UV index dialog.

        Args:
            location_name: Name of the location
            environmental: Environmental conditions data
            app: Application instance
            **kwargs: Additional keyword arguments passed to Dialog

        """
        self.location_name = location_name
        self.environmental = environmental
        self.app = app

        kwargs.setdefault("title", f"UV Index - {location_name}")
        super().__init__(**kwargs)

    def render(self, **kwargs):
        """Render the dialog and populate with data."""
        super().render(**kwargs)
        self._populate_data()
        self._setup_accessibility()

    def _populate_data(self) -> None:
        """Populate the dialog with UV index data."""
        # Check if we have data
        has_data = (
            self.environmental
            and hasattr(self.environmental, "has_data")
            and self.environmental.has_data()
        )

        if not has_data:
            self.no_data_label.set_label("UV index data is not available for this location.")
            # Hide other sections
            self.summary_header.set_label("")
            self.uv_label.set_label("")
            self.guidance_label.set_label("")
            self.updated_label.set_label("")
            self.hourly_header.set_label("")
            self.hourly_display.set_value("")
            self.safety_header.set_label("")
            self.safety_display.set_value("")
            return

        # Hide no data message
        self.no_data_label.set_label("")

        # Populate summary section
        self._populate_summary()

        # Populate hourly forecast
        self._populate_hourly()

        # Populate sun safety
        self._populate_safety()

    def _populate_summary(self) -> None:
        """Populate the summary section."""
        uv_index = getattr(self.environmental, "uv_index", None)
        category = getattr(self.environmental, "uv_category", None)

        if uv_index is not None or category:
            uv_text = ""
            if uv_index is not None:
                uv_text = f"UV Index: {int(round(uv_index))}"
            if category:
                if uv_text:
                    uv_text += f" ({category})"
                else:
                    uv_text = category
            self.uv_label.set_label(uv_text)

        # Health guidance
        guidance = _UV_INDEX_GUIDANCE.get(
            category or "", "Monitor UV levels and use sun protection as needed."
        )
        self.guidance_label.set_label(f"Health guidance: {guidance}")

        # Last updated
        updated_at = getattr(self.environmental, "updated_at", None)
        if updated_at:
            timestamp = updated_at.strftime("%I:%M %p").lstrip("0")
            date_str = updated_at.strftime("%B %d, %Y")
            self.updated_label.set_label(f"Last updated: {timestamp} on {date_str}")

    def _populate_hourly(self) -> None:
        """Populate the hourly forecast section."""
        hourly_data = getattr(self.environmental, "hourly_uv_index", None)
        if not hourly_data:
            self.hourly_display.set_value("Hourly forecast data is not available.")
            return

        # Build forecast text
        forecast_lines = []
        for i, hour in enumerate(hourly_data[:12]):
            time_str = getattr(hour, "time", f"Hour {i + 1}")
            uv = getattr(hour, "uv_index", None)
            if uv is not None:
                forecast_lines.append(f"{time_str}: UV {int(round(uv))}")

        forecast_text = "\n".join(forecast_lines) if forecast_lines else "No forecast data."
        self.hourly_display.set_value(forecast_text)

    def _populate_safety(self) -> None:
        """Populate the sun safety section."""
        category = getattr(self.environmental, "uv_category", None)
        if not category:
            self.safety_display.set_value("Sun safety recommendations are not available.")
            return

        recommendations = _UV_SUN_SAFETY.get(category, "")
        if recommendations:
            self.safety_display.set_value(recommendations)
        else:
            self.safety_display.set_value("Sun safety recommendations are not available.")

    def _setup_accessibility(self) -> None:
        """Set up accessibility labels for screen readers."""
        self.hourly_display.set_accessible_label("Hourly UV forecast")
        self.safety_display.set_accessible_label("Sun safety recommendations")

    @close_button.add_callback
    def on_close(self):
        """Handle close button press."""
        self.widget.control.EndModal(wx.ID_CLOSE)


def show_uv_index_dialog(parent, app: AccessiWeatherApp) -> None:
    """
    Show the UV index dialog.

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

        # Get weather data for environmental conditions
        weather_data = getattr(app, "current_weather_data", None)
        environmental = getattr(weather_data, "environmental", None) if weather_data else None

        dlg = UVIndexDialog(location.name, environmental, app, parent=parent_ctrl)
        dlg.render()
        dlg.widget.control.ShowModal()
        dlg.widget.control.Destroy()

    except Exception as e:
        logger.error(f"Failed to show UV index dialog: {e}")
        wx.MessageBox(
            f"Failed to open UV index dialog: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
