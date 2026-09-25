"""Golden parity data for the Rust Settings dialog (ui/dialogs/settings_*.py).

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/settings.py

Builds the real SettingsDialogSimple (hidden, never shown) on a stub app,
loads fixed settings into it and records every control and the collected
settings dict, plus the pure helpers behind the dialog (shortcut parsing,
summaries, model browser text, tray format validation, portable copy checks).
Writes rust/testdata/golden/settings/cases.json.
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import wx

import accessiweather.notifications.sound_player as sound_player
from accessiweather.api.openrouter_models import OpenRouterModel
from accessiweather.api.venice_models import VeniceBalance, VeniceModel
from accessiweather.format_string_parser import FormatStringParser
from accessiweather.global_hotkeys import normalize_hotkey
from accessiweather.models import AppSettings
from accessiweather.shortcut_preferences import normalize_shortcut_text
from accessiweather.ui.dialogs import model_browser_dialog as mbd
from accessiweather.ui.dialogs.settings_dialog import SettingsDialogSimple
from accessiweather.ui.dialogs.settings_tabs.audio import AudioTab
from accessiweather.ui.dialogs.settings_tabs.data_sources import DataSourcesTab

OUT = Path(__file__).resolve().parents[2] / "testdata" / "golden" / "settings" / "cases.json"

SOUND_PACKS = {
    "default": {"name": "Default", "specific": True},
    "chimes": {"name": "Soft Chimes", "specific": False},
    "nature": {"name": "Nature Sounds", "specific": False},
}

BOXES: list[dict] = []


def fake_box(message, caption, style=0, parent=None):
    BOXES.append({"message": message, "caption": caption})
    return wx.YES


def install_stubs():
    wx.MessageBox = fake_box
    sound_player.get_available_sound_packs = lambda: {
        pid: {"name": info["name"]} for pid, info in SOUND_PACKS.items()
    }
    sound_player.sound_pack_uses_specific_alert_sounds = lambda pid: SOUND_PACKS.get(pid, {}).get(
        "specific", False
    )


def make_dialog(settings: AppSettings, startup_actual: bool):
    manager = SimpleNamespace(
        get_settings=lambda: settings,
        is_startup_enabled=lambda: startup_actual,
        config_dir=Path("C:/cfg"),
        update_settings=lambda **kw: True,
    )
    app = SimpleNamespace(config_manager=manager, _portable_mode=False, paths=SimpleNamespace())
    return SettingsDialogSimple(None, app)


def control_state(dlg) -> dict:
    out = {}
    for key, ctrl in dlg._controls.items():
        if isinstance(ctrl, wx.Choice):
            out[key] = ctrl.GetSelection()
        elif isinstance(ctrl, (wx.StaticText, wx.Button)) or (
            isinstance(ctrl, wx.TextCtrl) and key == "source_settings_summary"
        ):
            continue
        else:
            out[key] = ctrl.GetValue()
    return out


def snapshot(dlg) -> dict:
    c = dlg._controls
    return {
        "controls": control_state(dlg),
        "enabled": {
            key: c[key].IsEnabled()
            for key in (
                "taskbar_icon_dynamic_enabled",
                "taskbar_icon_text_format_dialog",
                "minimize_on_startup",
                "specific_alert_sounds_for_pack",
            )
        },
        "pw_section_shown": dlg._pw_config_sizer.GetItem(0).IsShown(),
        "venice_panel_shown": dlg._tab_objects_by_key["ai"]._provider_panels["venice"].IsShown(),
        "ai_model_items": c["ai_model"].GetStrings(),
        "sound_pack_items": c["sound_pack"].GetStrings(),
        "event_sounds_summary": c["event_sounds_summary"].GetLabel(),
        "source_settings_summary": c["source_settings_summary"].GetValue(),
        "collect": dlg._collect_tab_values(),
    }


def settings_with(**overrides) -> AppSettings:
    settings = AppSettings()
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


CUSTOM = dict(
    update_interval_minutes=500,
    taskbar_icon_text_enabled=True,
    taskbar_icon_dynamic_enabled=False,
    taskbar_icon_text_format="{location}: {temp}",
    noaa_radio_hotkey="win+ctrl+f9",
    temperature_unit="celsius",
    wind_speed_unit="mps",
    round_values=True,
    location_sort_order="nearest_current",
    forecast_duration_days=16,
    hourly_forecast_hours=400,
    trend_hours=0,
    show_dewpoint=False,
    show_impact_summaries=True,
    forecast_time_reference="user_local",
    time_display_mode="both",
    time_format_12hour=False,
    show_timezone_suffix=True,
    date_format="us_long",
    verbosity_level="detailed",
    severe_weather_override=True,
    alert_display_style="combined",
    location_buttons_on_top=True,
    enable_alerts=False,
    alert_notifications_enabled=False,
    alert_radius_type="zone",
    alert_notify_minor=True,
    alert_notify_extreme=False,
    immediate_alert_details_popups=True,
    auto_tune_weather_radio_alerts=True,
    auto_tune_weather_radio_duration_minutes=90,
    alert_global_cooldown_minutes=75,
    alert_per_alert_cooldown_minutes=30,
    alert_freshness_window_minutes=200,
    alert_max_notifications_per_hour=0,
    notify_daily_climate_report_update=True,
    notify_hwo_update=False,
    minutely_precipitation_fast_polling=True,
    precipitation_sensitivity="heavy",
    notify_precipitation_likelihood=True,
    precipitation_likelihood_threshold=0.7,
    sound_enabled=False,
    sound_pack="chimes",
    muted_sound_events=[" alert ", "tornado_warning", "bogus", "alert", "exit", "watch"],
    specific_alert_sound_packs=["nature", "default"],
    data_source="openmeteo",
    pirate_weather_api_key="pw-secret",
    airnow_api_key="air-secret",
    station_selection_strategy="nearest",
    auto_mode_api_budget="economy",
    auto_sources_us=["pirateweather", "bogus", "nws"],
    auto_sources_international=[],
    ai_provider="venice",
    venice_api_key=" ven-secret ",
    venice_model="",
    openrouter_api_key="or-secret",
    ai_model_preference="anthropic/claude-3.5-sonnet",
    ai_explanation_style="brief",
    custom_system_prompt="Be terse.",
    custom_instructions="",
    auto_update_enabled=False,
    update_channel="dev",
    update_check_interval_hours=0,
    minimize_to_tray=False,
    minimize_on_startup=True,
    shortcut_show_main_window="ctrl+shift+w",
    shortcut_hide_main_window="",
    startup_enabled=True,
    weather_history_enabled=False,
)

EDGE = dict(
    temperature_unit="F",
    wind_speed_unit="kph",
    forecast_duration_days=14,
    precipitation_likelihood_threshold=0.65,
    alert_radius_type="county-wide",
    date_format="nope",
    verbosity_level="",
    location_sort_order="manual",
    sound_pack="missing",
    specific_alert_sound_packs=[],
    muted_sound_events=[],
    data_source="pirateweather",
    station_selection_strategy="unknown",
    auto_mode_api_budget="lavish",
    ai_model_preference="openrouter/auto",
    ai_explanation_style="verbose",
    update_channel="nightly",
    noaa_radio_hotkey="Ctrl+Hyper+Q",
    minimize_to_tray=True,
    minimize_on_startup=True,
    custom_system_prompt=None,
    custom_instructions="Mention pollen.",
)


def case_dialog():
    out = []
    for name, overrides, startup_actual in (
        ("defaults", {}, False),
        ("custom", CUSTOM, False),
        ("edge", EDGE, True),
        ("specific_free_model", dict(ai_model_preference="meta/llama-3:free"), False),
        ("empty_model", dict(ai_model_preference=""), False),
    ):
        settings = settings_with(**overrides)
        BOXES.clear()
        dlg = make_dialog(settings, startup_actual)
        loaded = snapshot(dlg)
        loaded["boxes"] = list(BOXES)
        out.append(
            {
                "name": name,
                "settings": dataclasses.asdict(settings),
                "startup_actual": startup_actual,
                "loaded": loaded,
            }
        )
        dlg.Destroy()
    return out


def case_widgets():
    """Every control on every page, in creation order."""
    dlg = make_dialog(AppSettings(), False)

    def walk(window, out):
        for child in window.GetChildren():
            entry = {
                "class": child.__class__.__name__,
                "label": child.GetLabel(),
                "name": child.GetName(),
            }
            if isinstance(child, wx.Choice):
                entry["choices"] = child.GetStrings()
            tip = child.GetToolTipText()
            if tip:
                entry["tooltip"] = tip
            out.append(entry)
            walk(child, out)
        return out

    pages = [
        {"label": dlg.notebook.GetPageText(i), "widgets": walk(dlg.notebook.GetPage(i), [])}
        for i in range(dlg.notebook.GetPageCount())
    ]
    intro = [c.GetLabel() for c in dlg.GetChildren() if isinstance(c, wx.StaticText)]
    buttons = [c.GetLabel() for c in dlg.GetChildren() if isinstance(c, wx.Button)]
    title, size, min_size = dlg.GetTitle(), list(dlg.GetSize()), list(dlg.GetMinSize())
    dlg.Destroy()
    return {
        "title": title,
        "size": size,
        "min_size": min_size,
        "intro": intro,
        "buttons": buttons,
        "pages": pages,
    }


def case_edits():
    """User edits followed by the handlers Python runs, then collect."""
    settings = settings_with(**CUSTOM)
    dlg = make_dialog(settings, False)
    c = dlg._controls
    steps = []

    def step(label, fn):
        BOXES.clear()
        fn()
        snap = snapshot(dlg)
        snap["boxes"] = list(BOXES)
        steps.append({"step": label, **snap})

    def minimize_on():
        c["minimize_tray"].SetValue(True)
        dlg._update_minimize_on_startup_state(True)
        c["minimize_on_startup"].SetValue(True)

    def minimize_off():
        c["minimize_tray"].SetValue(False)
        dlg._update_minimize_on_startup_state(False)

    def pick_pack(index):
        c["sound_pack"].SetSelection(index)
        dlg._audio_tab._refresh_specific_alert_sounds_control()

    def browse(model_id):
        orig = mbd.show_model_browser_dialog
        import accessiweather.ui.dialogs.model_browser_dialog as module

        module.show_model_browser_dialog = lambda *a, **k: model_id
        try:
            dlg._on_browse_models(None)
        finally:
            module.show_model_browser_dialog = orig

    def source_modal():
        dlg._source_settings_states = {
            "auto_mode_api_budget": 1,
            "auto_sources_us": ["openmeteo"],
            "auto_sources_international": ["pirateweather", "openmeteo"],
            "station_selection_strategy": 3,
        }
        dlg._refresh_source_settings_summary()

    def event_sounds():
        states = dict(dlg._event_sound_states)
        states["startup"] = False
        states["alert"] = True
        dlg._event_sound_states = states
        dlg._audio_tab._refresh_event_sound_summary()

    def all_sounds_off():
        dlg._event_sound_states = dict.fromkeys(dlg._event_sound_states, False)
        dlg._audio_tab._refresh_event_sound_summary()

    step("minimize_on", minimize_on)
    step("minimize_off", minimize_off)
    step("pick_default_pack", lambda: pick_pack(0))
    step("pick_nature_pack", lambda: pick_pack(2))
    step("untick_specific", lambda: c["specific_alert_sounds_for_pack"].SetValue(False))
    step("browse_specific", lambda: browse("openai/gpt-4o-mini"))
    step("browse_again", lambda: browse("google/gemini-2.0"))
    step("browse_auto", lambda: browse("openrouter/auto"))
    step("browse_free", lambda: browse("openrouter/free"))
    step("source_modal", source_modal)
    step("event_sounds", event_sounds)
    step("all_sounds_off", all_sounds_off)
    step("valid_hotkey", lambda: c["noaa_radio_hotkey"].SetValue("  alt + shift + f12 "))
    step("invalid_hotkey", lambda: c["noaa_radio_hotkey"].SetValue("Shift"))
    step("blank_hotkey", lambda: c["noaa_radio_hotkey"].SetValue("   "))
    step("blank_venice_model", lambda: c["venice_model"].SetValue("  "))
    step(
        "data_source_nws",
        lambda: (c["data_source"].SetSelection(1), dlg._update_api_key_visibility()),
    )
    step("reset_prompt", lambda: dlg._on_reset_prompt(None))
    dlg.Destroy()
    return {"settings": dataclasses.asdict(settings), "steps": steps}


def case_save_guard():
    """`_save_settings` drops a blanked key unless the user edited the field."""
    out = []
    for edits in (
        {"pw_key": ("change", ""), "airnow_key": ("set", "")},
        {"openrouter_key": ("change", ""), "venice_key": ("set", "   ")},
        {"pw_key": ("set", "new-pw"), "venice_key": ("change", "")},
    ):
        settings = settings_with(**CUSTOM)
        dlg = make_dialog(settings, False)
        captured = {}
        dlg.config_manager.update_settings = lambda **kw: captured.update(kw) or True
        cleared = {}
        for key, (how, value) in edits.items():
            ctrl = dlg._controls[key]
            if how == "set":
                ctrl.SetValue(value)
            else:
                ctrl.ChangeValue(value)
        for key, attr in (
            ("pw_key", "_pw_key_cleared"),
            ("airnow_key", "_airnow_key_cleared"),
            ("openrouter_key", "_openrouter_key_cleared"),
            ("venice_key", "_venice_key_cleared"),
        ):
            cleared[key] = bool(getattr(dlg, attr, False))
        dlg._save_settings()
        out.append(
            {
                "settings": dataclasses.asdict(settings),
                "edits": {k: v[1] for k, v in edits.items()},
                "cleared": cleared,
                "saved_keys": {
                    k: captured.get(k)
                    for k in (
                        "pirate_weather_api_key",
                        "airnow_api_key",
                        "openrouter_api_key",
                        "venice_api_key",
                    )
                    if k in captured
                },
            }
        )
        dlg.Destroy()
    return out


def case_shortcuts():
    out = []
    for show, hide, tray, radio in (
        ("Ctrl+Alt+Shift+W", "Ctrl+Alt+Shift+M", "Ctrl+Alt+Shift+I", "Ctrl+Alt+Shift+R"),
        ("ctrl + shift + w", "alt+m", " ", ""),
        ("Shift+W", "", "", ""),
        ("Ctrl+S", "", "", ""),
        ("alt+f4", "", "", ""),
        ("Ctrl+Alt+R", "", "", "control+alt+r"),
        ("Ctrl+Alt+Q", "alt+ctrl+q", "", ""),
        ("Ctrl+Hyper+Q", "", "", ""),
        ("Ctrl++Q", "", "", ""),
        ("Ctrl+Ctrl+Q", "", "", ""),
        ("Ctrl+F25", "", "", ""),
        ("Ctrl+PageUp", "", "", ""),
        ("Ctrl+Alt+esc", "ctrl+alt+space", "Command+Option+Tab", ""),
        ("Ctrl+Alt+W", "Ctrl+Alt+F05", "Ctrl+Alt+Shift+I", "Win+Ctrl+Alt+Shift+I"),
        ("", "Ctrl+Alt+M", "ctrl+it's", ""),
    ):
        settings = settings_with(
            shortcut_show_main_window=show,
            shortcut_hide_main_window=hide,
            shortcut_read_tray_info=tray,
            noaa_radio_hotkey=radio,
        )
        dlg = make_dialog(settings, False)
        result = dlg._validate_window_tray_shortcuts()
        c = dlg._controls
        out.append(
            {
                "input": [show, hide, tray, radio],
                "result": list(result) if result else None,
                "fields": [
                    c["shortcut_show_main_window"].GetValue(),
                    c["shortcut_hide_main_window"].GetValue(),
                    c["shortcut_read_tray_info"].GetValue(),
                ],
            }
        )
        dlg.Destroy()
    return out


def attempt(fn, value):
    try:
        return {"ok": fn(value)}
    except ValueError as exc:
        return {"err": str(exc)}


def case_normalize():
    shortcut_inputs = [
        "",
        "  ",
        "ctrl+alt+shift+w",
        "Shift+Alt+Ctrl+x",
        "control+option+esc",
        "cmd+Space",
        "Ctrl+tab",
        "F5",
        "f24",
        "Ctrl+F0",
        "Ctrl+F007",
        "Ctrl+",
        "+Q",
        "Ctrl+Meta+Q",
        "Alt+Option+Q",
        "Ctrl+PgUp",
        "Ctrl+é",
        "Ctrl+Alt+7",
        "Ctrl+it's",
    ]
    hotkey_inputs = [
        "Ctrl+Alt+Shift+R",
        "shift+ctrl+r",
        "Win+F1",
        "super+alt+f24",
        "cmd+command+x",
        "ctrl+alt+f25",
        "R",
        "",
        "Ctrl+",
        "Ctrl+Hyper+R",
        "Ctrl+Space",
        "Ctrl+é",
        "control + alt + 9",
        "Ctrl+it's",
    ]
    return {
        "shortcuts": [
            {"input": v, **attempt(lambda x: normalize_shortcut_text(x, allow_empty=True), v)}
            for v in shortcut_inputs
        ],
        "hotkeys": [{"input": v, **attempt(normalize_hotkey, v)} for v in hotkey_inputs],
    }


def case_summaries():
    sources = []
    for state in (
        DataSourcesTab._build_default_source_settings_states(),
        {
            "auto_mode_api_budget": 0,
            "auto_sources_us": ["openmeteo", "nws"],
            "auto_sources_international": ["bogus"],
            "station_selection_strategy": 2,
        },
        {
            "auto_mode_api_budget": 7,
            "auto_sources_us": [],
            "auto_sources_international": ["pirateweather", "nws"],
            "station_selection_strategy": -1,
        },
    ):
        sources.append(
            {"state": state, "text": DataSourcesTab.build_source_settings_summary_text(state)}
        )
    keys = [k for k, _label in AudioTab._get_mutable_sound_events()]
    events = []
    for muted in ([], keys[:1], keys[:5], keys):
        states = {k: k not in muted for k in keys}
        events.append({"muted": muted, "text": AudioTab.build_event_sound_summary_text(states)})
    sections = [
        {"title": t, "description": d, "events": list(e)}
        for t, d, e in AudioTab._get_event_sound_sections()
    ]
    return {
        "sources": sources,
        "events": events,
        "sections": sections,
        "mutable": [list(p) for p in AudioTab._get_mutable_sound_events()],
    }


def openrouter(id, name, desc, ctx, prompt, completion):
    free = id.endswith(":free") or (prompt == 0 and completion == 0)
    return OpenRouterModel(
        id=id,
        name=name,
        description=desc,
        context_length=ctx,
        pricing_prompt=prompt,
        pricing_completion=completion,
        is_free=free,
        is_moderated=True,
        input_modalities=["text"],
        output_modalities=["text"],
    )


def model_json(m, provider_kind):
    return {
        "id": m.id,
        "name": m.name,
        "description": m.description,
        "context_length": m.context_length,
        "pricing_prompt": m.pricing_prompt,
        "pricing_completion": m.pricing_completion,
        "is_free": m.is_free,
        "supports_function_calling": getattr(m, "supports_function_calling", False),
        "offline": getattr(m, "offline", False),
        "provider": m.provider,
        "display_name": m.display_name,
        "context_display": m.context_display,
    }


class Widget:
    def __init__(self, value=None):
        self.value = value
        self.items = []
        self.enabled = None

    def GetValue(self):
        return self.value

    def SetValue(self, v):
        self.value = v

    def SetLabel(self, v):
        self.value = v

    def GetLabel(self):
        return self.value

    def Enable(self, on=True):
        self.enabled = on

    def Clear(self):
        self.items = []

    def Append(self, item):
        self.items.append(item)

    def GetSelection(self):
        return self.value


def browser_stub(
    provider,
    models,
    search="",
    free_only=False,
    price=0,
    function_only=False,
    provider_index=0,
    providers=None,
):
    stub = SimpleNamespace(
        provider=provider,
        _all_models=models,
        _filtered_models=[],
        _providers=providers or [],
        _selected_model_id=None,
        search_box=Widget(search),
        free_only_checkbox=Widget(free_only),
        price_choice=Widget(price),
        function_checkbox=Widget(function_only),
        provider_choice=Widget(provider_index),
        model_list=Widget(),
        status_label=Widget(),
        select_btn=Widget(),
        description_text=Widget(),
    )
    cls = mbd.ModelBrowserDialog
    for name in (
        "_matches_price_and_capability",
        "_get_selected_provider",
        "_apply_filters",
        "_populate_list",
    ):
        setattr(stub, name, getattr(cls, name).__get__(stub))
    stub._model_pricing = cls._model_pricing
    return stub


def case_model_browser():
    or_models = [
        openrouter("openai/gpt-4o-mini", "GPT-4o mini", "Small and fast.", 128000, 0.15, 0.6),
        openrouter("meta-llama/llama-3.1-8b:free", "Llama 3.1 8B", "", 131072, 0, 0),
        openrouter("anthropic/claude-3.5", "Claude 3.5", "Careful writer.", 2000000, 3, 15),
        openrouter("tiny/model", "Tiny", "Edge case", 512, 0.0000015, 0.1),
        openrouter("noslash", "No Slash", "unknown provider", None, 0, 0.2),
    ]
    ven_models = [
        VeniceModel(
            "venice-uncensored-1-2",
            "Venice Uncensored",
            "House model.",
            32768,
            0.5,
            2,
            False,
            True,
            False,
        ),
        VeniceModel("llama-3.3-70b", "Llama 3.3 70B", "", 65536, None, 2.8, False, True, False),
        VeniceModel("qwen3-4b", "Qwen 3 4B", "Tiny", 32000, 0, 0, True, False, False),
        VeniceModel("e2ee-grok-4", "Grok 4", "Private.", 1500000, 1.25, None, False, False, True),
    ]
    out = {"openrouter": {}, "venice": {}}
    out["openrouter"]["models"] = [model_json(m, "openrouter") for m in or_models]
    out["venice"]["models"] = [model_json(m, "venice") for m in ven_models]
    or_providers = sorted({m.provider for m in or_models})
    ven_providers = sorted({m.provider for m in ven_models})

    lists = []
    for kind, models, providers, filters in (
        ("openrouter", or_models, or_providers, {}),
        ("openrouter", or_models, or_providers, {"free_only": True}),
        ("openrouter", or_models, or_providers, {"search": "  FAST "}),
        ("openrouter", or_models, or_providers, {"search": "claude"}),
        ("openrouter", or_models, or_providers, {"provider_index": 2}),
        ("venice", ven_models, ven_providers, {}),
        ("venice", ven_models, ven_providers, {"price": 1}),
        ("venice", ven_models, ven_providers, {"price": 2}),
        ("venice", ven_models, ven_providers, {"function_only": True}),
        ("venice", ven_models, ven_providers, {"provider_index": 1}),
    ):
        stub = browser_stub(kind, models, providers=providers, **filters)
        stub._apply_filters()
        lists.append(
            {
                "provider": kind,
                "filters": filters,
                "providers": providers,
                "items": stub.model_list.items,
                "status": stub.status_label.value,
                "filtered": [m.id for m in stub._filtered_models],
            }
        )
    out["lists"] = lists

    descriptions = []
    for kind, models in (("openrouter", or_models), ("venice", ven_models)):
        for i in range(len(models)):
            stub = browser_stub(kind, models)
            stub._filtered_models = models
            stub.model_list = SimpleNamespace(GetSelection=lambda i=i: i)
            mbd.ModelBrowserDialog._on_model_selected(stub, None)
            descriptions.append(
                {
                    "provider": kind,
                    "index": i,
                    "text": stub.description_text.value,
                    "select_enabled": stub.select_btn.enabled,
                    "selected": stub._selected_model_id,
                }
            )
    out["descriptions"] = descriptions

    balances = []
    for b in (
        None,
        VeniceBalance(None, None, None, None),
        VeniceBalance(True, "USD", 12.5, None),
        VeniceBalance(False, None, 0.0, 0.0),
        VeniceBalance(False, "DIEM", 0.0, 3.25),
        VeniceBalance(True, None, 1234567.0, 0.00001),
    ):
        balances.append(
            {
                "balance": dataclasses.asdict(b) if b else None,
                "text": mbd.ModelBrowserDialog._balance_status(b),
            }
        )
    out["balances"] = balances
    out["provider_names"] = {
        p: mbd.get_provider_display_name(p)
        for p in ("openai", "meta-llama", "x-ai", "some-new-lab", "tiny", "unknown", "z-ai")
    }
    return out


def case_tray_format():
    parser = FormatStringParser()
    inputs = [
        "",
        "{temp} {condition}",
        "{temp",
        "{temp}}",
        "{bogus} and {temp} and {nope}",
        "{Temp}",
        "{temp_2}",
        "}{",
    ]
    return {
        "help": parser.get_supported_placeholders_help(),
        "validate": [
            {"input": v, "result": list(parser.validate_format_string(v))} for v in inputs
        ],
    }


def case_portable():
    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        def write(name, data):
            d = root / name
            d.mkdir(parents=True, exist_ok=True)
            if data is not None:
                (d / "accessiweather.json").write_text(
                    data if isinstance(data, str) else json.dumps(data), encoding="utf-8"
                )
            return d

        empty = root / "empty"
        empty.mkdir()
        other_file = write("other", None)
        (other_file / "notes.txt").write_text("x")
        cases = {
            "missing": (root / "nope", None),
            "empty": (empty, None),
            "no_config": (other_file, None),
            "zero_size": (write("zero", ""), None),
            "invalid": (write("invalid", "{not json"), None),
            "array": (write("array", "[1]"), None),
            "no_locations": (write("nolocs", {"settings": {}, "locations": []}), None),
            "good": (
                write(
                    "good",
                    {
                        "settings": {
                            "data_source": "nws",
                            "ai_model_preference": "openrouter/free",
                            "temperature_unit": "f",
                            "custom_instructions": "  ",
                        },
                        "locations": [{"name": "A"}, {"name": "B"}],
                    },
                ),
                write(
                    "good_copy",
                    {
                        "settings": {"data_source": "auto", "temperature_unit": "f"},
                        "locations": [{"name": "A"}],
                    },
                ),
            ),
            "prompt": (
                write(
                    "prompt",
                    {
                        "settings": {"prompt": "hi", "data_source": "auto"},
                        "locations": [{"name": "A"}],
                    },
                ),
                None,
            ),
        }
        for name, (src, dst) in cases.items():
            ok, reason = dialog._has_meaningful_installed_config_data(src)
            entry = {"name": name, "ok": ok, "reason": reason}
            if ok:
                entry["summary"] = dialog._build_portable_copy_summary(src)
                if dst is not None:
                    entry["validation"] = list(dialog._validate_portable_copy(src, dst))
            out.append(entry)
    return out


def main():
    install_stubs()
    app = wx.App(False)
    data = {
        "defaults": dataclasses.asdict(AppSettings()),
        "sound_packs": SOUND_PACKS,
        "widgets": case_widgets(),
        "dialog": case_dialog(),
        "edits": case_edits(),
        "save_guard": case_save_guard(),
        "shortcuts": case_shortcuts(),
        "normalize": case_normalize(),
        "summaries": case_summaries(),
        "model_browser": case_model_browser(),
        "tray_format": case_tray_format(),
        "portable": case_portable(),
    }
    del app
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
