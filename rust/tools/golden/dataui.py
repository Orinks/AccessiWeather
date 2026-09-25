"""Golden parity data for the Rust weather-data dialogs.

Covers ui/dialogs/weather_history_dialog.py, precipitation_timeline_dialog.py,
air_quality_dialog.py, uv_index_dialog.py and aviation_dialog.py.

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/dataui.py

Builds the real dialogs under a hidden frame (never shown, no main loop) and
records their title, the panel's controls in creation (tab) order with their
text, accessible name and look (bold, scale, gray, monospace, wrap width), and
the focused control. The aviation dialog is also driven through validation
and fetch-completion with synthetic data. Nothing here reads the clock.
Writes rust/testdata/golden/dataui/cases.json.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import wx
from common import jsonable, write

from accessiweather.models import (
    AviationData,
    CurrentConditions,
    EnvironmentalConditions,
    ForecastPeriod,
    HourlyAirQuality,
    HourlyUVIndex,
    Location,
    MinutelyPrecipitationForecast,
    MinutelyPrecipitationPoint,
    TrendInsight,
    WeatherData,
)
from accessiweather.ui.dialogs.air_quality_dialog import AirQualityDialog
from accessiweather.ui.dialogs.aviation_dialog import AviationDialog
from accessiweather.ui.dialogs.precipitation_timeline_dialog import (
    PrecipitationTimelineDialog,
    build_precipitation_timeline_text,
)
from accessiweather.ui.dialogs.uv_index_dialog import UVIndexDialog
from accessiweather.ui.dialogs.weather_history_dialog import (
    WeatherHistoryDialog,
    _build_history_sections,
)

EDT = timezone(timedelta(hours=-4))
UTC = timezone.utc
NY = ZoneInfo("America/New_York")


# StaticText.Wrap depends on font metrics; record the width instead.
def _record_wrap(self, width):
    self._golden_wrap = width


wx.StaticText.Wrap = _record_wrap


def controls(dlg) -> list[dict]:
    """The dialog panel's children in creation (tab) order."""
    (panel,) = dlg.GetChildren()
    base = panel.GetFont().GetFractionalPointSize()
    gray = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
    out = []
    for child in panel.GetChildren():
        font = child.GetFont()
        look = {
            "bold": font.GetWeight() == wx.FONTWEIGHT_BOLD,
            "scale": round(font.GetFractionalPointSize() / base, 2),
            "gray": child.GetForegroundColour() == gray,
        }
        if isinstance(child, wx.Button):
            out.append(
                {"kind": "button", "id": child.GetId(), "label": child.GetLabel(),
                 "name": child.GetName()}
            )
        elif isinstance(child, wx.TextCtrl):
            out.append(
                {"kind": "text", "name": child.GetName(), "value": child.GetValue(),
                 "mono": font.IsFixedWidth(),
                 "password": bool(child.GetWindowStyle() & wx.TE_PASSWORD)}
            )
        elif isinstance(child, wx.ListCtrl):
            cols = [child.GetColumn(i) for i in range(child.GetColumnCount())]
            out.append(
                {"kind": "list", "name": child.GetName(),
                 "columns": [[c.GetText(), c.GetWidth()] for c in cols]}
            )
        elif isinstance(child, wx.StaticText):
            out.append(
                {"kind": "label", "label": child.GetLabel(), "name": child.GetName(),
                 **look, "wrap": getattr(child, "_golden_wrap", None)}
            )
        else:
            raise TypeError(type(child))
    return out


def focus_index(dlg):
    (panel,) = dlg.GetChildren()
    focused = wx.Window.FindFocus()
    for i, child in enumerate(panel.GetChildren()):
        if child is focused or (focused and child.GetId() == focused.GetId()):
            return i
    return None


def record(dlg) -> dict:
    try:
        return {"title": dlg.GetTitle(), "controls": controls(dlg), "focus": focus_index(dlg)}
    finally:
        dlg.Destroy()


# ---------------------------------------------------------------------------
# Weather history
# ---------------------------------------------------------------------------

def period(name, start=None, temp=None, short=None):
    return ForecastPeriod(name=name, start_time=start, temperature=temp, short_forecast=short)


HISTORY_PERIODS = [
    period("Yesterday", datetime(2026, 9, 24, 6, 0, tzinfo=NY), 70.0, "Partly Sunny"),
    period("Tuesday", datetime(2026, 9, 23, 6, 0, tzinfo=EDT), 68.5, "Showers"),
    period("Monday", None, 66.0, "Cloudy"),
    period("", None, None, None),
    period("Saturday", datetime(2026, 9, 20, 0, 0, tzinfo=UTC), None, "Clear"),
    period("Friday", datetime(2026, 9, 19, 12, 0, tzinfo=NY), 81.25, ""),
    period("Thursday", datetime(2026, 9, 18, 12, 0, tzinfo=NY), -3.0, "Snow"),
    period("Wednesday", datetime(2026, 9, 17, 12, 0, tzinfo=NY), 99.0, "Hot"),
]

TRENDS = [
    TrendInsight(metric="temperature", direction="rising", change=4.5, unit="°F",
                 summary="Temperature rising +4.5°F over 24h"),
]


def weather(current_temp=..., history=(), trends=()):
    current = None if current_temp is ... else CurrentConditions(temperature_f=current_temp)
    return WeatherData(
        location=Location(name="Philadelphia, PA", latitude=39.95, longitude=-75.17),
        current=current,
        daily_history=list(history),
        trend_insights=list(trends),
    )


HISTORY_CASES = [
    ("no data", "Philadelphia, PA", None),
    ("no history", "Philadelphia, PA", weather(72.0, trends=TRENDS)),
    ("warmer", "Philadelphia, PA", weather(72.5, HISTORY_PERIODS, TRENDS)),
    ("about the same", "Zürich", weather(70.2, HISTORY_PERIODS[:2])),
    ("cooler", "Anchorage, AK", weather(65.0, [period("Yesterday", None, 71.3, "Rain")])),
    ("half degree", "Denver", weather(70.5, [period("Yesterday", None, 70.0, "Sun")])),
    ("no current temp", "Denver", weather(None, HISTORY_PERIODS[:1])),
    ("no current", "Denver", weather(..., HISTORY_PERIODS[:1])),
    ("no yesterday temp", "Denver", weather(60.0, [period("Yesterday", None, None, "Fog")])),
]


def history_case(parent, name, location, data) -> dict:
    sections = _build_history_sections(None, data)
    case = {
        "name": name,
        "location": location,
        "weather": None if data is None else {
            "current": data.current,
            "daily_history": data.daily_history,
            "trend_insights": data.trend_insights,
        },
        "sections": [list(s) for s in sections],
    }
    case.update(record(WeatherHistoryDialog(parent, location, sections)))
    return case


# ---------------------------------------------------------------------------
# Precipitation timeline
# ---------------------------------------------------------------------------

def point(minute, **kw):
    return MinutelyPrecipitationPoint(
        time=datetime(2026, 9, 25, 13, 58, tzinfo=UTC) + timedelta(minutes=minute), **kw
    )


POINTS = [
    point(0),
    point(1, precipitation_intensity=0.0, precipitation_probability=0.0),
    point(2, precipitation_intensity=0.2, precipitation_probability=0.125,
          precipitation_type="rain"),
    point(3, precipitation_intensity=0.05, precipitation_intensity_error=0.1,
          precipitation_probability=0.135, precipitation_type="rain"),
    point(4, precipitation_intensity=1.23456, precipitation_intensity_error=0.2,
          precipitation_type="snow", precipitation_probability=1.0),
    point(5, precipitation_probability=0.5),
    point(6, precipitation_probability=0.3, precipitation_type="sleet"),
    point(7, precipitation_intensity=0.4, precipitation_type="freezing-rain",
          precipitation_intensity_unit="in/hr", precipitation_intensity_error=0.01,
          precipitation_intensity_error_unit="in/hr"),
    point(8, precipitation_intensity=2.0, precipitation_type="hail"),
    point(9, precipitation_intensity=0.7, precipitation_type="ice"),
    point(10, precipitation_intensity=0.3, precipitation_type="drizzle",
          precipitation_probability=0.005),
    point(11, precipitation_intensity=0.0004, precipitation_probability=0.025),
] + [
    point(m, precipitation_intensity=0.1 * (m % 7), precipitation_probability=(m % 10) / 10,
          precipitation_type="rain" if m % 3 else None)
    for m in range(12, 61)
]

PRECIP_CASES = [
    ("new york", "Philadelphia, PA", "America/New_York",
     MinutelyPrecipitationForecast(summary="  Light rain starting in 12 min.  ", points=POINTS)),
    ("tokyo", "Tokyo", "Asia/Tokyo",
     MinutelyPrecipitationForecast(summary="Rain stopping soon.", points=POINTS[:5])),
    ("no zone", "Somewhere", None,
     MinutelyPrecipitationForecast(summary=None, points=POINTS[2:6])),
    ("bad zone", "Mars", "Mars/Olympus_Mons",
     MinutelyPrecipitationForecast(summary="", points=POINTS[:3])),
    ("midnight", "Honolulu", "Pacific/Honolulu",
     MinutelyPrecipitationForecast(summary="Dry.", points=[
         MinutelyPrecipitationPoint(time=datetime(2026, 9, 25, 10, 0, tzinfo=UTC)),
         MinutelyPrecipitationPoint(time=datetime(2026, 9, 25, 22, 1, tzinfo=UTC)),
     ])),
    ("empty", "Nowhere", "UTC", MinutelyPrecipitationForecast(summary="Nothing", points=[])),
]


def precip_case(parent, name, location, tz, forecast) -> dict:
    case = {
        "name": name,
        "location": location,
        "timezone": tz,
        "forecast": forecast,
        "text": build_precipitation_timeline_text(forecast, tz),
    }
    case.update(record(PrecipitationTimelineDialog(
        parent, location_name=location, forecast=forecast, timezone_name=tz
    )))
    return case


# ---------------------------------------------------------------------------
# Air quality and UV index
# ---------------------------------------------------------------------------

def aq_hour(h, aqi, **kw):
    return HourlyAirQuality(
        timestamp=datetime(2026, 9, 25, h % 24, 0, tzinfo=NY), aqi=aqi, category="Good", **kw
    )


AQ_HOURS = [
    aq_hour(0, 42, pm2_5=8.25, pm10=15.0, ozone=61.349, nitrogen_dioxide=12.05,
            sulphur_dioxide=1.0, carbon_monoxide=210.55),
    *[aq_hour(h, 40 + h, pm2_5=5.0 + h) for h in range(1, 14)],
]

UV_HOURS = [
    HourlyUVIndex(timestamp=datetime(2026, 9, 25, 6 + h, 0, tzinfo=NY), uv_index=v,
                  category="Moderate")
    for h, v in enumerate([0.0, 0.4, 1.5, 2.5, 3.49, 5.5, 7.5, 8.2, 9.0, 10.5, 11.0, 6.0, 3.0,
                           1.0])
]

UPDATED = datetime(2026, 9, 25, 9, 5, tzinfo=NY)

ENVIRONMENTS = [
    ("none", None),
    ("empty", EnvironmentalConditions()),
    ("full airnow", EnvironmentalConditions(
        air_quality_index=42.5, air_quality_category="Good", air_quality_pollutant="pm2_5",
        air_quality_updated_at=datetime(2026, 9, 25, 14, 0, tzinfo=EDT),
        air_quality_reporting_area="  Philadelphia  ", air_quality_source="AirNow",
        hourly_air_quality=AQ_HOURS,
        uv_index=7.5, uv_category="High", hourly_uv_index=UV_HOURS, updated_at=UPDATED,
        sources=["AirNow", "Open-Meteo Air Quality", "Open-Meteo Air Quality", "Pollen.com"],
    )),
    ("category only", EnvironmentalConditions(
        air_quality_category="Moderate", air_quality_pollutant="OZONE", pollen_index=3.0,
        uv_category="Moderate", updated_at=datetime(2026, 1, 5, 0, 30, tzinfo=UTC),
        sources=["Open-Meteo"],
    )),
    ("measurements missing", EnvironmentalConditions(
        air_quality_index=150.0, air_quality_category="Unhealthy for Sensitive Groups",
        air_quality_pollutant="NO2", air_quality_source="Open-Meteo Air Quality",
        hourly_air_quality=[aq_hour(12, 150)], uv_index=3.2,
    )),
    ("no2 dominant", EnvironmentalConditions(
        air_quality_index=99.0, air_quality_category="Moderate",
        air_quality_pollutant="no2",
        hourly_air_quality=[aq_hour(3, 99, nitrogen_dioxide=40.0, carbon_monoxide=300.0)],
        uv_category="Unknown Category", hourly_uv_index=UV_HOURS[:3],
    )),
    ("uv only", EnvironmentalConditions(uv_index=0.5, hourly_uv_index=UV_HOURS[:2])),
    ("aq only", EnvironmentalConditions(air_quality_index=301.5,
                                        air_quality_category="Hazardous",
                                        air_quality_pollutant="Smoke")),
    ("sources airnow", EnvironmentalConditions(
        air_quality_index=12.0, air_quality_category="Very Unhealthy",
        air_quality_reporting_area="   ",
        sources=["  ", "airnow.gov", "Open-Meteo Air Quality", "CAMS", "air quality lab"],
        uv_category="Extreme", uv_index=11.5,
    )),
    ("unknown category", EnvironmentalConditions(
        air_quality_index=55.0, air_quality_category="Mystery", air_quality_source="  ",
        sources=["Pirate", "Pirate", "Open-Meteo"], uv_category="Very High",
    )),
    ("uv category only", EnvironmentalConditions(uv_category="Low", pollen_tree_index=1.0)),
]


def env_case(parent, name, env) -> dict:
    location = "Philadelphia, PA"
    return {
        "name": name,
        "location": location,
        "environmental": env,
        "air_quality": record(AirQualityDialog(parent, location, env, None)),
        "uv_index": record(UVIndexDialog(parent, location, env, None)),
    }


# ---------------------------------------------------------------------------
# Aviation
# ---------------------------------------------------------------------------

def stub_app(avwx_key):
    settings = SimpleNamespace(avwx_api_key=avwx_key)
    return SimpleNamespace(config_manager=SimpleNamespace(get_settings=lambda: settings))


CODES = ["", "   ", "kjf", "kjfk", " egll ", "K1FK", "KJFKX", "ßabc", "ﬀab", "k j f"]

SIGMETS = [
    {"event": "Convective SIGMET 45E", "description": "  Embedded thunderstorms.  ",
     "startTime": "2026-09-25T14:55:00Z", "endTime": "2026-09-25T16:55:00Z"},
    {"event": "", "name": "SIGMET NOVEMBER 3", "summary": "Severe turbulence " * 20,
     "expires": "2026-09-25T18:00:00Z"},
    {"hazard": "ICE", "text": "\n", "validTimeStart": "2026-09-25T12:00:00Z"},
    {"issueTime": 1790000000, "validUntil": 1790003600},
    {"beginTime": 1.5},
    {"description": None, "summary": "", "text": "Mountain obscuration."},
] + [{"event": f"SIGMET {i}", "validTimeEnd": f"T{i}"} for i in range(6)]

CWAS = [
    {"event": "CWA 101", "description": "IFR conditions", "startTime": "a", "expires": "b"},
    {},
]

AVIATION_CASES = [
    ("none", "KJFK", None),
    ("blank taf", "KJFK", AviationData(raw_taf=None, decoded_taf="   ", station_id="KJFK")),
    ("full", "KJFK", AviationData(
        raw_taf="TAF KJFK 251720Z 2518/2624 20012KT P6SM FEW250",
        decoded_taf="Forecast for KJFK\nWinds from 200 at 12 knots.",
        station_id="KJFK", airport_name="John F Kennedy International Airport",
        active_sigmets=SIGMETS, active_cwas=CWAS,
    )),
    ("raw only", "EGLL", AviationData(raw_taf="TAF EGLL NIL", station_id="EGLL")),
    ("decoded only", "LFPG", AviationData(decoded_taf="Decoded only.", active_cwas=CWAS[:1])),
    ("cwas only", "KORD", AviationData(raw_taf="TAF KORD", decoded_taf="",
                                       airport_name="", station_id="",
                                       active_cwas=CWAS)),
]


def aviation_state(dlg) -> dict:
    items = dlg.advisories_list
    return {
        "status": dlg.status_label.GetLabel(),
        "status_gray": dlg.status_label.GetForegroundColour()
        == wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT),
        "raw": dlg.raw_taf_display.GetValue(),
        "decoded": dlg.decoded_taf_display.GetValue(),
        "rows": [
            [items.GetItemText(r, c) for c in range(4)] for r in range(items.GetItemCount())
        ],
        "info": dlg.advisories_info.GetLabel(),
        "fetch_enabled": dlg.fetch_button.IsEnabled(),
    }


def aviation_cases(parent) -> dict:
    dlg = AviationDialog(parent, stub_app("secret-key"))
    try:
        initial = {"title": dlg.GetTitle(), "controls": controls(dlg),
                   "focus": focus_index(dlg), **aviation_state(dlg)}
        validation = []
        for code in CODES:
            dlg.station_input.SetValue(code)
            dlg.status_label.SetLabel("unchanged")
            dlg._on_fetch(None)
            status = dlg.status_label.GetLabel()
            valid = status == "Weather client is not ready. Try again after initialization."
            validation.append({"input": code, "valid": valid,
                               "status": None if valid else status})
        fetches = []
        for name, code, aviation in AVIATION_CASES:
            dlg._on_fetch_complete(code, aviation)
            fetches.append({"name": name, "code": code, "aviation": aviation,
                            **aviation_state(dlg)})
        dlg._on_fetch_error("KJFK", "boom")
        error = aviation_state(dlg)
    finally:
        dlg.Destroy()
    return {"initial": initial, "validation": validation, "fetches": fetches, "error": error}


def main() -> None:
    app = wx.App()
    parent = wx.Frame(None)
    parent.Hide()
    try:
        data = {
            "history": [history_case(parent, *c) for c in HISTORY_CASES],
            "precipitation": [precip_case(parent, *c) for c in PRECIP_CASES],
            "environmental": [env_case(parent, *c) for c in ENVIRONMENTS],
            "aviation": aviation_cases(parent),
        }
    finally:
        parent.Destroy()
        del app
    write("dataui", "cases", data)


if __name__ == "__main__":
    main()
