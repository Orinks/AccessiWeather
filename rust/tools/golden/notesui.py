"""Golden parity data for the Rust Forecaster Notes dialogs (aw-app ui::forecast_products).

Run from the Python checkout:

    uv run python <worktree>/rust/tools/golden/notesui.py

Drives the real panel and dialog code (forecast_product_panel.py,
forecast_product_widgets.py, forecast_product_formatting.py,
forecast_products_dialog.py, national_products_dialog.py,
advanced_text_product_dialog.py) on stub objects with a recording fake of the
wx widgets (no wx.App, no display) and writes
rust/testdata/golden/notesui/cases.json.
"""

from __future__ import annotations

import inspect
import json
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import wx as real_wx

import accessiweather.ui.dialogs.advanced_text_product_dialog as atp
import accessiweather.ui.dialogs.forecast_product_formatting as fmt
import accessiweather.ui.dialogs.forecast_product_panel as fpp
import accessiweather.ui.dialogs.forecast_product_widgets as fpw
import accessiweather.ui.dialogs.forecast_products_dialog as fpd
import accessiweather.ui.dialogs.national_products_dialog as npd
from accessiweather.models import AppSettings, Location, TextProduct

OUT = Path(__file__).resolve().parents[2] / "testdata" / "golden" / "notesui" / "cases.json"

# ---------------------------------------------------------------------------
# Recording fake of the wx widgets
# ---------------------------------------------------------------------------

ID_NAMES = {real_wx.ID_OK: "OK", real_wx.ID_CLOSE: "CLOSE"}
TEXT_KINDS = {"StaticText", "Button", "CheckBox", "TextCtrl"}
CREATED: list[list[str]] = []


class Widget:
    def __init__(self, parent=None, id=-1, *, label=None, value=None, choices=None, **_kwargs):
        self.label = label or ""
        self.value = value or ""
        self.items = list(choices or [])
        self.selection = -1
        self.shown = True
        self.enabled = True
        self.focus = False
        self.focused = 0
        self.pages: list[str] = []
        kind = type(self).__name__
        if kind in TEXT_KINDS:
            text = self.value if kind == "TextCtrl" else self.label
            CREATED.append([kind + (f"#{ID_NAMES[id]}" if id in ID_NAMES else ""), text])

    def Show(self, show=True):
        self.shown = bool(show)

    def Hide(self):
        self.shown = False

    def Enable(self, enable=True):
        self.enabled = bool(enable)

    def Disable(self):
        self.enabled = False

    def HasFocus(self):
        return self.focus

    def SetFocus(self):
        self.focused += 1

    def SetValue(self, value):
        self.value = value

    def GetValue(self):
        return self.value

    def SetLabel(self, label):
        self.label = label

    def Clear(self):
        self.items = []
        self.selection = -1

    def Append(self, item):
        self.items.append(item)

    def SetSelection(self, index):
        self.selection = index

    def GetSelection(self):
        return self.selection

    def SetName(self, name):
        self.name = name

    def SetToolTip(self, tooltip):
        self.tooltip = tooltip

    def SetScrollRate(self, *_args):
        pass

    def FitInside(self):
        pass

    def SetSizer(self, sizer):
        self.sizer = sizer

    def AddPage(self, _page, label, *_args):
        self.pages.append(label)

    def Bind(self, *_args, **_kwargs):
        pass


def widget_class(name):
    return type(name, (Widget,), {})


class BoxSizer:
    def __init__(self, *_args):
        pass

    def Add(self, *_args, **_kwargs):
        pass

    def AddStretchSpacer(self, *_args):
        pass

    def Show(self, item, show=True):
        item.Show(show)

    def Layout(self):
        pass


FakeWx = SimpleNamespace(
    BoxSizer=BoxSizer,
    Size=lambda *_args: None,
    **{
        name: widget_class(name)
        for name in [
            "StaticText",
            "Button",
            "CheckBox",
            "TextCtrl",
            "Choice",
            "ComboBox",
            "SpinCtrl",
            "Notebook",
            "ScrolledWindow",
        ]
    },
    **{
        name: getattr(real_wx, name)
        for name in [
            "VERTICAL",
            "HORIZONTAL",
            "ALL",
            "EXPAND",
            "LEFT",
            "RIGHT",
            "TOP",
            "BOTTOM",
            "TE_MULTILINE",
            "TE_READONLY",
            "HSCROLL",
            "CB_READONLY",
            "ID_OK",
            "ID_CLOSE",
        ]
    },
)
for module in (fpw, fpd, npd, atp):
    module.wx = FakeWx
atp._SPINCTRL = FakeWx.SpinCtrl
atp._COMBOBOX = FakeWx.ComboBox
atp._SCROLLED_WINDOW = FakeWx.ScrolledWindow


def borrow(cls, names=None):
    names = names or [n for n, v in vars(cls).items() if callable(v) and n != "__init__"]
    attrs = {name: inspect.getattr_static(cls, name) for name in names}
    return type(f"{cls.__name__}Stub", (), attrs)


def capture(build) -> list[list[str]]:
    CREATED.clear()
    build()
    return list(CREATED)


# ---------------------------------------------------------------------------
# Panel state machine
# ---------------------------------------------------------------------------

PanelStub = borrow(fpp.ForecastProductPanel)
# Pin formatting that depends on the machine's time zone; format_issuance is
# checked on its own below and SPS entries in aw-providers.
fpp._format_issuance = lambda t: "Issued: " + (t.isoformat() if t else "unknown")
fpp._format_sps_choice_entry = lambda p: f"{p.product_id}: {p.headline or ''}"

EVENTS: list[str] = []


def make_panel(product_type, cwa, has_key):
    p = PanelStub()
    p.product_type = product_type
    p._product_loader = lambda: None
    p._ai_explainer = None
    p._cwa_office = cwa
    p._location_name = "Raleigh"
    p._settings = AppSettings(ai_provider="openrouter", openrouter_api_key="key" if has_key else "")
    p._app = SimpleNamespace(config_manager=SimpleNamespace(get_settings=lambda: p._settings))
    p._availability_callback = lambda _panel, has: EVENTS.append(f"availability:{str(has).lower()}")
    p._advanced_lookup_opener = None
    p._current_text = None
    p._sps_products = []
    p._is_loading = False
    p._is_explaining = False
    p._load_started = False
    p._announcer = SimpleNamespace(announce=lambda message: EVENTS.append("announce:" + message))
    p._schedule_load = lambda _coro: EVENTS.append("load")
    p._schedule_explain = lambda text: EVENTS.append("explain:" + text)
    p.SetSizer = lambda _sizer: None
    fpw.create_product_panel_widgets(p)
    p.GetSizer = lambda: p._main_sizer
    return p


def view(p) -> dict:
    assert p.ai_summary_header.shown == p.ai_summary_display.shown
    assert p.model_info_label.shown == p.model_info.shown
    if p.sps_choice is not None:
        assert p.sps_choice_label.shown == p.sps_choice.shown
    choice = p.sps_choice
    return {
        "product_text": p.product_textctrl.value,
        "issuance": p.issuance_label.label,
        "sps_entries": choice.items if choice else [],
        "sps_selection": choice.selection if choice and choice.selection >= 0 else None,
        "sps_visible": bool(choice and choice.shown),
        "retry_visible": p.retry_button.shown,
        "ai_visible": p.ai_summary_display.shown,
        "ai_text": p.ai_summary_display.value,
        "model_info_visible": p.model_info.shown,
        "model_info": p.model_info.value,
        "explain_visible": p.explain_button.shown,
        "explain_enabled": p.explain_button.enabled,
        "regenerate_visible": p.regenerate_button.shown,
    }


def product(product_type, product_id, text, issued=None, headline=None, office="RAH"):
    return {
        "product_type": product_type,
        "product_id": product_id,
        "cwa_office": office,
        "issuance_time": issued,
        "product_text": text,
        "headline": headline,
    }


def text_product(spec):
    issued = spec["issuance_time"]
    return TextProduct(
        product_type=spec["product_type"],
        product_id=spec["product_id"],
        cwa_office=spec["cwa_office"],
        issuance_time=datetime.fromisoformat(issued) if issued else None,
        product_text=spec["product_text"],
        headline=spec["headline"],
    )


def apply(p, step):
    op = step["op"]
    if op == "ensure_loaded":
        p.ensure_loaded()
    elif op == "trigger_load":
        p._on_retry(None)
    elif op == "load_complete":
        result = step["result"]
        if isinstance(result, list):
            result = [text_product(r) for r in result]
        elif result is not None:
            result = text_product(result)
        p._on_load_complete(result)
    elif op == "load_error":
        p._on_load_error(RuntimeError("boom"))
    elif op == "sps_choice":
        p.sps_choice.selection = step["index"]
        p._on_sps_choice_changed(None)
    elif op == "explain":
        p._on_explain(None)
    elif op == "regenerate":
        p._on_regenerate(None)
    elif op == "explain_status":
        p._on_explain_status(step["message"])
    elif op == "explain_complete":
        s = step["summary"]
        p.explain_button.focus = step["explain_had_focus"]
        p._on_explain_complete(
            s["text"],
            s["model_used"],
            s["token_count"],
            s["estimated_cost"],
            s["cached"],
            s["model_selection_reason"],
            s["requested_model"],
            tuple(s["model_attempts"]),
        )
    elif op == "explain_error":
        p._on_explain_error(step["message"])
    elif op == "set_key":
        p._settings.openrouter_api_key = "key" if step["has_key"] else ""
    else:
        raise AssertionError(op)


def summary(text, model_used="openrouter/free", **extra):
    return {
        "text": text,
        "model_used": model_used,
        "token_count": 321,
        "estimated_cost": 0.0,
        "cached": False,
        "model_selection_reason": None,
        "requested_model": None,
        "model_attempts": [],
    } | extra


AFD = product("AFD", "afd-1", "AREA FORECAST DISCUSSION\nNWS Raleigh", "2026-05-01T15:00:00+00:00")
SPS = [
    product("SPS", f"sps-{i}", f"SPECIAL WEATHER STATEMENT {i}", f"2026-05-01T1{i}:00:00-04:00", h)
    for i, h in [(3, "Fog"), (2, None), (1, "Wind")]
]

SCENARIOS = [
    (
        "afd_with_key_summary_flow",
        "AFD",
        "RAH",
        True,
        [
            {"op": "ensure_loaded"},
            {"op": "load_complete", "result": AFD},
            {"op": "ensure_loaded"},
            {"op": "explain"},
            {"op": "explain"},
            {"op": "explain_status", "message": "Trying openrouter/free..."},
            {"op": "explain_status", "message": ""},
            {
                "op": "explain_complete",
                "explain_had_focus": True,
                "summary": summary(
                    "Warm and dry.",
                    estimated_cost=0.000123456789,
                    cached=True,
                    model_selection_reason="free tier",
                    requested_model="openrouter/auto",
                    model_attempts=["a/model", "openrouter/free"],
                ),
            },
            {"op": "regenerate"},
            {"op": "explain_error", "message": "Rate limited (429)."},
            {"op": "regenerate"},
            {
                "op": "explain_complete",
                "explain_had_focus": False,
                "summary": summary("Again.", model_used="", estimated_cost=None),
            },
        ],
    ),
    (
        "afd_without_key",
        "AFD",
        "RAH",
        False,
        [
            {"op": "ensure_loaded"},
            {"op": "load_complete", "result": AFD},
            {"op": "set_key", "has_key": True},
            {"op": "trigger_load"},
            {"op": "load_complete", "result": [AFD]},
        ],
    ),
    (
        "afd_empty_text",
        "AFD",
        "RAH",
        True,
        [
            {"op": "ensure_loaded"},
            {"op": "load_complete", "result": product("AFD", "afd-2", "")},
            {"op": "explain"},
        ],
    ),
    (
        "hwo_empty",
        "HWO",
        "RAH",
        True,
        [{"op": "ensure_loaded"}, {"op": "load_complete", "result": None}],
    ),
    (
        "sps_multiple",
        "SPS",
        "RAH",
        True,
        [
            {"op": "ensure_loaded"},
            {"op": "load_complete", "result": SPS},
            {"op": "sps_choice", "index": 2},
            {"op": "explain"},
            {"op": "sps_choice", "index": 1},
            {"op": "explain_complete", "explain_had_focus": False, "summary": summary("Old SPS.")},
            {"op": "sps_choice", "index": 0},
        ],
    ),
    (
        "sps_single_then_error_and_retry",
        "SPS",
        "RAH",
        True,
        [
            {"op": "ensure_loaded"},
            {"op": "load_complete", "result": SPS[:2]},
            {"op": "load_error"},
            {"op": "trigger_load"},
            {"op": "load_complete", "result": SPS[2:]},
        ],
    ),
    (
        "sps_empty_list",
        "SPS",
        "RAH",
        True,
        [{"op": "ensure_loaded"}, {"op": "load_complete", "result": []}],
    ),
    (
        "afd_error_then_retry",
        "AFD",
        "RAH",
        True,
        [
            {"op": "ensure_loaded"},
            {"op": "load_complete", "result": AFD},
            {"op": "explain"},
            {"op": "explain_complete", "explain_had_focus": True, "summary": summary("Sum.")},
            {"op": "load_error"},
            {"op": "trigger_load"},
            {"op": "load_complete", "result": AFD},
        ],
    ),
    ("afd_without_office", "AFD", None, True, [{"op": "ensure_loaded"}, {"op": "trigger_load"}]),
    (
        "surf_without_office",
        "SURF",
        None,
        True,
        [
            {"op": "ensure_loaded"},
            {
                "op": "load_complete",
                "result": product(
                    "SURF_CONDITIONS", "surf-1", "Waves 2 ft.", "2026-05-01T14:00:00Z", office=""
                ),
            },
        ],
    ),
    (
        "surf_official_srf",
        "SURF",
        "mhx",
        True,
        [
            {"op": "ensure_loaded"},
            {
                "op": "load_complete",
                "result": product("SRF", "srf-1", "SURF ZONE FORECAST", office="MHX"),
            },
            {"op": "trigger_load"},
            {
                "op": "load_complete",
                "result": product(
                    "SRF",
                    "srf-2",
                    "Surf Zone Forecast issued by NWS MHX for regional beaches.\n\nBody",
                    office="MHX",
                ),
            },
        ],
    ),
    (
        "surf_empty",
        "SURF",
        "MHX",
        True,
        [{"op": "ensure_loaded"}, {"op": "load_complete", "result": None}],
    ),
    (
        "cli_blank_office",
        "CLI",
        "",
        True,
        [{"op": "ensure_loaded"}, {"op": "load_complete", "result": None}],
    ),
    ("cli_error", "CLI", "RAH", True, [{"op": "ensure_loaded"}, {"op": "load_error"}]),
    (
        "national_empty_and_error",
        "PMDSPD",
        "IEM",
        True,
        [
            {"op": "ensure_loaded"},
            {"op": "load_complete", "result": None},
            {"op": "load_error"},
        ],
    ),
    (
        "spc_outlook_error",
        "SPC_OUTLOOK",
        "IEM",
        True,
        [{"op": "ensure_loaded"}, {"op": "load_error"}],
    ),
    (
        "unknown_type_empty",
        "XYZ",
        "IEM",
        True,
        [{"op": "ensure_loaded"}, {"op": "load_complete", "result": None}],
    ),
]


def run_scenario(name, product_type, cwa, has_key, steps) -> dict:
    p = make_panel(product_type, cwa, has_key)
    initial = view(p)
    results = []
    for step in steps:
        EVENTS.clear()
        focused = p.ai_summary_display.focused
        apply(p, step)
        events = list(EVENTS)
        if p.ai_summary_display.focused > focused:
            # Python focuses the summary before announcing.
            events.insert(
                next((i for i, e in enumerate(events) if e.startswith("announce:")), len(events)),
                "focus:ai_summary",
            )
        results.append({"step": step, "events": events, "view": view(p)})
    return {
        "name": name,
        "product_type": product_type,
        "cwa_office": cwa,
        "has_key": has_key,
        "initial": initial,
        "steps": results,
    }


# ---------------------------------------------------------------------------
# format_issuance and model information
# ---------------------------------------------------------------------------


class FixedLocal(datetime):
    """A datetime whose ``astimezone()`` uses a chosen zone instead of the OS one."""

    zone: timezone = UTC

    def astimezone(self, tz=None):
        return datetime.astimezone(self, tz or FixedLocal.zone)


def issuance_cases() -> list[dict]:
    cases = []
    for issued, minutes, name in [
        ("2026-05-01T15:00:00+00:00", -240, "Eastern Daylight Time"),
        ("2026-01-15T03:30:00+00:00", -300, "Eastern Standard Time"),
        ("2026-05-01T09:05:00-05:00", 120, "W. Europe Daylight Time"),
        ("2026-12-31T23:59:59+00:00", 330, "India Standard Time"),
        ("2026-05-01T15:00:00+00:00", -240, "EDT"),
        ("2026-05-01T15:00:00+00:00", 0, ""),
    ]:
        FixedLocal.zone = timezone(timedelta(minutes=minutes), name)
        text = fmt.format_issuance(FixedLocal.fromisoformat(issued))
        cases.append({"time": issued, "offset_minutes": minutes, "zone_name": name, "text": text})
    cases.append(
        {"time": None, "offset_minutes": 0, "zone_name": "", "text": fmt.format_issuance(None)}
    )
    return cases


def host_issuance() -> dict:
    """format_issuance in this machine's real zone (the Windows full-name quirk)."""
    times = ["2026-07-04T16:00:00+00:00", "2026-01-15T16:00:00+00:00"]
    return {
        "tzname": list(time.tzname),
        "cases": [
            {"time": t, "text": fmt.format_issuance(datetime.fromisoformat(t))} for t in times
        ],
    }


def model_info_cases() -> list[dict]:
    cases = []
    for s in [
        summary("", estimated_cost=None),
        summary("", estimated_cost=0.0),
        summary("", estimated_cost=0.0000005),
        summary("", estimated_cost=1.5, token_count=0),
        summary("", requested_model="openrouter/free"),
        summary("", requested_model="", model_selection_reason=""),
        summary(
            "", requested_model="x/y", model_selection_reason="fallback", model_attempts=["x/y"]
        ),
        summary("", model_attempts=["x/y", "z/w", "openrouter/free"], cached=True),
    ]:
        text = fpp.ForecastProductPanel._build_model_info(
            None,
            s["model_used"],
            s["token_count"],
            s["estimated_cost"],
            s["cached"],
            s["model_selection_reason"],
            s["requested_model"],
            tuple(s["model_attempts"]),
        )
        cases.append({"summary": s, "text": text})
    return cases


# ---------------------------------------------------------------------------
# Dialog widgets
# ---------------------------------------------------------------------------

RALEIGH = Location(
    name="Raleigh, NC", latitude=35.78, longitude=-78.64, country_code="US", cwa_office="RAH"
)


def panel_widgets() -> dict:
    out = {}
    for product_type in (
        [t.product_type for t in fpd.ForecastProductsDialog._TABS]
        + [t.product_id for t in npd.NationalProductsDialog._TABS]
        + ["SRF", "SURF_CONDITIONS", "LSR", "PNS", "XYZ"]
    ):
        out[product_type] = capture(
            lambda pt=product_type: fpw.create_product_panel_widgets(
                SimpleNamespace(product_type=pt, SetSizer=lambda _s: None)
            )
        )
    return out


def notes_dialog_widgets() -> list:
    stub = borrow(
        fpd.ForecastProductsDialog, ["_TABS", "_create_widgets", "_should_autoload_tab"]
    )()
    stub._location = RALEIGH
    stub._add_tab_panel = lambda *_a, **_k: None
    stub.SetSizer = lambda _s: None
    return capture(stub._create_widgets)


def national_dialog_widgets() -> list:
    npd.ForecastProductPanel = lambda **_kwargs: SimpleNamespace()
    stub = borrow(npd.NationalProductsDialog, ["_create_widgets", "_make_loader"])()
    stub._TABS = npd.NationalProductsDialog._TABS
    stub._ai_explainer = None
    stub._app = None
    stub._service = None
    stub.panels = []
    stub.SetSizer = lambda _s: None
    return capture(stub._create_widgets)


def advanced_dialog() -> dict:
    stub = borrow(
        atp.AdvancedTextProductDialog,
        [
            "_create_widgets",
            "_preset_labels_for_category",
            "_set_accessibility_metadata",
            "_set_control_accessibility",
            "_focusable_controls",
        ],
    )()
    stub._location = RALEIGH
    stub.SetSizer = lambda _s: None
    widgets = capture(lambda: stub._create_widgets("AFD"))
    return {
        "widgets": widgets,
        "accessibility": [[c.name, c.tooltip] for c in stub._focusable_controls()],
    }


def main() -> None:
    cases = {
        "scenarios": [run_scenario(*s) for s in SCENARIOS],
        "issuance": issuance_cases(),
        "host_issuance": host_issuance(),
        "model_info": model_info_cases(),
        "forecaster_tabs": [[t.product_type, t.label] for t in fpd.ForecastProductsDialog._TABS],
        "national_tabs": [[t.product_id, t.label] for t in npd.NationalProductsDialog._TABS],
        "panel_widgets": panel_widgets(),
        "notes_dialog_widgets": notes_dialog_widgets(),
        "national_dialog_widgets": national_dialog_widgets(),
        "advanced_dialog": advanced_dialog(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cases, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
