"""Display settings tab."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(__name__)

_TEMP_VALUES = ["auto", "f", "c", "both"]
_TEMP_MAP = {"auto": 0, "f": 1, "fahrenheit": 1, "c": 2, "celsius": 2, "both": 3}
_FORECAST_DURATION_VALUES = [3, 5, 7, 10, 14, 15]
_FORECAST_DURATION_MAP = {3: 0, 5: 1, 7: 2, 10: 3, 14: 4, 15: 5}
_FORECAST_TIME_REF_VALUES = ["location", "user_local"]
_FORECAST_TIME_REF_MAP = {"location": 0, "user_local": 1}
_TIME_MODE_VALUES = ["local", "utc", "both"]
_TIME_MODE_MAP = {"local": 0, "utc": 1, "both": 2}
_VERBOSITY_VALUES = ["minimal", "standard", "detailed"]
_VERBOSITY_MAP = {"minimal": 0, "standard": 1, "detailed": 2}


class DisplayTab:
    """Display settings tab: temperature units, metrics, forecast, time/date, verbosity."""

    def __init__(self, dialog):
        """Store reference to the parent settings dialog."""
        self.dialog = dialog

    def create(self, page_label: str = "Display"):
        """Build the Display tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        self.dialog.add_help_text(
            panel,
            sizer,
            "Choose what weather details appear and how forecast times and units are shown.",
            left=5,
        )

        temperature_section = self.dialog.create_section(
            panel,
            sizer,
            "Temperature units",
            "Choose whether temperatures are shown automatically, in Fahrenheit, in Celsius, or both.",
        )
        controls["temp_unit"] = wx.Choice(
            panel,
            choices=[
                "Auto (based on location)",
                "Imperial (°F)",
                "Metric (°C)",
                "Both (°F and °C)",
            ],
        )
        self.dialog.add_labeled_row(
            panel,
            temperature_section,
            "Temperature units:",
            controls["temp_unit"],
        )
        controls["round_values"] = wx.CheckBox(
            panel,
            label="Show values as whole numbers when possible",
        )
        temperature_section.Add(
            controls["round_values"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )

        forecast_section = self.dialog.create_section(
            panel,
            sizer,
            "Forecast range",
            "Choose how many days and hours of forecast detail AccessiWeather should show.",
        )
        controls["forecast_duration_days"] = wx.Choice(
            panel,
            choices=["3 days", "5 days", "7 days (default)", "10 days", "14 days", "15 days"],
        )
        self.dialog.add_labeled_row(
            panel,
            forecast_section,
            "Daily forecast range:",
            controls["forecast_duration_days"],
        )
        controls["hourly_forecast_hours"] = wx.SpinCtrl(panel, min=1, max=168, initial=6)
        self.dialog.add_labeled_row(
            panel,
            forecast_section,
            "Hourly forecast range (hours):",
            controls["hourly_forecast_hours"],
        )

        details_section = self.dialog.create_section(
            panel,
            sizer,
            "Extra weather details",
            "Turn on the details that matter to you most.",
        )
        controls["show_dewpoint"] = wx.CheckBox(panel, label="Show dew point")
        details_section.Add(controls["show_dewpoint"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["show_visibility"] = wx.CheckBox(panel, label="Show visibility")
        details_section.Add(controls["show_visibility"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["show_uv_index"] = wx.CheckBox(panel, label="Show UV index")
        details_section.Add(controls["show_uv_index"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["show_pressure_trend"] = wx.CheckBox(panel, label="Show pressure trend")
        details_section.Add(
            controls["show_pressure_trend"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )
        controls["show_impact_summaries"] = wx.CheckBox(
            panel,
            label="Show impact summaries for outdoor, driving, and allergy conditions",
        )
        details_section.Add(
            controls["show_impact_summaries"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )

        time_section = self.dialog.create_section(
            panel,
            sizer,
            "Time display",
            "Choose whose timezone to use and how timestamps should be formatted.",
        )
        controls["forecast_time_reference"] = wx.Choice(
            panel,
            choices=["Location timezone (default)", "My local timezone"],
        )
        self.dialog.add_labeled_row(
            panel,
            time_section,
            "Forecast times are based on:",
            controls["forecast_time_reference"],
        )
        controls["time_display_mode"] = wx.Choice(
            panel,
            choices=["Local time only", "UTC time only", "Both local and UTC"],
        )
        self.dialog.add_labeled_row(
            panel,
            time_section,
            "Show times as:",
            controls["time_display_mode"],
        )
        controls["time_format_12hour"] = wx.CheckBox(
            panel,
            label="Use 12-hour time format (for example, 3:00 PM)",
        )
        time_section.Add(
            controls["time_format_12hour"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )
        controls["show_timezone_suffix"] = wx.CheckBox(
            panel,
            label="Show timezone abbreviations (for example, EST or UTC)",
        )
        time_section.Add(
            controls["show_timezone_suffix"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )

        priority_section = self.dialog.create_section(
            panel,
            sizer,
            "Reading priority",
            "Decide how compact or detailed the spoken and displayed forecast should be.",
        )
        controls["verbosity_level"] = wx.Choice(
            panel,
            choices=[
                "Minimal (essentials only)",
                "Standard (recommended)",
                "Detailed (all available info)",
            ],
        )
        self.dialog.add_labeled_row(
            panel,
            priority_section,
            "Verbosity level:",
            controls["verbosity_level"],
        )
        controls["severe_weather_override"] = wx.CheckBox(
            panel,
            label="Automatically prioritize severe weather details",
        )
        priority_section.Add(
            controls["severe_weather_override"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, page_label)
        return panel

    def load(self, settings):
        """Populate Display tab controls from settings."""
        controls = self.dialog._controls

        temp_unit = getattr(settings, "temperature_unit", "both")
        controls["temp_unit"].SetSelection(_TEMP_MAP.get(temp_unit, 3))

        controls["show_dewpoint"].SetValue(getattr(settings, "show_dewpoint", True))
        controls["show_visibility"].SetValue(getattr(settings, "show_visibility", True))
        controls["show_uv_index"].SetValue(getattr(settings, "show_uv_index", True))
        controls["show_pressure_trend"].SetValue(getattr(settings, "show_pressure_trend", True))
        controls["show_impact_summaries"].SetValue(
            getattr(settings, "show_impact_summaries", False)
        )
        controls["round_values"].SetValue(getattr(settings, "round_values", False))

        forecast_duration_days = getattr(settings, "forecast_duration_days", 7)
        controls["forecast_duration_days"].SetSelection(
            _FORECAST_DURATION_MAP.get(forecast_duration_days, 2)
        )
        controls["hourly_forecast_hours"].SetValue(getattr(settings, "hourly_forecast_hours", 6))

        forecast_time_reference = getattr(settings, "forecast_time_reference", "location")
        controls["forecast_time_reference"].SetSelection(
            _FORECAST_TIME_REF_MAP.get(forecast_time_reference, 0)
        )

        time_mode = getattr(settings, "time_display_mode", "local")
        controls["time_display_mode"].SetSelection(_TIME_MODE_MAP.get(time_mode, 0))

        controls["time_format_12hour"].SetValue(getattr(settings, "time_format_12hour", True))
        controls["show_timezone_suffix"].SetValue(getattr(settings, "show_timezone_suffix", False))

        verbosity = getattr(settings, "verbosity_level", "standard")
        controls["verbosity_level"].SetSelection(_VERBOSITY_MAP.get(verbosity, 1))

        controls["severe_weather_override"].SetValue(
            getattr(settings, "severe_weather_override", True)
        )

    def save(self) -> dict:
        """Return Display tab settings as a dict."""
        controls = self.dialog._controls
        return {
            "temperature_unit": _TEMP_VALUES[controls["temp_unit"].GetSelection()],
            "show_dewpoint": controls["show_dewpoint"].GetValue(),
            "show_visibility": controls["show_visibility"].GetValue(),
            "show_uv_index": controls["show_uv_index"].GetValue(),
            "show_pressure_trend": controls["show_pressure_trend"].GetValue(),
            "show_impact_summaries": controls["show_impact_summaries"].GetValue(),
            "round_values": controls["round_values"].GetValue(),
            "forecast_duration_days": _FORECAST_DURATION_VALUES[
                controls["forecast_duration_days"].GetSelection()
            ],
            "hourly_forecast_hours": controls["hourly_forecast_hours"].GetValue(),
            "forecast_time_reference": _FORECAST_TIME_REF_VALUES[
                controls["forecast_time_reference"].GetSelection()
            ],
            "time_display_mode": _TIME_MODE_VALUES[controls["time_display_mode"].GetSelection()],
            "time_format_12hour": controls["time_format_12hour"].GetValue(),
            "show_timezone_suffix": controls["show_timezone_suffix"].GetValue(),
            "verbosity_level": _VERBOSITY_VALUES[controls["verbosity_level"].GetSelection()],
            "severe_weather_override": controls["severe_weather_override"].GetValue(),
        }

    def get_selected_temperature_unit(self) -> str:
        """Return the temperature unit selection currently shown in the dialog."""
        selection = self.dialog._controls["temp_unit"].GetSelection()
        if selection < 0 or selection >= len(_TEMP_VALUES):
            return "both"
        return _TEMP_VALUES[selection]

    def setup_accessibility(self):
        """Set accessibility names for Display tab controls."""
        controls = self.dialog._controls
        names = {
            "temp_unit": "Temperature units",
            "show_dewpoint": "Show dew point",
            "show_visibility": "Show visibility",
            "show_uv_index": "Show UV index",
            "show_pressure_trend": "Show pressure trend",
            "show_impact_summaries": "Show impact summaries for outdoor driving and allergy conditions",
            "round_values": "Show values as whole numbers when possible",
            "forecast_duration_days": "Daily forecast range",
            "hourly_forecast_hours": "Hourly forecast range in hours",
            "forecast_time_reference": "Forecast time reference",
            "time_display_mode": "Time display mode",
            "time_format_12hour": "Use 12-hour time format",
            "show_timezone_suffix": "Show timezone abbreviations",
            "verbosity_level": "Verbosity level",
            "severe_weather_override": "Automatically prioritize severe weather details",
        }
        for key, name in names.items():
            controls[key].SetName(name)
