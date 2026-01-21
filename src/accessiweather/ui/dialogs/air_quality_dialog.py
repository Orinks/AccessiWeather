"""Air quality dialog for displaying AQI and pollutant data using wxPython."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)

# Air quality guidance messages
_AIR_QUALITY_GUIDANCE = {
    "Good": "Air quality is satisfactory. No precautions needed.",
    "Moderate": "Unusually sensitive people should consider limiting prolonged outdoor exertion.",
    "Unhealthy for Sensitive Groups": "People with respiratory conditions, children, and older adults should limit prolonged outdoor exertion.",
    "Unhealthy": "Everyone should limit prolonged outdoor exertion.",
    "Very Unhealthy": "Everyone should avoid prolonged outdoor exertion.",
    "Hazardous": "Everyone should avoid all outdoor exertion. Stay indoors.",
}

_POLLUTANT_LABELS = {
    "PM2_5": "PM2.5 (Fine Particles)",
    "PM10": "PM10 (Coarse Particles)",
    "O3": "Ozone",
    "NO2": "Nitrogen Dioxide",
    "SO2": "Sulfur Dioxide",
    "CO": "Carbon Monoxide",
}


def show_air_quality_dialog(parent, app: AccessiWeatherApp) -> None:
    """
    Show the air quality dialog.

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

        dlg = AirQualityDialog(parent_ctrl, location.name, environmental, app)
        dlg.ShowModal()
        dlg.Destroy()

    except Exception as e:
        logger.error(f"Failed to show air quality dialog: {e}")
        wx.MessageBox(
            f"Failed to open air quality dialog: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )


class AirQualityDialog(wx.Dialog):
    """Dialog for displaying air quality information."""

    def __init__(self, parent, location_name: str, environmental, app: AccessiWeatherApp):
        """
        Initialize the air quality dialog.

        Args:
            parent: Parent window
            location_name: Name of the location
            environmental: Environmental conditions data
            app: Application instance

        """
        super().__init__(
            parent,
            title=f"Air Quality - {location_name}",
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
                label="Air quality data is not available for this location.",
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

            # Pollutant details section
            pollutant_box = self._build_pollutant_section(panel)
            main_sizer.Add(pollutant_box, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 15)

        # Close button
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        close_btn = wx.Button(panel, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        button_sizer.Add(close_btn, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)

        panel.SetSizer(main_sizer)

    def _build_summary_section(self, panel) -> wx.BoxSizer:
        """Build the current AQI summary section."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Section header
        header = wx.StaticText(panel, label="Current Air Quality")
        header.SetFont(header.GetFont().Bold().Scaled(1.1))
        sizer.Add(header, 0, wx.BOTTOM, 8)

        # AQI value and category
        aqi = getattr(self.environmental, "air_quality_index", None)
        category = getattr(self.environmental, "air_quality_category", None)

        if aqi is not None or category:
            aqi_text = ""
            if aqi is not None:
                aqi_text = f"AQI: {int(round(aqi))}"
            if category:
                if aqi_text:
                    aqi_text += f" ({category})"
                else:
                    aqi_text = category

            aqi_label = wx.StaticText(panel, label=aqi_text)
            aqi_label.SetFont(aqi_label.GetFont().Scaled(1.05))
            sizer.Add(aqi_label, 0, wx.BOTTOM, 4)

        # Dominant pollutant
        pollutant = getattr(self.environmental, "air_quality_pollutant", None)
        if pollutant:
            pollutant_name = _POLLUTANT_LABELS.get(pollutant.upper(), pollutant)
            pollutant_label = wx.StaticText(panel, label=f"Dominant pollutant: {pollutant_name}")
            sizer.Add(pollutant_label, 0, wx.BOTTOM, 4)

        # Health guidance
        guidance = _AIR_QUALITY_GUIDANCE.get(
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
        """Build the hourly forecast section."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Section header
        header = wx.StaticText(panel, label="Hourly Forecast")
        header.SetFont(header.GetFont().Bold().Scaled(1.1))
        sizer.Add(header, 0, wx.BOTTOM, 8)

        hourly_data = getattr(self.environmental, "hourly_air_quality", None)
        if not hourly_data:
            no_data = wx.StaticText(panel, label="Hourly forecast data is not available.")
            no_data.SetForegroundColour(wx.Colour(128, 128, 128))
            sizer.Add(no_data, 0)
            return sizer

        # Build forecast text
        forecast_lines = []
        for i, hour in enumerate(hourly_data[:12]):
            time_str = getattr(hour, "time", f"Hour {i + 1}")
            aqi = getattr(hour, "aqi", None)
            if aqi is not None:
                forecast_lines.append(f"{time_str}: AQI {int(round(aqi))}")

        forecast_text = "\n".join(forecast_lines) if forecast_lines else "No forecast data."

        forecast_display = wx.TextCtrl(
            panel,
            value=forecast_text,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, 100),
        )
        sizer.Add(forecast_display, 1, wx.EXPAND)

        return sizer

    def _build_pollutant_section(self, panel) -> wx.BoxSizer:
        """Build the pollutant details section."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Section header
        header = wx.StaticText(panel, label="Current Pollutant Levels")
        header.SetFont(header.GetFont().Bold().Scaled(1.1))
        sizer.Add(header, 0, wx.BOTTOM, 8)

        hourly_data = getattr(self.environmental, "hourly_air_quality", None)
        if not hourly_data:
            no_data = wx.StaticText(panel, label="Pollutant data is not available.")
            no_data.SetForegroundColour(wx.Colour(128, 128, 128))
            sizer.Add(no_data, 0)
            return sizer

        # Get the most recent hour's data
        current = hourly_data[0] if hourly_data else None
        dominant = getattr(self.environmental, "air_quality_pollutant", None)

        if current:
            pollutant_lines = []
            pollutants = [
                ("PM2_5", getattr(current, "pm2_5", None), "µg/m³"),
                ("PM10", getattr(current, "pm10", None), "µg/m³"),
                ("O3", getattr(current, "ozone", None), "µg/m³"),
                ("NO2", getattr(current, "nitrogen_dioxide", None), "µg/m³"),
                ("SO2", getattr(current, "sulphur_dioxide", None), "µg/m³"),
                ("CO", getattr(current, "carbon_monoxide", None), "µg/m³"),
            ]

            for code, value, unit in pollutants:
                if value is not None:
                    name = _POLLUTANT_LABELS.get(code, code)
                    line = f"{name}: {value:.1f} {unit}"
                    if dominant and code.upper() == dominant.upper():
                        line += " (dominant)"
                    pollutant_lines.append(line)

            pollutant_text = (
                "\n".join(pollutant_lines) if pollutant_lines else "No measurements available."
            )
        else:
            pollutant_text = "No pollutant measurements available."

        pollutant_display = wx.TextCtrl(
            panel,
            value=pollutant_text,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, 100),
        )
        sizer.Add(pollutant_display, 1, wx.EXPAND)

        return sizer

    def _setup_accessibility(self):
        """Set up accessibility labels."""
        # Controls are created with meaningful labels already

    def _on_close(self, event):
        """Handle close button press."""
        self.EndModal(wx.ID_CLOSE)
