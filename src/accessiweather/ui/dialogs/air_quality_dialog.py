"""Air quality dialog for displaying AQI and pollutant data using gui_builder."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx
from gui_builder import fields, forms

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


class AirQualityDialog(forms.Dialog):
    """Dialog for displaying air quality information using gui_builder."""

    # Summary section
    summary_header = fields.StaticText(label="Current Air Quality")
    aqi_label = fields.StaticText(label="")
    pollutant_label = fields.StaticText(label="")
    guidance_label = fields.StaticText(label="")
    updated_label = fields.StaticText(label="")

    # Hourly forecast section
    hourly_header = fields.StaticText(label="Hourly Forecast")
    hourly_display = fields.Text(
        label="Hourly air quality forecast",
        multiline=True,
        readonly=True,
    )

    # Pollutant details section
    pollutant_header = fields.StaticText(label="Current Pollutant Levels")
    pollutant_display = fields.Text(
        label="Current pollutant measurements",
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
        Initialize the air quality dialog.

        Args:
            location_name: Name of the location
            environmental: Environmental conditions data
            app: Application instance
            **kwargs: Additional keyword arguments passed to Dialog

        """
        self.location_name = location_name
        self.environmental = environmental
        self.app = app

        kwargs.setdefault("title", f"Air Quality - {location_name}")
        super().__init__(**kwargs)

    def render(self, **kwargs):
        """Render the dialog and populate with data."""
        super().render(**kwargs)
        self._populate_data()
        self._setup_accessibility()

    def _populate_data(self) -> None:
        """Populate the dialog with air quality data."""
        # Check if we have data
        has_data = (
            self.environmental
            and hasattr(self.environmental, "has_data")
            and self.environmental.has_data()
        )

        if not has_data:
            self.no_data_label.set_label("Air quality data is not available for this location.")
            # Hide other sections
            self.summary_header.set_label("")
            self.aqi_label.set_label("")
            self.pollutant_label.set_label("")
            self.guidance_label.set_label("")
            self.updated_label.set_label("")
            self.hourly_header.set_label("")
            self.hourly_display.set_value("")
            self.pollutant_header.set_label("")
            self.pollutant_display.set_value("")
            return

        # Hide no data message
        self.no_data_label.set_label("")

        # Populate summary section
        self._populate_summary()

        # Populate hourly forecast
        self._populate_hourly()

        # Populate pollutant details
        self._populate_pollutants()

    def _populate_summary(self) -> None:
        """Populate the summary section."""
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
            self.aqi_label.set_label(aqi_text)

        # Dominant pollutant
        pollutant = getattr(self.environmental, "air_quality_pollutant", None)
        if pollutant:
            pollutant_name = _POLLUTANT_LABELS.get(pollutant.upper(), pollutant)
            self.pollutant_label.set_label(f"Dominant pollutant: {pollutant_name}")

        # Health guidance
        guidance = _AIR_QUALITY_GUIDANCE.get(
            category or "", "Monitor air quality levels as needed."
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
        hourly_data = getattr(self.environmental, "hourly_air_quality", None)
        if not hourly_data:
            self.hourly_display.set_value("Hourly forecast data is not available.")
            return

        # Build forecast text
        forecast_lines = []
        for i, hour in enumerate(hourly_data[:12]):
            time_str = getattr(hour, "time", f"Hour {i + 1}")
            aqi = getattr(hour, "aqi", None)
            if aqi is not None:
                forecast_lines.append(f"{time_str}: AQI {int(round(aqi))}")

        forecast_text = "\n".join(forecast_lines) if forecast_lines else "No forecast data."
        self.hourly_display.set_value(forecast_text)

    def _populate_pollutants(self) -> None:
        """Populate the pollutant details section."""
        hourly_data = getattr(self.environmental, "hourly_air_quality", None)
        if not hourly_data:
            self.pollutant_display.set_value("Pollutant data is not available.")
            return

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

        self.pollutant_display.set_value(pollutant_text)

    def _setup_accessibility(self) -> None:
        """Set up accessibility labels for screen readers."""
        self.hourly_display.set_accessible_label("Hourly air quality forecast")
        self.pollutant_display.set_accessible_label("Current pollutant levels")

    @close_button.add_callback
    def on_close(self):
        """Handle close button press."""
        self.widget.control.EndModal(wx.ID_CLOSE)


def show_air_quality_dialog(parent, app: AccessiWeatherApp) -> None:
    """
    Show the air quality dialog.

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

        dlg = AirQualityDialog(location.name, environmental, app, parent=parent_ctrl)
        dlg.render()
        dlg.widget.control.ShowModal()
        dlg.widget.control.Destroy()

    except Exception as e:
        logger.error(f"Failed to show air quality dialog: {e}")
        wx.MessageBox(
            f"Failed to open air quality dialog: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
