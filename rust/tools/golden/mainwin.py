"""Golden parity data for the Rust main window (ui/main_window_*.py, location dialogs).

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/mainwin.py

Drives the real Python mixins on plain stub objects (no wx.App, no display)
and writes rust/testdata/golden/mainwin/cases.json.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import wx

from accessiweather.alert_lifecycle import compute_lifecycle_labels
from accessiweather.config.locations import LocationOperations
from accessiweather.location_manager import LocationManager
from accessiweather.location_sorting import sort_locations_for_display
from accessiweather.models import AppConfig, AppSettings
from accessiweather.models.alerts import WeatherAlert
from accessiweather.models.weather import (
    CurrentConditions,
    Location,
    WeatherAlerts,
    WeatherData,
)
from accessiweather.ui import main_window_display
from accessiweather.ui.dialogs.location_dialog import _edit_location_is_us
from accessiweather.ui.main_window_commands import MainWindowCommandMixin
from accessiweather.ui.main_window_display import MainWindowDisplayMixin
from accessiweather.ui.main_window_locations import MainWindowLocationMixin
from accessiweather.ui.main_window_refresh import MainWindowRefreshMixin
from accessiweather.ui.main_window_ui import MainWindowUIMixin

OUT = Path(__file__).resolve().parents[2] / "testdata" / "golden" / "mainwin" / "cases.json"


def jsonable(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.astimezone()).isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set | frozenset):
        return sorted(jsonable(v) for v in value)
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    return value


class Rec:
    """Records every wx call made on a stub widget."""

    def __init__(self, log=None, name=""):
        self.calls = []
        self._log = log
        self._name = name

    def __getattr__(self, attr):
        def method(*args, **kwargs):
            self.calls.append([attr, *args])
            if attr == "SetFocus" and self._log is not None:
                self._log.append(self._name)

        return method

    def last(self, attr):
        for call in reversed(self.calls):
            if call[0] == attr:
                return call[1:]
        return None


class FixedDatetime(datetime):
    fixed: datetime = datetime(2026, 1, 1, 9, 5)

    @classmethod
    def now(cls, tz=None):
        return cls.fixed


def alert(**kw) -> WeatherAlert:
    kw.setdefault("title", kw.get("event") or "Alert")
    kw.setdefault("description", "Details")
    return WeatherAlert(**kw)


FUTURE = datetime(2099, 1, 1, tzinfo=UTC)
PAST = datetime(2000, 1, 1, tzinfo=UTC)

ALERTS = [
    alert(
        event="Dense Fog Advisory", severity="Moderate", id="a1", source="NWS", message_type="Alert"
    ),
    alert(
        event="Wind Advisory",
        severity="Minor",
        id="a2",
        source="NWS",
        message_type="Update",
        expires=FUTURE,
    ),
    alert(event="Heat Advisory", severity="Severe", id="a3", source="NWS", message_type="Cancel"),
    alert(
        event="Flood Watch",
        severity="Extreme",
        id="a4",
        source="VisualCrossing",
        message_type="Alert",
    ),
    alert(
        event="Old Warning",
        severity="Severe",
        id="a5",
        source="NWS",
        message_type="Alert",
        expires=PAST,
    ),
    alert(
        title="No event", severity="Unknown", source="NWS", message_type="alert", areas=["B", "A"]
    ),
]


def case_alert_items():
    active = WeatherAlerts(alerts=ALERTS).get_active_alerts()
    labels = compute_lifecycle_labels(active)
    cases = []
    for use_labels in (True, False):
        stub = SimpleNamespace(alerts_list=Rec(), view_alert_button=Rec())
        MainWindowDisplayMixin._update_alerts(
            stub, WeatherAlerts(alerts=ALERTS), labels if use_labels else {}
        )
        cases.append(
            {
                "use_labels": use_labels,
                "items": (stub.alerts_list.last("Append") or [[]])[0],
                "button_enabled": stub.view_alert_button.calls[-1][0] == "Enable",
            }
        )
    empty = SimpleNamespace(alerts_list=Rec(), view_alert_button=Rec())
    MainWindowDisplayMixin._update_alerts(empty, WeatherAlerts(alerts=[]), {})
    cases.append({"use_labels": False, "items": [], "button_enabled": False, "empty": True})
    assert empty.view_alert_button.calls[-1][0] == "Disable"
    return {"alerts": jsonable(ALERTS), "labels": labels, "cases": cases}


def weather(
    loc, *, temp_f=None, temp_c=None, condition=None, alerts=None, stale=False, current=True
):
    data = WeatherData(location=loc)
    if current:
        data.current = CurrentConditions(
            temperature_f=temp_f, temperature_c=temp_c, condition=condition
        )
    if alerts is not None:
        data.alerts = WeatherAlerts(alerts=alerts)
    data.stale = stale
    return data


def summary_stub(locations, cached, settings, current=None):
    class Stub(MainWindowUIMixin, MainWindowDisplayMixin):
        pass

    stub = Stub()
    stub.app = SimpleNamespace(
        config_manager=SimpleNamespace(
            get_all_locations=lambda: list(locations),
            get_settings=lambda: settings,
            get_current_location=lambda: current,
        ),
        weather_client=SimpleNamespace(get_cached_weather=lambda loc: cached.get(loc.name)),
        update_tray_tooltip=lambda *a: None,
        is_updating=True,
    )
    for name in (
        "current_conditions",
        "alerts_list",
        "view_alert_button",
        "stale_warning_label",
        "refresh_button",
        "daily_forecast_display",
        "hourly_forecast_display",
        "_daily_forecast_label",
        "_hourly_forecast_label",
    ):
        setattr(stub, name, Rec())
    stub.GetSizer = lambda: None
    stub._show_all_locations_summary()
    return stub


def case_all_locations():
    philly = Location("Philadelphia, PA", 39.95, -75.16, country_code="US")
    london = Location("London", 51.5, -0.12, country_code="GB")
    austin = Location("austin", 30.27, -97.74, country_code="US")
    nowhere = Location("Zed", 10.0, 10.0)
    locations = [philly, london, austin, nowhere]
    cached = {
        philly.name: weather(
            philly, temp_f=72.5, temp_c=22.5, condition="Sunny", alerts=ALERTS[:3]
        ),
        london.name: weather(london, temp_c=11.0, condition=None, alerts=[], stale=True),
        austin.name: weather(austin, current=False, alerts=[ALERTS[3]]),
    }
    # austin: has_any_data (an alert) but current is None -> "No cached data" branch.
    austin_data = cached[austin.name]
    austin_data.current = CurrentConditions()
    cases = []
    for unit, round_values, sort_order in (
        ("both", False, "alphabetical"),
        ("f", True, "manual"),
        ("auto", False, "alphabetical"),
        ("celsius", False, "manual"),
    ):
        settings = SimpleNamespace(
            temperature_unit=unit, round_values=round_values, location_sort_order=sort_order
        )
        stub = summary_stub(locations, cached, settings, current=philly)
        cases.append(
            {
                "temperature_unit": unit,
                "round_values": round_values,
                "location_sort_order": sort_order,
                "text": stub.current_conditions.last("SetValue")[0],
                "alert_items": (stub.alerts_list.last("Append") or [[]])[0],
                "button_enabled": stub.view_alert_button.calls[-1][0] == "Enable",
            }
        )
    empty = summary_stub([], {}, SimpleNamespace(temperature_unit="both", round_values=False))
    return {
        "locations": jsonable(locations),
        "current": jsonable(philly),
        "cached": {k: jsonable(v) for k, v in cached.items()},
        "cases": cases,
        "empty_text": empty.current_conditions.last("SetValue")[0],
    }


def case_panels():
    ns = SimpleNamespace
    presentations = [
        {
            "current_conditions": {"fallback_text": "Sunny, 72F"},
            "source_attribution": {"summary_text": "Data from NWS."},
            "status_messages": ["Showing cached data.", "Refresh failed."],
            "forecast": {
                "daily_section_text": "Today: Sunny.\n",
                "hourly_section_text": "Next hours...",
                "marine_section_text": "Marine: calm.",
                "mobility_briefing": "Rain starts at 5 PM.",
            },
        },
        {
            "current_conditions": {"fallback_text": ""},
            "source_attribution": {"summary_text": ""},
            "status_messages": [],
            "forecast": {
                "daily_section_text": "",
                "hourly_section_text": "",
                "marine_section_text": "",
                "mobility_briefing": None,
            },
        },
        {
            "current_conditions": None,
            "source_attribution": None,
            "status_messages": ["Stale."],
            "forecast": None,
        },
        {
            "current_conditions": {"fallback_text": "Cloudy"},
            "source_attribution": None,
            "status_messages": [],
            "forecast": {
                "daily_section_text": "",
                "hourly_section_text": "H",
                "marine_section_text": "Marine only  \n\n",
                "mobility_briefing": "",
            },
        },
    ]

    def to_ns(p):
        return ns(
            current_conditions=ns(**p["current_conditions"]) if p["current_conditions"] else None,
            source_attribution=ns(**p["source_attribution"]) if p["source_attribution"] else None,
            status_messages=p["status_messages"],
            forecast=ns(**p["forecast"]) if p["forecast"] else None,
        )

    class Stub(MainWindowRefreshMixin, MainWindowDisplayMixin):
        def _process_notification_events(self, data):
            pass

        def _set_last_updated_status(self, when=None):
            pass

        def _update_precipitation_timeline_menu_state(self, data=None):
            pass

    FixedDatetime.fixed = datetime(2026, 1, 1, 17, 4)
    main_window_display.datetime = FixedDatetime
    cases = []
    for p in presentations:
        stub = Stub()
        presentation = to_ns(p)
        stub.app = SimpleNamespace(
            presenter=SimpleNamespace(present=lambda d, pr=presentation: pr),
            alert_notification_system=None,
            update_tray_tooltip=lambda *a: None,
            config_manager=SimpleNamespace(get_current_location=lambda: None),
            is_updating=True,
        )
        for name in (
            "current_conditions",
            "stale_warning_label",
            "daily_forecast_display",
            "hourly_forecast_display",
            "event_center_display",
            "alerts_list",
            "view_alert_button",
            "refresh_button",
        ):
            setattr(stub, name, Rec())
        stub._alert_lifecycle_labels = {}
        stub._on_weather_data_received(
            WeatherData(location=Location("X", 1.0, 2.0)), play_refresh_sound=False
        )
        cases.append(
            {
                "presentation": p,
                "current": stub.current_conditions.last("SetValue")[0],
                "stale_warning": stub.stale_warning_label.last("SetLabel")[0],
                "daily": stub.daily_forecast_display.last("SetValue")[0],
                "hourly": stub.hourly_forecast_display.last("SetValue")[0],
                "event_center": [c[1] for c in stub.event_center_display.calls],
            }
        )
    return cases


def case_sections():
    out = []
    for visible in (True, False):
        log: list[str] = []

        class Stub(MainWindowDisplayMixin):
            pass

        stub = Stub()
        stub._event_center_visible = visible
        stub.location_dropdown = Rec(log, "Location")
        stub.current_conditions = Rec(log, "Current conditions")
        stub.hourly_forecast_display = Rec(log, "Hourly / near-term")
        stub.daily_forecast_display = Rec(log, "Daily forecast")
        stub.alerts_list = Rec(log, "Alerts")
        stub.event_center_display = Rec(log, "Event Center")
        numbers = {}
        for n in range(1, 6):
            log.clear()
            stub.focus_section_by_number(n)
            numbers[str(n)] = log[0] if log else None
        log.clear()
        for _ in range(8):
            stub.cycle_section_focus()
        out.append(
            {
                "event_center_visible": visible,
                "sections": [label for label, _w in stub.get_visible_top_level_sections()],
                "numbers": numbers,
                "cycle": list(log),
            }
        )
    return out


def case_clock():
    out = []
    for hour, minute in ((9, 5), (12, 30), (0, 15), (23, 59), (13, 0)):
        FixedDatetime.fixed = datetime(2026, 3, 4, hour, minute)
        main_window_display.datetime = FixedDatetime
        entries = []
        for text, category in (("Hello", None), ("Rain soon", "Briefing"), ("", "X")):
            stub = SimpleNamespace(event_center_display=Rec())
            MainWindowDisplayMixin.append_event_center_entry(stub, text, category=category)
            entries.append(
                {
                    "text": text,
                    "category": category,
                    "entry": stub.event_center_display.calls[0][1]
                    if stub.event_center_display.calls
                    else None,
                }
            )
        bar = Rec()
        stub = SimpleNamespace(GetStatusBar=lambda bar=bar: bar)
        MainWindowDisplayMixin._set_last_updated_status(stub, FixedDatetime.fixed)
        out.append(
            {
                "hour": hour,
                "minute": minute,
                "entries": entries,
                "last_updated": bar.last("SetStatusText")[0],
            }
        )
    return out


def case_titles():
    out = []
    for name in (None, "", "All Locations", "Philadelphia, PA"):
        titles: list[str] = []
        stub = SimpleNamespace(SetTitle=titles.append)
        MainWindowUIMixin._update_title_for_location(stub, name)
        out.append({"name": name, "title": titles[0]})
    return out


def case_sorting():
    locs = [
        Location("boston", 42.36, -71.06),
        Location("Austin", 30.27, -97.74),
        Location("Chicago", 41.88, -87.63),
        Location("austin", 30.0, -97.0),
        Location("Denver", 39.74, -104.99),
    ]
    anchor = Location("Chicago", 41.88, -87.63)
    out = []
    for order in ("alphabetical", "manual", "nearest_current", "bogus", None):
        for use_anchor in (True, False):
            result = sort_locations_for_display(locs, order, anchor=anchor if use_anchor else None)
            out.append(
                {
                    "order": order,
                    "anchor": use_anchor,
                    "names": [loc.name for loc in result],
                }
            )
    return {"locations": jsonable(locs), "anchor": jsonable(anchor), "cases": out}


def case_location_manager():
    manager = LocationManager()
    coords = [(39.9526, -75.1652), (-33.8688, 151.2093), (0.0, 0.0), (51.123456, -0.00004)]
    formatted = [
        {"lat": lat, "lon": lon, "text": manager.format_coordinates(lat, lon)}
        for lat, lon in coords
    ]
    a = Location("A", 39.9526, -75.1652)
    b = Location("B", 40.7128, -74.0060)
    c = Location("C", -33.8688, 151.2093)
    distances = [
        {"a": jsonable(x), "b": jsonable(y), "miles": f"{manager.calculate_distance(x, y):.2f}"}
        for x, y in ((a, b), (a, c), (a, a))
    ]
    is_us = [
        {"location": jsonable(loc), "is_us": _edit_location_is_us(loc)}
        for loc in (
            Location("x", 45.0, -75.0, country_code="us"),
            Location("x", 40.0, -100.0, country_code="CA"),
            Location("Victoria", 48.43, -123.37),
            Location("Toronto", 43.65, -79.38),
            Location("Anchorage", 61.2, -149.9),
            Location("Honolulu", 21.3, -157.8),
            Location("London", 51.5, -0.12),
        )
    ]
    return {"formatted": formatted, "distances": distances, "is_us": is_us}


def case_location_ops():
    config = AppConfig.from_dict(
        {
            "settings": {},
            "locations": [
                {
                    "name": "Home",
                    "latitude": 39.95,
                    "longitude": -75.16,
                    "country_code": "US",
                    "timezone": "America/New_York",
                    "forecast_zone_id": "PAZ106",
                    "cwa_office": "PHI",
                    "county_zone_id": "PAC101",
                    "fire_zone_id": "PAZ106",
                    "radar_station": "KDIX",
                }
            ],
            "current_location": None,
        }
    )
    manager = SimpleNamespace(
        get_config=lambda: config,
        save_config=lambda: True,
        _get_logger=lambda: logging.getLogger("golden"),
    )
    ops = LocationOperations(manager)
    initial = config.to_dict()
    steps = [
        ["add_location", "Work", 40.0, -75.0, "us", False],
        ["add_location", "Beach", 39.3, -74.5, None, True],
        ["add_location", "Work", 1.0, 1.0, None, False],
        ["add_location", "Bad", 95.0, 0.0, None, False],
        ["set_current_location", "Home"],
        ["set_current_location", "Nowhere"],
        ["update_location_details", "Home", 39.95, -75.16, "US", True, "Home Sweet Home"],
        ["update_location_details", "Home Sweet Home", 40.5, -75.5, None, False, "Home Sweet Home"],
        ["update_location_details", "Work", 40.0, -75.0, "US", False, "Beach"],
        ["update_location_details", "Work", 40.0, -75.0, "US", False, "  "],
        ["reorder_locations", ["Beach", "Home Sweet Home", "Work"]],
        ["reorder_locations", ["Beach", "Work"]],
        ["reorder_locations", ["Beach", "Home Sweet Home", "Work"]],
        ["remove_location", "Home Sweet Home"],
        ["remove_location", "Missing"],
        ["remove_location", "Beach"],
        ["remove_location", "Work"],
        ["add_location", "Solo", 10.0, 10.0, None, False],
    ]
    out = []
    for step in steps:
        name, *args = step
        if name == "update_location_details":
            loc, lat, lon, cc, marine, display = args
            result = ops.update_location_details(
                loc,
                latitude=lat,
                longitude=lon,
                country_code=cc,
                marine_mode=marine,
                display_name=display,
            )
        elif name == "add_location":
            loc, lat, lon, cc, marine = args
            result = ops.add_location(loc, lat, lon, country_code=cc, marine_mode=marine)
        else:
            result = getattr(ops, name)(*args)
        data = config.to_dict()
        out.append(
            {
                "step": step,
                "result": result,
                "locations": data["locations"],
                "current_location": data["current_location"],
            }
        )
    return {
        "initial": {k: initial[k] for k in ("locations", "current_location")},
        "steps": out,
    }


def case_messages():
    captured = []

    def fake_box(message, caption, style=0, parent=None):
        kinds = [
            name
            for name, flag in (
                ("yes_no", wx.YES_NO),
                ("warning", wx.ICON_WARNING),
                ("question", wx.ICON_QUESTION),
                ("information", wx.ICON_INFORMATION),
                ("error", wx.ICON_ERROR),
            )
            if style & flag == flag
        ]
        captured.append({"message": message, "caption": caption, "style": kinds})
        return wx.NO

    wx.MessageBox = fake_box

    class Stub(MainWindowLocationMixin, MainWindowCommandMixin):
        pass

    def stub_with(selection, locations):
        stub = Stub()
        stub.location_dropdown = SimpleNamespace(GetStringSelection=lambda: selection)
        stub.app = SimpleNamespace(
            config_manager=SimpleNamespace(
                get_all_locations=lambda: locations,
                get_current_location=lambda: None,
                get_settings=lambda: AppSettings(),
                config_dir="C:\\Config",
            ),
            _portable_mode=True,
        )
        return stub

    one = [Location("Home", 1.0, 2.0)]
    two = [Location("Home", 1.0, 2.0), Location("Work", 3.0, 4.0)]
    stub_with("All Locations", two).on_edit_location()
    stub_with("All Locations", two).on_remove_location()
    stub_with("Home", one).on_remove_location()
    stub_with("Work", two).on_remove_location()
    stub_with("Home", one).on_reorder_locations()
    stub_with("Home", one)._on_forecast_products()
    import accessiweather

    about = stub_with("Home", one)
    version = accessiweather.__version__
    about._on_about()
    about.app._portable_mode = False
    about._on_about()
    return {"version": version, "boxes": captured}


def case_check_updates():
    out = []
    for channel in ("stable", "nightly", "dev", "beta-test", "rc2x"):
        item = Rec()
        stub = SimpleNamespace(
            _check_updates_item=item,
            app=SimpleNamespace(
                config_manager=SimpleNamespace(
                    get_settings=lambda channel=channel: SimpleNamespace(update_channel=channel)
                )
            ),
        )
        stub._get_update_channel = lambda stub=stub: MainWindowCommandMixin._get_update_channel(
            stub
        )
        MainWindowCommandMixin.update_check_updates_menu_label(stub)
        out.append({"channel": channel, "label": item.last("SetItemLabel")[0]})
    return out


def main():
    data = {
        "alert_items": case_alert_items(),
        "all_locations": case_all_locations(),
        "panels": case_panels(),
        "sections": case_sections(),
        "clock": case_clock(),
        "titles": case_titles(),
        "sorting": case_sorting(),
        "location_manager": case_location_manager(),
        "location_ops": case_location_ops(),
        "messages": case_messages(),
        "check_updates": case_check_updates(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
