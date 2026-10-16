"""Golden parity data for the Rust alert dialogs (ui/dialogs/alert_dialog.py, alerts_summary_dialog.py).

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/alertui.py

Builds the real dialogs under a hidden frame (never shown, no main loop) and
records their title, controls in creation (tab) order with the text each
field shows, and the focused control, plus the combined / copy text for
several date and time settings and the summary dialog text.
Writes rust/testdata/golden/alertui/cases.json.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import wx

from accessiweather.models import AppSettings
from accessiweather.models.alerts import WeatherAlert
from accessiweather.ui.dialogs.alert_dialog import AlertDialog
from accessiweather.ui.dialogs.alerts_summary_dialog import AlertsSummaryDialog

OUT = Path(__file__).resolve().parents[2] / "testdata" / "golden" / "alertui" / "cases.json"

EDT = timezone(timedelta(hours=-4))
UTC = UTC

ALERTS = [
    # A full NWS alert: wrapped description, instruction, both times.
    WeatherAlert(
        title="Frost Advisory issued April 18 at 2:10PM EDT",
        description=(
            "* WHAT...Temperatures as low as 30 will result in frost\n"
            "formation.\n\n"
            "* WHERE...Portions of southeast Michigan.\n\n"
            "* WHEN...From 2 AM to 10 AM EDT Saturday."
        ),
        severity="Minor",
        urgency="Expected",
        certainty="Likely",
        event="Frost Advisory",
        headline="Frost Advisory issued April 18 at 2:10PM EDT until April 19 at 10:00AM EDT",
        instruction="Take steps now to protect tender plants from the cold.",
        sent=datetime(2026, 4, 18, 14, 10, tzinfo=EDT),
        expires=datetime(2026, 4, 19, 10, 0, tzinfo=EDT),
        areas=["Wayne", "Oakland"],
        id="urn:oid:frost-1",
    ),
    # No headline (event is the subject), no instruction, only "sent", AM time.
    WeatherAlert(
        title="Wind Advisory",
        description="West winds 25 to 35 mph with gusts up to 50 mph.",
        severity="Moderate",
        urgency="Immediate",
        certainty="Observed",
        event="Wind Advisory",
        sent=datetime(2026, 4, 8, 9, 5, tzinfo=EDT),
    ),
    # Nothing but the required fields: event None, empty description.
    WeatherAlert(title="Untitled", description=""),
    # Empty strings everywhere: info field and details are omitted.
    WeatherAlert(
        title="t",
        description="",
        severity="",
        urgency="",
        certainty="",
        event="Special Weather Statement",
        headline="",
        instruction="",
        expires=datetime(2026, 12, 31, 0, 5, tzinfo=UTC),
    ),
    # Only some metadata, instruction without description, midnight/noon times.
    WeatherAlert(
        title="Heat Advisory",
        description="",
        severity="Severe",
        urgency="",
        certainty="Possible",
        event="",
        headline="Heat Advisory until 8 PM",
        instruction="Drink plenty of fluids.\nStay in an air-conditioned room.",
        sent=datetime(2026, 7, 4, 12, 30, tzinfo=UTC),
        expires=datetime(2026, 7, 5, 0, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    ),
    # Non-ASCII text.
    WeatherAlert(
        title="Avertissement",
        description="Pluie verglaçante — prudence sur les routes.",
        severity="Moderate",
        event="Avertissement de pluie verglaçante",
        headline="Pluie verglaçante prévue cette nuit",
    ),
]

SETTINGS = [
    {"date_format": "iso", "time_format_12hour": True},
    {"date_format": "iso", "time_format_12hour": False},
    {"date_format": "us_short", "time_format_12hour": True},
    {"date_format": "us_long", "time_format_12hour": True},
    {"date_format": "eu", "time_format_12hour": False},
    {"date_format": "bogus", "time_format_12hour": True},
]

SUMMARY_BATCHES = [[0, 1], [2, 3, 4, 5], [1]]


def jsonable(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.astimezone()).isoformat()
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    return value


def controls(dlg) -> list[dict]:
    """The dialog panel's children in creation (tab) order."""
    (panel,) = dlg.GetChildren()
    out = []
    for child in panel.GetChildren():
        if isinstance(child, wx.Button):
            out.append(
                {
                    "kind": "button",
                    "id": child.GetId(),
                    "label": child.GetLabel(),
                    "name": child.GetName(),
                }
            )
        elif isinstance(child, wx.TextCtrl):
            out.append({"kind": "text", "name": child.GetName(), "value": child.GetValue()})
        elif isinstance(child, wx.StaticText):
            bold = child.GetFont().GetWeight() == wx.FONTWEIGHT_BOLD
            out.append({"kind": "label", "label": child.GetLabel(), "bold": bold})
        else:
            raise TypeError(type(child))
    return out


def alert_case(parent, alert) -> dict:
    case = {"alert": jsonable(alert)}
    for style in ("separate", "combined"):
        dlg = AlertDialog(parent, alert, AppSettings(alert_display_style=style))
        try:
            case["title"] = dlg.GetTitle()
            case[f"{style}_controls"] = controls(dlg)
            focused = wx.Window.FindFocus()
            case[f"{style}_focus"] = focused.GetName() if focused else None
        finally:
            dlg.Destroy()
    view = type("View", (), {"alert": alert})()
    case["subject"] = AlertDialog._build_subject_text(view)
    case["info"] = AlertDialog._build_info_text(view)
    case["combined"] = [AlertDialog._build_combined_text(alert, AppSettings(**s)) for s in SETTINGS]
    case["copy"] = [AlertDialog._copy_payload(alert, AppSettings(**s)) for s in SETTINGS]
    return case


def summary_case(parent, indices) -> dict:
    alerts = [ALERTS[i] for i in indices]
    dlg = AlertsSummaryDialog(parent, alerts)
    try:
        return {
            "alerts": indices,
            "title": dlg.GetTitle(),
            "controls": controls(dlg),
            "text": dlg._build_summary_text(),
        }
    finally:
        dlg.Destroy()


def main() -> None:
    app = wx.App()
    parent = wx.Frame(None)
    parent.Hide()
    try:
        data = {
            "settings": SETTINGS,
            "alerts": [alert_case(parent, a) for a in ALERTS],
            "summaries": [summary_case(parent, b) for b in SUMMARY_BATCHES],
        }
    finally:
        parent.Destroy()
        del app
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
