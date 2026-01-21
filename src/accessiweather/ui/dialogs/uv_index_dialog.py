"""UV index dialog for displaying UV data and safety recommendations using wxPython."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx

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


def show_uv_index_dialog(parent, app: AccessiWeatherApp) -> None:
    """
    Show the UV index dialog.

    Args:
        parent: Parent window
        app: Application instance

    """
    try:
        parent_ctrl = parent

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

        dlg = UVIndexDialog(parent_ctrl, location.name, environmental, app)
        dlg.ShowModal()
        dlg.Destroy()

    except Exception as e:
        logger.error(f"Failed to show UV index dialog: {e}")
        wx.MessageBox(
            f"Failed to open UV index dialog: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )


class UVIndexDialog(wx.Dialog):
    """Dialog for displaying UV index information."""

    def __init__(self, parent, location_name: str, environmental, app: AccessiWeatherApp):
        """
        Initialize the UV index dialog.

        Args:
            parent: Parent window
            location_name: Name of the location
            environmental: Environmental conditions data
            app: Application instance

        """
        super().__init__(
            parent,
            title=f"UV Index - {location_name}",
            size=(600, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.location_name = location_name
        self.environmental = environmental
        self.app = app

        self._create_ui()
        self._setup_accessibility()

    def _create_ui(self):
        """Create the dialog UI."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Check if we have data
        has_data = (
            self.environmental
            and hasattr(self.environmental, "has_data")
            and self.environmental.has_data()
        )

        if not has_data:
            no_data = wx.StaticText(
                panel,
                label="UV index data is not available for this location.",
            )
            no_data.SetFont(no_data.GetFont().Scaled(1.1))
            main_sizer.Add(no_data, 0, wx.ALL, 20)
        else:
            # Summary section
            summary_box = self._build_summary_section(panel)
            main_sizer.Add(summary_box, 0, wx.EXPAND | wx.ALL, 15)

            # Hourly forecast section
            hourly_box = self._build_hourly_section(panel)
            main_sizer.Add(hourly_box, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

            # Sun safety section
            safety_box = self._build_sun_safety_section(panel)
            main_sizer.Add(safety_box, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 15)

        # Close button
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        close_btn = wx.Button(panel, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        button_sizer.Add(close_btn, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)

        panel.SetSizer(main_sizer)

    def _build_summary_section(self, panel) -> wx.BoxSizer:
        """Build the current UV index summary section."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Section header
        header = wx.StaticText(panel, label="Current UV Index")
        header.SetFont(header.GetFont().Bold().Scaled(1.1))
        sizer.Add(header, 0, wx.BOTTOM, 8)

        # UV index value and category
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

            uv_label = wx.StaticText(panel, label=uv_text)
            uv_label.SetFont(uv_label.GetFont().Scaled(1.05))
            sizer.Add(uv_label, 0, wx.BOTTOM, 4)

        # Health guidance
        guidance = _UV_INDEX_GUIDANCE.get(
            category or "", "Monitor UV levels and use sun protection as needed."
        )
        guidance_label = wx.StaticText(panel, label=f"Health guidance: {guidance}")
        guidance_label.SetForegroundColour(wx.Colour(128, 128, 128))
        guidance_label.Wrap(550)
        sizer.Add(guidance_label, 0, wx.BOTTOM, 4)

        # Last updated
        updated_at = getattr(self.environmental, "updated_at", None)
        if updated_at:
            timestamp = updated_at.strftime("%I:%M %p").lstrip("0")
            date_str = updated_at.strftime("%B %d, %Y")
            updated_label = wx.StaticText(panel, label=f"Last updated: {timestamp} on {date_str}")
            updated_label.SetForegroundColour(wx.Colour(128, 128, 128))
            sizer.Add(updated_label, 0)

        return sizer

    def _build_hourly_section(self, panel) -> wx.BoxSizer:
        """Build the hourly UV forecast section."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Section header
        header = wx.StaticText(panel, label="Hourly Forecast")
        header.SetFont(header.GetFont().Bold().Scaled(1.1))
        sizer.Add(header, 0, wx.BOTTOM, 8)

        hourly_data = getattr(self.environmental, "hourly_uv_index", None)
        if not hourly_data:
            no_data = wx.StaticText(panel, label="Hourly forecast data is not available.")
            no_data.SetForegroundColour(wx.Colour(128, 128, 128))
            sizer.Add(no_data, 0)
            return sizer

        # Build forecast text
        forecast_lines = []
        for i, hour in enumerate(hourly_data[:12]):
            time_str = getattr(hour, "time", f"Hour {i + 1}")
            uv = getattr(hour, "uv_index", None)
            if uv is not None:
                forecast_lines.append(f"{time_str}: UV {int(round(uv))}")

        forecast_text = "\n".join(forecast_lines) if forecast_lines else "No forecast data."

        forecast_display = wx.TextCtrl(
            panel,
            value=forecast_text,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, 100),
        )
        sizer.Add(forecast_display, 1, wx.EXPAND)

        return sizer

    def _build_sun_safety_section(self, panel) -> wx.BoxSizer:
        """Build the sun safety recommendations section."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Section header
        header = wx.StaticText(panel, label="Sun Safety Recommendations")
        header.SetFont(header.GetFont().Bold().Scaled(1.1))
        sizer.Add(header, 0, wx.BOTTOM, 8)

        category = getattr(self.environmental, "uv_category", None)
        if not category:
            no_data = wx.StaticText(panel, label="Sun safety recommendations are not available.")
            no_data.SetForegroundColour(wx.Colour(128, 128, 128))
            sizer.Add(no_data, 0)
            return sizer

        recommendations = _UV_SUN_SAFETY.get(category, "")
        if recommendations:
            safety_display = wx.TextCtrl(
                panel,
                value=recommendations,
                style=wx.TE_MULTILINE | wx.TE_READONLY,
                size=(-1, 100),
            )
            sizer.Add(safety_display, 1, wx.EXPAND)
        else:
            no_data = wx.StaticText(panel, label="Sun safety recommendations are not available.")
            no_data.SetForegroundColour(wx.Colour(128, 128, 128))
            sizer.Add(no_data, 0)

        return sizer

    def _setup_accessibility(self):
        """Set up accessibility labels."""
        # Controls are created with meaningful labels already

    def _on_close(self, event):
        """Handle close button press."""
        self.EndModal(wx.ID_CLOSE)
