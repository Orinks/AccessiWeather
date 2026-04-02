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

    def create(self):
        """Build the Display tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        # Unit Preference
        sizer.Add(wx.StaticText(panel, label="Unit Preference:"), 0, wx.ALL | wx.EXPAND, 5)
        controls["temp_unit"] = wx.Choice(
            panel,
            choices=[
                "Auto (based on location)",
                "Imperial (°F)",
                "Metric (°C)",
                "Both (°F and °C)",
            ],
        )
        sizer.Add(controls["temp_unit"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # Metric Visibility
        sizer.Add(wx.StaticText(panel, label="Metric Visibility:", style=wx.BOLD), 0, wx.ALL, 5)
        sizer.Add(
            wx.StaticText(panel, label="Select which weather metrics to display:"),
            0,
            wx.LEFT | wx.BOTTOM,
            5,
        )

        controls["show_dewpoint"] = wx.CheckBox(panel, label="Show dewpoint")
        sizer.Add(controls["show_dewpoint"], 0, wx.LEFT, 10)

        controls["show_visibility"] = wx.CheckBox(panel, label="Show visibility")
        sizer.Add(controls["show_visibility"], 0, wx.LEFT, 10)

        controls["show_uv_index"] = wx.CheckBox(panel, label="Show UV index")
        sizer.Add(controls["show_uv_index"], 0, wx.LEFT, 10)

        controls["show_pressure_trend"] = wx.CheckBox(panel, label="Show pressure trend")
        sizer.Add(controls["show_pressure_trend"], 0, wx.LEFT, 10)

        controls["show_impact_summaries"] = wx.CheckBox(
            panel, label="Show weather impact analysis (Outdoor, Driving, Allergy)"
        )
        sizer.Add(controls["show_impact_summaries"], 0, wx.LEFT, 10)

        controls["round_values"] = wx.CheckBox(
            panel, label="Show values as whole numbers (no decimals)"
        )
        sizer.Add(controls["round_values"], 0, wx.LEFT | wx.TOP, 10)

        row_forecast_duration = wx.BoxSizer(wx.HORIZONTAL)
        row_forecast_duration.Add(
            wx.StaticText(panel, label="Forecast duration:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["forecast_duration_days"] = wx.Choice(
            panel,
            choices=["3 days", "5 days", "7 days (default)", "10 days", "14 days", "15 days"],
        )
        row_forecast_duration.Add(controls["forecast_duration_days"], 0)
        sizer.Add(row_forecast_duration, 0, wx.LEFT | wx.TOP, 10)

        row_hourly_hours = wx.BoxSizer(wx.HORIZONTAL)
        row_hourly_hours.Add(
            wx.StaticText(panel, label="Hourly forecast hours:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["hourly_forecast_hours"] = wx.SpinCtrl(panel, min=1, max=168, initial=6)
        row_hourly_hours.Add(controls["hourly_forecast_hours"], 0)
        sizer.Add(row_hourly_hours, 0, wx.LEFT | wx.TOP, 10)

        # Time & Date Display
        sizer.Add(wx.StaticText(panel, label="Time & Date Display:"), 0, wx.ALL, 5)

        row_time_ref = wx.BoxSizer(wx.HORIZONTAL)
        row_time_ref.Add(
            wx.StaticText(panel, label="Forecast time display:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["forecast_time_reference"] = wx.Choice(
            panel,
            choices=["Location's timezone (default)", "My local timezone"],
        )
        row_time_ref.Add(controls["forecast_time_reference"], 0)
        sizer.Add(row_time_ref, 0, wx.LEFT, 10)

        row_tz = wx.BoxSizer(wx.HORIZONTAL)
        row_tz.Add(
            wx.StaticText(panel, label="Time zone display:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["time_display_mode"] = wx.Choice(
            panel,
            choices=["Local time only", "UTC time only", "Both (Local and UTC)"],
        )
        row_tz.Add(controls["time_display_mode"], 0)
        sizer.Add(row_tz, 0, wx.LEFT, 10)

        controls["time_format_12hour"] = wx.CheckBox(
            panel, label="Use 12-hour time format (e.g., 3:00 PM)"
        )
        sizer.Add(controls["time_format_12hour"], 0, wx.LEFT | wx.TOP, 10)

        controls["show_timezone_suffix"] = wx.CheckBox(
            panel, label="Show timezone abbreviations (e.g., EST, UTC)"
        )
        sizer.Add(controls["show_timezone_suffix"], 0, wx.LEFT, 10)

        # Verbosity
        sizer.Add(wx.StaticText(panel, label="Information Priority:"), 0, wx.ALL, 5)

        row_verb = wx.BoxSizer(wx.HORIZONTAL)
        row_verb.Add(
            wx.StaticText(panel, label="Verbosity level:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["verbosity_level"] = wx.Choice(
            panel,
            choices=[
                "Minimal (essentials only)",
                "Standard (recommended)",
                "Detailed (all available info)",
            ],
        )
        row_verb.Add(controls["verbosity_level"], 0)
        sizer.Add(row_verb, 0, wx.LEFT, 10)

        controls["severe_weather_override"] = wx.CheckBox(
            panel, label="Automatically prioritize severe weather info"
        )
        sizer.Add(controls["severe_weather_override"], 0, wx.ALL, 10)

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, "Display")
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
            "temp_unit": "Unit Preference",
            "show_dewpoint": "Show dewpoint",
            "show_visibility": "Show visibility",
            "show_uv_index": "Show UV index",
            "show_pressure_trend": "Show pressure trend",
            "show_impact_summaries": "Show weather impact analysis (Outdoor, Driving, Allergy)",
            "forecast_duration_days": "Forecast duration",
            "hourly_forecast_hours": "Hourly forecast hours",
            "forecast_time_reference": "Forecast time display",
            "time_display_mode": "Time zone display",
            "time_format_12hour": "Use 12-hour time format (e.g., 3:00 PM)",
            "show_timezone_suffix": "Show timezone abbreviations (e.g., EST, UTC)",
            "verbosity_level": "Verbosity level",
            "severe_weather_override": "Automatically prioritize severe weather info",
        }
        for key, name in names.items():
            controls[key].SetName(name)
