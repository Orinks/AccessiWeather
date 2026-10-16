"""Golden parity data for the Rust AI dialogs.

Covers ui/dialogs/explanation_dialog.py (loading and explanation dialogs),
ui/dialogs/weather_assistant_dialog.py + weather_assistant_widgets.py and
the startup "AI Model Not Found" question in app_initialization.py.

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/aiui.py

Builds the real dialogs under a hidden frame (never shown, no main loop),
records their controls in creation (tab) order, the focused control, and
the text, status and screen reader announcements after each step of the
explanation and assistant flows. Network work is stubbed out; the clock is
frozen. Writes rust/testdata/golden/aiui/cases.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import wx

from accessiweather import app_initialization
from accessiweather.ai_explainer import DEFAULT_FREE_MODEL, ExplanationResult
from accessiweather.ui.dialogs import (
    explanation_dialog as expl,
    weather_assistant_dialog as wad,
)

OUT = Path(__file__).resolve().parents[2] / "testdata" / "golden" / "aiui" / "cases.json"

EDT = timezone(timedelta(hours=-4))
NOW = datetime(2026, 9, 25, 14, 3, 5)  # naive local, as datetime.now() returns


class Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


RESULTS = [
    # Free model, not cached.
    ExplanationResult(
        text="Mild and dry this afternoon.",
        model_used="vendor/model:free",
        token_count=412,
        estimated_cost=0.0,
        cached=False,
        timestamp=datetime(2026, 9, 25, 14, 3, 5, tzinfo=EDT),
    ),
    # Paid model, cached, morning timestamp with leading zeros.
    ExplanationResult(
        text="Rain arrives tonight.\n\nCarry an umbrella tomorrow.",
        model_used="openai/gpt-4o",
        token_count=1234,
        estimated_cost=0.000617,
        cached=True,
        timestamp=datetime(2026, 1, 5, 9, 7, tzinfo=EDT),
    ),
    # Venice (unknown cost), empty text.
    ExplanationResult(
        text="",
        model_used="venice-uncensored-1-2",
        token_count=0,
        estimated_cost=None,
        cached=False,
        timestamp=datetime(2026, 12, 31, 0, 0, tzinfo=EDT),
    ),
]


def control(child) -> dict:
    if isinstance(child, wx.Button):
        return {
            "kind": "button",
            # Auto-assigned (negative) ids differ per run.
            "id": child.GetId() if child.GetId() >= 0 else "auto",
            "label": child.GetLabel(),
            "name": child.GetName(),
            "enabled": child.IsEnabled(),
        }
    if isinstance(child, wx.TextCtrl):
        return {"kind": "text", "name": child.GetName(), "value": child.GetValue()}
    if isinstance(child, wx.StaticText):
        font = child.GetFont()
        return {
            "kind": "label",
            "label": child.GetLabel(),
            "bold": font.GetWeight() == wx.FONTWEIGHT_BOLD,
            "italic": font.GetStyle() == wx.FONTSTYLE_ITALIC,
        }
    if isinstance(child, wx.Gauge):
        return {"kind": "gauge", "range": child.GetRange()}
    raise TypeError(type(child))


def controls(parent) -> list[dict]:
    return [control(c) for c in parent.GetChildren()]


def focus_name() -> str | None:
    focused = wx.Window.FindFocus()
    return focused.GetName() if focused else None


class Announcer:
    spoken: list[str] = []

    def announce(self, text):
        Announcer.spoken.append(text)

    def shutdown(self):
        pass


def take_spoken() -> list[str]:
    spoken, Announcer.spoken = Announcer.spoken, []
    return spoken


def explanation_cases(parent) -> list[dict]:
    cases = []
    app = SimpleNamespace(ai_explanation_cache=MagicMock())
    for i, result in enumerate(RESULTS):
        location = "Philadelphia, Pennsylvania"
        dlg = expl.ExplanationDialog(parent, result, location, app=app)
        try:
            case = {
                "result": {
                    "text": result.text,
                    "model_used": result.model_used,
                    "token_count": result.token_count,
                    "estimated_cost": result.estimated_cost,
                    "cached": result.cached,
                    "timestamp": result.timestamp.isoformat(),
                },
                "location": location,
                "title": dlg.GetTitle(),
                "controls": controls(dlg),
                "focus": focus_name(),
            }
            # Regenerate: the "generating" state before the worker answers.
            with patch.object(expl.threading, "Thread"):
                dlg._on_regenerate(None)
            case["regenerating"] = controls(dlg)
            # A new result arrives.
            dlg._on_regenerate_complete(RESULTS[(i + 1) % len(RESULTS)])
            case["regenerated"] = controls(dlg)
            case["regenerated_focus"] = focus_name()
            # A failure arrives.
            with patch.object(expl, "ScreenReaderAnnouncer", Announcer):
                dlg._on_regenerate_error("No weather data available.")
            case["failed"] = controls(dlg)
            case["failed_spoken"] = take_spoken()
        finally:
            dlg.Destroy()
        cases.append(case)
    return cases


def loading_case(parent) -> dict:
    dlg = expl.LoadingDialog(parent, "Philadelphia, Pennsylvania")
    try:
        dlg.timer.Stop()
        return {"title": dlg.GetTitle(), "controls": controls(dlg)}
    finally:
        dlg.Destroy()


def explanation_messages() -> list[dict]:
    """The message boxes show_explanation_dialog raises before generating."""
    out = []
    location = SimpleNamespace(name="Home")
    for location_value, weather in [
        (None, None),
        (location, None),
        (location, SimpleNamespace(current=None)),
    ]:
        app = SimpleNamespace(
            config_manager=SimpleNamespace(get_current_location=lambda v=location_value: v),
            current_weather_data=weather,
        )
        with patch.object(expl.wx, "MessageBox") as box:
            expl.show_explanation_dialog(None, app)
        message, caption, style = box.call_args.args
        out.append(
            {
                "has_location": location_value is not None,
                "message": message,
                "caption": caption,
                "icon": "warning" if style & wx.ICON_WARNING else "other",
            }
        )
    return out


def assistant_app(location_name):
    location = SimpleNamespace(name=location_name) if location_name else None
    config_manager = SimpleNamespace(get_current_location=lambda: location)
    return SimpleNamespace(config_manager=config_manager, current_weather_data=None)


def assistant_state(dlg) -> dict:
    (panel,) = dlg.GetChildren()
    return {
        "history": dlg.history_display.GetValue(),
        "status": dlg.status_label.GetLabel(),
        "input": dlg.input_ctrl.GetValue(),
        "send_enabled": dlg.send_button.IsEnabled(),
        "clear_enabled": dlg.clear_button.IsEnabled(),
        "spoken": take_spoken(),
        "controls": controls(panel),
    }


def assistant_case(parent, location_name) -> dict:
    with (
        patch.object(wad, "ScreenReaderAnnouncer", Announcer),
        patch.object(wad, "datetime", Frozen),
        patch.object(wad.WeatherAssistantDialog, "_generate_response", lambda self: None),
    ):
        dlg = wad.WeatherAssistantDialog(parent, assistant_app(location_name))
        try:
            steps = [{"step": "open", "focus": focus_name(), **assistant_state(dlg)}]
            case = {"location": location_name, "title": dlg.GetTitle()}

            def step(name, **extra):
                steps.append({"step": name, **extra, **assistant_state(dlg)})

            dlg.input_ctrl.SetValue("  Will it rain tonight?  ")
            dlg._on_send(None)
            step("send", message="  Will it rain tonight?  ")
            # Sending while a reply is pending is ignored.
            dlg.input_ctrl.SetValue("Another")
            dlg._on_send(None)
            step("send_while_generating", message="Another")
            dlg.input_ctrl.SetValue("")
            conversation = [
                {"role": "user", "content": "Will it rain tonight?"},
                {"role": "assistant", "content": "No rain is expected."},
            ]
            dlg._on_response_received("No rain is expected.", "vendor/model:free", conversation)
            step("reply", text="No rain is expected.", model="vendor/model:free")
            dlg.input_ctrl.SetValue("What about tomorrow?")
            dlg._on_send(None)
            step("send", message="What about tomorrow?")
            dlg._on_response_error("Venice rate limit reached. Wait a moment and try again.")
            step("error", error="Venice rate limit reached. Wait a moment and try again.")
            dlg._on_send(None)
            step("send", message="What about tomorrow?")
            dlg.input_ctrl.SetValue("draft")
            dlg._on_response_error(
                "Received an empty response. Try again or switch models in Settings."
            )
            step(
                "error",
                error="Received an empty response. Try again or switch models in Settings.",
                input_before="draft",
            )
            # Empty input is not sent.
            dlg.input_ctrl.SetValue("   ")
            dlg._on_send(None)
            step("send", message="   ")
            dlg._on_copy(None)
            step("copy")
            dlg._on_clear(None)
            step("clear")
            case["steps"] = steps
            case["conversation_after_clear"] = dlg._conversation
            return case
        finally:
            dlg.Destroy()


def invalid_model_cases() -> list[dict]:
    out = []
    for answer in (wx.ID_YES, wx.ID_NO):
        dialog = MagicMock()
        dialog.ShowModal.return_value = answer
        settings = SimpleNamespace(ai_model_preference="removed/model")
        app = SimpleNamespace(config_manager=MagicMock(), main_window=MagicMock())
        app.config_manager.get_settings.return_value = settings
        with (
            patch.object(app_initialization.wx, "MessageDialog", return_value=dialog) as ctor,
            patch.object(app_initialization.wx, "MessageBox") as box,
            patch("dataclasses.replace", lambda s, **kw: SimpleNamespace(**{**vars(s), **kw})),
        ):
            app_initialization._show_invalid_model_warning(app, "removed/model", DEFAULT_FREE_MODEL)
        _, message, caption, style = ctor.call_args.args
        case = {
            "answer": "yes" if answer == wx.ID_YES else "no",
            "message": message,
            "caption": caption,
            "yes_no": bool(style & wx.YES_NO),
            "icon_warning": bool(style & wx.ICON_WARNING),
            "labels": list(dialog.SetYesNoLabels.call_args.args),
            "opened_settings": app.main_window.on_settings.called,
        }
        if box.called:
            case["confirmation"] = list(box.call_args.args[:2])
            saved = app.config_manager.save_settings.call_args.args[0]
            case["saved_model"] = saved.ai_model_preference
        out.append(case)
    return out


def main() -> None:
    app = wx.App()
    parent = wx.Frame(None)
    parent.Hide()
    try:
        data = {
            "explanations": explanation_cases(parent),
            "loading": loading_case(parent),
            "explanation_messages": explanation_messages(),
            "assistant": [assistant_case(parent, n) for n in ("Lumberton, NJ", None)],
            "invalid_model": invalid_model_cases(),
            "ids": {"close": wx.ID_CLOSE, "cancel": wx.ID_CANCEL},
        }
    finally:
        parent.Destroy()
        del app
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
