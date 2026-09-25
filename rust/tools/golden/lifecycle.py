"""
Golden parity data for hotkey and shortcut handling (global_hotkeys.py,
shortcut_preferences.py, the settings dialog's shortcut validation and the
load-time clean-up in AppSettings.from_dict).

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/lifecycle.py
Writes rust/testdata/golden/lifecycle/*.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import wx

from accessiweather.global_hotkeys import HotkeyParseError, normalize_hotkey, parse_hotkey
from accessiweather.models import AppSettings
from accessiweather.shortcut_preferences import (
    DEFAULT_SHOW_MAIN_WINDOW_SHORTCUT,
    normalize_shortcut_text,
    resolve_shortcut_binding,
)
from accessiweather.ui.dialogs.settings_dialog_handlers import SettingsDialogHandlersMixin

RUST = Path(__file__).resolve().parents[2]
OUT = RUST / "testdata" / "golden" / "lifecycle"


def write(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    (OUT / name).write_text(text, encoding="utf-8", newline="\n")
    print("wrote", OUT / name)


def result(fn, *args):
    try:
        return {"ok": fn(*args)}
    except ValueError as exc:
        return {"error": str(exc)}


COMBOS = [
    "Ctrl+Alt+Shift+R", "ctrl+alt+shift+r", " Control + Alt + R ", "shift+ctrl+w",
    "Win+Alt+R", "super+F5", "cmd+command+x", "Ctrl+Ctrl+R", "Ctrl+F1", "Ctrl+F24",
    "Ctrl+F25", "Ctrl+F0", "Ctrl+F01", "Ctrl+f12", "Alt+F", "Alt+Fx", "Ctrl+1", "Ctrl+é",
    "Ctrl+Space", "Ctrl+Escape", "Ctrl+Tab", "R", "", "   ", "+", "Ctrl+", "+R", "Ctrl++",
    "Meta+R", "Option+R", "Ctrl+Alt+Shift+W", "Ctrl + Shift + I", "Ctrl+RR", "Ctrl+?",
    "Alt+F4", "Ctrl+ß", "Shift+F99999999999",
]

SHORTCUTS = [
    *COMBOS, "Esc", "ctrl+esc", "Alt+space", "ctrl+TAB", "Option+Cmd+W", "Alt+Alt+W",
    "Ctrl+Alt+Shift+Shift+W", "F2", "F5", "Escape", "Shift+F3", "ctrl+r", "Control+5",
    "Ctrl+Alt+F24", "Ctrl+Alt+F25", "Ctrl+Alt+F", "Ctrl+Alt+Win+W", "Ctrl+Alt+1",
]


def hotkeys() -> None:
    cases = []
    for combo in COMBOS:
        try:
            parsed = {"ok": list(parse_hotkey(combo))}
        except HotkeyParseError as exc:
            parsed = {"error": str(exc)}
        cases.append(
            {
                "combo": combo,
                "parse": parsed,
                "normalize": result(normalize_hotkey, combo),
                "setting": AppSettings._normalized_hotkey(combo),
            }
        )
    write("hotkeys.json", cases)


def key_code(binding):
    try:
        return binding.key_code(wx)
    except ValueError:
        return None


def shortcuts() -> None:
    cases = []
    for text in SHORTCUTS:
        binding = resolve_shortcut_binding(text, default=DEFAULT_SHOW_MAIN_WINDOW_SHORTCUT)
        cases.append(
            {
                "text": text,
                "normalize": result(lambda t: normalize_shortcut_text(t, allow_empty=True), text),
                "normalize_strict": result(
                    lambda t: normalize_shortcut_text(t, allow_empty=False), text
                ),
                "resolved": None
                if binding is None
                else {
                    "normalized": binding.normalized,
                    "modifiers": binding.hotkey_modifiers(wx),
                    "key_code": key_code(binding),
                },
            }
        )
    write("shortcuts.json", cases)


class _Field:
    def __init__(self, value: str) -> None:
        self.value = value
        self.written = None

    def GetValue(self) -> str:  # noqa: N802 - wx API
        return self.value

    def SetValue(self, value: str) -> None:  # noqa: N802 - wx API
        self.written = value
        self.value = value


VALIDATION = [
    ("Ctrl+Alt+Shift+R", ["Ctrl+Alt+Shift+W", "Ctrl+Alt+Shift+M", "Ctrl+Alt+Shift+I"]),
    ("Ctrl+Alt+Shift+R", ["ctrl+alt+shift+w", "", " alt+shift+m "]),
    ("Ctrl+Alt+Shift+R", ["Ctrl+Alt+Shift+R", "", ""]),
    ("Win+Alt+R", ["Alt+R", "", ""]),
    ("", ["Shift+W", "", ""]),
    ("", ["F5", "", ""]),
    ("", ["Ctrl+R", "", ""]),
    ("", ["Ctrl+Alt+W", "Ctrl+Alt+W", ""]),
    ("", ["Ctrl+Alt+W", "Ctrl+Bogus+W", ""]),
    ("", ["Ctrl+Alt+W", "Ctrl+Alt+M", "Ctrl++"]),
    ("", ["Ctrl+Alt+W", "Ctrl+Alt+M", "Ctrl+Alt+F30"]),
    ("", ["Ctrl+Shift+Shift+W", "", ""]),
    ("", ["Ctrl+Q", "", ""]),
    ("", ["Alt+F4", "", ""]),
    ("", ["Ctrl+Escape", "Ctrl+Alt+Space", "Alt+Tab"]),
    ("not a combo", ["Ctrl+Alt+Shift+R", "", ""]),
    ("ctrl+alt+shift+r", ["Ctrl+Alt+Shift+R", "", ""]),
]


def validation() -> None:
    from accessiweather.shortcut_preferences import WINDOW_TRAY_SHORTCUTS

    cases = []
    for radio, values in VALIDATION:
        fields = {p.setting_name: _Field(v) for p, v in zip(WINDOW_TRAY_SHORTCUTS, values)}
        fields["noaa_radio_hotkey"] = _Field(radio)
        handler = SimpleNamespace(_controls=fields)
        error = SettingsDialogHandlersMixin._validate_window_tray_shortcuts(handler)
        cases.append(
            {
                "radio": radio,
                "values": values,
                "error": list(error) if error else None,
                "normalized": [fields[p.setting_name].written for p in WINDOW_TRAY_SHORTCUTS],
            }
        )
    write("validation.json", cases)


SETTINGS = [
    ("Ctrl+Alt+Shift+R", "Ctrl+Shift+W", "Ctrl+Shift+M", "Ctrl+Shift+I"),
    ("Ctrl+Alt+Shift+W", "Ctrl+Shift+W", "Ctrl+Shift+M", "Ctrl+Shift+I"),
    ("", "Ctrl+Shift+W", "Ctrl+Alt+Shift+M", "ctrl+shift+i"),
    ("win+alt+r", "ctrl+alt+shift+w", "bogus", ""),
    ("junk", "Ctrl+Alt+W", "Ctrl+Shift+M", "Ctrl+Alt+Shift+M"),
    ("   ", "", "", ""),
    ("Ctrl+Alt+Shift+R", "Alt+F2", "Ctrl+Shift+W", "Ctrl+Shift+W"),
]


def settings_load() -> None:
    keys = (
        "noaa_radio_hotkey",
        "shortcut_show_main_window",
        "shortcut_hide_main_window",
        "shortcut_read_tray_info",
    )
    cases = []
    for values in SETTINGS:
        data = dict(zip(keys, values))
        settings = AppSettings.from_dict(data)
        cases.append({"input": data, "output": {k: getattr(settings, k) for k in keys}})
    write("settings_load.json", cases)


if __name__ == "__main__":
    hotkeys()
    shortcuts()
    validation()
    settings_load()
