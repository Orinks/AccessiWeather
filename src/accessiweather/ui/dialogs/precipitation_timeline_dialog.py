"""Pirate Weather minutely precipitation timeline dialog."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import wx

from ...notifications.minutely_precipitation import is_wet, precipitation_type_label

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp
    from ...models import MinutelyPrecipitationForecast, MinutelyPrecipitationPoint

logger = logging.getLogger(__name__)


def has_precipitation_timeline_data(weather_data) -> bool:
    """Return True when minutely precipitation data is available."""
    forecast = getattr(weather_data, "minutely_precipitation", None)
    if forecast is None:
        return False

    has_data = getattr(forecast, "has_data", None)
    if callable(has_data):
        return bool(has_data())

    return bool(getattr(forecast, "points", None))


def show_precipitation_timeline_dialog(parent, app: AccessiWeatherApp) -> None:
    """Show the minutely precipitation timeline dialog."""
    try:
        config_manager = getattr(app, "config_manager", None)
        location = config_manager.get_current_location() if config_manager else None
        if not location:
            wx.MessageBox(
                "Please select a location first.",
                "No Location Selected",
                wx.OK | wx.ICON_WARNING,
            )
            return

        weather_data = getattr(app, "current_weather_data", None)
        forecast = getattr(weather_data, "minutely_precipitation", None)
        if forecast is None or not has_precipitation_timeline_data(weather_data):
            wx.MessageBox(
                "Minutely precipitation data is not available for this location yet.",
                "No Precipitation Timeline Available",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        dlg = PrecipitationTimelineDialog(
            parent,
            location_name=location.name,
            forecast=forecast,
            timezone_name=getattr(location, "timezone", None),
        )
        dlg.ShowModal()
        dlg.Destroy()
    except Exception as exc:
        logger.error("Failed to show precipitation timeline dialog: %s", exc)
        wx.MessageBox(
            f"Failed to open precipitation timeline: {exc}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )


def build_precipitation_timeline_text(
    forecast: MinutelyPrecipitationForecast,
    timezone_name: str | None = None,
) -> str:
    """Build a plain-text minute-by-minute timeline."""
    zone = _resolve_zone(timezone_name)
    zone_label = zone.key if zone else "forecast time"

    header = [
        "Offset  Time      Conditions",
        "------  --------  ----------",
    ]

    lines = [
        _format_timeline_line(index, point, zone)
        for index, point in enumerate(getattr(forecast, "points", []))
    ]
    if not lines:
        lines = ["No minutely precipitation data available."]

    return f"Times shown in {zone_label}.\n\n" + "\n".join(header + lines)


class PrecipitationTimelineDialog(wx.Dialog):
    """Dialog for Pirate Weather minutely precipitation guidance."""

    def __init__(
        self,
        parent,
        *,
        location_name: str,
        forecast: MinutelyPrecipitationForecast,
        timezone_name: str | None = None,
    ) -> None:
        """Initialize the precipitation timeline dialog."""
        super().__init__(
            parent,
            title=f"Precipitation Timeline - {location_name}",
            size=(720, 540),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.location_name = location_name
        self.forecast = forecast
        self.timezone_name = timezone_name

        self._create_ui()
        self._setup_accessibility()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def _create_ui(self) -> None:
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(panel, label=f"Precipitation Timeline for {self.location_name}")
        header.SetFont(header.GetFont().Bold().Scaled(1.2))
        main_sizer.Add(header, 0, wx.ALL, 15)

        description = wx.StaticText(
            panel,
            label=(
                "Pirate Weather minutely guidance for the next hour. "
                "Summary first, followed by a plain-text timeline."
            ),
        )
        description.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        description.Wrap(650)
        main_sizer.Add(description, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        summary_header = wx.StaticText(panel, label="Summary")
        summary_header.SetFont(summary_header.GetFont().Bold().Scaled(1.05))
        main_sizer.Add(summary_header, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        summary_text = (self.forecast.summary or "No summary available.").strip()
        self.summary_label = wx.StaticText(panel, label=summary_text)
        self.summary_label.Wrap(650)
        main_sizer.Add(self.summary_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        timeline_header = wx.StaticText(panel, label="Minute-by-minute timeline")
        timeline_header.SetFont(timeline_header.GetFont().Bold().Scaled(1.05))
        main_sizer.Add(timeline_header, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        timeline_text = build_precipitation_timeline_text(self.forecast, self.timezone_name)
        self.timeline_display = wx.TextCtrl(
            panel,
            value=timeline_text,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
        )
        self.timeline_display.SetFont(
            wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        )
        main_sizer.Add(self.timeline_display, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        button_sizer.Add(close_btn, 0)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)

        panel.SetSizer(main_sizer)
        self.timeline_display.SetFocus()

    def _setup_accessibility(self) -> None:
        """Set accessible names for key controls."""
        self.summary_label.SetName("Precipitation summary")
        self.timeline_display.SetName("Precipitation timeline text")

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        """Close the dialog when Escape is pressed."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self._on_close(event)
            return
        event.Skip()

    def _on_close(self, event) -> None:
        """Handle close button press."""
        self.EndModal(wx.ID_CLOSE)


def _format_timeline_line(
    minute_offset: int,
    point: MinutelyPrecipitationPoint,
    zone: ZoneInfo | None,
) -> str:
    offset_label = "Now" if minute_offset == 0 else f"+{minute_offset:02d}m"
    point_time = point.time.astimezone(zone) if zone else point.time
    time_label = point_time.strftime("%I:%M %p").lstrip("0")
    return f"{offset_label:<6}  {time_label:<8}  {_format_point_conditions(point)}"


def _format_point_conditions(point: MinutelyPrecipitationPoint) -> str:
    details = [precipitation_type_label(point.precipitation_type)] if is_wet(point) else ["Dry"]

    probability = getattr(point, "precipitation_probability", None)
    if probability is not None and probability > 0:
        details.append(f"{round(probability * 100):.0f}% chance")

    intensity = getattr(point, "precipitation_intensity", None)
    if intensity is not None and intensity > 0:
        details.append(f"{intensity:.3f} in/hr")

    return " | ".join(details)


def _resolve_zone(timezone_name: str | None) -> ZoneInfo | None:
    if not timezone_name:
        return None
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.debug("Unknown timezone for precipitation timeline: %s", timezone_name)
        return None
